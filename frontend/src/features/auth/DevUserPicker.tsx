import { useState } from "react";

import { ApiError } from "../../lib/apiClient";
import { useAuth } from "./AuthContext";

const DEV_ACCOUNTS = [
  { account: "common", label: "Common" },
  { account: "admin", label: "Admin" },
] as const;

export function DevUserPicker() {
  const { loginAs } = useAuth();
  const [pendingAccount, setPendingAccount] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  async function handleLogin(account: string) {
    setPendingAccount(account);
    setErrorMessage(null);

    try {
      await loginAs(account);
    } catch (error) {
      setErrorMessage(getLoginErrorMessage(error));
      setPendingAccount(null);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-aurora px-4 py-6 text-ink">
      <section
        aria-labelledby="dev-user-picker-title"
        className="min-w-0 w-full max-w-sm rounded-2xl border border-hairline-soft bg-canvas/95 p-4 shadow-sm shadow-primary/5"
      >
        <div className="mb-4">
          <p className="text-2xs font-semibold uppercase tracking-normal text-primary-deep">
            Development
          </p>
          <h1
            className="mt-1 text-base font-semibold tracking-tight text-ink"
            id="dev-user-picker-title"
          >
            Choose a user
          </h1>
          <p className="mt-1 text-xs text-mute">
            Select a local account to continue.
          </p>
        </div>

        {errorMessage ? (
          <p
            className="mb-3 min-w-0 break-words rounded-xl border border-error-soft bg-canvas px-3 py-2 text-xs text-error-deep"
            role="alert"
          >
            {errorMessage}
          </p>
        ) : null}

        <p aria-busy={pendingAccount !== null} className="sr-only" role="status">
          {pendingAccount ? "Signing in…" : "Ready"}
        </p>

        <div className="grid gap-2">
          {DEV_ACCOUNTS.map(({ account, label }) => (
            <button
              className="h-10 min-w-0 rounded-full border border-transparent bg-primary px-5 text-sm font-semibold text-on-primary transition-colors hover:bg-primary-deep disabled:cursor-not-allowed disabled:bg-mute"
              disabled={pendingAccount !== null}
              key={account}
              onClick={() => {
                void handleLogin(account);
              }}
              type="button"
            >
              {pendingAccount === account ? "Signing in…" : label}
            </button>
          ))}
        </div>
      </section>
    </main>
  );
}

function getLoginErrorMessage(error: unknown): string {
  if (error instanceof ApiError && error.detail) {
    return error.detail;
  }

  if (error instanceof Error) {
    return error.message;
  }

  return "Login failed.";
}
