import { useEffect, useState } from "react";
import { features, request } from "../services/engine";
export interface ImportConfig {
  mapping: Record<string, string>;
  units: Record<string, string>;
  interval: string;
  quality_only: boolean;
  label_column: string;
}
export function importProblem(config: ImportConfig): string {
  const mapped = Object.entries(config.mapping).filter(([, column]) => column);
  const columns = mapped.map(([, column]) => column);
  if (new Set(columns).size !== columns.length)
    return "Map each source column to only one pollutant.";
  if (columns.some((column) => /^(aqi|co2|carbondioxide|airqualityindex)/.test(column.toLowerCase().replace(/[^a-z0-9]/g, "")) || ["label", "target", "category"].includes(column.toLowerCase().replace(/[^a-z0-9]/g, ""))))
    return "AQI, category labels, and CO₂ cannot be used as pollutant inputs. Choose the measured pollutant column.";
  if (config.quality_only) return "";
  if (!mapped.length) return "Map at least one pollutant or choose quality-only analysis.";
  if (config.interval !== "daily") return "Confirm Daily averages below, or choose quality-only analysis for hourly or unknown intervals.";
  if (mapped.some(([feature]) => !["ug/m3", "mg/m3"].includes(config.units[feature])))
    return "Classification requires µg/m³ or mg/m³. Choose quality-only analysis for unsupported units.";
  return "";
}
// A File remains the same object while navigating between pages. Avoid uploading
// and profiling that same dataset again just to restore its preview.
const inspectionCache = new WeakMap<File, Inspection>();
export interface Inspection {
  headers: string[];
  suggestions: Record<string, string>;
  reference_suggestion: string;
  total: number;
  preview: Record<string, string>[];
  duplicate_rows: number;
  temporal?: {
    date_column: string;
    station_column: string | null;
    invalid_timestamps: number;
    missing_timestamps: number;
    missing_station_days: number | null;
    duplicate_station_days: number | null;
    method: string;
  } | null;
  columns: {
    name: string;
    missing: number;
    numeric: number;
    negative: number;
    min: number | null;
    max: number | null;
    mean: number | null;
    histogram: { lower: number; upper: number; count: number }[];
  }[];
}
interface SensorModel {
  id: string;
  name: string;
  features: string[];
  accuracy: number;
  macro_f1: number;
  station_holdout?: { accuracy: number; macro_f1: number };
}
export function ImportWizard({
  file,
  config,
  onChange,
  onReady,
  initialize,
}: {
  file: File;
  initialize: boolean;
  config: ImportConfig;
  onChange: (config: ImportConfig) => void;
  onReady: (ready: boolean) => void;
}) {
  const [inspection, setInspection] = useState<Inspection | null>(null);
  const [models, setModels] = useState<SensorModel[]>([]);
  const [error, setError] = useState("");
  const [profileColumn, setProfileColumn] = useState("");
  useEffect(() => {
    let cancelled = false;
    const controller = new AbortController();
    onReady(false);
    setInspection(null);
    setError("");
    const body = new FormData();
    body.append("file", file);
    const cached = inspectionCache.get(file);
    (cached ? Promise.resolve(cached) : request<Inspection>("/inspect", { method: "POST", body, signal: controller.signal }))
      .then((data) => {
        if (cancelled) return;
        inspectionCache.set(file, data);
        setInspection(data);
        if (initialize)
          onChange({
            mapping: data.suggestions,
            units: Object.fromEntries(
              features.map((f) => [f, f === "CO" ? "mg/m3" : "ug/m3"]),
            ),
            interval: "unknown",
            quality_only: !Object.values(data.suggestions).some(Boolean),
            label_column: data.reference_suggestion,
          });
        onReady(true);
      })
      .catch((e) => {
        if (!cancelled) setError(e.message);
      });
    request<SensorModel[]>("/models", { signal: controller.signal })
      .then((data) => {
        if (!cancelled) setModels(data);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [file]);
  if (error)
    return (
      <section className="panel space-top error" role="alert">
        {error}
      </section>
    );
  if (!inspection)
    return (
      <section className="panel space-top">
        Inspecting columns and data quality…
      </section>
    );
  const mapped = features.filter((f) => config.mapping[f]);
  const eligible = models.filter((m) =>
    m.features.every((f) => mapped.includes(f as (typeof features)[number])),
  );
  return (
    <section className="panel space-top">
      <h2>Confirm your import</h2>
      <p className="muted">
        Suggestions match names only. Confirm the physical measurements, units,
        and daily averaging interval. A name match does not establish sensor
        compatibility.
      </p>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Model measurement</th>
              <th>Your column</th>
              <th>Source unit</th>
            </tr>
          </thead>
          <tbody>
            {features.map((f) => (
              <tr key={f}>
                <td>{f}</td>
                <td>
                  <select
                    aria-label={`Map ${f}`}
                    value={config.mapping[f] || ""}
                    onChange={(e) =>
                      onChange({
                        ...config,
                        mapping: { ...config.mapping, [f]: e.target.value },
                      })
                    }
                  >
                    <option value="">Unavailable</option>
                    {inspection.headers.map((h) => (
                      <option key={h} value={h}>
                        {h}
                      </option>
                    ))}
                  </select>
                </td>
                <td>
                  <select
                    aria-label={`Unit ${f}`}
                    value={config.units[f]}
                    onChange={(e) =>
                      onChange({
                        ...config,
                        units: { ...config.units, [f]: e.target.value },
                      })
                    }
                  >
                    <option value="ug/m3">µg/m³</option>
                    <option value="mg/m3">mg/m³</option>
                    <option value="ppm">
                      ppm — classification unavailable
                    </option>
                  </select>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="input-grid">
        <label className="field">
          Measurement interval
          <select
            value={config.interval}
            onChange={(e) => onChange({ ...config, interval: e.target.value })}
          >
            <option value="daily">Daily averages</option>
            <option value="hourly">Hourly</option>
            <option value="unknown">Unknown / other</option>
          </select>
        </label>
        <label className="field">
          Reference category column
          <select
            value={config.label_column}
            onChange={(e) =>
              onChange({ ...config, label_column: e.target.value })
            }
          >
            <option value="">No reference labels</option>
            {inspection.headers.map((h) => (
              <option key={h} value={h}>
                {h}
              </option>
            ))}
          </select>
        </label>
      </div>
      <label className="field">
        <span>
          <input
            type="checkbox"
            checked={config.quality_only}
            onChange={(e) =>
              onChange({ ...config, quality_only: e.target.checked })
            }
          />{" "}
          Analyze quality only — skip classification
        </span>
      </label>
      <div className="quality">
        <div>
          <h3>Compatibility preview</h3>
          <p>
            {mapped.length} of 6 pollutant columns mapped. {inspection.total}{" "}
            observations. {inspection.duplicate_rows} exact duplicate rows.
          </p>
          <p>
            {config.quality_only
              ? "Quality-only analysis is available for any CSV schema."
              : eligible.length
                ? `Eligible research models: ${eligible.map((m) => m.name).join("; ")}`
                : "No complete sensor configuration is mapped. The baseline would use training imputation; review completeness carefully."}
          </p>
          {eligible.map((m) => (
            <p key={m.id} className="muted small">
              {m.name}: random-split accuracy {(m.accuracy * 100).toFixed(2)}%,
              macro F1 {(m.macro_f1 * 100).toFixed(2)}%.{" "}
              {m.station_holdout &&
                `Held-out-station accuracy ${(m.station_holdout.accuracy * 100).toFixed(2)}%.`}{" "}
              Uncalibrated.
            </p>
          ))}
          {config.interval !== "daily" && !config.quality_only && (
            <p className="negative">
              Classification requires daily observations. Choose quality-only
              analysis; automatic temporal aggregation is not implemented.
            </p>
          )}
        </div>
      </div>
      <h3>Dataset quality preview</h3>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Column</th>
              <th>Missing</th>
              <th>Finite numeric</th>
              <th>Negative</th>
              <th>Minimum</th>
              <th>Maximum</th>
            </tr>
          </thead>
          <tbody>
            {inspection.columns.map((c) => (
              <tr key={c.name}>
                <td>{c.name}</td>
                <td>{c.missing}</td>
                <td>{c.numeric}</td>
                <td>{c.negative}</td>
                <td>{c.min ?? "—"}</td>
                <td>{c.max ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {inspection.temporal && (
        <div className="quality">
          <div>
            <h3>Time and station quality</h3>
            <p>
              {inspection.temporal.invalid_timestamps} invalid ISO timestamps;{" "}
              {inspection.temporal.missing_timestamps} missing timestamps.{" "}
              {inspection.temporal.missing_station_days ?? "Not available"}{" "}
              missing station-days within observed ranges;{" "}
              {inspection.temporal.duplicate_station_days ?? "Not available"}{" "}
              duplicate station-days.
            </p>
            <p className="muted small">{inspection.temporal.method}</p>
          </div>
        </div>
      )}
      <label className="field">
        Inspect a numeric distribution
        <select
          value={profileColumn}
          onChange={(e) => setProfileColumn(e.target.value)}
        >
          <option value="">Select a column</option>
          {inspection.columns
            .filter((c) => c.numeric > 0)
            .map((c) => (
              <option key={c.name} value={c.name}>
                {c.name}
              </option>
            ))}
        </select>
      </label>
      {inspection.columns
        .filter((c) => c.name === profileColumn)
        .map((c) => (
          <div className="distribution" key={c.name}>
            <p className="muted small">
              Raw uploaded values. Mean:{" "}
              {c.mean?.toPrecision(5) ?? "Unavailable"}. Units are unchanged in
              this preview.
            </p>
            {c.histogram.map((bin, i) => (
              <div className="distribution-row" key={i}>
                <span>
                  {bin.lower.toPrecision(4)}–{bin.upper.toPrecision(4)}
                </span>
                <div className="track">
                  <i
                    style={{
                      width: `${(100 * bin.count) / Math.max(...c.histogram.map((b) => b.count), 1)}%`,
                    }}
                  />
                </div>
                <b>{bin.count}</b>
              </div>
            ))}
          </div>
        ))}
      <h3 className="space-top">First five original observations</h3>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              {inspection.headers.map((h) => (
                <th key={h}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {inspection.preview.map((row, i) => (
              <tr key={i}>
                {inspection.headers.map((h) => (
                  <td key={h}>{row[h] || "Missing"}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
