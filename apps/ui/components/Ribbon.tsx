"use client";

type RibbonProps = {
  confidence?: number;
  costTokens?: number;
  durationMs?: number;
};

export default function Ribbon({ confidence, costTokens, durationMs }: RibbonProps) {
  const percentage = confidence !== undefined ? Math.round(confidence * 100) : null;
  const tokenCost = costTokens !== undefined ? `${costTokens.toLocaleString()} tok` : "-";
  const duration = durationMs !== undefined ? `${(durationMs / 1000).toFixed(2)} s` : "-";

  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        background: "linear-gradient(90deg, #1e293b, #0f172a)",
        color: "white",
        borderRadius: 14,
        padding: "12px 18px",
        alignItems: "center",
        fontSize: 14,
      }}
    >
      <div style={{ display: "flex", gap: 24 }}>
        <span>
          Confidence: <strong>{percentage !== null ? `${percentage}%` : "-"}</strong>
        </span>
        <span>
          Approx. token cost: <strong>{tokenCost}</strong>
        </span>
        <span>
          Run time: <strong>{duration}</strong>
        </span>
      </div>
      <span style={{ fontStyle: "italic" }}>Guarded by OverhearOps</span>
    </div>
  );
}
