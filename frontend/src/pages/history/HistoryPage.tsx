import { useEffect, useState, useCallback, useRef } from "react";
import { useSearchParams } from "react-router-dom";
import { Resizable } from "react-resizable";
import "react-resizable/css/styles.css";
import "./history-table.css";
import {
  Button,
  Drawer,
  Divider,
  Form,
  Input,  // TextArea 用
  message,  // 成功/失败提示
  Modal,  // 标注弹窗
  Radio,
  Row,
  Col,
  Select,
  Spin,
  Table,
  Tag,
  Tooltip,
  Typography,
} from "antd";
import { EyeOutlined } from "@ant-design/icons";
import type { ColumnsType, TablePaginationConfig } from "antd/es/table";
import {
  historyApi,
  type HistoryItem,
  type HistoryFilterOptions,
  type HistoryQueryParams,
  type FailureProcessOptions,  // 标注弹窗选项
  type FailureProcessRequest,  // 标注提交请求
  type ModuleItem,
  type InheritFailureReasonRequest,
  type InheritSourceOptions,
  type InheritSourceRecordItem,
  type BatchReportResponse,
} from "../../services";

const { Text, Title, Paragraph } = Typography;

/** 轮次群通告正文（与产品约定模板一致） */
function buildRollingReportMarkdown(data: BatchReportResponse): string {
  const lines: string[] = [];
  lines.push("【rolling线看护进展通告】");
  lines.push(`batch：${data.start_time}`);
  lines.push(
    `用例总数：${data.total}，成功：${data.passed}，失败：${data.failed}，跳过：${data.skip}`,
  );
  lines.push("");
  lines.push("怀疑修改引入问题：");
  lines.push("");
  if (!data.platforms?.length) {
    lines.push("（本轮该批次无失败原因为 bug 的用例）");
  } else {
    for (const plat of data.platforms) {
      lines.push(`${plat.platform}：`);
      for (const o of plat.owners) {
        const namePart = o.employee_name ? `${o.employee_name} ` : "";
        const modParts = o.modules.map((m) => `${m.main_module}（${m.count}）`).join("，");
        lines.push(`${namePart}${o.employee_id} 【${o.case_count}条】：${modParts}`);
      }
      lines.push("");
    }
  }
  const board = new URLSearchParams();
  board.append("start_time", data.start_time);
  board.append("failed_type", "bug");
  const url = `${window.location.origin}/history?${board.toString()}`;
  lines.push(`详见：${url}`);
  lines.push("");
  lines.push("——————————————");
  return lines.join("\n");
}

/** 钻取页链接（spec/12），新标签打开 */
function caseExecutionsDrilldownHref(record: HistoryItem): string {
  const qs = new URLSearchParams();
  if (record.case_name) qs.append("case_name", record.case_name);
  if (record.platform) qs.append("platform", record.platform);
  if (record.code_branch) qs.append("code_branch", record.code_branch);
  qs.set("page", "1");
  return `/history/case-executions?${qs.toString()}`;
}

function UrlLink({
  url,
  label,
}: {
  url: string | null | undefined;
  label: string;
}) {
  if (url) {
    const href =
      url.startsWith("http://") || url.startsWith("https://")
        ? url
        : `https://${url}`;
    return (
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        onClick={(e) => e.stopPropagation()}
      >
        {label}
      </a>
    );
  }
  return <Text type="secondary">暂无</Text>;
}

/** 仅当内容被遮挡时悬停显示 */
function EllipsisTooltip({
  title,
  children,
  placement = "topLeft",
}: {
  title: string;
  children: React.ReactNode;
  placement?: "topLeft" | "top" | "topRight" | "bottomLeft" | "bottom" | "bottomRight";
}) {
  const [truncated, setTruncated] = useState(false);
  const ref = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const check = () => setTruncated(el.scrollWidth > el.clientWidth);
    check();
    const ro = new ResizeObserver(check);
    ro.observe(el);
    return () => ro.disconnect();
  }, [title, children]);

  return (
    <Tooltip title={truncated ? title : undefined} placement={placement}>
      <span
        ref={ref}
        style={{
          display: "block",
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
        }}
      >
        {children}
      </span>
    </Tooltip>
  );
}

// 可调整列宽的表头
function ResizableTitle(
  props: React.HTMLAttributes<any> & {
    onResize?: (e: React.SyntheticEvent, data: { size: { width: number; height: number } }) => void;
    width?: number;
  }
) {
  const { onResize, width, ...restProps } = props;
  if (!width || !onResize) return <th {...restProps} />;
  return (
    <Resizable
      width={width}
      height={0}
      axis="x"
      resizeHandles={["e"]}
      handle={
        <span
          className="react-resizable-handle"
          onClick={(e) => e.stopPropagation()}
        />
      }
      onResize={onResize}
      draggableOpts={{ enableUserSelectHack: false }}
    >
      <th {...restProps} style={{ ...restProps.style, width }} />
    </Resizable>
  );
}

// 默认列宽（考虑表头与内容，表头不换行，整体稍宽）
const DEFAULT_WIDTHS: Record<string, number> = {
  start_time: 120,
  subtask: 90,
  case_name: 140,
  main_module: 90,
  case_result: 90,
  failure_owner: 80,
  failed_type: 110,
  case_level: 100,
  analyzed: 90,
  platform: 80,
  code_branch: 100,
  screenshot_url: 90,
  reports_url: 90,
  action: 80,
};

/** 从表格区域量得的高度中，为表头与底部分页（含每页条数）预留的像素，用于推算 `scroll.y` */
const HISTORY_TABLE_SCROLL_RESERVE_PX = 118;

/** main_module 与 ums_module_owner.module 小写匹配（与后端模块责任人逻辑一致） */
function findModuleItemInsensitive(
  modules: ModuleItem[] | undefined,
  mainModule: string | undefined,
): ModuleItem | undefined {
  if (!modules?.length || !mainModule?.trim()) return undefined;
  const q = mainModule.trim().toLowerCase();
  return modules.find((m) => m.module.trim().toLowerCase() === q);
}

/** bug：按模块负责人在 ums_email 中解析为「姓名 工号」；无姓名则退回工号 */
function formatBugOwnerDisplay(
  employeeId: string | undefined,
  opts: FailureProcessOptions | null,
): string {
  if (!employeeId?.trim()) return "";
  const id = employeeId.trim();
  const row = opts?.owners?.find((o) => o.employee_id === id);
  if (row?.name?.trim()) {
    return `${row.name.trim()} ${id}`;
  }
  return id;
}

export type HistoryPageProps = {
  /** 用例执行历史钻取（spec/12），URL 为 /history/case-executions */
  drilldown?: boolean;
};

export default function HistoryPage({ drilldown = false }: HistoryPageProps) {
  const [searchParams, setSearchParams] = useSearchParams();
  const [data, setData] = useState<HistoryItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [options, setOptions] = useState<HistoryFilterOptions | null>(null);
  const [optionsLoading, setOptionsLoading] = useState(false);
  const [drawerVisible, setDrawerVisible] = useState(false);
  const [drawerRecord, setDrawerRecord] = useState<HistoryItem | null>(null);
  const [reasonExpanded, setReasonExpanded] = useState(false);
  const [form] = Form.useForm();
  const [processForm] = Form.useForm();  // 标注弹窗表单
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20 });
  const [colWidths, setColWidths] = useState<Record<string, number>>(DEFAULT_WIDTHS);
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([]);  // 勾选的行 id
  const [processModalVisible, setProcessModalVisible] = useState(false);
  const [failureProcessOptions, setFailureProcessOptions] = useState<FailureProcessOptions | null>(null);
  const [processSubmitLoading, setProcessSubmitLoading] = useState(false);
  const processFailedType = Form.useWatch("failed_type", processForm);  // 监听失败类型，控制模块字段显隐
  const [inheritForm] = Form.useForm();
  const [inheritModalVisible, setInheritModalVisible] = useState(false);
  const [inheritSubmitLoading, setInheritSubmitLoading] = useState(false);
  const [oneClickLoading, setOneClickLoading] = useState(false);
  const [bugNotifyLoading, setBugNotifyLoading] = useState(false);
  const [reportModalVisible, setReportModalVisible] = useState(false);
  const [reportLoading, setReportLoading] = useState(false);
  const [reportText, setReportText] = useState("");
  const [inheritBatchOptions, setInheritBatchOptions] = useState<string[]>([]);
  const [inheritBatchOptionsLoading, setInheritBatchOptionsLoading] = useState(false);
  const [inheritSourceOptions, setInheritSourceOptions] = useState<InheritSourceOptions>({
    case_names: [],
    platforms: [],
    batches: [],
  });
  const [inheritSourceOptionsLoading, setInheritSourceOptionsLoading] = useState(false);
  const [inheritSourceRecords, setInheritSourceRecords] = useState<InheritSourceRecordItem[]>([]);
  const [inheritSourceRecordsLoading, setInheritSourceRecordsLoading] = useState(false);
  const inheritMode = Form.useWatch("inherit_mode", inheritForm);

  /** 中间表格区高度（视口剩余），供 Ant Design Table `scroll.y` 使用 */
  const tableAreaRef = useRef<HTMLDivElement>(null);
  const [tableScrollY, setTableScrollY] = useState(300);

  /** 钻取页首次有效 URL 快照，用于「筛选重置」恢复用例名/平台/分支 */
  const drilldownAnchorRef = useRef<{
    case_name?: string[];
    platform?: string[];
    code_branch?: string[];
  } | null>(null);
  const drilldownInvalidWarnedRef = useRef(false);

  const paramsFromUrl = (): HistoryQueryParams => {
    const getList = (key: string) => {
      const vals = searchParams.getAll(key);
      return vals.length > 0 ? vals : undefined;
    };
    const getIntList = (key: string) => {
      const vals = searchParams.getAll(key);
      if (vals.length === 0) return undefined;
      return vals.map((v) => parseInt(v, 10)).filter((n) => !isNaN(n));
    };
    return {
      page: searchParams.get("page") ? parseInt(searchParams.get("page")!, 10) : 1,
      page_size: searchParams.get("page_size")
        ? parseInt(searchParams.get("page_size")!, 10)
        : 20,
      start_time: getList("start_time"),
      subtask: getList("subtask"),
      case_name: getList("case_name"),
      main_module: getList("main_module"),
      case_result: getList("case_result"),
      case_level: getList("case_level"),
      analyzed: getIntList("analyzed"),
      platform: getList("platform"),
      code_branch: getList("code_branch"),
      failure_owner: getList("failure_owner"),
      failed_type: getList("failed_type"),
      sort_field: searchParams.get("sort_field") || undefined,
      sort_order: searchParams.get("sort_order") || undefined,
    };
  };

  const syncParamsToUrl = useCallback(
    (params: HistoryQueryParams) => {
      const next = new URLSearchParams();
      if (params.page && params.page > 1) next.set("page", String(params.page));
      if (params.page_size && params.page_size !== 20)
        next.set("page_size", String(params.page_size));
      const appendList = (key: string, vals?: string[] | number[]) => {
        if (vals?.length) vals.forEach((v) => next.append(key, String(v)));
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
      if (params.sort_field) next.set("sort_field", params.sort_field);
      if (params.sort_order) next.set("sort_order", params.sort_order);
      setSearchParams(next, { replace: true });
    },
    [setSearchParams]
  );

  const fetchData = async (params: HistoryQueryParams) => {
    setLoading(true);
    try {
      const res = await historyApi.list(params);
      setData(res.items);
      setTotal(res.total);
    } catch (e: unknown) {
      const err = e as {
        code?: string;
        message?: string;
        response?: { status?: number; data?: { detail?: string } };
      };
      if (err.code === "ECONNABORTED" || err.message?.toLowerCase().includes("timeout")) {
        message.error("请求超时，请缩小筛选范围（如选择批次或平台）后重试");
      } else if (err.response?.status && err.response.status >= 500) {
        message.error("服务异常，请稍后重试");
      } else {
        const detail = err.response?.data?.detail;
        message.error((typeof detail === "string" && detail) ? detail : "加载失败");
      }
      // 失败时保留上次数据，不调用 setData/setTotal
    } finally {
      setLoading(false);
    }
  };

  const fetchOptions = async () => {
    setOptionsLoading(true);
    try {
      const opts = await historyApi.options();
      setOptions(opts);
    } finally {
      setOptionsLoading(false);
    }
  };

  useEffect(() => {
    fetchOptions();
  }, []);

  useEffect(() => {
    if (!drilldown) {
      drilldownInvalidWarnedRef.current = false;
      return;
    }
    const params = paramsFromUrl();
    const hasCase = params.case_name?.some((n) => n && String(n).trim());
    if (hasCase) {
      drilldownInvalidWarnedRef.current = false;
    } else if (!drilldownInvalidWarnedRef.current) {
      drilldownInvalidWarnedRef.current = true;
      message.error("链接无效：缺少用例名");
    }
  }, [drilldown, searchParams]);

  useEffect(() => {
    const params = paramsFromUrl();
    form.setFieldsValue({
      start_time: params.start_time,
      subtask: params.subtask,
      case_name: params.case_name,
      main_module: params.main_module,
      case_result: params.case_result,
      case_level: params.case_level,
      analyzed: params.analyzed,
      platform: params.platform,
      code_branch: params.code_branch,
      failure_owner: params.failure_owner,
      failed_type: params.failed_type,
    });
    setPagination({ current: params.page ?? 1, pageSize: params.page_size ?? 20 });
  }, [searchParams]);

  useEffect(() => {
    const params = paramsFromUrl();
    if (drilldown) {
      const hasCase = params.case_name?.some((n) => n && String(n).trim());
      if (!hasCase) {
        setData([]);
        setTotal(0);
        return;
      }
      if (drilldownAnchorRef.current === null) {
        drilldownAnchorRef.current = {
          case_name: params.case_name,
          platform: params.platform,
          code_branch: params.code_branch,
        };
      }
    } else {
      drilldownAnchorRef.current = null;
    }
    fetchData({
      ...params,
      page: params.page ?? 1,
      page_size: params.page_size ?? 20,
    });
  }, [searchParams, drilldown]);

  useEffect(() => {
    const el = tableAreaRef.current;
    if (!el) return;
    const update = () => {
      const h = el.getBoundingClientRect().height;
      setTableScrollY(Math.max(120, Math.floor(h - HISTORY_TABLE_SCROLL_RESERVE_PX)));
    };
    update();
    const ro = new ResizeObserver(() => update());
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const handleFilterChange = () => {
    const values = form.getFieldsValue();
    const params: HistoryQueryParams = {
      page: 1,
      page_size: pagination.pageSize,
      start_time: values.start_time?.length ? values.start_time : undefined,
      subtask: values.subtask?.length ? values.subtask : undefined,
      case_name: values.case_name?.length ? values.case_name : undefined,
      main_module: values.main_module?.length ? values.main_module : undefined,
      case_result: values.case_result?.length ? values.case_result : undefined,
      case_level: values.case_level?.length ? values.case_level : undefined,
      analyzed: values.analyzed?.length ? values.analyzed : undefined,
      platform: values.platform?.length ? values.platform : undefined,
      code_branch: values.code_branch?.length ? values.code_branch : undefined,
      failure_owner: values.failure_owner?.length ? values.failure_owner : undefined,
      failed_type: values.failed_type?.length ? values.failed_type : undefined,
    };
    syncParamsToUrl(params);
    setPagination((p) => ({ ...p, current: 1 }));
  };

  const handleReset = () => {
    if (drilldown && drilldownAnchorRef.current) {
      syncParamsToUrl({
        page: 1,
        page_size: pagination.pageSize,
        case_name: drilldownAnchorRef.current.case_name,
        platform: drilldownAnchorRef.current.platform,
        code_branch: drilldownAnchorRef.current.code_branch,
      });
    } else {
      syncParamsToUrl({ page: 1, page_size: pagination.pageSize });
    }
    setPagination((p) => ({ ...p, current: 1 }));
  };

  const handleTableChange = (
    pag: TablePaginationConfig,
    _filters: Record<string, unknown>,
    sorter: unknown
  ) => {
    const nextPage = pag.current ?? 1;
    const nextSize = pag.pageSize ?? 20;
    const params = paramsFromUrl();
    const sort = Array.isArray(sorter) ? (sorter as { field?: string; order?: string }[])[0] : (sorter as { field?: string; order?: string });
    const sortField = (typeof sort?.field === "string" ? sort.field : undefined) || undefined;
    const sortOrder =
      sort?.order === "ascend" ? "asc" : sort?.order === "descend" ? "desc" : undefined;
    const sortChanged =
      sortField !== params.sort_field || sortOrder !== params.sort_order;
    const pageToUse = sortChanged ? 1 : nextPage;
    syncParamsToUrl({
      ...params,
      page: pageToUse,
      page_size: nextSize,
      sort_field: sortField,
      sort_order: sortOrder,
    });
    setPagination({ current: pageToUse, pageSize: nextSize });
    setSelectedRowKeys([]);  // 切换分页时清空勾选
  };

  const selectedRows = data.filter((r) => selectedRowKeys.includes(r.id));
  const hasSelectedFailedOrError = selectedRows.some(
    (r) => r.case_result === "failed" || r.case_result === "error"
  );
  const processBtnEnabled = selectedRowKeys.length > 0 && hasSelectedFailedOrError;  // 至少勾选一条失败/异常记录时可用
  const currentBatch =
    selectedRows.length === 0
      ? undefined
      : selectedRows.length === 1
        ? selectedRows[0].start_time ?? undefined
        : (() => {
            const first = selectedRows[0]?.start_time;
            return selectedRows.every((r) => r.start_time === first) ? first ?? undefined : undefined;
          })();
  /** 勾选至少一行且同属一轮次，用于一键生成通报 */
  const reportBtnEnabled = selectedRowKeys.length > 0 && currentBatch != null;
  /** 与一键分析相同勾选范围，且必须同一轮次（spec/13） */
  const notifyBtnEnabled = processBtnEnabled && currentBatch != null;
  const showBatchDimension = currentBatch != null;

  const openProcessModal = async () => {
    if (!processBtnEnabled) return;
    setProcessModalVisible(true);
    try {
      const opts = await historyApi.failureProcessOptions();
      setFailureProcessOptions(opts);
      const firstFailed = selectedRows.find(
        (r) => r.case_result === "failed" || r.case_result === "error"
      );
      const rawModule = firstFailed?.main_module ?? undefined;
      const modItem0 = findModuleItemInsensitive(opts.modules, rawModule);
      const moduleValue = modItem0?.module ?? rawModule;
      processForm.setFieldsValue({
        failed_type: undefined,
        owner: undefined,
        reason: undefined,
        module: moduleValue,
      });
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } }; message?: string };
      message.error(err?.response?.data?.detail || err?.message || "获取选项失败");
    }
  };

  const handleProcessModalOk = async () => {
    try {
      const values = await processForm.validateFields();
      const failedOnlyIds = selectedRows
        .filter((r) => r.case_result === "failed" || r.case_result === "error")
        .map((r) => r.id);
      if (!failedOnlyIds.length) {
        message.warning("请至少勾选一条失败或异常记录");
        return;
      }
      const failedType = values.failed_type as string;
      const isBug = failedType?.trim().toLowerCase() === "bug";  // bug 匹配：忽略首尾空格、大小写
      const payload: FailureProcessRequest = {
        history_ids: failedOnlyIds.map(Number),
        failed_type: failedType,
        owner: values.owner,
        reason: values.reason?.trim() ?? "",
      };
      if (isBug && values.module) {
        payload.module = values.module;
      }
      setProcessSubmitLoading(true);
      await historyApi.failureProcess(payload);
      message.success("标注成功");
      setProcessModalVisible(false);
      processForm.resetFields();
      setSelectedRowKeys([]);
      const params = paramsFromUrl();
      await fetchData({  // 刷新当前页，保持分页与筛选
        ...params,
        page: params.page ?? 1,
        page_size: params.page_size ?? 20,
      });
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } }; message?: string };
      const msg = err?.response?.data?.detail || err?.message || "提交失败";
      if (typeof msg === "string") {
        message.error(msg);
      } else if (Array.isArray(msg)) {
        const parts = (msg as Array<{ msg?: string }>).map((m) => m.msg || "");
        message.error(parts.join("; "));
      } else {
        message.error("提交失败");
      }
    } finally {
      setProcessSubmitLoading(false);
    }
  };

  const handleProcessModalCancel = () => {
    setProcessModalVisible(false);
    processForm.resetFields();
  };

  const openInheritModal = async () => {
    if (!processBtnEnabled) return;
    setInheritModalVisible(true);
    setInheritSourceRecords([]);
    inheritForm.setFieldsValue({
      inherit_mode: showBatchDimension ? "batch" : "case",
      source_batch: undefined,
      source_case_name: undefined,
      source_platform: undefined,
      source_pfr_id: undefined,
    });
    if (showBatchDimension) {
      setInheritBatchOptionsLoading(true);
      try {
        const res = await historyApi.inheritBatchOptions(currentBatch);
        setInheritBatchOptions(res.batches ?? []);
      } catch (e: unknown) {
        const err = e as { response?: { data?: { detail?: string } }; message?: string };
        message.error(err?.response?.data?.detail || err?.message || "获取批次选项失败");
      } finally {
        setInheritBatchOptionsLoading(false);
      }
    } else {
      setInheritSourceOptionsLoading(true);
      try {
        const res = await historyApi.inheritSourceOptions();
        setInheritSourceOptions(res);
      } catch (e: unknown) {
        const err = e as { response?: { data?: { detail?: string } }; message?: string };
        message.error(err?.response?.data?.detail || err?.message || "获取源选项失败");
      } finally {
        setInheritSourceOptionsLoading(false);
      }
    }
  };

  const handleInheritModalOk = async () => {
    try {
      const values = await inheritForm.validateFields();
      const payload: InheritFailureReasonRequest = {
        inherit_mode: values.inherit_mode,
      };
      if (values.inherit_mode === "batch") {
        payload.source_batch = values.source_batch;
        payload.target_batch = currentBatch!;
      } else {
        const failedOnlyIds = selectedRows
          .filter((r) => r.case_result === "failed" || r.case_result === "error")
          .map((r) => r.id);
        if (!failedOnlyIds.length) {
          message.warning("用例维度继承需至少勾选一条失败或异常记录");
          return;
        }
        payload.source_pfr_id = values.source_pfr_id;
        payload.history_ids = failedOnlyIds.map(Number);
      }
      setInheritSubmitLoading(true);
      const res = await historyApi.inheritFailureReason(payload);
      message.success(res.message || `继承成功，共继承 ${res.inherited_count} 条`);
      setInheritModalVisible(false);
      inheritForm.resetFields();
      setSelectedRowKeys([]);
      const params = paramsFromUrl();
      await fetchData({
        ...params,
        page: params.page ?? 1,
        page_size: params.page_size ?? 20,
      });
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } }; message?: string };
      const msg = err?.response?.data?.detail || err?.message || "继承失败";
      if (typeof msg === "string") {
        message.error(msg);
      } else if (Array.isArray(msg)) {
        const parts = (msg as Array<{ msg?: string }>).map((m) => m.msg || "");
        message.error(parts.join("; "));
      } else {
        message.error("继承失败");
      }
    } finally {
      setInheritSubmitLoading(false);
    }
  };

  const handleInheritModalCancel = () => {
    setInheritModalVisible(false);
    inheritForm.resetFields();
  };

  /** 一键分析：取勾选记录中第一条 failed/error 作为锚点，整批未分析失败/异常标记 bug */
  const handleOneClickAnalyze = () => {
    if (!processBtnEnabled) return;
    let anchorId: number | undefined;
    for (const key of selectedRowKeys) {
      const row = data.find((r) => r.id === Number(key));
      if (
        row &&
        (row.case_result === "failed" || row.case_result === "error")
      ) {
        anchorId = row.id;
        break;
      }
    }
    if (anchorId === undefined) return;

    const anchorRow = data.find((r) => r.id === anchorId);
    const batchLabel = anchorRow?.start_time ?? "—";

    Modal.confirm({
      title: "一键分析",
      content: `将对批次「${batchLabel}」下所有未分析的失败/异常用例标记为失败类型 bug，跟踪人为各用例开发责任人。是否继续？`,
      okText: "确定",
      cancelText: "取消",
      onOk: async () => {
        setOneClickLoading(true);
        try {
          const res = await historyApi.oneClickAnalyze({ anchor_history_id: anchorId! });
          message.success(res.message || `一键分析完成，成功 ${res.applied_count} 条`);
          setSelectedRowKeys([]);
          const params = paramsFromUrl();
          await fetchData({
            ...params,
            page: params.page ?? 1,
            page_size: params.page_size ?? 20,
          });
        } catch (e: unknown) {
          const err = e as { response?: { data?: { detail?: string } }; message?: string };
          const msg = err?.response?.data?.detail || err?.message || "一键分析失败";
          if (typeof msg === "string") {
            message.error(msg);
          } else if (Array.isArray(msg)) {
            const parts = (msg as Array<{ msg?: string }>).map((m) => m.msg || "");
            message.error(parts.join("; "));
          } else {
            message.error("一键分析失败");
          }
        } finally {
          setOneClickLoading(false);
        }
      },
    });
  };

  /** 一键通知：锚点定批次，向该批所有 bug 失败跟踪人发 WeLink（spec/13） */
  const handleOneClickBugNotify = () => {
    if (!notifyBtnEnabled) return;
    let anchorId: number | undefined;
    for (const key of selectedRowKeys) {
      const row = data.find((r) => r.id === Number(key));
      if (
        row &&
        (row.case_result === "failed" || row.case_result === "error")
      ) {
        anchorId = row.id;
        break;
      }
    }
    if (anchorId === undefined) return;

    const batchLabel = currentBatch ?? "—";
    const selectedIds = selectedRowKeys.map((k) => Number(k));

    Modal.confirm({
      title: "一键通知",
      content: `将向批次「${batchLabel}」内所有「失败类型为 bug」的用例跟踪人发送 WeLink 通知（不仅限于当前勾选行）。是否继续？`,
      okText: "确定",
      cancelText: "取消",
      onOk: async () => {
        setBugNotifyLoading(true);
        try {
          const res = await historyApi.oneClickBugNotify({
            anchor_history_id: anchorId!,
            selected_history_ids: selectedIds,
          });
          message.success(res.message || `已通知 ${res.notified_count} 人`);
          if (
            (res.skipped_no_domain_count ?? 0) > 0 ||
            (res.skipped_parse_owner_count ?? 0) > 0 ||
            (res.failed_delivery_count ?? 0) > 0
          ) {
            const parts: string[] = [];
            if (res.skipped_parse_owner_count)
              parts.push(`工号解析失败 ${res.skipped_parse_owner_count} 组`);
            if (res.skipped_no_domain_count)
              parts.push(
                `未配置域账号 ${res.skipped_no_domain_count} 组，请在 ums_email 维护 domain_account`
              );
            if (res.failed_delivery_count)
              parts.push(`WeLink 发送失败 ${res.failed_delivery_count} 组`);
            message.warning(parts.join("；"));
          }
          setSelectedRowKeys([]);
          const params = paramsFromUrl();
          await fetchData({
            ...params,
            page: params.page ?? 1,
            page_size: params.page_size ?? 20,
          });
        } catch (e: unknown) {
          const err = e as { response?: { data?: { detail?: string } }; message?: string };
          const msg = err?.response?.data?.detail || err?.message || "一键通知失败";
          if (typeof msg === "string") {
            message.error(msg);
          } else if (Array.isArray(msg)) {
            const parts = (msg as Array<{ msg?: string }>).map((m) => m.msg || "");
            message.error(parts.join("; "));
          } else {
            message.error("一键通知失败");
          }
        } finally {
          setBugNotifyLoading(false);
        }
      },
    });
  };

  /** 一键生成通报：按勾选行所属批次拉取汇总并展示可复制文案 */
  const handleOpenReport = async () => {
    if (!reportBtnEnabled || !currentBatch) return;
    setReportModalVisible(true);
    setReportText("");
    setReportLoading(true);
    try {
      const data = await historyApi.batchReport(currentBatch);
      setReportText(buildRollingReportMarkdown(data));
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } }; message?: string };
      message.error(err?.response?.data?.detail || err?.message || "生成通报失败");
      setReportModalVisible(false);
    } finally {
      setReportLoading(false);
    }
  };

  const handleReportModalClose = () => {
    setReportModalVisible(false);
    setReportText("");
  };

  /** 非 HTTPS 或浏览器限制时 clipboard API 常失败，回退到 execCommand */
  const handleCopyReport = async () => {
    if (!reportText) return;
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(reportText);
        message.success("已复制到剪贴板");
        return;
      }
    } catch {
      /* 走下方回退 */
    }
    const ta = document.createElement("textarea");
    ta.value = reportText;
    ta.setAttribute("readonly", "");
    ta.style.position = "fixed";
    ta.style.top = "0";
    ta.style.left = "0";
    ta.style.width = "1px";
    ta.style.height = "1px";
    ta.style.opacity = "0";
    ta.style.pointerEvents = "none";
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    ta.setSelectionRange(0, reportText.length);
    let ok = false;
    try {
      ok = document.execCommand("copy");
    } finally {
      document.body.removeChild(ta);
    }
    if (ok) {
      message.success("已复制到剪贴板");
    } else {
      message.error("复制失败，请手动选择文本复制");
    }
  };

  const fetchInheritSourceOptions = async (caseName?: string, platform?: string) => {
    setInheritSourceOptionsLoading(true);
    try {
      const res = await historyApi.inheritSourceOptions(caseName, platform);
      setInheritSourceOptions(res);
    } catch {
      setInheritSourceOptions({ case_names: [], platforms: [], batches: [] });
    } finally {
      setInheritSourceOptionsLoading(false);
    }
  };

  const fetchInheritSourceRecords = async () => {
    const caseName = inheritForm.getFieldValue("source_case_name");
    if (!caseName || !String(caseName).trim()) {
      message.warning("请先选择源用例名");
      return;
    }
    setInheritSourceRecordsLoading(true);
    setInheritSourceRecords([]);
    inheritForm.setFieldValue("source_pfr_id", undefined);
    try {
      const res = await historyApi.inheritSourceRecords(
        String(caseName).trim(),
        inheritForm.getFieldValue("source_platform") || undefined,
        inheritForm.getFieldValue("source_batch") || undefined
      );
      setInheritSourceRecords(res.records ?? []);
      if (!(res.records?.length)) {
        message.info(
          "未找到匹配的源记录。可尝试只填「源用例名」查询，或确认平台、批次是否与历史分析记录一致。"
        );
      }
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } }; message?: string };
      message.error(err?.response?.data?.detail || err?.message || "查询失败");
    } finally {
      setInheritSourceRecordsLoading(false);
    }
  };

  const isBugType = (failedReasonType: string) =>
    failedReasonType?.trim().toLowerCase() === "bug";  // 仅 bug 时显示模块字段

  const handleRowClick = (record: HistoryItem) => {
    setDrawerRecord(record);
    setDrawerVisible(true);
    setReasonExpanded(false);
  };

  const handleResize =
    (key: string) =>
    (_: React.SyntheticEvent, data: { size: { width: number; height: number } }) => {
      setColWidths((prev) => ({ ...prev, [key]: data.size.width }));
    };

  const ellipsisCell = (val: string | null | undefined) =>
    val ? (
      <EllipsisTooltip title={val} placement="topLeft">
        {val}
      </EllipsisTooltip>
    ) : (
      "—"
    );

  const sortField = searchParams.get("sort_field") || undefined;
  const sortOrder =
    searchParams.get("sort_order") === "asc"
      ? "ascend"
      : searchParams.get("sort_order") === "desc"
        ? "descend"
        : undefined;
  const sortOrderFor = (field: string) => (field === sortField ? sortOrder : undefined);

  const columns: ColumnsType<HistoryItem> = [
    {
      title: "批次",
      dataIndex: "start_time",
      width: colWidths.start_time,
      sorter: true,
      sortOrder: sortOrderFor("start_time"),
      ellipsis: { showTitle: false },
      render: (val: string | null) => ellipsisCell(val),
      onHeaderCell: (col) => ({
        width: colWidths.start_time,
        onResize: handleResize("start_time"),
      }),
    },
    {
      title: "分组",
      dataIndex: "subtask",
      width: colWidths.subtask,
      sorter: true,
      sortOrder: sortOrderFor("subtask"),
      ellipsis: { showTitle: false },
      render: (val: string | null) => ellipsisCell(val),
      onHeaderCell: (col) => ({
        width: colWidths.subtask,
        onResize: handleResize("subtask"),
      }),
    },
    {
      title: "用例名",
      dataIndex: "case_name",
      width: colWidths.case_name,
      sorter: true,
      sortOrder: sortOrderFor("case_name"),
      ellipsis: { showTitle: false },
      render: (val: string | null, record: HistoryItem) => {
        if (!val) return "—";
        if (drilldown) {
          return ellipsisCell(val);
        }
        return (
          <EllipsisTooltip title={val} placement="topLeft">
            <a
              href={caseExecutionsDrilldownHref({ ...record, case_name: val })}
              target="_blank"
              rel="noopener noreferrer"
              title="在新标签页中查看该用例的全历史执行记录"
              onClick={(e) => e.stopPropagation()}
            >
              {val}
            </a>
          </EllipsisTooltip>
        );
      },
      onHeaderCell: (col) => ({
        width: colWidths.case_name,
        onResize: handleResize("case_name"),
      }),
    },
    {
      title: "主模块",
      dataIndex: "main_module",
      width: colWidths.main_module,
      sorter: true,
      sortOrder: sortOrderFor("main_module"),
      ellipsis: { showTitle: false },
      render: (val: string | null) => ellipsisCell(val),
      onHeaderCell: (col) => ({
        width: colWidths.main_module,
        onResize: handleResize("main_module"),
      }),
    },
    {
      title: "执行结果",
      dataIndex: "case_result",
      width: colWidths.case_result,
      sorter: true,
      sortOrder: sortOrderFor("case_result"),
      ellipsis: { showTitle: false },
      render: (val: string | null) => {
        if (!val) return "—";
        const color =
          val === "passed"
            ? "green"
            : val === "failed"
              ? "red"
              : val === "error"
                ? "orange"
                : val === "skip"
                  ? "geekblue"
                  : "default";
        return (
          <EllipsisTooltip title={val} placement="topLeft">
            <Tag color={color}>{val}</Tag>
          </EllipsisTooltip>
        );
      },
      onHeaderCell: (col) => ({
        width: colWidths.case_result,
        onResize: handleResize("case_result"),
      }),
    },
    {
      title: "跟踪人",
      dataIndex: "failure_owner",
      width: colWidths.failure_owner,
      ellipsis: { showTitle: false },
      render: (val: string | null) => ellipsisCell(val),
      onHeaderCell: (col) => ({
        width: colWidths.failure_owner,
        onResize: handleResize("failure_owner"),
      }),
    },
    {
      title: "失败原因",
      dataIndex: "failed_type",
      width: colWidths.failed_type,
      ellipsis: { showTitle: false },
      render: (val: string | null) => ellipsisCell(val),
      onHeaderCell: (col) => ({
        width: colWidths.failed_type,
        onResize: handleResize("failed_type"),
      }),
    },
    {
      title: "用例级别",
      dataIndex: "case_level",
      width: colWidths.case_level,
      sorter: true,
      sortOrder: sortOrderFor("case_level"),
      ellipsis: { showTitle: false },
      render: (val: string | null) => ellipsisCell(val),
      onHeaderCell: (col) => ({
        width: colWidths.case_level,
        onResize: handleResize("case_level"),
      }),
    },
    {
      title: "已分析",
      dataIndex: "analyzed",
      width: colWidths.analyzed,
      sorter: true,
      sortOrder: sortOrderFor("analyzed"),
      ellipsis: { showTitle: false },
      render: (val: number | null) => {
        const text = val === 1 ? "已分析" : "未分析";
        return (
          <EllipsisTooltip title={text} placement="topLeft">
            <Tag color={val === 1 ? "blue" : "default"}>{text}</Tag>
          </EllipsisTooltip>
        );
      },
      onHeaderCell: (col) => ({
        width: colWidths.analyzed,
        onResize: handleResize("analyzed"),
      }),
    },
    {
      title: "平台",
      dataIndex: "platform",
      width: colWidths.platform,
      sorter: true,
      sortOrder: sortOrderFor("platform"),
      ellipsis: { showTitle: false },
      render: (val: string | null) => ellipsisCell(val),
      onHeaderCell: (col) => ({
        width: colWidths.platform,
        onResize: handleResize("platform"),
      }),
    },
    {
      title: "代码分支",
      dataIndex: "code_branch",
      width: colWidths.code_branch,
      sorter: true,
      sortOrder: sortOrderFor("code_branch"),
      ellipsis: { showTitle: false },
      render: (val: string | null) => ellipsisCell(val),
      onHeaderCell: (col) => ({
        width: colWidths.code_branch,
        onResize: handleResize("code_branch"),
      }),
    },
    {
      title: "截图",
      dataIndex: "screenshot_url",
      width: colWidths.screenshot_url,
      ellipsis: { showTitle: false },
      render: (url: string | null) => (
        <EllipsisTooltip title={url || "暂无"} placement="topLeft">
          <UrlLink url={url} label="查看" />
        </EllipsisTooltip>
      ),
      onHeaderCell: (col) => ({
        width: colWidths.screenshot_url,
        onResize: handleResize("screenshot_url"),
      }),
    },
    {
      title: "测试报告",
      dataIndex: "reports_url",
      width: colWidths.reports_url,
      ellipsis: { showTitle: false },
      render: (url: string | null) => (
        <EllipsisTooltip title={url || "暂无"} placement="topLeft">
          <UrlLink url={url} label="查看" />
        </EllipsisTooltip>
      ),
      onHeaderCell: (col) => ({
        width: colWidths.reports_url,
        onResize: handleResize("reports_url"),
      }),
    },
    {
      title: "查看详情",
      key: "action",
      width: colWidths.action,
      fixed: "right",
      render: (_: unknown, record: HistoryItem) => (
        <div style={{ display: "flex", justifyContent: "center", alignItems: "center" }}>
          <Tooltip title="查看详情">
            <a
              onClick={(e) => {
                e.stopPropagation();
                handleRowClick(record);
              }}
              style={{ fontSize: 16, color: "#1890ff" }}
            >
              <EyeOutlined />
            </a>
          </Tooltip>
        </div>
      ),
      onHeaderCell: (col) => ({
        width: colWidths.action,
        onResize: handleResize("action"),
      }),
    },
  ];

  const totalWidth = Object.values(colWidths).reduce((a, b) => a + b, 0);

  const drilldownCaseTitle = (() => {
    if (!drilldown) return "";
    const p = paramsFromUrl();
    const names = p.case_name?.filter((n) => n && String(n).trim()) ?? [];
    return names.length ? names.join("、") : "";
  })();

  return (
    <div style={{ padding: "0 16px 24px" }} className="history-table history-page-layout">
      {drilldown && (
        <div style={{ marginBottom: 16 }}>
          <Title level={4} style={{ margin: 0 }}>
            用例执行历史
          </Title>
          {drilldownCaseTitle ? (
            <Text type="secondary">用例名：{drilldownCaseTitle}</Text>
          ) : null}
          <Paragraph type="secondary" style={{ margin: "8px 0 0", fontSize: 12, marginBottom: 0 }}>
            未选批次时查询该用例在全时间范围内的记录（分页展示）。
          </Paragraph>
        </div>
      )}
      <Form form={form} style={{ marginBottom: 16 }} disabled={loading}>
        <Row gutter={16}>
          <Col span={4}>
            <Form.Item name="start_time" label="批次" style={{ marginBottom: 8 }}>
              <Select
                mode="multiple"
                allowClear
                placeholder={
                  drilldown
                    ? "未选批次则查询全时间范围"
                    : "不选则默认最近30批"
                }
                maxTagCount="responsive"
                loading={optionsLoading}
                showSearch
                autoClearSearchValue={false}
                filterOption={(input, option) =>
                  (option?.label ?? "").toString().toLowerCase().includes(input.toLowerCase())
                }
                options={options?.start_time?.map((v) => ({ label: v, value: v })) ?? []}
              />
            </Form.Item>
          </Col>
          <Col span={4}>
            <Form.Item name="subtask" label="分组" style={{ marginBottom: 8 }}>
              <Select
                mode="multiple"
                allowClear
                placeholder="全部"
                maxTagCount="responsive"
                loading={optionsLoading}
                showSearch
                autoClearSearchValue={false}
                filterOption={(input, option) =>
                  (option?.label ?? "").toString().toLowerCase().includes(input.toLowerCase())
                }
                options={options?.subtask?.map((v) => ({ label: v, value: v })) ?? []}
              />
            </Form.Item>
          </Col>
          <Col span={4}>
            <Form.Item name="case_name" label="用例名" style={{ marginBottom: 8 }}>
              <Select
                mode="multiple"
                allowClear
                placeholder="全部"
                maxTagCount="responsive"
                loading={optionsLoading}
                showSearch
                autoClearSearchValue={false}
                filterOption={(input, option) =>
                  (option?.label ?? "").toString().toLowerCase().includes(input.toLowerCase())
                }
                options={options?.case_name?.map((v) => ({ label: v, value: v })) ?? []}
              />
            </Form.Item>
          </Col>
          <Col span={4}>
            <Form.Item name="main_module" label="主模块" style={{ marginBottom: 8 }}>
              <Select
                mode="multiple"
                allowClear
                placeholder="全部"
                maxTagCount="responsive"
                loading={optionsLoading}
                showSearch
                autoClearSearchValue={false}
                filterOption={(input, option) =>
                  (option?.label ?? "").toString().toLowerCase().includes(input.toLowerCase())
                }
                options={options?.main_module?.map((v) => ({ label: v, value: v })) ?? []}
              />
            </Form.Item>
          </Col>
          <Col span={4}>
            <Form.Item name="case_result" label="执行结果" style={{ marginBottom: 8 }}>
              <Select
                mode="multiple"
                allowClear
                placeholder="全部"
                maxTagCount="responsive"
                showSearch
                autoClearSearchValue={false}
                filterOption={(input, option) =>
                  (option?.label ?? "").toString().toLowerCase().includes(input.toLowerCase())
                }
                options={options?.case_result?.map((v) => ({ label: v, value: v })) ?? [
                  { label: "passed", value: "passed" },
                  { label: "failed", value: "failed" },
                  { label: "error", value: "error" },
                  { label: "skip", value: "skip" },
                ]}
              />
            </Form.Item>
          </Col>
          <Col span={4}>
            <Form.Item name="case_level" label="用例级别" style={{ marginBottom: 8 }}>
              <Select
                mode="multiple"
                allowClear
                placeholder="全部"
                maxTagCount="responsive"
                loading={optionsLoading}
                showSearch
                autoClearSearchValue={false}
                filterOption={(input, option) =>
                  (option?.label ?? "").toString().toLowerCase().includes(input.toLowerCase())
                }
                options={options?.case_level?.map((v) => ({ label: v, value: v })) ?? []}
              />
            </Form.Item>
          </Col>
          <Col span={4}>
            <Form.Item name="analyzed" label="是否已分析" style={{ marginBottom: 8 }}>
              <Select
                mode="multiple"
                allowClear
                placeholder="全部"
                maxTagCount="responsive"
                showSearch
                autoClearSearchValue={false}
                filterOption={(input, option) =>
                  (option?.label ?? "").toString().toLowerCase().includes(input.toLowerCase())
                }
                options={[
                  { label: "已分析", value: 1 },
                  { label: "未分析", value: 0 },
                ]}
              />
            </Form.Item>
          </Col>
          <Col span={4}>
            <Form.Item name="platform" label="平台" style={{ marginBottom: 8 }}>
              <Select
                mode="multiple"
                allowClear
                placeholder="全部"
                maxTagCount="responsive"
                loading={optionsLoading}
                showSearch
                autoClearSearchValue={false}
                filterOption={(input, option) =>
                  (option?.label ?? "").toString().toLowerCase().includes(input.toLowerCase())
                }
                options={options?.platform?.map((v) => ({ label: v, value: v })) ?? []}
              />
            </Form.Item>
          </Col>
          <Col span={4}>
            <Form.Item name="code_branch" label="代码分支" style={{ marginBottom: 8 }}>
              <Select
                mode="multiple"
                allowClear
                placeholder="全部"
                maxTagCount="responsive"
                loading={optionsLoading}
                showSearch
                autoClearSearchValue={false}
                filterOption={(input, option) =>
                  (option?.label ?? "").toString().toLowerCase().includes(input.toLowerCase())
                }
                options={options?.code_branch?.map((v) => ({ label: v, value: v })) ?? []}
              />
            </Form.Item>
          </Col>
          <Col span={4}>
            <Form.Item name="failure_owner" label="跟踪人" style={{ marginBottom: 8 }}>
              <Select
                mode="multiple"
                allowClear
                placeholder="全部"
                maxTagCount="responsive"
                loading={optionsLoading}
                showSearch
                autoClearSearchValue={false}
                filterOption={(input, option) =>
                  (option?.label ?? "").toString().toLowerCase().includes(input.toLowerCase())
                }
                options={options?.failure_owner?.map((v) => ({ label: v, value: v })) ?? []}
              />
            </Form.Item>
          </Col>
          <Col span={4}>
            <Form.Item name="failed_type" label="失败原因" style={{ marginBottom: 8 }}>
              <Select
                mode="multiple"
                allowClear
                placeholder="全部"
                maxTagCount="responsive"
                loading={optionsLoading}
                showSearch
                autoClearSearchValue={false}
                filterOption={(input, option) =>
                  (option?.label ?? "").toString().toLowerCase().includes(input.toLowerCase())
                }
                options={options?.failed_type?.map((v) => ({ label: v, value: v })) ?? []}
              />
            </Form.Item>
          </Col>
        </Row>
        <Row gutter={16} style={{ marginTop: 8 }}>
          <Col>
            <Button type="primary" onClick={handleFilterChange} disabled={loading}>
              筛选确认
            </Button>
          </Col>
          <Col>
            <Button onClick={handleReset} disabled={loading}>
              筛选重置
            </Button>
          </Col>
          <Col>
            {/* 至少勾选一条失败记录时可用 */}
            <Button
              onClick={openProcessModal}
              disabled={!processBtnEnabled || loading}
            >
              分析处理
            </Button>
          </Col>
          <Col>
            <Button
              onClick={openInheritModal}
              disabled={!processBtnEnabled || loading}
            >
              继承失败原因
            </Button>
          </Col>
          <Col>
            <Button
              loading={oneClickLoading}
              onClick={handleOneClickAnalyze}
              disabled={!processBtnEnabled || loading || oneClickLoading || bugNotifyLoading}
            >
              一键分析
            </Button>
          </Col>
          <Col>
            <Button
              loading={bugNotifyLoading}
              onClick={handleOneClickBugNotify}
              disabled={!notifyBtnEnabled || loading || bugNotifyLoading || oneClickLoading}
            >
              一键通知
            </Button>
          </Col>
          <Col>
            <Button
              loading={reportLoading}
              onClick={handleOpenReport}
              disabled={!reportBtnEnabled || loading || reportLoading}
            >
              一键生成通报
            </Button>
          </Col>
        </Row>
      </Form>

      <div ref={tableAreaRef} className="history-page-table-area">
        <Table<HistoryItem>
          rowKey="id"
          columns={columns}
          dataSource={data}
          loading={loading}
          rowSelection={{
            selectedRowKeys,
            onChange: (keys) => setSelectedRowKeys(keys),
            getCheckboxProps: (record) => ({
              disabled: record.case_result !== "failed" && record.case_result !== "error",
            }),
          }}
          components={{
            header: {
              cell: ResizableTitle,
            },
          }}
          pagination={{
            current: pagination.current,
            pageSize: pagination.pageSize,
            total,
            showSizeChanger: true,
            showTotal: (t) => `共 ${t} 条`,
            disabled: loading,
          }}
          onChange={handleTableChange}
          onRow={() => ({})}
          scroll={{ x: totalWidth, y: tableScrollY }}
          size="small"
        />
      </div>

      <Modal
        title="失败记录标注"
        width={500}
        open={processModalVisible}
        onOk={handleProcessModalOk}
        onCancel={handleProcessModalCancel}
        confirmLoading={processSubmitLoading}
        okText="确定"
        cancelText="取消"
        destroyOnClose
      >
        {/* 字段顺序：失败类型 → 模块（仅 bug 时显示）→ 跟踪人 → 详细原因 */}
        <Form
          form={processForm}
          layout="vertical"
          style={{ marginTop: 16 }}
          onValuesChange={(changed, all) => {
            // 失败类型变化：更新跟踪人默认值；bug 时显示模块并取 ums_module_owner.owner
            if ("failed_type" in changed) {
              const ft = all.failed_type as string;
              if (!isBugType(ft)) {
                processForm.setFieldValue("module", undefined);
                const cft = failureProcessOptions?.case_failed_types?.find(
                  (t) => t.failed_reason_type === ft
                );
                processForm.setFieldValue("owner", cft?.owner ?? undefined);
              } else {
                const firstFailed = selectedRows.find(
                  (r) => r.case_result === "failed" || r.case_result === "error"
                );
                const rawModule = firstFailed?.main_module ?? undefined;
                const modItem = findModuleItemInsensitive(
                  failureProcessOptions?.modules,
                  rawModule,
                );
                processForm.setFieldValue("module", modItem?.module ?? rawModule);
                processForm.setFieldValue(
                  "owner",
                  formatBugOwnerDisplay(modItem?.owner, failureProcessOptions),
                );
              }
            }
            if ("module" in changed && isBugType(all.failed_type as string)) {
              const mod = all.module as string;
              const modItem = failureProcessOptions?.modules?.find((m) => m.module === mod);
              if (modItem?.owner) {
                processForm.setFieldValue(
                  "owner",
                  formatBugOwnerDisplay(modItem.owner, failureProcessOptions),
                );
              }
            }
          }}
        >
          <Form.Item
            name="failed_type"
            label="失败类型"
            rules={[{ required: true, message: "请选择失败类型" }]}
          >
            <Select
              placeholder="请选择失败类型"
              allowClear
              options={failureProcessOptions?.case_failed_types?.map((t) => ({
                label: t.failed_reason_type,
                value: t.failed_reason_type,
              })) ?? []}
            />
          </Form.Item>
          {/* 仅 failed_type=bug 时显示模块字段，且置于跟踪人之上 */}
          {processFailedType && isBugType(processFailedType) && (
            <Form.Item
              name="module"
              label="模块"
              rules={[{ required: true, message: "请选择模块" }]}
            >
              <Select
                placeholder="请选择模块"
                allowClear
                showSearch
                filterOption={(input, option) =>
                  (option?.label ?? "").toString().toLowerCase().includes(input.toLowerCase())
                }
                options={failureProcessOptions?.modules?.map((m) => ({
                  label: m.module,
                  value: m.module,
                })) ?? []}
              />
            </Form.Item>
          )}
          <Form.Item
            name="owner"
            label="跟踪人"
            rules={[
              { required: true, message: "请填写跟踪人" },
              { max: 100, message: "最多 100 字符" },
            ]}
          >
            {processFailedType && isBugType(processFailedType) ? (
              <Input
                placeholder="按模块自动带出「姓名 工号」，可修改"
                allowClear
                maxLength={100}
              />
            ) : (
              <Select
                placeholder="请选择跟踪人"
                allowClear
                showSearch
                filterOption={(input, option) =>
                  (option?.label ?? "").toString().toLowerCase().includes(input.toLowerCase())
                }
                options={failureProcessOptions?.owners?.map((o) => ({
                  label: o.name,
                  value: o.employee_id,
                })) ?? []}
              />
            )}
          </Form.Item>
          <Form.Item
            name="reason"
            label="详细原因"
            rules={[
              { required: true, message: "请输入详细原因" },
              { whitespace: true, message: "请输入详细原因" },
              { max: 2000, message: "最多 2000 字符" },
            ]}
          >
            <Input.TextArea rows={4} placeholder="请输入详细原因" maxLength={2000} showCount />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="轮次通报"
        width={640}
        open={reportModalVisible}
        onCancel={handleReportModalClose}
        footer={[
          <Button
            key="copy"
            type="primary"
            onClick={handleCopyReport}
            disabled={reportLoading || !reportText}
          >
            复制全文
          </Button>,
          <Button key="close" onClick={handleReportModalClose}>
            关闭
          </Button>,
        ]}
        destroyOnClose
      >
        <Spin spinning={reportLoading}>
          <Input.TextArea
            readOnly
            value={reportText}
            placeholder={reportLoading ? "正在生成通报文案…" : ""}
            rows={18}
            style={{ fontFamily: "monospace", fontSize: 13 }}
          />
        </Spin>
      </Modal>

      <Modal
        title="继承失败原因"
        width={520}
        open={inheritModalVisible}
        onOk={handleInheritModalOk}
        onCancel={handleInheritModalCancel}
        confirmLoading={inheritSubmitLoading}
        okText="确定"
        cancelText="取消"
        destroyOnClose
      >
        <Form
          form={inheritForm}
          layout="vertical"
          style={{ marginTop: 16 }}
          onValuesChange={async (changed, all) => {
            if ("inherit_mode" in changed) {
              inheritForm.setFieldValue("source_batch", undefined);
              inheritForm.setFieldValue("source_case_name", undefined);
              inheritForm.setFieldValue("source_platform", undefined);
              inheritForm.setFieldValue("source_pfr_id", undefined);
              setInheritSourceRecords([]);
              if (all.inherit_mode === "batch" && showBatchDimension) {
                setInheritBatchOptionsLoading(true);
                try {
                  const res = await historyApi.inheritBatchOptions(currentBatch);
                  setInheritBatchOptions(res.batches ?? []);
                } catch {
                  setInheritBatchOptions([]);
                } finally {
                  setInheritBatchOptionsLoading(false);
                }
              } else {
                fetchInheritSourceOptions();
              }
            }
            if ("source_case_name" in changed) {
              inheritForm.setFieldValue("source_platform", undefined);
              inheritForm.setFieldValue("source_batch", undefined);
              inheritForm.setFieldValue("source_pfr_id", undefined);
              setInheritSourceRecords([]);
              fetchInheritSourceOptions(all.source_case_name);
            }
            if ("source_platform" in changed) {
              inheritForm.setFieldValue("source_batch", undefined);
              inheritForm.setFieldValue("source_pfr_id", undefined);
              setInheritSourceRecords([]);
              fetchInheritSourceOptions(all.source_case_name, all.source_platform);
            }
            if ("source_batch" in changed && (inheritMode ?? "case") === "case") {
              inheritForm.setFieldValue("source_pfr_id", undefined);
              setInheritSourceRecords([]);
            }
          }}
        >
          {showBatchDimension ? (
            <Form.Item
              name="inherit_mode"
              label="继承维度"
              rules={[{ required: true, message: "请选择继承维度" }]}
            >
              <Radio.Group>
                <Radio value="batch">批次维度</Radio>
                <Radio value="case">用例维度</Radio>
              </Radio.Group>
            </Form.Item>
          ) : null}
          {((inheritMode ?? "batch") === "batch" && showBatchDimension) && (
            <Form.Item
              name="source_batch"
              label="源批次"
              rules={[{ required: true, message: "请选择源批次" }]}
            >
              <Select
                placeholder="请选择要继承的历史批次"
                allowClear
                showSearch
                loading={inheritBatchOptionsLoading}
                filterOption={(input, option) =>
                  (option?.label ?? "").toString().toLowerCase().includes(input.toLowerCase())
                }
                options={inheritBatchOptions.map((v) => ({ label: v, value: v }))}
              />
            </Form.Item>
          )}
          {((inheritMode ?? "case") === "case" || !showBatchDimension) && (
            <>
              <Form.Item
                name="source_case_name"
                label="源用例名"
                rules={[{ required: true, message: "请选择源用例名" }]}
              >
                <Select
                  placeholder="请选择要继承失败原因的用例"
                  allowClear
                  showSearch
                  loading={inheritSourceOptionsLoading}
                  filterOption={(input, option) =>
                    (option?.label ?? "").toString().toLowerCase().includes(input.toLowerCase())
                  }
                  options={[
                    ...new Set([
                      ...inheritSourceOptions.case_names,
                      ...selectedRows.map((r) => r.case_name).filter((v): v is string => !!v),
                    ]),
                  ]
                    .sort()
                    .map((v) => ({ label: v, value: v }))}
                />
              </Form.Item>
              <Form.Item name="source_platform" label="源平台">
                <Select
                  placeholder="可选，用于缩小范围"
                  allowClear
                  showSearch
                  loading={inheritSourceOptionsLoading}
                  filterOption={(input, option) =>
                    (option?.label ?? "").toString().toLowerCase().includes(input.toLowerCase())
                  }
                  options={inheritSourceOptions.platforms.map((v) => ({ label: v, value: v }))}
                />
              </Form.Item>
              <Form.Item name="source_batch" label="源批次">
                <Select
                  placeholder="可选，用于缩小范围"
                  allowClear
                  showSearch
                  loading={inheritSourceOptionsLoading}
                  filterOption={(input, option) =>
                    (option?.label ?? "").toString().toLowerCase().includes(input.toLowerCase())
                  }
                  options={inheritSourceOptions.batches.map((v) => ({ label: v, value: v }))}
                />
              </Form.Item>
              <Form.Item>
                <Button
                  type="primary"
                  onClick={fetchInheritSourceRecords}
                  loading={inheritSourceRecordsLoading}
                >
                  查询
                </Button>
              </Form.Item>
              {inheritSourceRecords.length > 0 && (
                <Form.Item
                  name="source_pfr_id"
                  label="选择源记录"
                  rules={[{ required: true, message: "请从查询结果中选择一条源记录" }]}
                >
                  <Radio.Group style={{ width: "100%" }}>
                    <div style={{ maxHeight: 200, overflow: "auto", border: "1px solid #d9d9d9", borderRadius: 4, padding: 8 }}>
                      {inheritSourceRecords.map((r) => (
                        <div key={r.id} style={{ marginBottom: 8 }}>
                          <Radio value={r.id}>
                            <span style={{ marginRight: 8 }}>{r.platform ?? "—"}</span>
                            <span style={{ marginRight: 8 }}>{r.failed_batch ?? "—"}</span>
                            <span style={{ marginRight: 8 }}>{r.failed_type ?? "—"}</span>
                            {r.reason ? (
                              <span style={{ color: "#666" }} title={r.reason}>
                                {r.reason.length > 30 ? `${r.reason.slice(0, 30)}…` : r.reason}
                              </span>
                            ) : null}
                          </Radio>
                        </div>
                      ))}
                    </div>
                  </Radio.Group>
                </Form.Item>
              )}
            </>
          )}
        </Form>
      </Modal>

      <Drawer
        title={<span style={{ fontSize: 18 }}>执行详情</span>}
        placement="right"
        width={480}
        onClose={() => setDrawerVisible(false)}
        open={drawerVisible}
      >
        {drawerRecord && (
          <>
            <div style={{ marginBottom: 16 }}>
              <Text strong style={{ fontSize: 16 }}>
                基本信息
              </Text>
            </div>
            <div style={{ marginBottom: 24 }}>
              <div style={{ marginBottom: 8 }}>
                <Text strong>用例名：</Text>
                {drawerRecord.case_name ?? "—"}
              </div>
              <div style={{ marginBottom: 8 }}>
                <Text strong>批次：</Text>
                {drawerRecord.start_time ?? "—"}
              </div>
              <div style={{ marginBottom: 8 }}>
                <Text strong>分组：</Text>
                {drawerRecord.subtask ?? "—"}
              </div>
              <div style={{ marginBottom: 8 }}>
                <Text strong>主模块：</Text>
                {drawerRecord.main_module || "—"}
              </div>
              <div style={{ marginBottom: 8 }}>
                <Text strong>模块：</Text>
                {drawerRecord.module ?? "—"}
              </div>
              <div style={{ marginBottom: 8 }}>
                <Text strong>用例级别：</Text>
                {drawerRecord.case_level || "—"}
              </div>
              <div style={{ marginBottom: 8 }}>
                <Text strong>用例开发责任人：</Text>
                {drawerRecord.owner ?? "—"}
              </div>
              <div style={{ marginBottom: 8 }}>
                <Text strong>平台：</Text>
                {drawerRecord.platform ?? "—"}
              </div>
              <div>
                <Text strong>代码分支：</Text>
                {drawerRecord.code_branch ?? "—"}
              </div>
            </div>

            {(drawerRecord.case_result === "failed" || drawerRecord.case_result === "error") && (
              <>
                <Divider style={{ margin: "16px 0" }} />
                <div style={{ marginBottom: 16 }}>
                  <Text strong style={{ fontSize: 16 }}>
                    失败归因
                  </Text>
                </div>
                <div style={{ marginBottom: 24 }}>
                  <div style={{ marginBottom: 8 }}>
                    <Text strong>跟踪人：</Text>
                    {drawerRecord.failure_owner ?? "—"}
                  </div>
              <div style={{ marginBottom: 8 }}>
                    <Text strong>失败原因：</Text>
                    {drawerRecord.failed_type ?? "—"}
                  </div>
              {/* 粗略按字符数判断是否“超过约 3 行”，控制是否展示展开/收起按钮 */}
              {(() => {
                const text = drawerRecord.reason ?? "";
                const canExpand = text.length > 100; // 约等于 3 行以上的长文案
                return (
              <div style={{ marginBottom: 8 }}>
                <Text strong>详细原因：</Text>
                {text ? (
                  <div
                    style={{
                      marginTop: 4,
                      padding: 8,
                      borderRadius: 4,
                      background: "#fafafa",
                      border: "1px solid #f0f0f0",
                      maxHeight: reasonExpanded ? 200 : 72, // 约 3 行高度
                      overflowY: "auto",
                      whiteSpace: "pre-wrap",
                      wordBreak: "break-word",
                    }}
                  >
                    {text}
                  </div>
                ) : (
                  "—"
                )}
                {text && canExpand && (
                  <div style={{ marginTop: 4, textAlign: "right" }}>
                    <a
                      onClick={(e) => {
                        e.stopPropagation();
                        setReasonExpanded((prev) => !prev);
                      }}
                    >
                      {reasonExpanded ? "收起" : "展开更多"}
                    </a>
                  </div>
                )}
              </div>
                );
              })()}
              <div style={{ marginBottom: 8 }}>
                    <Text strong>分析人：</Text>
                    {drawerRecord.failure_analyzer ?? "—"}
                  </div>
              <div>
                <Text strong>分析时间：</Text>
                {drawerRecord.analyzed_at
                  ? drawerRecord.analyzed_at.replace("T", " ")
                  : "—"}
              </div>
                </div>
              </>
            )}

            <Divider style={{ margin: "16px 0" }} />

            <div style={{ marginBottom: 16 }}>
              <Text strong style={{ fontSize: 16 }}>
                外部链接
              </Text>
            </div>
            <div>
              <div style={{ marginBottom: 8 }}>
                <Text strong>截图：</Text>
                <UrlLink url={drawerRecord.screenshot_url} label="打开链接" />
              </div>
              <div style={{ marginBottom: 8 }}>
                <Text strong>测试报告：</Text>
                <UrlLink url={drawerRecord.reports_url} label="打开链接" />
              </div>
              <div style={{ marginBottom: 8 }}>
                <Text strong>日志：</Text>
                <UrlLink url={drawerRecord.log_url} label="打开链接" />
              </div>
              <div>
                <Text strong>流水线：</Text>
                <UrlLink url={drawerRecord.pipeline_url} label="打开链接" />
              </div>
            </div>
          </>
        )}
      </Drawer>
    </div>
  );
}
