"use client";

import { ReactNode } from "react";

export default function Modal({
  open,
  onClose,
  title,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
}) {
  if (!open) {
    return null;
  }
  return (
    <div
      aria-modal
      role="dialog"
      style={{ position: "fixed", inset: 0, background: "rgba(15,23,42,0.45)", zIndex: 1000 }}
      onClick={onClose}
    >
      <div
        onClick={(event) => event.stopPropagation()}
        style={{
          position: "absolute",
          top: "10%",
          left: "50%",
          transform: "translateX(-50%)",
          width: 720,
          background: "#fff",
          borderRadius: 12,
          padding: 20,
          boxShadow: "0 16px 48px rgba(15,23,42,0.18)",
          display: "grid",
          gap: 12,
        }}
      >
        <header style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <h3 style={{ margin: 0 }}>{title}</h3>
          <button type="button" onClick={onClose} style={{ border: "none", background: "transparent", cursor: "pointer" }}>
            Close
          </button>
        </header>
        <section>{children}</section>
      </div>
    </div>
  );
}
