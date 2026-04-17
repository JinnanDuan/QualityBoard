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
  /** 用例开发责任人：姓名+工号（后端按 main_module→ums_module_owner 拼接） */
  owner: string | null;
  platform: string | null;
  code_branch: string | null;
  analyzed: number | null;
  failure_owner: string | null;
  failed_type: string | null;
  reason: string | null;
  failure_analyzer: string | null;
  analyzed_at: string | null;
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
  owner: string;  // 失败跟踪人：非 bug 多为工号；bug 时为「姓名 工号」展示串，可自定义
  reason: string;
  module?: string;  // 仅 failed_type=bug 时必填
}

export interface InheritFailureReasonRequest {
  inherit_mode: "batch" | "case";
  source_batch?: string;
  target_batch?: string;
  source_pfr_id?: number;  // 用例维度时必填，用户从筛选结果中选择的 pfr.id
  history_ids?: number[];
}

export interface InheritSourceRecordItem {
  id: number;
  case_name: string | null;
  platform: string | null;
  failed_batch: string | null;
  failed_type: string | null;
  owner: string | null;
  reason: string | null;
}

export interface InheritFailureReasonResponse {
  success: boolean;
  inherited_count: number;
  skipped_count: number;
  message: string;
}

export interface OneClickAnalyzeRequest {
  anchor_history_id: number;
}

export interface OneClickAnalyzeResponse {
  success: boolean;
  message: string;
  batch: string;
  applied_count: number;
  skipped_no_owner_count: number;
  skipped_not_eligible_count: number;
}

export interface OneClickBugNotifyRequest {
  anchor_history_id: number;
  selected_history_ids?: number[];
}

export interface BugNotifyFailedOwnerItem {
  owner: string;
  reason: string;
}

export interface OneClickBugNotifyDetails {
  skipped_owners: string[];
  failed_owners: BugNotifyFailedOwnerItem[];
}

export interface OneClickBugNotifyResponse {
  success: boolean;
  message: string;
  batch: string;
  notified_count: number;
  skipped_no_domain_count: number;
  skipped_parse_owner_count: number;
  failed_delivery_count: number;
  details?: OneClickBugNotifyDetails | null;
}

/** GET /history/batch-report 轮次通报汇总 */
export interface BatchReportModuleCount {
  main_module: string;
  count: number;
}

export interface BatchReportOwnerGroup {
  employee_id: string;
  employee_name: string | null;
  case_count: number;
  modules: BatchReportModuleCount[];
}

export interface BatchReportPlatformGroup {
  platform: string;
  owners: BatchReportOwnerGroup[];
}

export interface BatchReportResponse {
  start_time: string;
  total: number;
  passed: number;
  failed: number;
  skip: number;
  platforms: BatchReportPlatformGroup[];
}

export interface InheritSourceOptions {
  case_names: string[];
  platforms: string[];
  batches: string[];
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
  /** 获取继承弹窗批次选项 */
  inheritBatchOptions(excludeBatch?: string): Promise<{ batches: string[] }> {
    const params = excludeBatch ? { exclude_batch: excludeBatch } : {};
    return request.get("/history/inherit-batch-options", { params }) as any;
  },
  /** 获取继承弹窗用例维度源选择三字段选项 */
  inheritSourceOptions(caseName?: string, platform?: string): Promise<InheritSourceOptions> {
    const params: Record<string, string> = {};
    if (caseName) params.case_name = caseName;
    if (platform) params.platform = platform;
    return request.get("/history/inherit-source-options", { params }) as any;
  },
  /** 根据三字段筛选，返回匹配的源记录列表，供用户选择 */
  inheritSourceRecords(
    caseName: string,
    platform?: string,
    batch?: string
  ): Promise<{ records: InheritSourceRecordItem[] }> {
    const params: Record<string, string> = { case_name: caseName };
    if (platform) params.platform = platform;
    if (batch) params.batch = batch;
    return request.get("/history/inherit-source-records", { params }) as any;
  },
  /** 提交失败原因继承（大批量可能较慢，单独 60s 超时）；signal 用于关闭弹窗时中止请求、尽快释放服务端锁 */
  inheritFailureReason(
    data: InheritFailureReasonRequest,
    signal?: AbortSignal
  ): Promise<InheritFailureReasonResponse> {
    return request.post("/history/inherit-failure-reason", data, {
      timeout: 60000,
      signal,
    }) as any;
  },
  /** 一键分析：整批未分析失败/异常标记为 bug（锚点解析批次） */
  oneClickAnalyze(data: OneClickAnalyzeRequest): Promise<OneClickAnalyzeResponse> {
    return request.post("/history/one-click-analyze", data, { timeout: 60000 }) as any;
  },
  /** 一键通知：按锚点批次向 bug 失败跟踪人发 WeLink（spec/13） */
  oneClickBugNotify(data: OneClickBugNotifyRequest): Promise<OneClickBugNotifyResponse> {
    return request.post("/history/one-click-bug-notify", data, { timeout: 120000 }) as any;
  },
  /** 轮次通报：按批次汇总结果分布与 bug 归因（用于复制群通告） */
  batchReport(startTime: string): Promise<BatchReportResponse> {
    return request.get("/history/batch-report", {
      params: { start_time: startTime },
    }) as any;
  },
};

// --- Dashboard API ---

export interface LatestBatchItem {
  batch: string;
  total_case_num: number;
  passed_num: number;
  failed_num: number;
  pass_rate: number;
  batch_start: string | null;
  batch_end: string | null;
  result: string;
}

export interface BatchTrendItem {
  batch: string;
  total_case_num: number;
  passed_num: number;
  failed_num: number;
  pass_rate: number;
  batch_start: string | null;
}

export const dashboardApi = {
  latestBatch: (): Promise<LatestBatchItem | null> =>
    request.get("/dashboard/latest-batch") as Promise<LatestBatchItem | null>,
  batchTrend: (
    limit = 30,
    codeBranch: "master" | "bugfix" = "master"
  ): Promise<{ items: BatchTrendItem[] }> =>
    request.get("/dashboard/batch-trend", {
      params: { limit, code_branch: codeBranch },
    }) as Promise<{ items: BatchTrendItem[] }>,
};

// --- Overview（分组执行历史，pipeline_overview，spec/14）---

export interface OverviewItem {
  id: number;
  batch: string | null;
  subtask: string | null;
  result: string | null;
  case_num: string | null;
  batch_start: string | null;
  batch_end: string | null;
  reports_url: string | null;
  log_url: string | null;
  screenshot_url: string | null;
  pipeline_url: string | null;
  created_at: string | null;
  updated_at: string | null;
  passed_num: number | null;
  failed_num: number | null;
  platform: string | null;
  code_branch: string | null;
}

export interface OverviewQueryParams {
  page?: number;
  page_size?: number;
  batch?: string[];
  subtask?: string[];
  platform?: string[];
  code_branch?: string[];
  result?: string[];
  sort_field?: string;
  sort_order?: string;
  /** 为 true 时不注入默认最近 30 批；须带 subtask（专用分组页） */
  all_batches?: boolean;
}

export interface OverviewFilterOptions {
  batch: string[];
  subtask: string[];
  platform: string[];
  code_branch: string[];
  result: string[];
}

function overviewToSearchParams(params?: OverviewQueryParams): URLSearchParams {
  const p = new URLSearchParams();
  if (!params) return p;
  p.set("page", String(params.page ?? 1));
  p.set("page_size", String(params.page_size ?? 20));
  const appendList = (key: string, vals?: string[]) => {
    if (vals?.length) vals.forEach((v) => p.append(key, v));
  };
  appendList("batch", params.batch);
  appendList("subtask", params.subtask);
  appendList("platform", params.platform);
  appendList("code_branch", params.code_branch);
  appendList("result", params.result);
  if (params.sort_field) p.set("sort_field", params.sort_field);
  if (params.sort_order) p.set("sort_order", params.sort_order);
  if (params.all_batches) p.set("all_batches", "true");
  return p;
}

export const overviewApi = {
  list(params?: OverviewQueryParams): Promise<PageResponse<OverviewItem>> {
    return request.get("/overview", { params: overviewToSearchParams(params) }) as any;
  },
  options(): Promise<OverviewFilterOptions> {
    return request.get("/overview/options") as any;
  },
};
