import { ApiError } from "../../../lib/apiClient";

export function getMcpErrorMessage(error: Error | null): string | null {
  if (!error) {
    return null;
  }

  const status = getErrorStatus(error);

  if (status === 409) {
    return "请先停止服务再修改配置";
  }

  if (status === 404) {
    return "MCP 服务不存在，请刷新列表后重试";
  }

  if (status === 502 || status === 503) {
    return "MCP 服务操作失败，请执行 check 后重试";
  }

  if (error instanceof ApiError && error.detail) {
    return error.detail;
  }

  return error.message;
}

export function isMcpNotFoundError(error: Error | null): boolean {
  return error ? getErrorStatus(error) === 404 : false;
}

function getErrorStatus(error: Error): number | null {
  if (error instanceof ApiError) {
    return error.status;
  }

  const maybeError = error as Error & { status?: unknown };
  return typeof maybeError.status === "number" ? maybeError.status : null;
}
