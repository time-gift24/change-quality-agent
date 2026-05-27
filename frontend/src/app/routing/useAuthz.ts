import { useAuth } from "../../features/auth/AuthContext";

export type AuthzState = {
  isAdmin: boolean;
};

export function useAuthz(): AuthzState {
  const { user } = useAuth();

  return { isAdmin: user?.is_admin === true };
}
