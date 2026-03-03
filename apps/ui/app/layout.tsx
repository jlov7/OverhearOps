import React from "react";

export const metadata = { title: "OverhearOps", description: "Listen-first agent demo" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body style={{ fontFamily: "\"Segoe UI\", system-ui, sans-serif" }}>
        <header
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "10px 16px",
            borderBottom: "1px solid #d1d5db",
            background: "linear-gradient(90deg, #0f172a, #1e293b)",
            color: "#ffffff",
          }}
        >
          <strong>OverhearOps</strong>
          <nav style={{ display: "flex", gap: 12, fontSize: 14 }}>
            <a href="/">Home</a>
            <a href="/history">History</a>
            <a href="/admin">Admin</a>
          </nav>
        </header>
        {children}
      </body>
    </html>
  );
}
