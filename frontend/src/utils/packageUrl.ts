import type { FrontendConfig } from "../services";

export type PackageUrlResolve =
  | { kind: "url"; url: string }
  | { kind: "unknown_platform" }
  | { kind: "unavailable" };

/** 根据环境配置与行数据拼接取包地址（platform 忽略大小写） */
export function resolvePackageUrl(
  config: Pick<
    FrontendConfig,
    "package_init_url" | "package_name_mac" | "package_name_oh"
  > | null | undefined,
  codeBranch: string | null | undefined,
  startTime: string | null | undefined,
  platform: string | null | undefined,
): PackageUrlResolve {
  const template = config?.package_init_url?.trim();
  if (!template) return { kind: "unavailable" };

  const branch = codeBranch?.trim();
  const batch = startTime?.trim().replace(/_/g, "");
  if (!branch || !batch) return { kind: "unavailable" };

  const plat = platform?.trim().toLowerCase();
  let packageName: string | undefined;
  if (plat === "mac") {
    packageName = config?.package_name_mac?.trim();
  } else if (plat === "oh") {
    packageName = config?.package_name_oh?.trim();
  } else {
    return { kind: "unknown_platform" };
  }

  if (!packageName) return { kind: "unavailable" };

  const url = template
    .replace(/code_branch/g, branch)
    .replace(/start_time/g, batch)
    .replace(/package_name/g, packageName);

  return { kind: "url", url };
}
