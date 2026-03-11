import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import ReactECharts from "echarts-for-react";
import { Card, Col, Row, Spin, Statistic } from "antd";
import dayjs from "dayjs";
import {
  dashboardApi,
  type BatchTrendItem,
  type LatestBatchItem,
} from "../../services";

function buildChartOption(items: BatchTrendItem[]) {
  return {
    tooltip: {
      trigger: "axis" as const,
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
      bottom: 0,
    },
    grid: { left: "3%", right: "4%", bottom: "15%", top: "8%", containLabel: true },
    xAxis: {
      type: "category" as const,
      data: items.map((i) => i.batch),
      axisLabel: { rotate: 45 },
    },
    yAxis: {
      type: "value" as const,
      splitLine: { show: false },
    },
    series: [
      {
        name: "失败用例数",
        type: "line" as const,
        data: items.map((i) => i.failed_num),
        itemStyle: { color: "#ff4d4f" },
        label: { show: true, position: "top" as const },
      },
      {
        name: "总用例数",
        type: "line" as const,
        data: items.map((i) => i.total_case_num),
        itemStyle: { color: "#1890ff" },
        label: { show: true, position: "top" as const },
      },
    ],
  };
}

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

  return (
    <div style={{ padding: "8px 0" }}>
      <h2 style={{ marginBottom: 12 }}>首页大盘</h2>

      {/* 最新批次状态卡片 */}
      <Card title="最新批次状态" style={{ marginBottom: 24 }}>
        {loading ? (
          <div style={{ textAlign: "center", padding: 24 }}>
            <Spin />
          </div>
        ) : !hasLatestBatch ? (
          <div style={{ padding: 16, textAlign: "center", color: "#999" }}>
            暂无批次数据
          </div>
        ) : (
          <Row
            gutter={[24, 0]}
            wrap={false}
            onClick={() => handleCardClick(latestBatch!.batch)}
            style={{ cursor: "pointer" }}
          >
            <Col flex="1">
              <Statistic
                title="批次"
                value={latestBatch!.batch}
                valueStyle={{ fontSize: 16, fontWeight: 600 }}
              />
            </Col>
            <Col flex="1">
              <Statistic title="总用例数" value={latestBatch!.total_case_num ?? "—"} />
            </Col>
            <Col flex="1">
              <Statistic
                title="通过数"
                value={latestBatch!.passed_num ?? "—"}
                valueStyle={{ color: "#52c41a" }}
              />
            </Col>
            <Col flex="1">
              <Statistic
                title="失败数"
                value={latestBatch!.failed_num ?? "—"}
                valueStyle={{ color: "#ff4d4f" }}
              />
            </Col>
            <Col flex="1">
              <Statistic
                title="通过率"
                value={
                  latestBatch!.total_case_num
                    ? `${latestBatch!.pass_rate.toFixed(2)}%`
                    : "—"
                }
              />
            </Col>
          </Row>
        )}
      </Card>

      {/* master 分支趋势折线图 */}
      <Card
        title={<div style={{ textAlign: "center" }}>master 分支最近 batch 执行情况</div>}
        style={{ marginBottom: 24 }}
      >
        {masterTrendLoading ? (
          <div style={{ textAlign: "center", padding: 40 }}>
            <Spin />
          </div>
        ) : masterTrendItems.length === 0 ? (
          <div style={{ padding: 40, textAlign: "center", color: "#999" }}>
            暂无趋势数据
          </div>
        ) : (
          <ReactECharts
            option={buildChartOption(masterTrendItems)}
            style={{ height: 400 }}
            onEvents={{
              click: createChartClickHandler(masterTrendItems),
            }}
          />
        )}
      </Card>

      {/* bugfix 分支趋势折线图 */}
      <Card
        title={<div style={{ textAlign: "center" }}>bugfix 分支最近 batch 执行情况</div>}
      >
        {bugfixTrendLoading ? (
          <div style={{ textAlign: "center", padding: 40 }}>
            <Spin />
          </div>
        ) : bugfixTrendItems.length === 0 ? (
          <div style={{ padding: 40, textAlign: "center", color: "#999" }}>
            暂无趋势数据
          </div>
        ) : (
          <ReactECharts
            option={buildChartOption(bugfixTrendItems)}
            style={{ height: 400 }}
            onEvents={{
              click: createChartClickHandler(bugfixTrendItems),
            }}
          />
        )}
      </Card>
    </div>
  );
}
