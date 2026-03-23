/** 登录回跳 redirect 参数最大长度，防止超长 query */
const MAX_REDIRECT_LEN = 2048;

/**
 * 校验 URL 中的 redirect 参数，仅允许站内相对路径（含 query），防止开放重定向。
 * 合法则返回解码后的路径，否则返回 null（调用方应回退到首页）。
 */
export function getSafeRedirectPath(raw: string | null): string | null {
  if (raw == null || raw === "") {
    return null;
  }
  let decoded: string;
  try {
    decoded = decodeURIComponent(raw.trim());
  } catch {
    return null;
  }
  if (decoded.length > MAX_REDIRECT_LEN) {
    return null;
  }
  if (!decoded.startsWith("/")) {
    return null;
  }
  if (decoded.startsWith("//")) {
    return null;
  }
  const lower = decoded.toLowerCase();
  if (
    lower.startsWith("/\\") ||
    lower.includes("javascript:") ||
    lower.includes("\n") ||
    lower.includes("\r")
  ) {
    return null;
  }
  if (decoded === "/login" || decoded.startsWith("/login?")) {
    return null;
  }
  return decoded;
}
