import { Alert, List, Tag, Typography } from "antd";
import type { ProgressEventPayload } from "../../../../services/aiAnalysisService";

const { Text } = Typography;

interface ProgressStreamProps {
  events: ProgressEventPayload[];
}

export default function ProgressStream({ events }: ProgressStreamProps) {
  return (
    <div style={{ marginTop: 8 }}>
      <Alert
        type="info"
        showIcon
        message="正在分析中"
        description="AI 正在拉取与整理证据，请稍候..."
        style={{ marginBottom: 12 }}
      />
      <List
        size="small"
        bordered
        dataSource={events}
        locale={{ emptyText: "等待进度事件..." }}
        renderItem={(item) => (
          <List.Item>
            <div style={{ width: "100%" }}>
              <div style={{ marginBottom: 4 }}>
                <Tag color="blue">{item.stage || "unknown"}</Tag>
              </div>
              <Text>{item.message || "分析中..."}</Text>
            </div>
          </List.Item>
        )}
      />
    </div>
  );
}
