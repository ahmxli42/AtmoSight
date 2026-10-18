import { ImportWizard, ImportConfig, importProblem } from "./components/ImportWizard";
import { useEffect, useState, FormEvent } from "react";
import {
  Activity,
  ArrowRight,
  BarChart3,
  Check,
  ChevronRight,
  Download,
  FileUp,
  FlaskConical,
  History,
  LayoutDashboard,
  Moon,
  Settings,
  ShieldCheck,
  Sun,
  Wind,
  X,
  AlertTriangle,
} from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import {
  Batch,
  Model,
  Result,
  Inputs,
  RecordItem,
  categories,
  features,
  keys,
  request,
  download,
} from "./services/engine";
const navigation = [
  { name: "Dashboard", icon: LayoutDashboard },
  { name: "Classify", icon: Wind },
  { name: "Upload & Analyze", icon: FileUp },
  { name: "History", icon: History },
  { name: "Model Info", icon: FlaskConical },
  { name: "Settings", icon: Settings },
];
const empty: Inputs = {
  pm25: null,
  pm10: null,
  so2: null,
  no2: null,
  co: null,
  o3: null,
};
const percent = (value: number) => `${(value * 100).toFixed(1)}%`;
const message = (error: unknown) =>
  error instanceof Error ? error.message : "An unexpected error occurred.";
const historyKey = "atmosight.research.history.v1";
function loadTheme() {
  try {
    return localStorage.getItem("atmosight.theme") === "dark";
  } catch {
    return false;
  }
}
function loadHistory(): RecordItem[] {
  try {
    const data = JSON.parse(localStorage.getItem(historyKey) || "[]");
    return Array.isArray(data)
      ? data
          .filter(
            (r) =>
              r?.id &&
              r?.date &&
              categories.includes(r?.result?.predicted_category) &&
              Array.isArray(r?.result?.warnings) &&
              Array.isArray(r?.result?.top_factors) &&
              r?.result?.probabilities &&
              r?.result?.original_values &&
              Number.isFinite(r?.result?.confidence) &&
              Number.isFinite(r?.result?.completeness) &&
              Number.isFinite(r?.result?.anomaly_score),
          )
          .slice(0, 100)
      : [];
  } catch {
    return [];
  }
}
function Prediction({ result }: { result: Result }) {
  return (
    <>
      <div className="result-heading">
        <span
          className={`category category-${categories.indexOf(result.predicted_category)}`}
        >
          {result.predicted_category}
        </span>
        <span className="eyebrow">MODEL CLASSIFICATION</span>
      </div>
      <div className="result-stats">
        <div>
          <strong>{percent(result.confidence)}</strong>
          <span>Model probability · uncalibrated</span>
        </div>
        <div>
          <strong>{percent(result.completeness)}</strong>
          <span>Input completeness</span>
        </div>
      </div>
      <p className="muted small">
        Selected model: {result.model_name || "Six-pollutant baseline"}.
        Required-feature completeness:{" "}
        {percent(result.model_completeness ?? result.completeness)}. Overall
        six-pollutant completeness is shown separately.
      </p>
      {result.model_evaluation && (
        <p className="muted small">
          Selected-model random test accuracy:{" "}
          {percent(result.model_evaluation.accuracy)}; macro F1:{" "}
          {percent(result.model_evaluation.macro_f1)}.{" "}
          {result.model_evaluation.station_holdout &&
            `Held-out-station accuracy: ${percent(result.model_evaluation.station_holdout.accuracy)}.`}{" "}
          These are evaluation scores, not calibrated confidence for this
          observation.
        </p>
      )}
      <h3>Class probabilities</h3>
      <div className="probabilities">
        {categories.map((c) => (
          <div className="prob-row" key={c}>
            <span>{c}</span>
            <div className="track">
              <i style={{ width: percent(result.probabilities[c] || 0) }} />
            </div>
            <b>{percent(result.probabilities[c] || 0)}</b>
          </div>
        ))}
      </div>
      {!!result.top_factors.length && (
        <>
          <div className="section-heading">
            <h3>What influenced this result</h3>
            <span className="tag">SHAP</span>
          </div>
          <p className="muted small">
            Signed contributions to the predicted class probability. Positive
            values support this class. Imputed inputs may also contribute.
          </p>
          <div className="factors">
            {result.top_factors.map((f) => (
              <div key={f.pollutant}>
                <span>{f.pollutant}</span>
                <b className={f.impact >= 0 ? "positive" : "negative"}>
                  {f.impact >= 0 ? "+" : ""}
                  {(f.impact * 100).toFixed(2)} pp
                </b>
              </div>
            ))}
          </div>
          <p className="muted small">
            Base probability: {percent(result.explanation_base || 0)}.
            Contributions are percentage points, not pollution shares.
          </p>
        </>
      )}
      <div className="quality">
        <ShieldCheck size={18} />
        <div>
          <h3>Data quality & anomaly screening</h3>
          <p>
            {result.warnings.length
              ? `${result.warnings.length} review notes`
              : "All six measurements supplied. No screening warnings."}
          </p>
          <p className="muted small">
            Isolation Forest score: {result.anomaly_score.toFixed(3)} ·{" "}
            {result.is_unusual_reading ? "Unusual" : "Not flagged"}
          </p>
          {result.warnings.length > 0 && (
            <ul>
              {result.warnings.map((w) => (
                <li key={w}>{w}</li>
              ))}
            </ul>
          )}
        </div>
      </div>
      <p className="disclaimer">{result.disclaimer}</p>
    </>
  );
}
export function App() {
  const [page, setPage] = useState("Dashboard");
  const [dark, setDark] = useState(loadTheme);
  const [model, setModel] = useState<Model | null>(null);
  const [online, setOnline] = useState(false);
  const [inputs, setInputs] = useState<Inputs>(empty);
  const [label, setLabel] = useState("");
  const [result, setResult] = useState<Result | null>(null);
  const [records, setRecords] = useState<RecordItem[]>(loadHistory);
  const [selected, setSelected] = useState<RecordItem | null>(null);
  const [batch, setBatch] = useState<Batch | null>(null);
  const [batchPage, setBatchPage] = useState(0);
  const batchPageSize = 100;
  useEffect(() => { setBatchPage(0); }, [batch]);
  const [file, setFile] = useState<File | null>(null);
  const [importReady, setImportReady] = useState(false);
  const [importConfig, setImportConfig] = useState<ImportConfig>({
    mapping: {},
    units: {},
    interval: "daily",
    quality_only: false,
    label_column: "",
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [storageError, setStorageError] = useState("");
  const [filter, setFilter] = useState("");
  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    try {
      localStorage.setItem("atmosight.theme", dark ? "dark" : "light");
    } catch {
      /* memory only */
    }
  }, [dark]);
  useEffect(() => {
    let mounted = true;
    let pending = false;
    const controller = new AbortController();
    const check = () => {
      if (pending) return;
      pending = true;
      return request<Model>("/model", { signal: controller.signal })
        .then((m) => {
          if (mounted) {
            setOnline(true);
            setModel(m);
          }
        })
        .catch(() => {
          if (mounted) setOnline(false);
        }).finally(() => { pending = false; });
    };
    check();
    const interval = setInterval(check, 15000);
    return () => {
      mounted = false;
      clearInterval(interval);
      controller.abort();
    };
  }, []);
  function persist(next: RecordItem[]) {
    setRecords(next);
    try {
      localStorage.setItem(historyKey, JSON.stringify(next));
      setStorageError("");
    } catch {
      setStorageError(
        "History could not be saved. Export it before closing the app.",
      );
    }
  }
  async function classify(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setResult(null);
    try {
      const prediction = await request<Result>("/predict", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(inputs),
      });
      setResult(prediction);
      setOnline(true);
      persist(
        [
          {
            id: crypto.randomUUID(),
            date: new Date().toISOString(),
            label: label.trim() || "Manual measurement",
            result: prediction,
          },
          ...records,
        ].slice(0, 100),
      );
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  }
  async function analyze() {
    if (!file) return;
    const problem = importProblem(importConfig);
    if (problem) { setError(problem); return; }
    setBusy(true);
    setError("");
    setBatch(null);
    try {
      const body = new FormData();
      body.append("file", file);
      body.append("config", JSON.stringify(importConfig));
      setBatch(await request<Batch>("/analyze", { method: "POST", body }));
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  }
  const go = (name: string) => {
    setPage(name);
    setError("");
    setSelected(null);
  };
  const visible = records.filter((r) =>
    `${r.label} ${r.result.predicted_category}`
      .toLowerCase()
      .includes(filter.toLowerCase()),
  );
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a
          className="brand"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            go("Dashboard");
          }}
        >
          <span className="brand-mark">
            <Wind size={24} />
          </span>
          <span>
            atmosight
            <span className="brand-sub">ENVIRONMENTAL INTELLIGENCE</span>
          </span>
        </a>
        <span className="nav-label">WORKSPACE</span>
        <nav aria-label="Main navigation">
          {navigation.map(({ name, icon: Icon }) => (
            <button
              key={name}
              className={page === name ? "nav-item active" : "nav-item"}
              aria-label={name}
              onClick={() => go(name)}
            >
              <Icon size={19} />
              <span>{name}</span>
              {page === name && <ChevronRight size={15} />}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="research-note">
            <FlaskConical size={18} />
            <strong>Built for research</strong>
            <p>Adaptive, robust and explainable air quality classification.</p>
            <span>NUST · HITEC University</span>
          </div>
          <button
            className="theme-button"
            aria-label={dark ? "Light appearance" : "Dark appearance"}
            onClick={() => setDark(!dark)}
          >
            {dark ? <Sun size={18} /> : <Moon size={18} />}
            <span>{dark ? "Light appearance" : "Dark appearance"}</span>
          </button>
        </div>
      </aside>
      <div className="main-shell">
        <header className="toolbar">
          <div>
            <span className="muted">Workspace</span>
            <ChevronRight size={14} />
            <strong>{page}</strong>
          </div>
          <span className={`service ${online ? "ready" : ""}`}>
            <i />
            {online ? "Local engine ready" : "Engine unavailable"}
          </span>
        </header>
        <main>
          <div className="page-heading">
            <div>
              <span className="eyebrow">
                ATMOSIGHT /{" "}
                {page === "Classify"
                  ? "SINGLE OBSERVATION"
                  : "RESEARCH WORKSPACE"}
              </span>
              <h1>
                {page === "Dashboard" ? "Your air quality workspace" : page}
              </h1>
              <p>
                {
                  (
                    {
                      Dashboard:
                        "From sensor measurements to understandable evidence.",
                      Classify:
                        "Explore one observation with the six-pollutant baseline.",
                      "Upload & Analyze":
                        "Inspect a dataset, preserve original values, and review every row.",
                      History:
                        "Your latest 100 classifications, stored on this device.",
                      "Model Info":
                        "Measured performance, preprocessing, and research limitations.",
                      Settings:
                        "Appearance, local data, and application information.",
                    } as Record<string, string>
                  )[page]
                }
              </p>
            </div>
            <span className="tag">
              <ShieldCheck size={14} /> Offline inference
            </span>
          </div>
          {error && (
            <div className="error" role="alert">
              <AlertTriangle size={18} />
              {error}
              <button aria-label="Dismiss error" onClick={() => setError("")}>
                <X size={16} />
              </button>
            </div>
          )}
          {storageError && (
            <div className="error" role="alert">
              {storageError}
            </div>
          )}
          {page === "Dashboard" && (
            <>
              <div className="overview-grid">
                <section className="panel welcome">
                  <div className="section-heading">
                    <span className="eyebrow">
                      MEASURE. CLASSIFY. UNDERSTAND.
                    </span>
                    <Wind size={25} />
                  </div>
                  <h2>A clearer view of your measurements</h2>
                  <p className="muted">
                    A local machine learning workspace for data-sparse
                    monitoring. Bring your measurements; examine the prediction
                    and its limitations together.
                  </p>
                  <button className="primary" onClick={() => go("Classify")}>
                    Classify an observation <ArrowRight size={17} />
                  </button>
                  <div className="workflow">
                    <span>01 · Measurements</span>
                    <ChevronRight size={14} />
                    <span>02 · Inference</span>
                    <ChevronRight size={14} />
                    <span>03 · Evidence</span>
                  </div>
                </section>
                <section className="panel engine-card">
                  <span className="eyebrow">INFERENCE ENGINE</span>
                  <h2>{model?.name || "Waiting for local service"}</h2>
                  <p className="muted">
                    {model
                      ? "200 trees · six pollutants · CPU inference"
                      : "Start the packaged application or the development backend."}
                  </p>
                  <dl>
                    <div>
                      <dt>Available variants</dt>
                      <dd>
                        {model
                          ? "Inspect sensor configurations"
                          : "Unavailable"}
                      </dd>
                    </div>
                    <div>
                      <dt>Probability calibration</dt>
                      <dd>Uncalibrated</dd>
                    </div>
                    <div>
                      <dt>Records on this device</dt>
                      <dd>{records.length}</dd>
                    </div>
                  </dl>
                  <button
                    className="text-button"
                    onClick={() => go("Model Info")}
                  >
                    Inspect model evidence <ArrowRight size={16} />
                  </button>
                </section>
              </div>
              <div className="section-heading space-top">
                <h2>Continue your analysis</h2>
                <button className="text-button" onClick={() => go("History")}>
                  View history <ArrowRight size={16} />
                </button>
              </div>
              <div className="overview-grid">
                <section className="panel">
                  <div className="section-heading">
                    <h3>Recent observations</h3>
                    <History size={19} />
                  </div>
                  {records.length ? (
                    records.slice(0, 4).map((r) => (
                      <button
                        className="recent-row"
                        key={r.id}
                        onClick={() => {
                          go("History");
                          setSelected(r);
                        }}
                      >
                        <span>
                          <strong>{r.label}</strong>
                          <small>{new Date(r.date).toLocaleString()}</small>
                        </span>
                        <span
                          className={`category category-${categories.indexOf(r.result.predicted_category)}`}
                        >
                          {r.result.predicted_category}
                        </span>
                      </button>
                    ))
                  ) : (
                    <div className="empty">
                      <Activity size={30} />
                      <h3>No observations yet</h3>
                      <p>Your completed classifications will appear here.</p>
                    </div>
                  )}
                </section>
                <section className="panel">
                  <div className="section-heading">
                    <h3>Analyze a CSV dataset</h3>
                    <FileUp size={21} />
                  </div>
                  <p className="muted">
                    Batch classification with row-level validation,
                    missing-input reporting, and anomaly screening.
                  </p>
                  <div className="file-spec">
                    <span>CSV / UTF-8</span>
                    <span>Up to 250,000 rows · 50 MB</span>
                  </div>
                  <button
                    className="secondary"
                    onClick={() => go("Upload & Analyze")}
                  >
                    Open dataset analysis <ArrowRight size={17} />
                  </button>
                </section>
              </div>
              <div className="footnote">
                Research decision support · No live monitoring data is
                displayed.
              </div>
            </>
          )}
          {page === "Classify" && (
            <div className="classify-grid">
              <form className="panel" onSubmit={classify}>
                <div className="section-heading">
                  <h2>Pollutant measurements</h2>
                  <span className="tag">Six features</span>
                </div>
                <p className="muted">
                  Enter daily-average concentrations. Leave unknown values blank
                  to use saved training medians.
                </p>
                <label className="field full">
                  Observation label
                  <input
                    disabled={busy}
                    value={label}
                    onChange={(e) => setLabel(e.target.value)}
                    placeholder="Optional station or sample name"
                    maxLength={100}
                  />
                </label>
                <div className="input-grid">
                  {features.map((name, i) => (
                    <label className="field" key={name}>
                      <span>
                        {name}
                        <small>{name === "CO" ? "mg/m³" : "µg/m³"}</small>
                      </span>
                      <input
                        disabled={busy}
                        type="number"
                        min="0"
                        step="any"
                        placeholder="Not measured"
                        value={inputs[keys[i]] ?? ""}
                        onChange={(e) => {
                          setResult(null);
                          setInputs({
                            ...inputs,
                            [keys[i]]:
                              e.target.value === ""
                                ? null
                                : Number(e.target.value),
                          });
                        }}
                      />
                    </label>
                  ))}
                </div>
                <div className="input-note">
                  <ShieldCheck size={18} />
                  <span>
                    {Object.values(inputs).filter((v) => v !== null).length} of
                    6 measurements supplied. Missing values do not represent
                    zero.
                  </span>
                </div>
                <div className="actions">
                  <button
                    className="primary"
                    disabled={
                      busy || Object.values(inputs).every((v) => v === null)
                    }
                  >
                    {busy ? "Running inference…" : "Classify observation"}
                    <ArrowRight size={17} />
                  </button>
                  <button
                    disabled={busy}
                    type="button"
                    className="text-button"
                    onClick={() => {
                      setInputs(empty);
                      setResult(null);
                      setLabel("");
                    }}
                  >
                    Clear
                  </button>
                </div>
                <p className="muted small">
                  Available research models are selected by measured sensor
                  inputs. Partial-input results need additional caution.
                </p>
              </form>
              <section className="panel result-panel" aria-live="polite">
                <div className="section-heading">
                  <h2>Classification evidence</h2>
                  <span className="tag">LOCAL MODEL</span>
                </div>
                {result ? (
                  <Prediction result={result} />
                ) : (
                  <div className="empty result-empty">
                    <BarChart3 size={38} />
                    <h3>Evidence starts with a measurement</h3>
                    <p>
                      Run a classification to review probabilities, SHAP
                      contributions, and quality notes.
                    </p>
                    <div className="empty-checks">
                      <span>
                        <Check size={15} /> Training-time imputation
                      </span>
                      <span>
                        <Check size={15} /> No AQI target features
                      </span>
                      <span>
                        <Check size={15} /> Local inference
                      </span>
                    </div>
                  </div>
                )}
              </section>
            </div>
          )}
          {page === "Upload & Analyze" && (
            <>
              <section className="panel upload-panel">
                <div>
                  <h2>Bring your dataset</h2>
                  <p className="muted">
                    Map your dataset columns and confirm source units.
                    Additional columns are preserved for reporting and excluded
                    from inference. AQI_Bucket is used only for reference
                    agreement.
                    Files up to 50 MB and 250,000 rows are supported. Large
                    analyses can take several minutes; results show 100 rows
                    per page and exports include every row.
                  </p>
                  <code>{features.join(", ")}</code>
                </div>
                <div className="upload-controls">
                  <label className="file-picker">
                    <FileUp size={24} />
                    <span>{file?.name || "Choose a CSV file"}</span>
                    <input
                      type="file"
                      accept=".csv,text/csv"
                      disabled={busy}
                      onChange={(e) => {
                        const next = e.target.files?.[0] || null;
                        setImportReady(false);
                        setFile(next && next.size <= 50_000_000 ? next : null);
                        setBatch(null);
                        setError(next && next.size > 50_000_000 ? "CSV exceeds the 50 MB limit. Split the dataset into smaller files before uploading." : "");
                        e.target.value = "";
                      }}
                    />
                  </label>
                  <button
                    className="primary"
                    disabled={!file || busy || !importReady || !!importProblem(importConfig)}
                    onClick={analyze}
                  >
                    {busy ? "Analyzing dataset…" : "Analyze dataset"}
                    <ArrowRight size={17} />
                  </button>
                  {file && importReady && importProblem(importConfig) && (
                    <p role="status" className="negative small">{importProblem(importConfig)}</p>
                  )}
                  <button
                    className="text-button"
                    onClick={() =>
                      download(
                        "atmosight-template.csv",
                        `${features.join(",")},StationId,Date,AQI_Bucket\n`,
                        "text/csv",
                      )
                    }
                  >
                    Download CSV template <Download size={15} />
                  </button>
                </div>
              </section>
              {file && (
                <fieldset className="import-fieldset" disabled={busy}>
                  <ImportWizard
                    file={file}
                    config={importConfig}
                    initialize={!importReady}
                    onChange={(next) => {
                      setImportConfig(next);
                      setBatch(null);
                    }}
                    onReady={setImportReady}
                  />
                  <button className="primary space-top" disabled={!importReady || busy || !!importProblem(importConfig)} onClick={analyze}>
                    {busy ? "Analyzing dataset…" : "Analyze confirmed dataset"}
                  </button>
                </fieldset>
              )}
              {batch?.compatibility && (
                <section className="panel space-top">
                  <h2>
                    {batch.compatibility.quality_only
                      ? "Quality-only report"
                      : "Import compatibility"}
                  </h2>
                  <p>{batch.compatibility.policy}</p>
                  <p>
                    {batch.quality?.duplicate_rows} duplicate rows. Originals
                    retained in the JSON export.
                  </p>
                  {batch.evaluation && (
                    <>
                      <p>
                        Uploaded-label macro F1:{" "}
                        {percent(batch.evaluation.macro_f1)}.{" "}
                        {batch.evaluation.caveat}
                      </p>
                      <div className="table-scroll">
                        <table>
                          <thead>
                            <tr>
                              <th>Actual / predicted</th>
                              {batch.evaluation.categories.map((c) => (
                                <th key={c}>{c}</th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {batch.evaluation.confusion_matrix.map((row, i) => (
                              <tr key={i}>
                                <td>{batch.evaluation!.categories[i]}</td>
                                {row.map((n, j) => (
                                  <td key={j}>{n}</td>
                                ))}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </>
                  )}
                </section>
              )}
              {batch ? (
                <>
                  <div className="batch-stats">
                    {[
                      ["Observations", batch.summary.total],
                      ["Classified", batch.summary.valid],
                      ["Invalid rows", batch.summary.invalid],
                      ["Quality notes", batch.summary.with_warnings],
                      ["Unusual readings", batch.summary.unusual],
                    ].map(([name, value]) => (
                      <div key={name}>
                        <span>{name}</span>
                        <strong>{value}</strong>
                      </div>
                    ))}
                  </div>
                  <section className="panel">
                    <div className="section-heading">
                      <h2>Row-level results</h2>
                      <button
                        className="secondary"
                        onClick={() =>
                          download(
                            "atmosight-analysis.json",
                            JSON.stringify(batch),
                          )
                        }
                      >
                        <Download size={16} />
                        Export complete report
                      </button>
                    </div>
                    <p className="muted small">
                      Batch reports omit SHAP for speed. Open a classified row
                      to request its explanation. Exports retain original values
                      and quality notes.
                    </p>
                    {batch.summary.reference_agreement !== null && (
                      <p>
                        Reference-label agreement:{" "}
                        {percent(batch.summary.reference_agreement)} across{" "}
                        {batch.summary.reference_rows} rows. This is
                        uploaded-label agreement, not independent validation.
                      </p>
                    )}
                    <div className="table-scroll">
                      <table>
                        <thead>
                          <tr>
                            <th>CSV row</th>
                            <th>Category</th>
                            <th>Selected model</th>
                            <th>Probability</th>
                            <th>Completeness</th>
                            <th>Quality</th>
                          </tr>
                        </thead>
                        <tbody>
                          {batch.rows.slice(batchPage * batchPageSize, (batchPage + 1) * batchPageSize).map((r) => (
                            <tr key={r.row}>
                              <td>{r.row}</td>
                              <td>
                                {r.result ? (
                                  <button
                                    className="text-button"
                                    onClick={() => {
                                      const value = r.result!;
                                      setInputs(
                                        Object.fromEntries(
                                          keys.map((k, i) => [
                                            k,
                                            value.original_values[features[i]],
                                          ]),
                                        ) as Inputs,
                                      );
                                      setResult(null);
                                      setLabel(`CSV row ${r.row}`);
                                      go("Classify");
                                    }}
                                  >
                                    {r.result.predicted_category}
                                    <ChevronRight size={14} />
                                  </button>
                                ) : batch.compatibility?.quality_only ? (
                                  "Not classified"
                                ) : (
                                  "Invalid"
                                )}
                              </td>
                              <td>
                                {r.result?.model_name || "Not classified"}
                              </td>
                              <td>
                                {r.result ? percent(r.result.confidence) : "—"}
                              </td>
                              <td>
                                {r.result
                                  ? percent(r.result.completeness)
                                  : "—"}
                              </td>
                              <td>
                                {r.error ||
                                  r.result?.warnings.join(" ") ||
                                  "No warnings"}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    <nav aria-label="Dataset result pages" className="section-heading">
                      <button className="secondary" disabled={batchPage === 0} onClick={() => setBatchPage(p => p - 1)}>Previous rows</button>
                      <span aria-live="polite">Rows {batchPage * batchPageSize + 1}–{Math.min((batchPage + 1) * batchPageSize, batch.rows.length)} of {batch.rows.length.toLocaleString()}</span>
                      <button className="secondary" disabled={(batchPage + 1) * batchPageSize >= batch.rows.length} onClick={() => setBatchPage(p => p + 1)}>Next rows</button>
                    </nav>
                    {!batch.compatibility?.quality_only && (
                      <button
                        className="secondary"
                        onClick={() => {
                          const quote = (v: unknown) =>
                            '"' + String(v ?? "").replace(/"/g, '""') + '"';
                          const lines = [
                            ["CSV row", "Error", ...features]
                              .map(quote)
                              .join(","),
                            ...batch.rows.map((r) =>
                              [
                                r.row,
                                r.error,
                                ...features.map((f) => r.normalized?.[f]),
                              ]
                                .map(quote)
                                .join(","),
                            ),
                          ];
                          download(
                            "atmosight-normalized.csv",
                            lines.join("\n"),
                            "text/csv",
                          );
                        }}
                      >
                        Export converted measurements
                      </button>
                    )}
                    <p className="disclaimer">{batch.disclaimer}</p>
                  </section>
                </>
              ) : (
                <section className="panel">
                  <div className="empty">
                    <FileUp size={34} />
                    <h3>Your dataset stays on this device</h3>
                    <p>
                      Missing inputs use training medians. Invalid rows remain
                      visible in the report.
                    </p>
                  </div>
                </section>
              )}
            </>
          )}
          {page === "History" && (
            <>
              <section className="panel">
                <div className="section-heading">
                  <input
                    className="search"
                    aria-label="Search history"
                    placeholder="Search labels or categories…"
                    value={filter}
                    onChange={(e) => setFilter(e.target.value)}
                  />
                  <button
                    className="secondary"
                    disabled={!records.length}
                    onClick={() =>
                      download(
                        "atmosight-history.json",
                        JSON.stringify(records, null, 2),
                      )
                    }
                  >
                    <Download size={16} />
                    Export history
                  </button>
                </div>
                {visible.length ? (
                  <div className="table-scroll">
                    <table>
                      <thead>
                        <tr>
                          <th>Observation</th>
                          <th>Recorded</th>
                          <th>Category</th>
                          <th>Selected model</th>
                          <th>Probability</th>
                          <th>Review</th>
                        </tr>
                      </thead>
                      <tbody>
                        {visible.map((r) => (
                          <tr key={r.id}>
                            <td>
                              <button
                                className="text-button"
                                onClick={() => setSelected(r)}
                              >
                                {r.label}
                                <ChevronRight size={14} />
                              </button>
                            </td>
                            <td>{new Date(r.date).toLocaleString()}</td>
                            <td>
                              <span
                                className={`category category-${categories.indexOf(r.result.predicted_category)}`}
                              >
                                {r.result.predicted_category}
                              </span>
                            </td>
                            <td>
                              {r.result.model_name || "Six-pollutant baseline"}
                            </td>
                            <td>{percent(r.result.confidence)}</td>
                            <td>
                              {r.result.warnings.length
                                ? `${r.result.warnings.length} notes`
                                : "No warnings"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="empty">
                    <History size={32} />
                    <h3>
                      {filter
                        ? "No matching observations"
                        : "A fresh research log"}
                    </h3>
                    <p>
                      Complete a classification to save your first observation.
                    </p>
                  </div>
                )}
              </section>
              {selected && (
                <section className="panel space-top">
                  <div className="section-heading">
                    <h2>{selected.label}</h2>
                    <button
                      className="secondary"
                      onClick={() => setSelected(null)}
                    >
                      Close
                      <X size={16} />
                    </button>
                  </div>
                  <p className="muted">
                    {new Date(selected.date).toLocaleString()}
                  </p>
                  <dl className="measurement-list">
                    {Object.entries(selected.result.original_values).map(
                      ([k, v]) => (
                        <div key={k}>
                          <dt>{k}</dt>
                          <dd>{v ?? "Missing"}</dd>
                        </div>
                      ),
                    )}
                  </dl>
                  <Prediction result={selected.result} />
                </section>
              )}
            </>
          )}
          {page === "Model Info" &&
            (model ? (
              <>
                <section className="panel">
                  <div className="section-heading">
                    <h2>{model.name}</h2>
                    <span className="tag">New local evaluation</span>
                  </div>
                  <p className="muted">{model.evaluation}</p>
                  <div className="model-metrics">
                    <div>
                      <strong>{percent(model.accuracy)}</strong>
                      <span>Test accuracy</span>
                    </div>
                    <div>
                      <strong>{percent(model.macro_f1)}</strong>
                      <span>Macro F1</span>
                    </div>
                    <div>
                      <strong>{model.observations.toLocaleString()}</strong>
                      <span>Labelled observations</span>
                    </div>
                  </div>
                  <p>
                    {model.train_rows.toLocaleString()} training rows ·{" "}
                    {model.test_rows.toLocaleString()} test rows · seed 42 ·
                    balanced class weights
                  </p>
                  <p className="muted">{model.source}</p>
                  {model.station_holdout && (
                    <p className="muted">
                      Separate held-out-station experiment: accuracy{" "}
                      {percent(model.station_holdout.accuracy)}, macro F1{" "}
                      {percent(model.station_holdout.macro_f1)}. This score
                      comes from a separately fitted pipeline, not from testing
                      the shipped random-split artifact on unseen training
                      stations.
                    </p>
                  )}
                </section>
                <div className="overview-grid space-top">
                  <section className="panel">
                    <h2>Shared preprocessing</h2>
                    <p className="muted">
                      Saved medians fitted on training data only. Feature order
                      is fixed; AQI and label columns never enter inference.
                    </p>
                    <dl>
                      {Object.entries(model.imputation).map(([name, value]) => (
                        <div key={name}>
                          <dt>{name}</dt>
                          <dd>{value.toFixed(3)}</dd>
                        </div>
                      ))}
                    </dl>
                  </section>
                  <section className="panel">
                    <h2>Random missing-input stress test</h2>
                    <p className="muted small">
                      Measured on the same held-out random split. Synthetic
                      missingness does not establish real-world sensor
                      robustness.
                    </p>
                    <div className="chart">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart
                          data={model.robustness.map((r) => ({
                            missing: `${r.missing_fraction * 100}% missing`,
                            accuracy: r.accuracy * 100,
                            "Macro F1": r.macro_f1 * 100,
                          }))}
                        >
                          <XAxis dataKey="missing" tick={{ fontSize: 12 }} />
                          <YAxis domain={[0, 100]} tick={{ fontSize: 12 }} />
                          <Tooltip
                            formatter={(value: number) =>
                              `${value.toFixed(1)}%`
                            }
                          />
                          <Legend />
                          <Bar
                            isAnimationActive={false}
                            dataKey="accuracy"
                            fill="#147d77"
                            radius={[3, 3, 0, 0]}
                          />
                          <Bar
                            isAnimationActive={false}
                            dataKey="Macro F1"
                            fill="#93b9ae"
                            radius={[3, 3, 0, 0]}
                          />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  </section>
                </div>
                {model.sensor_models && (
                  <section className="panel space-top">
                    <h2>Sensor configurations</h2>
                    <p className="muted">
                      Selection uses available measurements, not an assumption
                      that fewer inputs are equally accurate. Dedicated research
                      variants require their listed features.
                    </p>
                    <div className="table-scroll">
                      <table>
                        <thead>
                          <tr>
                            <th>Model</th>
                            <th>Features</th>
                            <th>Random accuracy</th>
                            <th>Macro F1</th>
                            <th>Held-out-station accuracy</th>
                          </tr>
                        </thead>
                        <tbody>
                          {model.sensor_models.map((m) => (
                            <tr key={m.id}>
                              <td>{m.name}</td>
                              <td>{m.features.join(", ")}</td>
                              <td>{percent(m.accuracy)}</td>
                              <td>{percent(m.macro_f1)}</td>
                              <td>
                                {m.station_holdout
                                  ? percent(m.station_holdout.accuracy)
                                  : "Not evaluated"}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </section>
                )}
                {model.noise_stress && (
                  <section className="panel space-top">
                    <h2>Synthetic sensor-noise stress test</h2>
                    <p className="muted">
                      Multiplicative Gaussian noise, clipped to nonnegative
                      values. Relative standard deviation controls perturbation
                      strength. This does not validate any physical sensor.
                    </p>
                    <div className="table-scroll">
                      <table>
                        <thead>
                          <tr>
                            <th>Relative noise SD</th>
                            <th>Accuracy</th>
                            <th>Macro F1</th>
                          </tr>
                        </thead>
                        <tbody>
                          {model.noise_stress.map((r) => (
                            <tr key={r.relative_std}>
                              <td>{percent(r.relative_std)}</td>
                              <td>{percent(r.accuracy)}</td>
                              <td>{percent(r.macro_f1)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </section>
                )}
                <section className="panel space-top">
                  <h2>Interpretation & limitations</h2>
                  <ul className="limitations">
                    {model.limitations.map((l) => (
                      <li key={l}>{l}</li>
                    ))}
                  </ul>
                  <p className="disclaimer">
                    The historical 77.31% accuracy and 76.55% macro F1 in the
                    project brief are separate reported baseline results. Their
                    saved model and evaluation outputs were absent. Unverified
                    experimental figures are not shown.
                  </p>
                </section>
              </>
            ) : (
              <section className="panel">
                <div className="empty">
                  <FlaskConical size={32} />
                  <h3>Model information unavailable</h3>
                  <p>
                    Connect to the local backend to load its saved evaluation
                    evidence.
                  </p>
                </div>
              </section>
            ))}
          {page === "Settings" && (
            <div className="settings-grid">
              <section className="panel">
                <h2>Appearance</h2>
                <p className="muted">
                  Choose the workspace appearance. Your preference is saved
                  locally.
                </p>
                <div className="theme-options">
                  <button
                    className={!dark ? "theme-option selected" : "theme-option"}
                    onClick={() => setDark(false)}
                  >
                    <Sun size={23} />
                    Light{!dark && <Check size={16} />}
                  </button>
                  <button
                    className={dark ? "theme-option selected" : "theme-option"}
                    onClick={() => setDark(true)}
                  >
                    <Moon size={23} />
                    Dark{dark && <Check size={16} />}
                  </button>
                </div>
              </section>
              <section className="panel">
                <h2>Local research data</h2>
                <p className="muted">
                  Compact records stay in local storage. Batch files are held in
                  memory for the current session.
                </p>
                <dl>
                  <div>
                    <dt>Saved observations</dt>
                    <dd>{records.length} / 100</dd>
                  </div>
                  <div>
                    <dt>Inference endpoint</dt>
                    <dd>{import.meta.env.VITE_BACKEND_URL || "http://127.0.0.1:8000"}</dd>
                  </div>
                </dl>
                <button
                  className="secondary"
                  disabled={!records.length}
                  onClick={() =>
                    download(
                      "atmosight-history.json",
                      JSON.stringify(records, null, 2),
                    )
                  }
                >
                  <Download size={16} />
                  Export records
                </button>
                <button
                  className="danger-button"
                  disabled={!records.length || busy}
                  onClick={() => {
                    if (
                      window.confirm(
                        "Delete all locally saved Atmosight observations? Export them first if needed.",
                      )
                    ) {
                      persist([]);
                      setSelected(null);
                    }
                  }}
                >
                  Clear local history
                </button>
              </section>
              <section className="panel">
                <h2>About Atmosight</h2>
                <p>
                  Adaptive, Robust and Explainable Machine Learning for Air
                  Quality Classification in Data-Sparse Regions.
                </p>
                <p className="muted">
                  Research internship at NUST · BS Computer Science Final Year
                  Project at HITEC University Taxila.
                </p>
                <p className="disclaimer">
                  Research decision support. Not an official government AQI
                  advisory system.
                </p>
              </section>
            </div>
          )}
        </main>
        <footer>
          <span>Atmosight · Research workspace</span>
          <span>Local processing / Uncalibrated model probabilities</span>
        </footer>
      </div>
    </div>
  );
}
