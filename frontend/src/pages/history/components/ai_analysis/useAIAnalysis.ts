import { useCallback, useEffect, useRef, useState } from "react";
import { message } from "antd";
import {
  aiAnalysisApi,
  type AiAnalysisReportEnvelope,
  type ProgressEventPayload,
  streamAnalyze,
} from "../../../../services/aiAnalysisService";

export type AIAnalysisStatus = "idle" | "loading" | "ready" | "error";

export interface UseAIAnalysisResult {
  status: AIAnalysisStatus;
  sessionId: string;
  progressEvents: ProgressEventPayload[];
  report: AiAnalysisReportEnvelope | null;
  errorMessage: string;
  applying: boolean;
  rejecting: boolean;
  startInitialAnalyze: () => Promise<void>;
  retryAnalyze: () => Promise<void>;
  applyFailureReason: () => Promise<void>;
  rejectDraft: () => Promise<void>;
  resetState: () => void;
}

function newSessionId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export function useAIAnalysis(historyId: number): UseAIAnalysisResult {
  const [status, setStatus] = useState<AIAnalysisStatus>("idle");
  const [sessionId, setSessionId] = useState<string>(() => newSessionId());
  const [progressEvents, setProgressEvents] = useState<ProgressEventPayload[]>([]);
  const [report, setReport] = useState<AiAnalysisReportEnvelope | null>(null);
  const [errorMessage, setErrorMessage] = useState("");
  const [applying, setApplying] = useState(false);
  const [rejecting, setRejecting] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
      abortRef.current = null;
    };
  }, []);

  useEffect(() => {
    // 切换到另一条 history 记录时，清空上一条的分析会话与结果。
    abortRef.current?.abort();
    abortRef.current = null;
    setStatus("idle");
    setProgressEvents([]);
    setReport(null);
    setErrorMessage("");
    setApplying(false);
    setRejecting(false);
    setSessionId(newSessionId());
  }, [historyId]);

  const startAnalyzeWithSession = useCallback(
    async (targetSessionId: string) => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      setStatus("loading");
      setErrorMessage("");
      setReport(null);
      setProgressEvents([]);

      try {
        await streamAnalyze(
          {
            history_id: historyId,
            mode: "initial",
            session_id: targetSessionId,
          },
          {
            onProgress: (payload) => {
              const next = {
                stage: payload.stage || "unknown",
                message: payload.message || "分析中...",
                elapsed_ms: payload.elapsed_ms,
                percent: payload.percent,
                detail: payload.detail,
              };
              setProgressEvents((prev) => [...prev, next].slice(-30));
            },
            onReport: (payload) => {
              setReport(payload);
              setStatus("ready");
            },
            onError: (msg) => {
              setErrorMessage(msg);
              setStatus("error");
            },
          },
          controller.signal,
        );
      } catch (err) {
        if (controller.signal.aborted) return;
        const msg = err instanceof Error ? err.message : "AI 分析失败，请稍后重试";
        setErrorMessage(msg);
        setStatus("error");
      } finally {
        if (abortRef.current === controller) {
          abortRef.current = null;
        }
      }
    },
    [historyId],
  );

  const startInitialAnalyze = useCallback(async () => {
    await startAnalyzeWithSession(sessionId);
  }, [sessionId, startAnalyzeWithSession]);

  const retryAnalyze = useCallback(async () => {
    const nextSession = newSessionId();
    setSessionId(nextSession);
    await startAnalyzeWithSession(nextSession);
  }, [startAnalyzeWithSession]);

  const applyFailureReason = useCallback(async () => {
    const failureCategory = report?.report?.failure_category?.trim();
    const detailedReason = report?.report?.detailed_reason?.trim();
    if (!failureCategory || !detailedReason) {
      message.warning("报告缺少可入库字段，暂无法一键设置到失败原因");
      return;
    }
    setApplying(true);
    try {
      const res = await aiAnalysisApi.applyFailureReason({
        history_id: historyId,
        failure_category: failureCategory,
        detailed_reason: detailedReason,
        session_id: sessionId,
        analysis_draft_id: report?.analysis_draft_id,
      });
      message.success(res.message || "已写入失败原因");
    } catch (err) {
      const e = err as { response?: { data?: { detail?: string } }; message?: string };
      message.error(e?.response?.data?.detail || e?.message || "一键入库失败");
    } finally {
      setApplying(false);
    }
  }, [historyId, report, sessionId]);

  const rejectDraft = useCallback(async () => {
    setRejecting(true);
    try {
      const res = await aiAnalysisApi.rejectFailureReason({
        history_id: historyId,
        session_id: sessionId,
        analysis_draft_id: report?.analysis_draft_id,
      });
      message.success(res.message || "已拒绝本次分析结果");
      setStatus("idle");
      setReport(null);
      setProgressEvents([]);
      setErrorMessage("");
    } catch (err) {
      const e = err as { response?: { data?: { detail?: string } }; message?: string };
      message.error(e?.response?.data?.detail || e?.message || "拒绝失败");
    } finally {
      setRejecting(false);
    }
  }, [historyId, report?.analysis_draft_id, sessionId]);

  const resetState = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setStatus("idle");
    setProgressEvents([]);
    setReport(null);
    setErrorMessage("");
    setSessionId(newSessionId());
  }, []);

  return {
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
    resetState,
  };
}
