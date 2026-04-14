import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Resizable } from "react-resizable";
import "react-resizable/css/styles.css";
import "../history/history-table.css";
import {
  Alert,
  Button,
  Col,
  Form,
  Modal,
  Radio,
  Row,
  Select,
  Table,
  Tag,
  Typography,
  message,
} from "antd";
import type { ColumnsType, TablePaginationConfig } from "antd/es/table";
import {
  overviewApi,
  type OverviewItem,
  type OverviewFilterOptions,
  type OverviewQueryParams,
} from "../../services";

const { Text } = Typography;

export type OverviewPageVariant = "default" | "subtask-all-batches";

function openInNewTab(href: string) {
  const a = document.createElement("a");
  a.href = href;
  a.target = "_blank";
  a.rel = "noopener noreferrer";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
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
      url.startsWith("http://") || url.startsWith("https://") ? url : `https://${url}`;
    return (
      <a href={href} target="_blank" rel="noopener noreferrer" onClick={(e) => e.stopPropagation()}>
        {label}
      </a>
    );
  }
  return <Text type="secondary">暂无</Text>;
}

function fmtDt(s: string | null | undefined): string {
  if (!s) return "—";
  return String(s).replace("T", " ").slice(0, 19);
}

function historyBatchHref(batch: string | null | undefined): string {
  const q = new URLSearchParams();
  if (batch) q.append("start_time", batch);
  return `/history?${q.toString()}`;
}

function ResizableTitle(
  props: React.HTMLAttributes<HTMLTableHeaderCellElement> & {
    onResize?: (e: React.SyntheticEvent, data: { size: { width: number; height: number } }) => void;
    width?: number;
  },
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

const DEFAULT_WIDTHS: Record<string, number> = {
  batch: 120,
  subtask: 120,
  result: 100,
  case_num: 90,
  passed_num: 80,
  failed_num: 80,
  batch_start: 160,
  batch_end: 160,
  platform: 100,
  code_branch: 110,
  reports_url: 88,
  log_url: 72,
  pipeline_url: 88,
  created_at: 160,
};

const SORTABLE: Record<string, boolean> = {
  batch: true,
  subtask: true,
  result: true,
  case_num: true,
  batch_start: true,
  batch_end: true,
  passed_num: true,
  failed_num: true,
  platform: true,
  code_branch: true,
  created_at: true,
};

/** 与 History 一致：表头 + 底部分页（含每页条数）预留高度，用于计算 Table `scroll.y` */
const OVERVIEW_TABLE_SCROLL_RESERVE_PX = 118;

export default function OverviewPage({
  variant = "default",
}: {
  variant?: OverviewPageVariant;
}) {
  const [searchParams, setSearchParams] = useSearchParams();
  const [form] = Form.useForm();
  const [data, setData] = useState<OverviewItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [options, setOptions] = useState<OverviewFilterOptions | null>(null);
  const [optionsLoading, setOptionsLoading] = useState(false);
  const [colWidths, setColWidths] = useState<Record<string, number>>(DEFAULT_WIDTHS);
  const [subtaskModalRow, setSubtaskModalRow] = useState<OverviewItem | null>(null);
  const [subtaskChoice, setSubtaskChoice] = useState<"all-batches" | "same-batch">(
    "all-batches",
  );
  const subtaskInvalidWarnedRef = useRef(false);
  /** 表格区域高度（与 history-table.css 中 flex 布局配合，必须设置 scroll.y 否则表体无限增高、分页被 overflow:hidden 裁掉） */
  const tableAreaRef = useRef<HTMLDivElement>(null);
  const [tableScrollY, setTableScrollY] = useState(300);

  const lockedSubtask = variant === "subtask-all-batches" ? searchParams.get("subtask") : null;
  const lockedSubtaskTrimmed = lockedSubtask?.trim() || null;

  const paramsFromUrl = useCallback((): OverviewQueryParams => {
    const getList = (key: string) => {
      const vals = searchParams.getAll(key);
      return vals.length > 0 ? vals : undefined;
    };
    const base: OverviewQueryParams = {
      page: searchParams.get("page") ? parseInt(searchParams.get("page")!, 10) : 1,
      page_size: searchParams.get("page_size")
        ? parseInt(searchParams.get("page_size")!, 10)
        : 20,
      batch: getList("batch"),
      subtask: getList("subtask"),
      platform: getList("platform"),
      code_branch: getList("code_branch"),
      result: getList("result"),
      sort_field: searchParams.get("sort_field") || undefined,
      sort_order: searchParams.get("sort_order") || undefined,
    };
    if (variant === "subtask-all-batches" && lockedSubtaskTrimmed) {
      return {
        ...base,
        subtask: [lockedSubtaskTrimmed],
        all_batches: true,
      };
    }
    return base;
  }, [searchParams, variant, lockedSubtaskTrimmed]);

  const syncParamsToUrl = useCallback(
    (params: OverviewQueryParams) => {
      const next = new URLSearchParams();
      if (params.page && params.page > 1) next.set("page", String(params.page));
      if (params.page_size && params.page_size !== 20)
        next.set("page_size", String(params.page_size));
      const appendList = (key: string, vals?: string[]) => {
        if (vals?.length) vals.forEach((v) => next.append(key, v));
      };
      if (variant === "subtask-all-batches" && lockedSubtaskTrimmed) {
        next.set("subtask", lockedSubtaskTrimmed);
      } else {
        appendList("subtask", params.subtask);
      }
      appendList("batch", params.batch);
      appendList("platform", params.platform);
      appendList("code_branch", params.code_branch);
      appendList("result", params.result);
      if (params.sort_field) next.set("sort_field", params.sort_field);
      if (params.sort_order) next.set("sort_order", params.sort_order);
      setSearchParams(next, { replace: true });
    },
    [setSearchParams, variant, lockedSubtaskTrimmed],
  );

  const fetchData = async (params: OverviewQueryParams) => {
    setLoading(true);
    try {
      const res = await overviewApi.list(params);
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
        message.error(typeof detail === "string" && detail ? detail : "加载失败");
      }
    } finally {
      setLoading(false);
    }
  };

  const fetchOptions = async () => {
    setOptionsLoading(true);
    try {
      const opts = await overviewApi.options();
      setOptions(opts);
    } finally {
      setOptionsLoading(false);
    }
  };

  useEffect(() => {
    fetchOptions();
  }, []);

  useEffect(() => {
    const el = tableAreaRef.current;
    if (!el) return;
    const update = () => {
      const h = el.getBoundingClientRect().height;
      setTableScrollY(Math.max(120, Math.floor(h - OVERVIEW_TABLE_SCROLL_RESERVE_PX)));
    };
    update();
    const ro = new ResizeObserver(() => update());
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    if (variant !== "subtask-all-batches") {
      subtaskInvalidWarnedRef.current = false;
      return;
    }
    if (lockedSubtaskTrimmed) {
      subtaskInvalidWarnedRef.current = false;
    } else if (!subtaskInvalidWarnedRef.current) {
      subtaskInvalidWarnedRef.current = true;
      message.error("链接无效：缺少分组参数 subtask");
    }
  }, [variant, lockedSubtaskTrimmed]);

  useEffect(() => {
    const params = paramsFromUrl();
    if (variant === "subtask-all-batches" && !lockedSubtaskTrimmed) {
      form.setFieldsValue({
        batch: undefined,
        platform: undefined,
        code_branch: undefined,
        result: undefined,
      });
      setData([]);
      setTotal(0);
      return;
    }
    form.setFieldsValue({
      batch: params.batch,
      subtask: variant === "default" ? params.subtask : undefined,
      platform: params.platform,
      code_branch: params.code_branch,
      result: params.result,
    });
  }, [searchParams, variant, lockedSubtaskTrimmed, form, paramsFromUrl]);

  useEffect(() => {
    const params = paramsFromUrl();
    if (variant === "subtask-all-batches" && !lockedSubtaskTrimmed) {
      return;
    }
    fetchData({
      ...params,
      page: params.page ?? 1,
      page_size: params.page_size ?? 20,
    });
  }, [searchParams, variant, lockedSubtaskTrimmed, paramsFromUrl]);

  const handleFilterChange = () => {
    const values = form.getFieldsValue();
    const cur = paramsFromUrl();
    const params: OverviewQueryParams = {
      page: 1,
      page_size: cur.page_size ?? 20,
      batch: values.batch?.length ? values.batch : undefined,
      subtask:
        variant === "default" && values.subtask?.length ? values.subtask : undefined,
      platform: values.platform?.length ? values.platform : undefined,
      code_branch: values.code_branch?.length ? values.code_branch : undefined,
      result: values.result?.length ? values.result : undefined,
      sort_field: cur.sort_field,
      sort_order: cur.sort_order,
    };
    if (variant === "subtask-all-batches" && lockedSubtaskTrimmed) {
      params.subtask = [lockedSubtaskTrimmed];
      params.all_batches = true;
    }
    syncParamsToUrl(params);
  };

  const handleReset = () => {
    const cur = paramsFromUrl();
    if (variant === "subtask-all-batches" && lockedSubtaskTrimmed) {
      syncParamsToUrl({
        page: 1,
        page_size: cur.page_size ?? 20,
        subtask: [lockedSubtaskTrimmed],
        all_batches: true,
      });
    } else {
      syncParamsToUrl({ page: 1, page_size: cur.page_size ?? 20 });
    }
  };

  const handleTableChange = (
    pag: TablePaginationConfig,
    _filters: Record<string, unknown>,
    sorter: unknown,
  ) => {
    const nextPage = pag.current ?? 1;
    const nextSize = pag.pageSize ?? 20;
    const params = paramsFromUrl();
    const sort = Array.isArray(sorter)
      ? (sorter as { field?: string; order?: string }[])[0]
      : (sorter as { field?: string; order?: string });
    const sortField = (typeof sort?.field === "string" ? sort.field : undefined) || undefined;
    const sortOrder =
      sort?.order === "ascend" ? "asc" : sort?.order === "descend" ? "desc" : undefined;
    const sortChanged = sortField !== params.sort_field || sortOrder !== params.sort_order;
    const pageToUse = sortChanged ? 1 : nextPage;
    const nextParams: OverviewQueryParams = {
      ...params,
      page: pageToUse,
      page_size: nextSize,
      sort_field: sortField,
      sort_order: sortOrder,
    };
    if (variant === "subtask-all-batches" && lockedSubtaskTrimmed) {
      nextParams.subtask = [lockedSubtaskTrimmed];
      nextParams.all_batches = true;
    }
    syncParamsToUrl(nextParams);
  };

  const handleResize = useCallback(
    (key: string) =>
      (_: React.SyntheticEvent, data: { size: { width: number; height: number } }) => {
        setColWidths((prev) => ({ ...prev, [key]: data.size.width }));
      },
    [],
  );

  const urlQuery = paramsFromUrl();
  const pageCurrent = urlQuery.page ?? 1;
  const pageSize = urlQuery.page_size ?? 20;

  const sortField = searchParams.get("sort_field") || undefined;
  const sortOrderUrl =
    searchParams.get("sort_order") === "asc"
      ? "ascend"
      : searchParams.get("sort_order") === "desc"
        ? "descend"
        : undefined;
  const sortOrderFor = (field: string) => (field === sortField ? sortOrderUrl : undefined);

  const confirmSubtaskModal = () => {
    if (!subtaskModalRow) return;
    const st = subtaskModalRow.subtask ?? "";
    const bt = subtaskModalRow.batch ?? "";
    if (subtaskChoice === "all-batches") {
      const q = new URLSearchParams();
      q.set("subtask", st);
      openInNewTab(`${window.location.origin}/overview/subtask-executions?${q.toString()}`);
    } else {
      const q = new URLSearchParams();
      if (bt) q.append("start_time", bt);
      if (st) q.append("subtask", st);
      openInNewTab(`${window.location.origin}/history?${q.toString()}`);
    }
    setSubtaskModalRow(null);
  };

  const columns: ColumnsType<OverviewItem> = useMemo(
    () => [
      {
        title: "批次",
        dataIndex: "batch",
        width: colWidths.batch,
        ellipsis: true,
        sorter: SORTABLE.batch,
        sortOrder: sortOrderFor("batch"),
        render: (val: string | null) =>
          val ? (
            <a
              href={historyBatchHref(val)}
              target="_blank"
              rel="noopener noreferrer"
              onClick={(e) => e.stopPropagation()}
            >
              {val}
            </a>
          ) : (
            "—"
          ),
        onHeaderCell: () => ({
          width: colWidths.batch,
          onResize: handleResize("batch"),
        }),
      },
      {
        title: "分组",
        dataIndex: "subtask",
        width: colWidths.subtask,
        ellipsis: true,
        sorter: SORTABLE.subtask,
        sortOrder: sortOrderFor("subtask"),
        render: (val: string | null, record: OverviewItem) =>
          val ? (
            <Button
              type="link"
              size="small"
              style={{ padding: 0, height: "auto" }}
              onClick={(e) => {
                e.stopPropagation();
                setSubtaskChoice("all-batches");
                setSubtaskModalRow(record);
              }}
            >
              {val}
            </Button>
          ) : (
            "—"
          ),
        onHeaderCell: () => ({
          width: colWidths.subtask,
          onResize: handleResize("subtask"),
        }),
      },
      {
        title: "执行结果",
        dataIndex: "result",
        width: colWidths.result,
        sorter: SORTABLE.result,
        sortOrder: sortOrderFor("result"),
        render: (val: string | null) => {
          if (!val) return "—";
          const color = val === "passed" ? "green" : val === "failed" ? "red" : "default";
          return <Tag color={color}>{val}</Tag>;
        },
        onHeaderCell: () => ({
          width: colWidths.result,
          onResize: handleResize("result"),
        }),
      },
      {
        title: "总用例数",
        dataIndex: "case_num",
        width: colWidths.case_num,
        sorter: SORTABLE.case_num,
        sortOrder: sortOrderFor("case_num"),
        onHeaderCell: () => ({
          width: colWidths.case_num,
          onResize: handleResize("case_num"),
        }),
      },
      {
        title: "通过数",
        dataIndex: "passed_num",
        width: colWidths.passed_num,
        sorter: SORTABLE.passed_num,
        sortOrder: sortOrderFor("passed_num"),
        onHeaderCell: () => ({
          width: colWidths.passed_num,
          onResize: handleResize("passed_num"),
        }),
      },
      {
        title: "失败数",
        dataIndex: "failed_num",
        width: colWidths.failed_num,
        sorter: SORTABLE.failed_num,
        sortOrder: sortOrderFor("failed_num"),
        onHeaderCell: () => ({
          width: colWidths.failed_num,
          onResize: handleResize("failed_num"),
        }),
      },
      {
        title: "开始时间",
        dataIndex: "batch_start",
        width: colWidths.batch_start,
        sorter: SORTABLE.batch_start,
        sortOrder: sortOrderFor("batch_start"),
        render: (v) => fmtDt(v),
        onHeaderCell: () => ({
          width: colWidths.batch_start,
          onResize: handleResize("batch_start"),
        }),
      },
      {
        title: "结束时间",
        dataIndex: "batch_end",
        width: colWidths.batch_end,
        sorter: SORTABLE.batch_end,
        sortOrder: sortOrderFor("batch_end"),
        render: (v) => fmtDt(v),
        onHeaderCell: () => ({
          width: colWidths.batch_end,
          onResize: handleResize("batch_end"),
        }),
      },
      {
        title: "平台",
        dataIndex: "platform",
        width: colWidths.platform,
        ellipsis: true,
        sorter: SORTABLE.platform,
        sortOrder: sortOrderFor("platform"),
        onHeaderCell: () => ({
          width: colWidths.platform,
          onResize: handleResize("platform"),
        }),
      },
      {
        title: "代码分支",
        dataIndex: "code_branch",
        width: colWidths.code_branch,
        ellipsis: true,
        sorter: SORTABLE.code_branch,
        sortOrder: sortOrderFor("code_branch"),
        onHeaderCell: () => ({
          width: colWidths.code_branch,
          onResize: handleResize("code_branch"),
        }),
      },
      {
        title: "测试报告",
        dataIndex: "reports_url",
        width: colWidths.reports_url,
        render: (v: string | null) => <UrlLink url={v} label="打开" />,
        onHeaderCell: () => ({
          width: colWidths.reports_url,
          onResize: handleResize("reports_url"),
        }),
      },
      {
        title: "日志",
        dataIndex: "log_url",
        width: colWidths.log_url,
        render: (v: string | null) => <UrlLink url={v} label="打开" />,
        onHeaderCell: () => ({
          width: colWidths.log_url,
          onResize: handleResize("log_url"),
        }),
      },
      {
        title: "流水线",
        dataIndex: "pipeline_url",
        width: colWidths.pipeline_url,
        render: (v: string | null) => <UrlLink url={v} label="打开" />,
        onHeaderCell: () => ({
          width: colWidths.pipeline_url,
          onResize: handleResize("pipeline_url"),
        }),
      },
      {
        title: "创建时间",
        dataIndex: "created_at",
        width: colWidths.created_at,
        sorter: SORTABLE.created_at,
        sortOrder: sortOrderFor("created_at"),
        render: (v) => fmtDt(v),
        onHeaderCell: () => ({
          width: colWidths.created_at,
          onResize: handleResize("created_at"),
        }),
      },
    ],
    [colWidths, sortField, sortOrderUrl, handleResize],
  );

  const totalWidth = useMemo(
    () => Object.values(colWidths).reduce((a, b) => a + b, 0),
    [colWidths],
  );

  return (
    <div
      style={{ padding: "0 16px 24px" }}
      className="history-table history-page-layout"
    >
      {variant === "subtask-all-batches" && lockedSubtaskTrimmed && (
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 12 }}
          message={`分组「${lockedSubtaskTrimmed}」跨全部轮次（不限制最近 30 批）`}
        />
      )}
      <Form form={form} style={{ marginBottom: 16 }} disabled={loading}>
        <Row gutter={16}>
          <Col span={4}>
            <Form.Item name="batch" label="批次" style={{ marginBottom: 8 }}>
              <Select
                mode="multiple"
                allowClear
                placeholder="不选则默认最近30批"
                maxTagCount="responsive"
                loading={optionsLoading}
                showSearch
                autoClearSearchValue={false}
                filterOption={(input, option) =>
                  (option?.label ?? "").toString().toLowerCase().includes(input.toLowerCase())
                }
                options={options?.batch?.map((v) => ({ label: v, value: v })) ?? []}
              />
            </Form.Item>
          </Col>
          {variant === "default" && (
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
          )}
          <Col span={4}>
            <Form.Item name="result" label="执行结果" style={{ marginBottom: 8 }}>
              <Select
                mode="multiple"
                allowClear
                placeholder="全部"
                maxTagCount="responsive"
                options={
                  options?.result?.map((v) => ({ label: v, value: v })) ?? [
                    { label: "passed", value: "passed" },
                    { label: "failed", value: "failed" },
                  ]
                }
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
        </Row>
      </Form>

      <div ref={tableAreaRef} className="history-page-table-area">
        <Table<OverviewItem>
          rowKey="id"
          loading={loading}
          columns={columns}
          dataSource={data}
          size="small"
          components={{
            header: {
              cell: ResizableTitle,
            },
          }}
          pagination={{
            current: pageCurrent,
            pageSize,
            total,
            showSizeChanger: true,
            showTotal: (t) => `共 ${t} 条`,
            disabled: loading,
          }}
          onChange={handleTableChange}
          scroll={{ x: totalWidth, y: tableScrollY }}
        />
      </div>

      <Modal
        title="打开方式"
        open={!!subtaskModalRow}
        onOk={confirmSubtaskModal}
        onCancel={() => setSubtaskModalRow(null)}
        okText="打开"
        cancelText="取消"
        destroyOnClose
      >
        <p style={{ marginBottom: 12 }}>请选择如何查看分组「{subtaskModalRow?.subtask ?? ""}」：</p>
        <Radio.Group
          value={subtaskChoice}
          onChange={(e) => setSubtaskChoice(e.target.value)}
        >
          <Radio value="all-batches">跨全部轮次（分组执行历史，不限制最近 30 批）</Radio>
          <Radio value="same-batch">当前批次下的用例明细（详细执行历史）</Radio>
        </Radio.Group>
      </Modal>
    </div>
  );
}
