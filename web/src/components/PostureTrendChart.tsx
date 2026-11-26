import React from "react";

export interface PostureTrendChartProps {
  points?: Array<{ date: string; count: number }>;
}

export function PostureTrendChart({ points }: PostureTrendChartProps) {
  if (!points || points.length < 2) {
    return (
      <div
        style={{
          padding: "16px",
          textAlign: "center",
          color: "var(--text-muted)",
          fontSize: 12,
          fontFamily: "var(--font-sans)",
          border: "1px dashed var(--border-subtle)",
          borderRadius: "var(--radius-md)",
        }}
      >
        Histórico insuficiente para curva de tendência (mínimo de 2 snapshots).
      </div>
    );
  }

  const maxVal = Math.max(1, ...points.map((p) => p.count));
  const minVal = Math.min(...points.map((p) => p.count));
  const range = Math.max(1, maxVal - minVal);

  const width = 440;
  const height = 110;
  const padX = 24;
  const padY = 16;

  const chartWidth = width - padX * 2;
  const chartHeight = height - padY * 2;

  const coords = points.map((p, idx) => {
    const x = padX + (idx / (points.length - 1)) * chartWidth;
    const y = padY + chartHeight - ((p.count - minVal) / range) * chartHeight;
    return { x, y, ...p };
  });

  const polylinePoints = coords.map((c) => `${c.x},${c.y}`).join(" ");

  return (
    <div style={{ width: "100%", overflowX: "auto" }}>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        style={{ width: "100%", height: "auto", display: "block" }}
        role="img"
        aria-label="Evolução de Postura e Achados ao longo do tempo"
      >
        {/* Linhas de Grade Sutis */}
        <line x1={padX} y1={padY} x2={width - padX} y2={padY} stroke="var(--border-subtle)" strokeDasharray="2 3" strokeWidth="1" />
        <line x1={padX} y1={padY + chartHeight / 2} x2={width - padX} y2={padY + chartHeight / 2} stroke="var(--border-subtle)" strokeDasharray="2 3" strokeWidth="1" />
        <line x1={padX} y1={padY + chartHeight} x2={width - padX} y2={padY + chartHeight} stroke="var(--border-subtle)" strokeDasharray="2 3" strokeWidth="1" />

        {/* Linha da Tendência */}
        <polyline
          fill="none"
          stroke="var(--accent-cyan)"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          points={polylinePoints}
        />

        {/* Pontos Interativos */}
        {coords.map((c, idx) => (
          <circle
            key={idx}
            cx={c.x}
            cy={c.y}
            r="3.5"
            fill="var(--bg-surface)"
            stroke="var(--accent-cyan)"
            strokeWidth="2"
          >
            <title>{`${c.date}: ${c.count} achados`}</title>
          </circle>
        ))}
      </svg>
    </div>
  );
}
