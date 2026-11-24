export interface HealthStatus {
  status: string;
}

export interface VersionInfo {
  name: string;
  version: string;
}

export interface ProjectItem {
  projectKey: string;
  name: string;
  created_at?: string;
}

export interface IssueLocation {
  file: string;
  startLine: number;
}

export interface IssueItem {
  id?: number;
  ruleId: string;
  language: string;
  severity: string;
  location: IssueLocation;
  message: string;
}

export interface QualityGateCondition {
  metric: string;
  operator: string;
  threshold: number;
  actual: number;
  status: string;
}

export interface QualityGateInfo {
  status: string;
  conditions: QualityGateCondition[];
}

export interface LatestAnalysis {
  analysisId: string;
  branch: string;
  status: string;
  createdAt: string;
}

export interface ProjectOverview {
  projectKey: string;
  name: string;
  latestAnalysis: LatestAnalysis | null;
  totalFiles: number;
  bugs: number;
  vulnerabilities: number;
  codeSmells: number;
  metrics: Record<string, number>;
  qualityGate: QualityGateInfo;
  issues: IssueItem[];
}

export class ApiClientError extends Error {
  constructor(
    message: string,
    public readonly statusCode?: number,
  ) {
    super(message);
    this.name = "ApiClientError";
  }
}
