import { useMemo, useState, type FormEvent } from "react";
import { useParams } from "react-router-dom";

import { Button } from "../../../components/ui/button";
import { useAgentChatMutations, useAgentDetail } from "../hooks";
import { useSessionStream } from "../../sessions/hooks";
import { StreamMarkdown } from "../../sop-quality-checks/components/StreamMarkdown";
import type { SessionMessage } from "../../sessions/types";
import { AgentPageLayout } from "./AgentPageLayout";

export function AgentChatPage() {
  const { agentId } = useParams<{ agentId: string }>();
  const detailState = useAgentDetail(agentId ?? null);
  const chatMutations = useAgentChatMutations();
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [composer, setComposer] = useState("");
  const streamState = useSessionStream(sessionId);
  const agent = detailState.data;

  const liveItems = useMemo(
    () =>
      Object.entries(streamState.state.liveBuffers).map(([key, content]) => ({
        content,
        key,
      })),
    [streamState.state.liveBuffers],
  );

  const connectionOpen =
    streamState.state.connectionStatus === "open" ||
    streamState.state.connectionStatus === "connecting" ||
    streamState.state.connectionStatus === "reconnecting";
  const sendDisabled = chatMutations.pending || connectionOpen || !composer.trim();
  const sendLabel = chatMutations.pending ? "发送中..." : "发送";

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!agentId) return;
    const message = composer.trim();
    if (!message) return;

    const response = await chatMutations.startAgentSession(agentId, {
      message,
      session_id: sessionId,
    });
    setComposer("");
    setSessionId(response.session_id);
  }

  return (
    <AgentPageLayout
      description={
        agent
          ? `${agent.draft?.model ?? "..."} · ${agent.enabled ? "已启用" : "已停用"}`
          : "加载 Agent..."
      }
      items={[
        { label: "Agent 配置", to: "/agents" },
        { label: agent?.display_name ?? agentId ?? "...", to: agentId ? `/agents/${agentId}/edit` : undefined },
        { label: "对话" },
      ]}
      title={agent?.display_name ?? "Agent 对话"}
    >
      {detailState.loading && !agent ? (
        <p className="text-xs text-mute">加载 Agent 信息中…</p>
      ) : null}
      {detailState.error && !detailState.loading ? (
        <p
          className="rounded-lg bg-error-soft px-3 py-2 text-xs text-error-deep"
          role="alert"
        >
          {detailState.error.message}
        </p>
      ) : null}
      {chatMutations.error ? (
        <p
          className="mb-3 rounded-lg bg-error-soft px-3 py-2 text-xs text-error-deep"
          role="alert"
        >
          {chatMutations.error.message}
        </p>
      ) : null}

      <section className="flex h-full flex-col gap-3 rounded-3xl border border-hairline-soft bg-canvas/95 p-4 shadow-sm shadow-primary/5">
        <div className="min-h-0 flex-1 space-y-3 overflow-y-auto">
          {streamState.state.messages.length === 0 && liveItems.length === 0 ? (
            <p className="text-center text-xs text-mute">
              尚未开始对话，输入消息试一下你的 Agent。
            </p>
          ) : (
            <>
              {streamState.state.messages.map((message) => (
                <MessageBubble key={message.id} message={message} />
              ))}
              {liveItems.map((item) => (
                <article
                  className="rounded-2xl border border-dashed border-hairline bg-canvas-soft/60 px-3 py-2 text-sm text-ink"
                  key={`live-${item.key}`}
                >
                  <StreamMarkdown>{item.content}</StreamMarkdown>
                </article>
              ))}
            </>
          )}
        </div>

        <form
          className="flex flex-col gap-2 border-t border-hairline pt-3"
          noValidate
          onSubmit={(event) => {
            void handleSubmit(event);
          }}
        >
          <label className="text-2xs font-medium uppercase tracking-[0.16em] text-mute" htmlFor="agent-chat-composer">
            对话消息
          </label>
          <textarea
            aria-label="对话消息"
            className="min-h-[96px] w-full rounded-xl border border-hairline bg-canvas px-3 py-2.5 text-sm leading-relaxed text-ink shadow-sm placeholder:text-mute outline-none focus:border-primary focus:ring-2 focus:ring-primary/15"
            id="agent-chat-composer"
            name="agent_chat_message"
            onChange={(event) => setComposer(event.target.value)}
            placeholder="向 Agent 发起新一轮对话…"
            value={composer}
          />
          <div className="flex items-center justify-end">
            <Button
              aria-busy={chatMutations.pending}
              disabled={sendDisabled}
              type="submit"
              variant="primary"
            >
              {sendLabel}
            </Button>
          </div>
        </form>
      </section>
    </AgentPageLayout>
  );
}

function MessageBubble({ message }: { message: SessionMessage }) {
  if (message.role === "assistant") {
    return (
      <article className="rounded-2xl border border-hairline bg-canvas px-3 py-2 text-sm text-ink">
        <p className="mb-1 text-2xs font-medium uppercase tracking-[0.16em] text-primary-deep">
          Assistant
        </p>
        <StreamMarkdown>{message.content}</StreamMarkdown>
      </article>
    );
  }
  if (message.role === "tool") {
    return (
      <details className="rounded-2xl border border-hairline bg-canvas-soft/60 px-3 py-2 text-xs text-body">
        <summary className="cursor-pointer text-2xs font-medium uppercase tracking-[0.16em] text-mute">
          工具输出
        </summary>
        <pre className="mt-2 whitespace-pre-wrap break-words font-mono text-xs text-ink">
          {message.content}
        </pre>
      </details>
    );
  }
  if (message.role === "system") {
    return (
      <article className="rounded-2xl border border-dashed border-hairline bg-canvas-soft/40 px-3 py-2 text-xs text-mute">
        <p className="mb-1 text-2xs font-medium uppercase tracking-[0.16em] text-mute">
          System
        </p>
        <p>{message.content}</p>
      </article>
    );
  }
  return (
    <article className="ml-auto max-w-[80%] rounded-2xl border border-primary/30 bg-primary/10 px-3 py-2 text-sm text-ink">
      <p className="mb-1 text-2xs font-medium uppercase tracking-[0.16em] text-primary-deep">
        You
      </p>
      <p className="whitespace-pre-wrap break-words">{message.content}</p>
    </article>
  );
}
