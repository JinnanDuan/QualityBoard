import { Alert, Button, Space, Typography } from "antd";
import AnalysisTrigger from "./AnalysisTrigger";
import ProgressStream from "./ProgressStream";
import ReportView from "./ReportView";
import { useAIAnalysis } from "./useAIAnalysis";

const { Text } = Typography;

interface AIFailureAnalysisTabProps {
  historyId: number;
  caseResult?: string | null;
}

export default function AIFailureAnalysisTab({ historyId, caseResult }: AIFailureAnalysisTabProps) {
  const {
    status,
    sessionId,
    progressEvents,
    report,
    errorMessage,
    applying,
    rejecting,
    startInitialAnalyze,
    retryAnalyze,
    applyFailureReason,
    rejectDraft,
  } = useAIAnalysis(historyId);

  if (caseResult !== "failed" && caseResult !== "error") {
    return <Alert type="info" showIcon message="仅失败或异常记录支持 AI 归因分析" />;
  }

  if (status === "idle") {
    return <AnalysisTrigger onStart={() => void startInitialAnalyze()} />;
  }

  if (status === "loading") {
    return (
      <div>
        <div style={{ marginBottom: 8 }}>
          <Text type="secondary">会话 ID：{sessionId}</Text>
        </div>
        <ProgressStream events={progressEvents} />
      </div>
    );
  }

  if (status === "error") {
    return (
      <Space direction="vertical" size={12} style={{ width: "100%" }}>
        <Alert
          type="error"
          showIcon
          message="AI 分析失败"
          description={errorMessage || "分析过程中出现异常，请稍后重试"}
        />
        <Button type="primary" onClick={() => void retryAnalyze()}>
          重试分析
        </Button>
      </Space>
    );
  }

  if (!report) {
    return (
      <Alert
        type="warning"
        showIcon
        message="未获取到报告数据"
        description="请重试分析，或联系管理员检查 AIFA 服务状态"
      />
    );
  }

  return (
    <ReportView
      reportEnvelope={report}
      applying={applying}
      rejecting={rejecting}
      onApply={() => void applyFailureReason()}
      onReject={() => void rejectDraft()}
    />
  );
}
