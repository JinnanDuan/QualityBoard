import { Button, Space, Typography } from "antd";

const { Paragraph, Text } = Typography;

interface AnalysisTriggerProps {
  disabled?: boolean;
  loading?: boolean;
  onStart: () => void;
}

export default function AnalysisTrigger({ disabled, loading, onStart }: AnalysisTriggerProps) {
  return (
    <div style={{ marginTop: 8 }}>
      <Paragraph style={{ marginBottom: 12 }}>
        <Text type="secondary">
          点击开始后才会发起 AI 分析请求；未点击前不会产生额外分析成本。
        </Text>
      </Paragraph>
      <Space>
        <Button type="primary" onClick={onStart} disabled={disabled} loading={loading}>
          开始分析
        </Button>
      </Space>
    </div>
  );
}
