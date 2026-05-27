import { ApiError } from "../../lib/apiClient";

export function getLoginErrorMessage(error: unknown): string {
  if (error instanceof ApiError && error.detail) {
    return error.detail;
  }

  if (error instanceof Error) {
    return error.message;
  }

  return "Login failed.";
}
