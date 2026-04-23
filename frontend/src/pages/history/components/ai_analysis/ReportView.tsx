import { Alert, Button, Card, Descriptions, Divider, List, Space, Tag, Typography } from "antd";
import type { AiAnalysisReportEnvelope } from "../../../../services/aiAnalysisService";

const { Paragraph, Text } = Typography;

interface ReportViewProps {
  reportEnvelope: AiAnalysisReportEnvelope;
  applying: boolean;
  rejecting: boolean;
  onApply: () => void;
  onReject: () => void;
}

export default function ReportView({
  reportEnvelope,
  applying,
  rejecting,
  onApply,
  onReject,
}: ReportViewProps) {
  const report = reportEnvelope.report;
  const confidence =
    typeof report?.confidence === "number" ? `${Math.round(report.confidence * 100)}%` : "—";
  const status = reportEnvelope.status || "unknown";

  return (
    <div style={{ marginTop: 8 }}>
      <Card
        size="small"
        title="AI 归因结果"
        extra={<Tag color={status === "ok" ? "green" : status === "partial" ? "orange" : "red"}>{status}</Tag>}
      >
        <Descriptions column={1} size="small">
          <Descriptions.Item label="失败分类">{report?.failure_category || "—"}</Descriptions.Item>
          <Descriptions.Item label="结论摘要">{report?.summary || "—"}</Descriptions.Item>
          <Descriptions.Item label="置信度">{confidence}</Descriptions.Item>
        </Descriptions>

        <Divider style={{ margin: "12px 0" }} />
        <Text strong>详细原因</Text>
        <Paragraph style={{ marginTop: 6, whiteSpace: "pre-wrap" }}>
          {report?.detailed_reason || "—"}
        </Paragraph>

        {report?.data_gaps?.length ? (
          <>
            <Divider style={{ margin: "12px 0" }} />
            <Alert
              type="warning"
              showIcon
              message="数据缺口"
              description={
                <List
                  size="small"
                  dataSource={report.data_gaps}
                  renderItem={(item) => <List.Item>{item}</List.Item>}
                />
              }
            />
          </>
        ) : null}

        {report?.suggested_next_steps?.length ? (
          <>
            <Divider style={{ margin: "12px 0" }} />
            <Text strong>建议下一步</Text>
            <List
              size="small"
              style={{ marginTop: 6 }}
              dataSource={report.suggested_next_steps}
              renderItem={(item) => <List.Item>{item}</List.Item>}
            />
          </>
        ) : null}

        <Divider style={{ margin: "12px 0" }} />
        <Space>
          <Button type="primary" onClick={onApply} loading={applying}>
            一键设置到失败原因
          </Button>
          <Button danger onClick={onReject} loading={rejecting}>
            拒绝本次结果
          </Button>
        </Space>
      </Card>
    </div>
  );
}
