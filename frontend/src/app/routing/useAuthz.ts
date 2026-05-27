export type AuthzState = {
  isAdmin: boolean;
};

export function useAuthz(): AuthzState {
  return { isAdmin: true };
}
