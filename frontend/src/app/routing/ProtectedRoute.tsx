import { Outlet } from "react-router-dom";

import { useAuthz } from "./useAuthz";

export function ProtectedRoute() {
  const { isAdmin } = useAuthz();

  if (!isAdmin) {
    return <div>403 Forbidden</div>;
  }

  return <Outlet />;
}
