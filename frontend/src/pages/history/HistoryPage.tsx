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
  Row,
  Col,
  Select,
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
} from "../../services";

const { Text } = Typography;

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

export default function HistoryPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [data, setData] = useState<HistoryItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [options, setOptions] = useState<HistoryFilterOptions | null>(null);
  const [optionsLoading, setOptionsLoading] = useState(false);
  const [drawerVisible, setDrawerVisible] = useState(false);
  const [drawerRecord, setDrawerRecord] = useState<HistoryItem | null>(null);
  const [form] = Form.useForm();
  const [processForm] = Form.useForm();  // 标注弹窗表单
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20 });
  const [colWidths, setColWidths] = useState<Record<string, number>>(DEFAULT_WIDTHS);
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([]);  // 勾选的行 id
  const [processModalVisible, setProcessModalVisible] = useState(false);
  const [failureProcessOptions, setFailureProcessOptions] = useState<FailureProcessOptions | null>(null);
  const [processSubmitLoading, setProcessSubmitLoading] = useState(false);
  const processFailedType = Form.useWatch("failed_type", processForm);  // 监听失败类型，控制模块字段显隐

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
    fetchData({
      ...params,
      page: params.page ?? 1,
      page_size: params.page_size ?? 20,
    });
  }, [searchParams]);

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
    syncParamsToUrl({ page: 1, page_size: pagination.pageSize });
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
  const hasSelectedFailed = selectedRows.some((r) => r.case_result === "failed");
  const processBtnEnabled = selectedRowKeys.length > 0 && hasSelectedFailed;  // 至少勾选一条失败记录时可用

  const openProcessModal = async () => {
    if (!processBtnEnabled) return;
    setProcessModalVisible(true);
    try {
      const opts = await historyApi.failureProcessOptions();
      setFailureProcessOptions(opts);
      const firstSelected = selectedRows[0];
      const defaultModule = firstSelected?.main_module ?? undefined;  // 方案 B：取第一条的 main_module
      processForm.setFieldsValue({
        failed_type: undefined,
        owner: undefined,
        reason: undefined,
        module: defaultModule,
      });
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } }; message?: string };
      message.error(err?.response?.data?.detail || err?.message || "获取选项失败");
    }
  };

  const handleProcessModalOk = async () => {
    try {
      const values = await processForm.validateFields();
      const failedType = values.failed_type as string;
      const isBug = failedType?.trim().toLowerCase() === "bug";  // bug 匹配：忽略首尾空格、大小写
      const payload: FailureProcessRequest = {
        history_ids: selectedRowKeys.map(Number),
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

  const isBugType = (failedReasonType: string) =>
    failedReasonType?.trim().toLowerCase() === "bug";  // 仅 bug 时显示模块字段

  const handleRowClick = (record: HistoryItem) => {
    setDrawerRecord(record);
    setDrawerVisible(true);
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
      render: (val: string | null) => ellipsisCell(val),
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
        const color = val === "passed" ? "green" : val === "failed" ? "red" : "default";
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

  return (
    <div style={{ padding: "0 16px 24px" }} className="history-table">
      <Form form={form} style={{ marginBottom: 16 }} disabled={loading}>
        <Row gutter={16}>
          <Col span={4}>
            <Form.Item name="start_time" label="批次" style={{ marginBottom: 8 }}>
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
                options={[
                  { label: "passed", value: "passed" },
                  { label: "failed", value: "failed" },
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
        </Row>
      </Form>

      <Table<HistoryItem>
        rowKey="id"
        columns={columns}
        dataSource={data}
        loading={loading}
        rowSelection={{
          selectedRowKeys,
          onChange: (keys) => setSelectedRowKeys(keys),
          getCheckboxProps: (record) => ({
            disabled: record.case_result !== "failed",  // 方案 A：仅 failed 行可勾选
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
        scroll={{ x: totalWidth }}
        size="small"
      />

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
                const firstSelected = selectedRows[0];
                const defaultModule = firstSelected?.main_module ?? undefined;  // 方案 B
                processForm.setFieldValue("module", defaultModule);
                const modItem = defaultModule
                  ? failureProcessOptions?.modules?.find((m) => m.module === defaultModule)
                  : undefined;
                processForm.setFieldValue("owner", modItem?.owner ?? undefined);
              }
            }
            if ("module" in changed && isBugType(all.failed_type as string)) {
              // 模块变化时，跟踪人默认值改为 ums_module_owner.owner
              const mod = all.module as string;
              const modItem = failureProcessOptions?.modules?.find((m) => m.module === mod);
              if (modItem?.owner) {
                processForm.setFieldValue("owner", modItem.owner);
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
            rules={[{ required: true, message: "请选择跟踪人" }]}
          >
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

            {drawerRecord.case_result === "failed" && (
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
                  <div>
                    <Text strong>失败原因：</Text>
                    {drawerRecord.failed_type ?? "—"}
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
