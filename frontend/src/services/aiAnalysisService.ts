import request from "./request";

export type AnalyzeMode = "initial" | "follow_up";

export interface AnalyzeRequestPayload {
  history_id: number;
  mode: AnalyzeMode;
  session_id?: string;
  follow_up_message?: string;
}

export interface ProgressEventPayload {
  stage: string;
  message: string;
  elapsed_ms?: number;
  percent?: number;
  detail?: string;
}

export interface AiAnalysisReport {
  failure_category?: string;
  verdict?: string;
  confidence?: number;
  summary?: string;
  detailed_reason?: string;
  data_gaps?: string[];
  suggested_next_steps?: string[];
  stage_timeline?: Array<{ stage?: string; message?: string; elapsed_ms?: number }>;
}

export interface AiAnalysisReportEnvelope {
  session_id?: string;
  status?: "ok" | "partial" | "error" | string;
  report?: AiAnalysisReport;
  trace?: {
    skills_invoked?: string[];
    llm_input_tokens?: number;
    llm_output_tokens?: number;
    elapsed_ms?: number;
  };
  analysis_draft_id?: string;
}

export interface StreamAnalyzeHandlers {
  onProgress?: (payload: ProgressEventPayload) => void;
  onReport?: (payload: AiAnalysisReportEnvelope) => void;
  onError?: (message: string) => void;
}

function parseEventBlock(block: string): { eventName: string; data: string } | null {
  const trimmed = block.trim();
  if (!trimmed) return null;

  const lines = trimmed.split("\n");
  let eventName = "message";
  const dataLines: string[] = [];

  lines.forEach((line) => {
    if (line.startsWith("event:")) {
      eventName = line.slice("event:".length).trim() || "message";
      return;
    }
    if (line.startsWith("data:")) {
      dataLines.push(line.slice("data:".length).trim());
    }
  });

  return {
    eventName,
    data: dataLines.join("\n"),
  };
}

function toErrorMessage(raw: unknown, fallback: string): string {
  if (typeof raw === "string" && raw.trim()) return raw.trim();
  if (raw && typeof raw === "object") {
    const maybeMessage = (raw as { message?: unknown; detail?: unknown }).message;
    if (typeof maybeMessage === "string" && maybeMessage.trim()) return maybeMessage.trim();
    const maybeDetail = (raw as { detail?: unknown }).detail;
    if (typeof maybeDetail === "string" && maybeDetail.trim()) return maybeDetail.trim();
  }
  return fallback;
}

export async function streamAnalyze(
  payload: AnalyzeRequestPayload,
  handlers: StreamAnalyzeHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const token = localStorage.getItem("token");
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch("/api/v1/ai/analyze", {
    method: "POST",
    headers,
    body: JSON.stringify(payload),
    signal,
  });

  if (!response.ok) {
    let msg = `分析请求失败（HTTP ${response.status}）`;
    try {
      const contentType = response.headers.get("content-type") || "";
      if (contentType.includes("application/json")) {
        const body = (await response.json()) as { detail?: unknown };
        msg = toErrorMessage(body.detail, msg);
      } else {
        const text = await response.text();
        msg = toErrorMessage(text, msg);
      }
    } catch {
      // 保持默认错误文案
    }
    throw new Error(msg);
  }

  if (!response.body) {
    throw new Error("分析服务未返回流式数据");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";
  let hasFinalEvent = false;

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    if (!value) continue;

    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() ?? "";

    for (const chunk of chunks) {
      const parsed = parseEventBlock(chunk);
      if (!parsed || !parsed.data) continue;

      let dataObj: unknown = parsed.data;
      try {
        dataObj = JSON.parse(parsed.data);
      } catch {
        // 允许非 JSON 场景，后续按字符串处理
      }

      if (parsed.eventName === "progress") {
        handlers.onProgress?.(dataObj as ProgressEventPayload);
        continue;
      }
      if (parsed.eventName === "report") {
        handlers.onReport?.(dataObj as AiAnalysisReportEnvelope);
        hasFinalEvent = true;
        continue;
      }
      if (parsed.eventName === "error") {
        handlers.onError?.(toErrorMessage(dataObj, "AI 分析失败，请稍后重试"));
        hasFinalEvent = true;
      }
    }
  }

  if (!hasFinalEvent) {
    throw new Error("分析流已结束，但未收到最终结果");
  }
}

export interface ApplyFailureReasonRequestPayload {
  history_id: number;
  failure_category: string;
  detailed_reason: string;
  session_id?: string;
  analysis_draft_id?: string;
  version?: string;
  nonce?: string;
}

export interface ApplyFailureReasonResponsePayload {
  success: boolean;
  history_id: number;
  applied: boolean;
  analyzed_updated: boolean;
  message: string;
}

export interface RejectFailureReasonRequestPayload {
  history_id: number;
  session_id?: string;
  analysis_draft_id?: string;
  reason?: string;
}

export interface RejectFailureReasonResponsePayload {
  success: boolean;
  history_id: number;
  rejected: boolean;
  message: string;
}

export const aiAnalysisApi = {
  applyFailureReason(
    data: ApplyFailureReasonRequestPayload,
  ): Promise<ApplyFailureReasonResponsePayload> {
    return request.post("/ai/apply-failure-reason", data) as Promise<ApplyFailureReasonResponsePayload>;
  },
  rejectFailureReason(
    data: RejectFailureReasonRequestPayload,
  ): Promise<RejectFailureReasonResponsePayload> {
    return request.post("/ai/reject-failure-reason", data) as Promise<RejectFailureReasonResponsePayload>;
  },
};
