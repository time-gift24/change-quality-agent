export type SopEnvironment = {
  key: string;
  name_en: string;
  name_zh: string;
};

export type SopQualityCheckHistoryItem = {
  check_id: string;
  sop_id?: string | null;
  env_key?: string | null;
  status?: string | null;
  created_at?: string | null;
};
