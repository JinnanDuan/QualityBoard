export interface PipelineHistory {
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

export interface PipelineOverview {
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

export interface PipelineFailureReason {
  id: number;
  case_name: string | null;
  failed_batch: string | null;
  owner: string | null;
  reason: string | null;
  created_at: string | null;
  updated_at: string | null;
  failed_type: string | null;
  recover_batch: string | null;
  platform: string | null;
  analyzer: string | null;
  dts_num: string | null;
}

export interface PipelineCases {
  id: number;
  case_name: string | null;
  case_level: string | null;
  case_type: string | null;
  test_type: string | null;
  is_online: string | null;
  state: string | null;
  state_detail: string | null;
  created_at: string | null;
  updated_at: string | null;
  platform: string | null;
  change_history: string | null;
  recover_batch: string | null;
  offline_reason_detail: string | null;
  pkg_type: string | null;
  offline_reason_type: string | null;
  offline_case_owner: string | null;
}

export interface UmsEmail {
  employee_id: string;
  name: string;
  email: string;
  created_at: string | null;
  updated_at: string | null;
  domain_account: string | null;
}

export interface UmsModuleOwner {
  module: string;
  owner: string;
  created_at: string | null;
  updated_at: string | null;
  for_reference: string | null;
}

export interface CaseFailedType {
  id: number;
  failed_reason_type: string;
  owner: string | null;
  creator: string;
  updater: string;
  created_time: string | null;
  updated_time: string | null;
}

export interface CaseOfflineType {
  id: number;
  offline_reason_type: string;
}

export interface PageResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface ApiResponse<T> {
  code: number;
  message: string;
  data: T | null;
}
