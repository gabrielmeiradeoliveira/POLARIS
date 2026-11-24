export type SeverityBucket = "critical" | "high" | "medium" | "low";

export function normalizeSeverityBucket(raw: string): SeverityBucket {
  const s = (raw || "").toUpperCase().trim();
  if (s === "BLOCKER" || s === "CRITICAL") return "critical";
  if (s === "HIGH" || s === "MAJOR") return "high";
  if (s === "MEDIUM" || s === "MINOR") return "medium";
  return "low";
}

export function severityTone(raw: string): "error" | "warning" | "primary" | "neutral" {
  const bucket = normalizeSeverityBucket(raw);
  if (bucket === "critical") return "error";
  if (bucket === "high") return "warning";
  if (bucket === "medium") return "primary";
  return "neutral";
}

export function summarizeSeverities(items: Array<{ severity: string }>): Record<SeverityBucket, number> {
  const counts: Record<SeverityBucket, number> = { critical: 0, high: 0, medium: 0, low: 0 };
  for (const item of items) {
    counts[normalizeSeverityBucket(item.severity)]++;
  }
  return counts;
}
