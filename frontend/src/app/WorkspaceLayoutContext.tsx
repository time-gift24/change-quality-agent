import { createContext, useContext, type ReactNode } from "react";

type WorkspaceLayoutContextValue = {
  refreshRecentSopQualityChecks: () => void;
  setNewConversationHandler: (handler: (() => void) | null) => void;
  setSidebarContent: (content: ReactNode | null) => void;
};

const noop = () => {};

const WorkspaceLayoutContext = createContext<WorkspaceLayoutContextValue>({
  refreshRecentSopQualityChecks: noop,
  setNewConversationHandler: noop,
  setSidebarContent: noop,
});

export const WorkspaceLayoutProvider = WorkspaceLayoutContext.Provider;

export function useWorkspaceLayout() {
  return useContext(WorkspaceLayoutContext);
}
