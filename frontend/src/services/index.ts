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
  failure_owner: string | null;
  failed_type: string | null;
}

export interface HistoryQueryParams {
  page?: number;
  page_size?: number;
  start_time?: string[];
  subtask?: string[];
  case_name?: string[];
  main_module?: string[];
  case_result?: string[];
  case_level?: string[];
  analyzed?: number[];
  platform?: string[];
  code_branch?: string[];
  failure_owner?: string[];
  failed_type?: string[];
  sort_field?: string;
  sort_order?: string;
}

export interface HistoryFilterOptions {
  start_time: string[];
  subtask: string[];
  case_name: string[];
  main_module: string[];
  case_result: string[];
  case_level: string[];
  platform: string[];
  code_branch: string[];
  failure_owner: string[];
  failed_type: string[];
}

export interface CaseFailedTypeItem {
  id: number;
  failed_reason_type: string;  // 失败类型，如 bug、环境问题
  owner: string | null;  // 默认跟踪人工号
}

export interface OwnerItem {
  employee_id: string;  // 工号，提交时用
  name: string;  // 姓名，下拉展示用
}

export interface ModuleItem {
  module: string;
  owner: string;  // 模块负责人工号
}

export interface FailureProcessOptions {
  case_failed_types: CaseFailedTypeItem[];
  owners: OwnerItem[];
  modules: ModuleItem[];
}

export interface FailureProcessRequest {
  history_ids: number[];
  failed_type: string;
  owner: string;  // 跟踪人工号
  reason: string;
  module?: string;  // 仅 failed_type=bug 时必填
}

// 将多选参数转为 URLSearchParams（key=val1&key=val2），供 FastAPI List 解析
function toSearchParams(params?: HistoryQueryParams): URLSearchParams {
  const p = new URLSearchParams();
  if (!params) return p;
  p.set("page", String(params.page ?? 1));
  p.set("page_size", String(params.page_size ?? 20));
  const appendList = (key: string, vals?: string[] | number[]) => {
    if (vals?.length) vals.forEach((v) => p.append(key, String(v)));
  };
  appendList("start_time", params.start_time);
  appendList("subtask", params.subtask);
  appendList("case_name", params.case_name);
  appendList("main_module", params.main_module);
  appendList("case_result", params.case_result);
  appendList("case_level", params.case_level);
  appendList("analyzed", params.analyzed);
  appendList("platform", params.platform);
  appendList("code_branch", params.code_branch);
  appendList("failure_owner", params.failure_owner);
  appendList("failed_type", params.failed_type);
  if (params.sort_field) p.set("sort_field", params.sort_field);
  if (params.sort_order) p.set("sort_order", params.sort_order);
  return p;
}

export const historyApi = {
  list(params?: HistoryQueryParams): Promise<PageResponse<HistoryItem>> {
    return request.get("/history", { params: toSearchParams(params) }) as any;
  },
  options(): Promise<HistoryFilterOptions> {
    return request.get("/history/options") as any;
  },
  /** 获取标注弹窗选项（失败类型、跟踪人、模块） */
  failureProcessOptions(): Promise<FailureProcessOptions> {
    return request.get("/history/failure-process-options") as any;
  },
  /** 提交失败记录标注 */
  failureProcess(data: FailureProcessRequest): Promise<{ success: boolean; message: string }> {
    return request.post("/history/failure-process", data) as any;
  },
};
