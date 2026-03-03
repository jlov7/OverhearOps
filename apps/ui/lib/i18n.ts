export type Locale = "en" | "es";

const COPY: Record<Locale, Record<string, string>> = {
  en: {
    app_title: "OverhearOps",
    suggest_plans: "Suggest Plans",
    thinking: "Thinking...",
    thread: "Thread",
    history: "History",
    admin: "Admin",
    run_history: "Run History",
    compare_runs: "Compare Runs",
    export_jsonl: "Export JSONL",
    filters: "Filters",
    settings: "Settings",
    prompts: "Prompts",
    policies: "Policies",
    save: "Save",
    explainability: "Explainability",
    trace_links: "Trace Links",
  },
  es: {
    app_title: "OverhearOps",
    suggest_plans: "Sugerir planes",
    thinking: "Pensando...",
    thread: "Hilo",
    history: "Historial",
    admin: "Admin",
    run_history: "Historial de ejecuciones",
    compare_runs: "Comparar ejecuciones",
    export_jsonl: "Exportar JSONL",
    filters: "Filtros",
    settings: "Configuración",
    prompts: "Prompts",
    policies: "Políticas",
    save: "Guardar",
    explainability: "Explicabilidad",
    trace_links: "Enlaces de trazas",
  },
};

export function t(locale: Locale, key: string): string {
  return COPY[locale]?.[key] ?? COPY.en[key] ?? key;
}

export function normalizeLocale(input: string | null | undefined): Locale {
  return input === "es" ? "es" : "en";
}
