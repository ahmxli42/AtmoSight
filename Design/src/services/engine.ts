export const features = ["PM2.5", "PM10", "SO2", "NO2", "CO", "O3"] as const;
export const keys = ["pm25", "pm10", "so2", "no2", "co", "o3"] as const;
export const categories = [
  "Good",
  "Satisfactory",
  "Moderate",
  "Poor",
  "Very Poor",
  "Severe",
];
export type Inputs = Record<(typeof keys)[number], number | null>;
export interface Result {
  model_id?: string;
  model_name?: string;
  model_features?: string[];
  model_completeness?: number;
  model_evaluation?: {
    accuracy: number;
    macro_f1: number;
    station_holdout?: { accuracy: number; macro_f1: number } | null;
  };
  predicted_category: string;
  confidence: number;
  probabilities: Record<string, number>;
  top_factors: { pollutant: string; impact: number }[];
  explanation_base: number | null;
  is_unusual_reading: boolean;
  anomaly_score: number;
  completeness: number;
  warnings: string[];
  original_values: Record<string, number | null>;
  disclaimer: string;
}
export interface Model {
  station_holdout?: { accuracy: number; macro_f1: number };
  sensor_models?: {
    id: string;
    name: string;
    features: string[];
    accuracy: number;
    macro_f1: number;
    station_holdout?: { accuracy: number; macro_f1: number };
  }[];
  name: string;
  features: string[];
  observations: number;
  train_rows: number;
  test_rows: number;
  accuracy: number;
  macro_f1: number;
  imputation: Record<string, number>;
  evaluation: string;
  limitations: string[];
  source: string;
  robustness: {
    missing_fraction: number;
    accuracy: number;
    macro_f1: number;
  }[];
  noise_stress?: { relative_std: number; accuracy: number; macro_f1: number }[];
}
export interface Batch {
  quality?: import("../components/ImportWizard").Inspection;
  compatibility?: { quality_only: boolean; mapped: string[]; policy: string };
  evaluation?: {
    accuracy: number;
    macro_f1: number;
    confusion_matrix: number[][];
    categories: string[];
    caveat: string;
  } | null;
  rows: {
    row: number;
    original: Record<string, string>;
    result: Result | null;
    error: string | null;
    normalized?: Record<string, number | null> | null;
  }[];
  summary: {
    total: number;
    valid: number;
    invalid: number;
    unusual: number;
    with_warnings: number;
    reference_rows: number;
    reference_agreement: number | null;
  };
  disclaimer: string;
}
export interface RecordItem {
  id: string;
  date: string;
  label: string;
  result: Result;
}
export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const cancel = () => controller.abort();
  init?.signal?.addEventListener("abort", cancel, { once: true });
  if (init?.signal?.aborted) controller.abort();
  let timedOut = false;
  const timeout = setTimeout(
    () => { timedOut = true; controller.abort(); },
    path === "/analyze" || path === "/inspect" ? 1_800_000 : 60000,
  );
  try {
    const response = await fetch(
      `${import.meta.env.VITE_BACKEND_URL || "http://127.0.0.1:8000"}${path}`,
      {
        ...init,
        signal: controller.signal,
      },
    );
    if (!response.ok) {
      const payload = await response.json().catch(() => null);
      throw new Error(
        typeof payload?.detail === "string"
          ? payload.detail
          : `Request failed (${response.status}). Check measurements and backend status.`,
      );
    }
    return (await response.json()) as T;
  } catch (error) {
    if (timedOut)
      throw new Error("The local engine took too long to respond. Wait for it to finish starting, then retry. For a large CSV, try a smaller file.");
    if (error instanceof TypeError)
      throw new Error(
        "Cannot connect to the local inference service. Start the backend and try again.",
      );
    throw error;
  } finally {
    clearTimeout(timeout);
    init?.signal?.removeEventListener("abort", cancel);
  }
}
export function download(
  name: string,
  content: string,
  type = "application/json",
) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
