import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import ReactECharts from "echarts-for-react";
import { Card, Col, Row, Spin, Tag, Typography } from "antd";
import dayjs from "dayjs";
import {
  dashboardApi,
  type BatchTrendItem,
  type LatestBatchItem,
} from "../../services";

const pageBg = "#f4f8fc";
/** 与 `src/styles/global.css` body、侧边栏 DT-Report 一致的系统字体栈 */
const appFontFamily =
  '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif';
/**
 * 环形图：与侧栏 #2e3b7c、菜单高亮 #667eea 同系蓝紫，
 * 通过偏浅亮（接近高光），失败偏深靛（略向紫偏），色相一致、主要靠明度与饱和度区分。
 */
const donutPassColor = "#a8b9ee";
const donutFailColor = "#4a5a9a";

/**
 * Renders a styled status tag or placeholder for a batch result string.
 *
 * @param result - The batch result text to display; may be null or undefined.
 * @returns A React element: a colored Tag indicating "fail" (error color), "pass" (success color), or "processing" for other values, or a bold dash when the input is empty.
 */
function renderBatchResultTag(result: string | null | undefined) {
  const label = (result || "").trim();
  if (!label) {
    return (
      <Typography.Text strong style={{ fontSize: 16, color: "#102a43" }}>
        —
      </Typography.Text>
    );
  }
  const raw = label.toLowerCase();
  const fail = raw.includes("fail") || raw.includes("失败") || raw.includes("error");
  const ok = raw.includes("pass") || raw.includes("成功") || raw === "success";
  return (
    <Tag
      color={fail ? "error" : ok ? "success" : "processing"}
      style={{ margin: 0, fontSize: 15, padding: "4px 12px", lineHeight: 1.5 }}
    >
      {label}
    </Tag>
  );
}

/**
 * Build an ECharts option for visualizing batch trends as two smoothed line series.
 *
 * @param items - Array of batch trend entries; each element is used in order for x-axis categories and series data points.
 * @returns An ECharts option object that renders two line series labeled "失败用例数" (failed cases) and "总用例数" (total cases), with axis, tooltip, legend, grid, and area styling configured for trend visualization.
 */
function buildChartOption(items: BatchTrendItem[]) {
  return {
    tooltip: {
      trigger: "axis" as const,
      axisPointer: { type: "cross" as const, label: { backgroundColor: "#6a7985" } },
      formatter: (params: unknown) => {
        const arr = Array.isArray(params) ? params : [];
        if (arr.length === 0 || !arr[0]) return "";
        const idx = (arr[0] as { dataIndex?: number }).dataIndex ?? 0;
        const item = items[idx];
        if (!item) return "";
        const timeStr = item.batch_start
          ? dayjs(item.batch_start).format("YYYY-MM-DD HH:mm")
          : "—";
        return [
          `批次：${item.batch}`,
          `执行时间：${timeStr}`,
          `总用例数：${item.total_case_num}`,
          `通过数：${item.passed_num}`,
          `失败数：${item.failed_num}`,
          `通过率：${item.pass_rate.toFixed(2)}%`,
        ].join("<br/>");
      },
    },
    legend: {
      data: ["失败用例数", "总用例数"],
      top: 4,
      itemGap: 20,
    },
    grid: { left: "2%", right: "3%", bottom: "12%", top: "16%", containLabel: true },
    xAxis: {
      type: "category" as const,
      boundaryGap: false,
      data: items.map((i) => i.batch),
      axisLine: { lineStyle: { color: "#d9d9d9" } },
      axisLabel: {
        rotate: 38,
        fontSize: 11,
        color: "#595959",
        margin: 12,
        hideOverlap: true,
      },
    },
    yAxis: {
      type: "value" as const,
      minInterval: 1,
      splitLine: {
        show: true,
        lineStyle: { color: "#ebeef2", type: "dashed" as const },
      },
      axisLabel: { color: "#8c8c8c", fontSize: 11 },
    },
    series: [
      {
        name: "失败用例数",
        type: "line" as const,
        smooth: true,
        symbol: "circle",
        symbolSize: 7,
        data: items.map((i) => i.failed_num),
        itemStyle: { color: "#ff4d4f" },
        lineStyle: { width: 2 },
        areaStyle: { color: "rgba(255, 77, 79, 0.12)" },
        label: { show: true, position: "top" as const, fontSize: 11, color: "#595959" },
        emphasis: { focus: "series" as const },
      },
      {
        name: "总用例数",
        type: "line" as const,
        smooth: true,
        symbol: "circle",
        symbolSize: 7,
        data: items.map((i) => i.total_case_num),
        itemStyle: { color: "#1677ff" },
        lineStyle: { width: 2 },
        areaStyle: { color: "rgba(22, 119, 255, 0.14)" },
        label: { show: true, position: "top" as const, fontSize: 11, color: "#595959" },
        emphasis: { focus: "series" as const },
      },
    ],
  };
}

/**
 * Builds an ECharts option for a donut chart that visualizes pass vs. fail composition for a batch.
 *
 * @param passed - Number of passed cases in the batch.
 * @param failed - Number of failed cases in the batch.
 * @param totalCaseNum - Reported total case count to display at chart center; if not a number or negative, the displayed total falls back to `passed + failed`.
 * @returns An ECharts option object for a donut (pie) chart. If `passed + failed` is zero the option contains only centered total text and an empty-data title; otherwise it includes tooltip, legend, colored slices for "通过" and "失败", and a centered total graphic.
 */
function buildDonutOption(passed: number, failed: number, totalCaseNum: number) {
  const sum = passed + failed;
  const centerTotal =
    typeof totalCaseNum === "number" && totalCaseNum >= 0 ? totalCaseNum : sum;

  const centerGraphic = [
    {
      type: "text" as const,
      left: "center",
      top: "40%",
      style: {
        text: sum === 0 && centerTotal === 0 ? "—" : String(centerTotal),
        textAlign: "center" as const,
        textVerticalAlign: "middle" as const,
        fill: "#102a43",
        fontSize: 32,
        fontWeight: 700,
        fontFamily: appFontFamily,
      },
    },
    {
      type: "text" as const,
      left: "center",
      top: "50%",
      style: {
        text: "总用例数",
        textAlign: "center" as const,
        fill: "#8c8c8c",
        fontSize: 14,
        fontFamily: appFontFamily,
      },
    },
  ];

  if (sum === 0) {
    return {
      graphic: centerGraphic,
      title: {
        text: "暂无通过/失败构成数据",
        left: "center",
        top: "62%",
        textStyle: { color: "#bfbfbf", fontSize: 13, fontWeight: 400, fontFamily: appFontFamily },
      },
    };
  }

  return {
    tooltip: {
      trigger: "item" as const,
      formatter: "{b}<br/>数量：{c}<br/>占比：{d}%",
    },
    legend: {
      orient: "horizontal" as const,
      bottom: 4,
      itemGap: 16,
      textStyle: { color: "#595959", fontSize: 13, fontFamily: appFontFamily },
    },
    graphic: centerGraphic,
    color: [donutPassColor, donutFailColor],
    series: [
      {
        name: "本批次",
        type: "pie" as const,
        radius: ["46%", "74%"],
        center: ["50%", "46%"],
        avoidLabelOverlap: true,
        itemStyle: {
          borderRadius: 6,
          borderColor: "#fff",
          borderWidth: 2,
        },
        label: {
          show: true,
          formatter: "{b}\n{c} ({d}%)",
          fontSize: 13,
          color: "#434343",
          fontFamily: appFontFamily,
        },
        labelLine: {
          length: 14,
          length2: 10,
          lineStyle: { color: "#98a6c4", width: 1 },
        },
        data: [
          { value: passed, name: "通过", itemStyle: { color: donutPassColor } },
          { value: failed, name: "失败", itemStyle: { color: donutFailColor } },
        ],
      },
    ],
  };
}

/**
 * Render the dashboard page showing the latest batch donut and branch trend charts.
 *
 * Fetches latest batch data and recent batch trends for "master" and "bugfix", displays loading and empty states,
 * and navigates to the history view when a batch card or a chart point is clicked.
 *
 * @returns The React element for the dashboard page containing the latest-batch summary and branch trend charts.
 */
export default function DashboardPage() {
  const navigate = useNavigate();
  const [latestBatch, setLatestBatch] = useState<LatestBatchItem | null | undefined>(undefined);
  const [masterTrendItems, setMasterTrendItems] = useState<BatchTrendItem[]>([]);
  const [bugfixTrendItems, setBugfixTrendItems] = useState<BatchTrendItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [masterTrendLoading, setMasterTrendLoading] = useState(true);
  const [bugfixTrendLoading, setBugfixTrendLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    dashboardApi
      .latestBatch()
      .then((data) => {
        if (!cancelled) setLatestBatch(data);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    setMasterTrendLoading(true);
    dashboardApi
      .batchTrend(30, "master")
      .then((res) => {
        if (!cancelled) setMasterTrendItems(res.items || []);
      })
      .finally(() => {
        if (!cancelled) setMasterTrendLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    setBugfixTrendLoading(true);
    dashboardApi
      .batchTrend(30, "bugfix")
      .then((res) => {
        if (!cancelled) setBugfixTrendItems(res.items || []);
      })
      .finally(() => {
        if (!cancelled) setBugfixTrendLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const handleCardClick = (batch: string) => {
    navigate(`/history?start_time=${encodeURIComponent(batch)}`);
  };

  const createChartClickHandler = (items: BatchTrendItem[]) => (params: { dataIndex: number }) => {
    const item = items[params.dataIndex];
    if (item?.batch) {
      navigate(`/history?start_time=${encodeURIComponent(item.batch)}`);
    }
  };

  const hasLatestBatch = latestBatch && Object.keys(latestBatch).length > 0;

  const donutOption = useMemo(() => {
    if (!hasLatestBatch || !latestBatch) return null;
    const p = latestBatch.passed_num ?? 0;
    const f = latestBatch.failed_num ?? 0;
    const total = latestBatch.total_case_num ?? 0;
    return buildDonutOption(p, f, total);
  }, [hasLatestBatch, latestBatch]);

  const masterOption = useMemo(
    () => (masterTrendItems.length ? buildChartOption(masterTrendItems) : null),
    [masterTrendItems]
  );
  const bugfixOption = useMemo(
    () => (bugfixTrendItems.length ? buildChartOption(bugfixTrendItems) : null),
    [bugfixTrendItems]
  );

  const branchChartsLoading = masterTrendLoading || bugfixTrendLoading;

  return (
    <div
      style={{
        flex: 1,
        minHeight: 0,
        overflow: "auto",
        padding: "16px 24px 24px",
        background: pageBg,
      }}
    >
      <Typography.Title
        level={4}
        style={{
          marginTop: 0,
          marginBottom: 20,
          color: "#102a43",
          fontFamily: appFontFamily,
          fontWeight: 800,
          fontSize: 28,
          lineHeight: 1.25,
        }}
      >
        首页大盘
      </Typography.Title>

      <Card
        title="最新批次状态"
        variant="borderless"
        style={{
          marginBottom: 20,
          borderRadius: 10,
          boxShadow: "0 1px 3px rgba(15, 37, 64, 0.06)",
        }}
        styles={{ body: { paddingTop: 8 } }}
      >
        {loading ? (
          <div style={{ textAlign: "center", padding: 32 }}>
            <Spin />
          </div>
        ) : !hasLatestBatch ? (
          <div style={{ padding: 24, textAlign: "center", color: "#8c8c8c" }}>暂无批次数据</div>
        ) : (
          <Row gutter={[16, 16]}>
            <Col xs={24} lg={10}>
              <div
                style={{
                  borderRadius: 8,
                  border: "1px solid #e8ecf1",
                  background: "#fafbfd",
                  padding: "4px 4px 0",
                }}
              >
                {donutOption && (
                  <ReactECharts
                    option={donutOption}
                    style={{ height: 300, cursor: "pointer" }}
                    notMerge
                    lazyUpdate
                    onEvents={{
                      click: () => handleCardClick(latestBatch!.batch),
                    }}
                  />
                )}
              </div>
            </Col>
            <Col xs={24} lg={14}>
              <div
                style={{
                  height: "100%",
                  minHeight: 300,
                  borderRadius: 8,
                  border: "1px solid #e8ecf1",
                  background: "linear-gradient(165deg, #eef2f9 0%, #fafbfd 42%, #f7f9fc 100%)",
                  padding: "20px 22px",
                  display: "flex",
                  flexDirection: "column",
                  justifyContent: "center",
                  fontFamily: appFontFamily,
                }}
              >
                <Row gutter={[16, 16]} style={{ width: "100%" }}>
                  <Col span={24}>
                    <div
                      style={{
                        background: "#fff",
                        borderRadius: 8,
                        padding: "14px 18px",
                        border: "1px solid #e4e9f2",
                        boxShadow: "0 1px 2px rgba(46, 59, 124, 0.06)",
                      }}
                    >
                      <Typography.Text type="secondary" style={{ fontSize: 13, letterSpacing: 0.2 }}>
                        批次
                      </Typography.Text>
                      <Typography.Text
                        strong
                        style={{
                          display: "block",
                          fontSize: 17,
                          color: "#102a43",
                          marginTop: 6,
                          wordBreak: "break-all",
                          lineHeight: 1.5,
                        }}
                      >
                        {latestBatch!.batch}
                      </Typography.Text>
                    </div>
                  </Col>
                  <Col xs={24} sm={12}>
                    <div
                      style={{
                        background: "#fff",
                        borderRadius: 8,
                        padding: "14px 18px",
                        minHeight: 92,
                        border: "1px solid #e4e9f2",
                        boxShadow: "0 1px 2px rgba(46, 59, 124, 0.06)",
                        display: "flex",
                        flexDirection: "column",
                        justifyContent: "center",
                      }}
                    >
                      <Typography.Text type="secondary" style={{ fontSize: 13 }}>
                        执行时间
                      </Typography.Text>
                      <Typography.Text
                        strong
                        style={{ display: "block", fontSize: 16, color: "#102a43", marginTop: 8, lineHeight: 1.45 }}
                      >
                        {latestBatch!.batch_start
                          ? dayjs(latestBatch!.batch_start).format("YYYY-MM-DD HH:mm:ss")
                          : "—"}
                      </Typography.Text>
                    </div>
                  </Col>
                  <Col xs={24} sm={12}>
                    <div
                      style={{
                        background: "#fff",
                        borderRadius: 8,
                        padding: "14px 18px",
                        minHeight: 92,
                        border: "1px solid #e4e9f2",
                        boxShadow: "0 1px 2px rgba(46, 59, 124, 0.06)",
                        display: "flex",
                        flexDirection: "column",
                        justifyContent: "center",
                      }}
                    >
                      <Typography.Text type="secondary" style={{ fontSize: 13 }}>
                        批次结果
                      </Typography.Text>
                      <div style={{ marginTop: 8 }}>{renderBatchResultTag(latestBatch!.result)}</div>
                    </div>
                  </Col>
                </Row>
              </div>
            </Col>
          </Row>
        )}
      </Card>

      <Card
        title="各分支最近 batch 执行情况"
        variant="borderless"
        style={{
          borderRadius: 10,
          boxShadow: "0 1px 3px rgba(15, 37, 64, 0.06)",
        }}
        styles={{ body: { paddingTop: 8 } }}
      >
        {branchChartsLoading ? (
          <div style={{ textAlign: "center", padding: 48 }}>
            <Spin />
          </div>
        ) : masterTrendItems.length === 0 && bugfixTrendItems.length === 0 ? (
          <div style={{ padding: 40, textAlign: "center", color: "#8c8c8c" }}>暂无趋势数据</div>
        ) : (
          <Row gutter={[20, 24]}>
            <Col span={24}>
              <Typography.Text strong style={{ display: "block", marginBottom: 8, color: "#434343" }}>
                master
              </Typography.Text>
              {masterOption ? (
                <ReactECharts
                  option={masterOption}
                  style={{ height: 360 }}
                  onEvents={{
                    click: createChartClickHandler(masterTrendItems),
                  }}
                />
              ) : (
                <div style={{ padding: 32, textAlign: "center", color: "#8c8c8c" }}>暂无 master 数据</div>
              )}
            </Col>
            <Col span={24}>
              <Typography.Text strong style={{ display: "block", marginBottom: 8, color: "#434343" }}>
                bugfix
              </Typography.Text>
              {bugfixOption ? (
                <ReactECharts
                  option={bugfixOption}
                  style={{ height: 360 }}
                  onEvents={{
                    click: createChartClickHandler(bugfixTrendItems),
                  }}
                />
              ) : (
                <div style={{ padding: 32, textAlign: "center", color: "#8c8c8c" }}>暂无 bugfix 数据</div>
              )}
            </Col>
          </Row>
        )}
      </Card>
    </div>
  );
}
