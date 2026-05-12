import { useCallback, useEffect, useState } from "react";
import {
  Alert,
  Button,
  Card,
  DatePicker,
  Input,
  message,
  Select,
  Space,
  Spin,
  Table,
  Tag,
  Tooltip,
  Typography,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import dayjs from "dayjs";
import type { Dayjs } from "dayjs";
import { utGateApi, type UtGateRunItem, type UtGateRunListParams, type PageResponse } from "../../services";

const { RangePicker } = DatePicker;
const { Link, Text } = Typography;

function extractApiDetail(err: unknown): string {
  const ax = err as { response?: { data?: { detail?: unknown } } };
  const d = ax?.response?.data?.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) {
    const first = d[0] as { msg?: string } | undefined;
    if (first?.msg) return String(first.msg);
  }
  return "加载失败";
}

function formatDt(s: string | null | undefined): string {
  if (!s) return "—";
  const d = dayjs(s);
  return d.isValid() ? d.format("YYYY-MM-DD HH:mm:ss") : s;
}

export default function UtGateHistoryPage() {
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<PageResponse<UtGateRunItem>>({
    items: [],
    total: 0,
    page: 1,
    page_size: 20,
  });

  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [dateRange, setDateRange] = useState<[Dayjs, Dayjs] | null>(null);
  const [interceptFilter, setInterceptFilter] = useState<"all" | "yes" | "no">("all");
  const [mrUrlExact, setMrUrlExact] = useState("");
  const [mrUrlContains, setMrUrlContains] = useState("");
  const [jobNameContains, setJobNameContains] = useState("");

  const fetchList = useCallback(async (nextPage: number, nextPageSize: number) => {
    if (mrUrlExact.trim() && mrUrlContains.trim()) {
      message.warning("MR 精确与 MR 子串互斥，请只填其一");
      return;
    }
    setLoading(true);
    try {
      const params: UtGateRunListParams = {
        page: nextPage,
        page_size: nextPageSize,
        sort_field: "reported_at",
        sort_order: "desc",
      };
      if (dateRange?.[0]) params.start_time = dateRange[0].format("YYYY-MM-DD");
      if (dateRange?.[1]) params.end_time = dateRange[1].format("YYYY-MM-DD");
      if (interceptFilter === "yes") params.is_intercepted = true;
      if (interceptFilter === "no") params.is_intercepted = false;
      const m = mrUrlExact.trim();
      const mc = mrUrlContains.trim();
      if (m) params.mr_url = m;
      if (mc) params.mr_url_contains = mc;
      const j = jobNameContains.trim();
      if (j) params.job_name_contains = j;
      const res = await utGateApi.list(params);
      setData(res);
      setPage(res.page);
      setPageSize(res.page_size);
    } catch (e) {
      message.error(extractApiDetail(e));
    } finally {
      setLoading(false);
    }
  }, [dateRange, interceptFilter, mrUrlExact, mrUrlContains, jobNameContains]);

  useEffect(() => {
    void fetchList(1, pageSize);
    // 首次进入：默认排序与空筛选
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const onSearch = () => {
    void fetchList(1, pageSize);
  };

  const onReset = () => {
    setDateRange(null);
    setInterceptFilter("all");
    setMrUrlExact("");
    setMrUrlContains("");
    setJobNameContains("");
    setPageSize(20);
    void fetchList(1, 20);
  };

  const columns: ColumnsType<UtGateRunItem> = [
    {
      title: "ID",
      dataIndex: "id",
      key: "id",
      width: 120,
      ellipsis: true,
      render: (v: number) => <Tooltip title={String(v)}>{String(v)}</Tooltip>,
    },
    { title: "上报时间", dataIndex: "reported_at", key: "reported_at", width: 170, render: (v) => formatDt(v) },
    { title: "创建时间", dataIndex: "created_at", key: "created_at", width: 170, render: (v) => formatDt(v) },
    { title: "Job", dataIndex: "job_name", key: "job_name", ellipsis: true },
    { title: "构建号", dataIndex: "build_number", key: "build_number", width: 90 },
    {
      title: (
        <span>
          是否拦截
          <Tooltip title="未拦截（否）含多种情况：未检出失败、无 Summary、前置失败等，与「健康通过」不等价">
            <Text type="secondary" style={{ marginLeft: 4, cursor: "help" }}>
              (?)
            </Text>
          </Tooltip>
        </span>
      ),
      dataIndex: "is_intercepted",
      key: "is_intercepted",
      width: 110,
      render: (v: boolean) =>
        v ? <Tag color="red">已拦截</Tag> : <Tag>未拦截</Tag>,
    },
    {
      title: "MR 链接",
      dataIndex: "mr_url",
      key: "mr_url",
      ellipsis: true,
      render: (url: string | null) =>
        url ? (
          <Link href={url} target="_blank" rel="noopener noreferrer">
            打开
          </Link>
        ) : (
          "—"
        ),
    },
    {
      title: "构建链接",
      dataIndex: "build_url",
      key: "build_url",
      width: 90,
      render: (url: string | null) =>
        url ? (
          <Link href={url} target="_blank" rel="noopener noreferrer">
            Jenkins
          </Link>
        ) : (
          "—"
        ),
    },
    {
      title: "退出码",
      dataIndex: "ut_exit_code",
      key: "ut_exit_code",
      width: 80,
      render: (v: number | null) => (v === null || v === undefined ? "—" : String(v)),
    },
    {
      title: "幂等键",
      dataIndex: "idempotency_key",
      key: "idempotency_key",
      ellipsis: true,
      render: (t: string) => (
        <Tooltip title={t}>
          <span>{t}</span>
        </Tooltip>
      ),
    },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16, height: "100%", minHeight: 0 }}>
      <div>
        <Typography.Title level={4} style={{ margin: 0 }}>
          UT 门禁历史
        </Typography.Title>
        <Typography.Paragraph type="secondary" style={{ marginBottom: 8 }}>
          数据来自 Jenkins 上报；列表接口为 GET /api/v1/ut-gate-runs。
        </Typography.Paragraph>
        <Alert
          type="info"
          showIcon
          message="时间筛选对应上报时间 reported_at，与「详细执行历史」中的批次时间（start_time）不是同一概念。"
          style={{ marginBottom: 12 }}
        />
        <Card size="small" styles={{ body: { paddingBottom: 8 } }}>
          <Space wrap align="start">
            <div>
              <div style={{ marginBottom: 4, fontSize: 12, color: "#666" }}>上报时间</div>
              <RangePicker value={dateRange} onChange={(v) => setDateRange(v)} />
            </div>
            <div>
              <div style={{ marginBottom: 4, fontSize: 12, color: "#666" }}>是否拦截</div>
              <Select
                style={{ width: 120 }}
                value={interceptFilter}
                onChange={(v) => setInterceptFilter(v)}
                options={[
                  { value: "all", label: "全部" },
                  { value: "yes", label: "已拦截" },
                  { value: "no", label: "未拦截" },
                ]}
              />
            </div>
            <div>
              <div style={{ marginBottom: 4, fontSize: 12, color: "#666" }}>MR 精确</div>
              <Input
                style={{ width: 260 }}
                placeholder="完整 MR URL"
                value={mrUrlExact}
                onChange={(e) => setMrUrlExact(e.target.value)}
                allowClear
              />
            </div>
            <div>
              <div style={{ marginBottom: 4, fontSize: 12, color: "#666" }}>MR 子串</div>
              <Input
                style={{ width: 200 }}
                placeholder="与 MR 精确二选一"
                value={mrUrlContains}
                onChange={(e) => setMrUrlContains(e.target.value)}
                allowClear
              />
            </div>
            <div>
              <div style={{ marginBottom: 4, fontSize: 12, color: "#666" }}>Job 子串</div>
              <Input
                style={{ width: 200 }}
                placeholder="job_name 包含"
                value={jobNameContains}
                onChange={(e) => setJobNameContains(e.target.value)}
                allowClear
              />
            </div>
            <div style={{ alignSelf: "flex-end" }}>
              <Space>
                <Button type="primary" onClick={onSearch}>
                  查询
                </Button>
                <Button onClick={onReset}>重置</Button>
              </Space>
            </div>
          </Space>
        </Card>
      </div>
      <Spin spinning={loading} style={{ flex: 1, minHeight: 0 }}>
        <Table<UtGateRunItem>
          rowKey="id"
          columns={columns}
          dataSource={data.items}
          scroll={{ x: "max-content" }}
          pagination={{
            current: page,
            pageSize,
            total: data.total,
            showSizeChanger: true,
            pageSizeOptions: ["10", "20", "50", "100"],
            showTotal: (t) => `共 ${t} 条`,
            onChange: (p, ps) => {
              setPage(p);
              setPageSize(ps);
              void fetchList(p, ps);
            },
          }}
          locale={{ emptyText: "暂无数据" }}
        />
      </Spin>
    </div>
  );
}
