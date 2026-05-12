import request from "./request";
import type { PageResponse } from "../types";

/** 与后端 `UtGateRunItem` / 表字段一致，snake_case（spec/18） */
export interface UtGateRunItem {
  id: number;
  created_at: string | null;
  updated_at: string | null;
  reported_at: string | null;
  jenkins_base_url: string | null;
  job_name: string;
  build_number: number;
  build_url: string | null;
  mr_url: string | null;
  idempotency_key: string;
  is_intercepted: boolean;
  ut_exit_code: number | null;
}

/** GET /ut-gate-runs 查询参数（spec/17 §4） */
export interface UtGateRunListParams {
  page?: number;
  page_size?: number;
  start_time?: string;
  end_time?: string;
  is_intercepted?: boolean;
  mr_url?: string;
  mr_url_contains?: string;
  job_name_contains?: string;
  sort_field?: string;
  sort_order?: string;
}

function toSearchParams(params?: UtGateRunListParams): Record<string, string | number | boolean> {
  if (!params) return {};
  const out: Record<string, string | number | boolean> = {};
  const setIf = (key: string, v: string | number | boolean | undefined | null) => {
    if (v === undefined || v === null || v === "") return;
    out[key] = v;
  };
  setIf("page", params.page ?? 1);
  setIf("page_size", params.page_size ?? 20);
  setIf("start_time", params.start_time);
  setIf("end_time", params.end_time);
  if (params.is_intercepted !== undefined) setIf("is_intercepted", params.is_intercepted);
  setIf("mr_url", params.mr_url);
  setIf("mr_url_contains", params.mr_url_contains);
  setIf("job_name_contains", params.job_name_contains);
  setIf("sort_field", params.sort_field);
  setIf("sort_order", params.sort_order);
  return out;
}

export const utGateApi = {
  list(params?: UtGateRunListParams): Promise<PageResponse<UtGateRunItem>> {
    return request.get("/ut-gate-runs", { params: toSearchParams(params) }) as Promise<PageResponse<UtGateRunItem>>;
  },
};
