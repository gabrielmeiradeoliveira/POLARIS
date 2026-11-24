import { ApiClientError, HealthStatus, ProjectItem, ProjectOverview, VersionInfo } from "./types";

const DEFAULT_API_URL = "";

export function getApiBaseUrl(): string {
  const configured = import.meta.env.VITE_API_URL as string | undefined;
  return (configured && configured.trim() ? configured.trim() : DEFAULT_API_URL).replace(/\/+$/, "");
}

async function fetchJson<T>(path: string, timeoutMs = 5000): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${getApiBaseUrl()}${path}`, {
      signal: controller.signal,
      headers: { Accept: "application/json" },
    });
    if (!response.ok) {
      throw new ApiClientError(`HTTP ${response.status} on ${path}`, response.status);
    }
    return (await response.json()) as T;
  } catch (err) {
    if (err instanceof ApiClientError) throw err;
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new ApiClientError(`Request timeout on ${path}`);
    }
    throw new ApiClientError(err instanceof Error ? err.message : "Network or parse error");
  } finally {
    clearTimeout(timer);
  }
}

export const polarisApi = {
  getLive: () => fetchJson<HealthStatus>("/health/live"),
  getReady: () => fetchJson<HealthStatus>("/health/ready"),
  getVersion: () => fetchJson<VersionInfo>("/api/v1/version"),
  getProjects: async (): Promise<ProjectItem[]> => {
    const res = await fetchJson<{ projects?: ProjectItem[] } | ProjectItem[]>("/api/v1/projects");
    return Array.isArray(res) ? res : (res.projects ?? []);
  },
  getProjectOverview: (projectKey: string) =>
    fetchJson<ProjectOverview>(`/api/v1/projects/${encodeURIComponent(projectKey)}/overview`),
};
