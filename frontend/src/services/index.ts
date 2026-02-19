export { default as request } from "./request";

import request from "./request";

export interface PageResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface HistoryItem {
  id: number;
  start_time: string | null;
  subtask: string | null;
  reports_url: string | null;
  log_url: string;
  screenshot_url: string;
  module: string | null;
  case_name: string | null;
  case_result: string | null;
  created_at: string | null;
  updated_at: string | null;
  pipeline_url: string | null;
  case_level: string;
  main_module: string;
  owner_history: string | null;
  owner: string | null;
  platform: string | null;
  code_branch: string | null;
  analyzed: number | null;
}

export interface HistoryQueryParams {
  page?: number;
  page_size?: number;
  start_time?: string;
  case_result?: string;
  platform?: string;
}

export const historyApi = {
  list(params?: HistoryQueryParams): Promise<PageResponse<HistoryItem>> {
    return request.get("/history", { params }) as any;
  },
};
