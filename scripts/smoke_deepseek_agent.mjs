import { spawn } from "node:child_process";

const API_BASE_URL = process.env.API_BASE_URL ?? "http://127.0.0.1:8000";
const FRONTEND_URL = process.env.FRONTEND_URL ?? "http://127.0.0.1:5173";
const USER_ID = process.env.SMOKE_USER_ID ?? "local-user";
const DEEPSEEK_API_KEY = process.env.DEEPSEEK_API_KEY;
const DEEPSEEK_BASE_URL =
  process.env.DEEPSEEK_BASE_URL ?? "https://api.deepseek.com";
const DEEPSEEK_MODEL = process.env.DEEPSEEK_MODEL ?? "deepseek-chat";
const RUN_TIMEOUT_MS = Number(process.env.SMOKE_RUN_TIMEOUT_MS ?? 120000);
const READY_TIMEOUT_MS = Number(process.env.SMOKE_READY_TIMEOUT_MS ?? 60000);

const terminalStatuses = new Set(["success", "error", "timeout", "interrupted"]);

if (!DEEPSEEK_API_KEY) {
  console.error("Missing DEEPSEEK_API_KEY.");
  console.error("Run: export DEEPSEEK_API_KEY=<your DeepSeek API key>");
  process.exit(1);
}

let devProcess;
let shuttingDown = false;

function logStep(message) {
  console.log(`\n==> ${message}`);
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function main() {
  logStep("Starting local backend and frontend with make dev");
  devProcess = spawn("make", ["dev"], {
    cwd: process.cwd(),
    env: process.env,
    stdio: ["ignore", "pipe", "pipe"],
    detached: true,
  });
  devProcess.stdout.on("data", pipeDevOutput);
  devProcess.stderr.on("data", pipeDevOutput);
  devProcess.on("exit", (code, signal) => {
    if (!shuttingDown && code !== 0) {
      console.error(`make dev exited early: code=${code} signal=${signal}`);
    }
  });

  await waitForJson(`${API_BASE_URL}/health`, "backend health");
  await waitForHttp(FRONTEND_URL, "frontend");

  const stamp = new Date().toISOString().replace(/[-:.TZ]/g, "").slice(0, 14);
  const agentKey = `deepseek-smoke-${stamp}`;

  logStep("Creating DeepSeek provider");
  const provider = await requestJson(`${API_BASE_URL}/api/llm-providers`, {
    method: "POST",
    headers: authHeaders(),
    body: {
      name: `DeepSeek Local ${stamp}`,
      provider: "openai",
      base_url: DEEPSEEK_BASE_URL,
      api_key: DEEPSEEK_API_KEY,
      model: DEEPSEEK_MODEL,
      metadata: { smoke: "deepseek-agent", created_by_script: true },
    },
    stage: "provider create",
    expectedStatus: 201,
  });
  assertSecretHidden(provider);
  console.log(`provider_id=${provider.id}`);
  console.log(`api_key_hint=${provider.api_key_hint}`);

  logStep("Creating temporary agent");
  const agent = await requestJson(`${API_BASE_URL}/api/agents`, {
    method: "POST",
    headers: jsonHeaders(),
    body: {
      key: agentKey,
      display_name: `DeepSeek Smoke ${stamp}`,
      description: "Temporary DeepSeek provider smoke-test agent.",
      draft: {
        system_prompt:
          "You are a smoke-test assistant. Reply concisely and do not call tools.",
        provider_id: provider.id,
        model_config: { temperature: 0 },
        tool_allowlist: [],
        mcp_server_ids: [],
      },
    },
    stage: "agent create",
    expectedStatus: 201,
  });
  console.log(`agent_key=${agent.key}`);

  logStep("Publishing agent");
  const version = await requestJson(
    `${API_BASE_URL}/api/agents/${encodeURIComponent(agentKey)}/publish`,
    {
      method: "POST",
      headers: jsonHeaders(),
      stage: "agent publish",
      expectedStatus: 201,
    },
  );
  console.log(`version_number=${version.version_number}`);
  console.log(`version_provider_id=${version.provider_id}`);

  logStep("Starting agent test run");
  const start = await requestJson(
    `${API_BASE_URL}/api/agents/${encodeURIComponent(agentKey)}/test-runs`,
    {
      method: "POST",
      headers: authHeaders(),
      body: {
        version_number: version.version_number,
        messages: [
          {
            role: "user",
            content: "用一句话回复：DeepSeek provider 已连通。",
          },
        ],
      },
      stage: "agent test run start",
      expectedStatus: 202,
    },
  );
  console.log(`run_id=${start.run_id}`);
  console.log(`status_url=${start.status_url}`);
  console.log(`events_url=${start.events_url}`);

  logStep("Polling run until terminal status");
  const run = await waitForRun(start.status_url);
  console.log(`final_status=${run.status}`);
  console.log(`result_status=${run.result_status ?? ""}`);
  if (run.error_summary) {
    console.log(`error_summary=${run.error_summary}`);
  }

  const rawOutput = run.debug?.raw_graph_output;
  const messages = rawOutput?.messages ?? [];
  if (Array.isArray(messages) && messages.length > 0) {
    console.log("\nassistant_messages:");
    for (const message of messages) {
      if (message?.type === "ai" || message?.role === "assistant") {
        console.log(extractMessageContent(message));
      }
    }
  } else if (rawOutput) {
    console.log("\nraw_graph_output:");
    console.log(JSON.stringify(rawOutput, null, 2));
  }

  if (run.status !== "success") {
    throw new Error(`DeepSeek agent smoke failed with status ${run.status}`);
  }
}

function pipeDevOutput(chunk) {
  const text = String(chunk)
    .split("\n")
    .filter(Boolean)
    .map((line) => `[make dev] ${line}`)
    .join("\n");
  if (text) console.log(text);
}

function jsonHeaders() {
  return { "content-type": "application/json" };
}

function authHeaders() {
  return { ...jsonHeaders(), "x-user-id": USER_ID };
}

async function waitForJson(url, label) {
  await waitForHttp(url, label, async (response) => {
    await response.json();
  });
}

async function waitForHttp(url, label, validate = async () => {}) {
  const deadline = Date.now() + READY_TIMEOUT_MS;
  let lastError;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(url);
      if (response.ok) {
        await validate(response);
        console.log(`${label} ready: ${url}`);
        return;
      }
      lastError = new Error(`${response.status} ${response.statusText}`);
    } catch (error) {
      lastError = error;
    }
    await sleep(1000);
  }
  throw new Error(`Timed out waiting for ${label}: ${lastError?.message}`);
}

async function requestJson(url, options) {
  const response = await fetch(url, {
    method: options.method,
    headers: options.headers,
    body: options.body ? JSON.stringify(options.body) : undefined,
  });
  const text = await response.text();
  const data = text ? parseJson(text, options.stage) : null;
  if (response.status !== options.expectedStatus) {
    throw new Error(
      `${options.stage} failed: expected ${options.expectedStatus}, got ` +
        `${response.status}. Body: ${text}`,
    );
  }
  return data;
}

function parseJson(text, stage) {
  try {
    return JSON.parse(text);
  } catch (error) {
    throw new Error(`${stage} returned non-JSON response: ${text}`);
  }
}

function assertSecretHidden(provider) {
  if ("api_key" in provider || "api_key_ciphertext" in provider) {
    throw new Error("provider response leaked API key material");
  }
}

async function waitForRun(statusUrl) {
  const deadline = Date.now() + RUN_TIMEOUT_MS;
  let latest;
  while (Date.now() < deadline) {
    latest = await requestJson(`${API_BASE_URL}${statusUrl}?debug=true`, {
      method: "GET",
      headers: jsonHeaders(),
      stage: "run status poll",
      expectedStatus: 200,
    });
    if (terminalStatuses.has(latest.status)) {
      return latest;
    }
    console.log(`run_status=${latest.status}`);
    await sleep(2000);
  }
  throw new Error(`Timed out waiting for run. Latest: ${JSON.stringify(latest)}`);
}

function extractMessageContent(message) {
  const content = message.content;
  if (typeof content === "string") return content;
  return JSON.stringify(content);
}

function cleanup() {
  shuttingDown = true;
  if (devProcess?.pid) {
    try {
      process.kill(-devProcess.pid, "SIGTERM");
    } catch {
      try {
        devProcess.kill("SIGTERM");
      } catch {
        // Process already exited.
      }
    }
  }
}

process.on("SIGINT", () => {
  cleanup();
  process.exit(130);
});
process.on("SIGTERM", () => {
  cleanup();
  process.exit(143);
});
process.on("exit", cleanup);

main()
  .catch((error) => {
    console.error(error.message);
    process.exitCode = 1;
  })
  .finally(cleanup);
