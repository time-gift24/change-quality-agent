export async function requestJson<T>(
  url: string,
  init: RequestInit = {},
): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");

  const response = await fetch(url, {
    ...init,
    headers,
  });

  if (!response.ok) {
    throw await apiErrorFromResponse(response);
  }

  return (await response.json()) as T;
}

export async function apiErrorFromResponse(response: Response): Promise<ApiError> {
  return new ApiError(
    response.status,
    response.statusText,
    await readErrorDetail(response),
  );
}

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly statusText: string,
    public readonly detail?: string,
  ) {
    super(
      detail
        ? `API request failed: ${status} ${statusText}: ${detail}`
        : `API request failed: ${status} ${statusText}`,
    );
    this.name = "ApiError";
  }
}

async function readErrorDetail(response: Response): Promise<string | undefined> {
  const body = await response.text();

  if (!body) {
    return undefined;
  }

  try {
    const parsed = JSON.parse(body) as { detail?: unknown };

    if (typeof parsed.detail === "string") {
      return parsed.detail;
    }

    if (parsed.detail !== undefined) {
      return JSON.stringify(parsed.detail);
    }
  } catch {
    return body;
  }

  return undefined;
}
