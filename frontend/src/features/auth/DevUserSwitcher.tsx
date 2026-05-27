import { useState } from "react";

import { useAuth } from "./AuthContext";
import { DEV_ACCOUNTS } from "./devAccounts";
import { getLoginErrorMessage } from "./loginErrors";

export function DevUserSwitcher() {
  const { loginAs, user } = useAuth();
  const [pendingAccount, setPendingAccount] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  if (!user) {
    return null;
  }

  async function handleSwitch(account: string) {
    if (pendingAccount || account === user?.account) {
      return;
    }

    setPendingAccount(account);
    setErrorMessage(null);

    try {
      await loginAs(account);
    } catch (error) {
      setErrorMessage(getLoginErrorMessage(error));
    } finally {
      setPendingAccount(null);
    }
  }

  return (
    <section className="px-3 pb-2" aria-label="开发用户切换">
      <div className="mb-2 min-w-0">
        <p
          className="truncate text-xs font-semibold text-ink"
          id="dev-user-switcher-label"
        >
          开发用户
        </p>
        <p className="mt-0.5 truncate text-2xs text-mute">
          Dev 模式权限视角
        </p>
      </div>
      <div
        aria-labelledby="dev-user-switcher-label"
        className="grid grid-cols-2 gap-1 rounded-full border border-hairline-soft bg-canvas-soft p-1"
        role="group"
      >
        {DEV_ACCOUNTS.map(({ account, label }) => {
          const active = user.account === account;
          const pending = pendingAccount === account;

          return (
            <button
              aria-pressed={active}
              className={`h-8 min-w-0 rounded-full px-2 text-xs font-semibold transition-colors disabled:cursor-not-allowed ${
                active
                  ? "bg-ink text-canvas"
                  : "text-body hover:bg-canvas hover:text-ink disabled:text-mute"
              }`}
              disabled={pendingAccount !== null}
              key={account}
              onClick={() => {
                void handleSwitch(account);
              }}
              type="button"
            >
              {pending ? "Signing in..." : label}
            </button>
          );
        })}
      </div>
      {errorMessage ? (
        <p
          className="mt-2 min-w-0 break-words rounded-lg border border-error-soft bg-canvas px-2 py-1 text-xs text-error-deep"
          role="alert"
        >
          {errorMessage}
        </p>
      ) : null}
    </section>
  );
}
