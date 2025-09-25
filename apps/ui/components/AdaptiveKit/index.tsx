"use client";

import clsx from "clsx";
import React from "react";

type TextWeight = "default" | "bolder";
type TextSize = "small" | "default" | "medium" | "large";

type TextBlockProps = {
  text: string;
  wrap?: boolean;
  size?: TextSize;
  weight?: TextWeight;
  spacing?: "none" | "small" | "default" | "medium" | "large";
};

export function TextBlock({
  text,
  wrap = true,
  size = "default",
  weight = "default",
  spacing = "default",
}: TextBlockProps) {
  const className = clsx(
    "adaptive-text",
    size !== "default" && `adaptive-text-${size}`,
    weight !== "default" && `adaptive-text-${weight}`,
    spacing !== "default" && `adaptive-spacing-${spacing}`
  );
  return (
    <p className={className} style={{ whiteSpace: wrap ? "pre-wrap" : "nowrap" }}>
      {text}
    </p>
  );
}

type FactSetProps = {
  facts: { title: string; value: string }[];
};

export function FactSet({ facts }: FactSetProps) {
  return (
    <dl className="adaptive-factset">
      {facts.map((fact) => (
        <React.Fragment key={fact.title}>
          <dt>{fact.title}</dt>
          <dd>{fact.value}</dd>
        </React.Fragment>
      ))}
    </dl>
  );
}

type ContainerProps = {
  children: React.ReactNode;
  style?: React.CSSProperties;
  bleed?: boolean;
};

export function Container({ children, style, bleed = false }: ContainerProps) {
  return (
    <section
      className={clsx("adaptive-container", bleed && "adaptive-container-bleed")}
      style={style}
    >
      {children}
    </section>
  );
}

type ColumnSetProps = {
  columns: React.ReactNode[];
};

export function ColumnSet({ columns }: ColumnSetProps) {
  return <div className="adaptive-columns">{columns}</div>;
}

type ActionSetProps = {
  actions: React.ReactNode[];
};

export function ActionSet({ actions }: ActionSetProps) {
  return <div className="adaptive-actions">{actions}</div>;
}

export function PrimaryButton({ label, onClick, disabled }: { label: string; onClick?: () => void; disabled?: boolean }) {
  return (
    <button className="adaptive-button" type="button" onClick={onClick} disabled={disabled}>
      {label}
    </button>
  );
}

export function AdaptiveCard({ children }: { children: React.ReactNode }) {
  return <div className="adaptive-card">{children}</div>;
}

export function registerAdaptiveStyles() {
  if (typeof document === "undefined") return;
  if (document.getElementById("adaptive-kit-styles")) return;
  const style = document.createElement("style");
  style.id = "adaptive-kit-styles";
  style.innerHTML = `
    .adaptive-card {
      background: #ffffff;
      border-radius: 12px;
      box-shadow: 0 1px 3px rgba(0,0,0,0.2);
      padding: 16px;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }
    .adaptive-text-bolder { font-weight: 600; }
    .adaptive-text-small { font-size: 12px; }
    .adaptive-text-medium { font-size: 16px; }
    .adaptive-text-large { font-size: 18px; }
    .adaptive-spacing-small { margin-bottom: 4px; }
    .adaptive-spacing-medium { margin-bottom: 8px; }
    .adaptive-spacing-large { margin-bottom: 12px; }
    .adaptive-factset {
      display: grid;
      grid-template-columns: max-content 1fr;
      gap: 4px 12px;
      margin: 0;
    }
    .adaptive-factset dt {
      font-weight: 600;
      color: #605e5c;
    }
    .adaptive-factset dd {
      margin: 0;
    }
    .adaptive-container {
      display: flex;
      flex-direction: column;
      gap: 12px;
    }
    .adaptive-container-bleed {
      margin-left: -16px;
      margin-right: -16px;
    }
    .adaptive-columns {
      display: grid;
      gap: 12px;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    }
    .adaptive-actions {
      display: flex;
      gap: 8px;
      justify-content: flex-end;
    }
    .adaptive-button {
      background: #6264a7;
      color: #fff;
      border: none;
      border-radius: 6px;
      padding: 8px 16px;
      font-weight: 600;
      cursor: pointer;
    }
    .adaptive-button:hover {
      background: #464775;
    }
    .adaptive-button:disabled {
      background: #bcbcbc;
      cursor: not-allowed;
    }
  `;
  document.head.appendChild(style);
}
