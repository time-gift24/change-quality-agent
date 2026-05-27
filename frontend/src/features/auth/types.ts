export type CurrentUser = {
  id: string;
  account: string;
  is_admin: boolean;
  meta: Record<string, unknown>;
};
