> Cleanup note: historical report; archived results are preserved. See the root README and scripts/reproduce.py for this repository. Old build paths describe earlier local releases; build outputs and original protected model binaries are excluded.

# Atmosight adaptability report

**Version:** 1.1.1 · **Updated:** 14 October 2026

## Executive assessment

Atmosight now adapts to different CSV column names, supported mass-concentration units, and three evaluated pollutant configurations. A dataset with unrelated columns can still receive a useful data-quality report. Importing a dataset does not retrain the models or teach the system a new region, label standard, or measurement type.

The practical value is a reusable local workflow: inspect a dataset, confirm its meaning, map appropriate measurements, identify quality problems, classify compatible observations, and export evidence. The system no longer requires every CSV to use one exact header layout.

## Implemented capabilities

| Capability | Implemented behavior | Boundary |
|---|---|---|
| Flexible columns | Conservative alias suggestions and manual source-column mapping for six pollutants | A different name must still represent the same physical measurement |
| Unit adaptation | Explicit conversion between mg/m3 and ug/m3 | No ppm conversion without the necessary physical assumptions |
| Sensor configurations | Six-pollutant, PM2.5 + PM10, and PM2.5-only models | Other sensor combinations use the explicitly identified baseline imputation fallback |
| Compatibility report | Shows mapped inputs, eligible models, evaluation evidence and selection policy | Eligibility does not establish accuracy on the uploaded dataset |
| Dataset quality | Missing values, numeric counts, negatives, range, mean, distributions and duplicate rows | General negative numbers can be legitimate; the report does not silently delete them |
| Time and station checks | Recognized ISO date/time columns, invalid dates, station-day duplicates and within-station daily gaps | No temporal prediction, interpolation or hourly-to-daily aggregation |
| Reference evaluation | Accuracy, six-class macro F1 and confusion matrix when compatible labels exist | Agreement with supplied labels is not independent scientific validation |
| Evidence and exports | Original rows, converted measurements, row errors, model identity, artifact hash, probabilities, SHAP and anomaly flags | Probabilities are uncalibrated; anomaly flags do not diagnose sensor failure |

## What happens to a new dataset

1. Upload a UTF-8 CSV. The limit is 50 MB and 250,000 observations. Inference runs in 1,000-row chunks; the interface displays 100 result rows per page, while exports retain every row. Headers must be nonempty and unique.
2. The app profiles every column and previews the original rows. Known pollutant aliases receive suggestions; ambiguous aliases require manual selection.
3. Confirm source columns and units. AQI, target labels and CO2 are blocked as pollutant inputs through conservative name guards. Disguised leakage cannot be universally detected, so semantic confirmation remains essential.
4. Confirm that observations are daily for classification. The UI starts with an unknown interval; hourly or unknown observations can receive quality-only analysis. The app does not invent daily measurements.
5. The engine validates mapped readings and selects a supported model for each eligible row. One invalid row is reported without discarding valid rows.
6. Inspect classifications, warnings, quality statistics, optional reference-label agreement and statistical anomalies. Export the complete JSON report or converted-measurement CSV.

For example, `Fine Dust`, `Coarse Dust` and `Carbon Monoxide` can map to PM2.5, PM10 and CO. A PM2.5 value of 0.042 mg/m3 becomes 42 ug/m3; CO at 800 ug/m3 becomes 0.8 mg/m3. The original strings remain in the JSON report.

A temperature/humidity-only dataset receives profiles, histograms, duplicates and available date/station diagnostics. It receives no fabricated air-quality classification. Spreadsheet workbooks, JSON datasets and live sensor streams are not import formats in this release.

## Model selection and missing measurements

Selection follows the most complete supported feature set, rather than choosing a model by its evaluation score:

1. All six pollutants present: original six-pollutant baseline.
2. PM2.5 and PM10 present: dedicated particulate-pair model.
3. PM2.5 present: dedicated PM2.5-only model.
4. Other partial inputs: baseline with saved training medians, accompanied by missing-input warnings.

Canonical units are ug/m3 for PM2.5, PM10, SO2, NO2 and O3, and mg/m3 for CO. Extra supplied pollutants are explicitly reported as unused when a smaller model is selected. For example, the PM-pair model ignores an additional CO value.

The interface distinguishes overall completeness across six pollutants from completeness of the selected model's required inputs. A complete PM2.5-only observation can satisfy its model while providing only one of the six baseline measurements. This does not make its prediction as accurate as the six-feature model.

## Measured model performance

All models use the existing India station-day research dataset (2015–2020), with 87,025 labeled observations. The random stratified split contains 69,620 training and 17,405 test rows, seed 42.

| Model | Random accuracy | Random macro F1 | Station-held-out accuracy | Station-held-out macro F1 |
|---|---:|---:|---:|---:|
| Six pollutants | 78.12% | 76.50% | 74.60% | 73.21% |
| PM2.5 + PM10 | 69.16% | 68.60% | 67.94% | 68.15% |
| PM2.5 only | 59.83% | 60.39% | 53.84% | 55.49% |

The sensor variants use 200 balanced Random Forest trees, maximum depth 12 and minimum leaf size 5. Their saved artifacts are approximately 19.67 MB for the pair and 21.06 MB for PM2.5, in decimal MB. Each includes a training-fitted median imputer and a 200-tree Isolation Forest with contamination 0.05. The original six-feature artifact was preserved.

The station experiment uses a separate GroupShuffleSplit: 87 training stations, 22 test stations, 71,877 training rows and 15,148 test rows. Station IDs do not overlap. **Each station experiment fits a separate pipeline; it does not evaluate the deployed random-split artifact on stations that artifact never saw.**

These are one random split and one station split of the same source data. Evaluation splits were reused during development and model-footprint regularization; they are not untouched blind external validation. Earlier unbounded sensor prototypes were archived and their preliminary scores are superseded by this table.

No score establishes performance in Pakistan, on future dates, on a different AQI standard or on a physical low-cost sensor. No probability-calibration experiment or temporal holdout was added. The historical project-brief results of 77.31% accuracy and 76.55% macro F1 remain separate from this local reproduction.

## Quality checks and interpretation

Quality profiles cover original source values, including columns not used for inference. Numeric distributions use ten bins, with a single bin for constant values. Dates are parsed conservatively, retaining their calendar date; daily gaps are calculated separately inside each station's observed range. Missing station IDs and malformed dates are reported. No gaps are filled and no future information is introduced into model features.

Accepted reference categories are Good, Satisfactory, Moderate, Poor, Very Poor and Severe. Reference evaluation includes valid predicted rows with recognized labels. Macro F1 averages all six classes, including zero contribution from absent classes. Consequently, perfect agreement on a tiny upload containing only two classes can show 100% accuracy but 33.33% macro F1. That is an explicit six-class calculation, not a claim of strong generalization.

SHAP explanations use the selected fitted model and identify influential inputs. They explain model behavior, not causal environmental mechanisms. Isolation Forest evaluates rarity within the selected feature space. Unusual measurements may be legitimate events; ordinary-looking measurements may still be inaccurate.

## Export and preservation policy

The JSON export includes original rows, mapping and unit configuration, quality and compatibility evidence, row-level errors and prediction results. Converted CSV contains canonical measured pollutant values and errors. Missing values remain blank; training-median replacements are not exported as measured observations. Invalid rows remain represented. Quality-only rows have no canonical normalization that could misrepresent unsupported units.

Uploaded files are not automatically added to training data. Batch reports are not silently archived as permanent datasets. The existing local history remains a compact observation workflow, not a dataset repository. Analysis runs locally through the loopback backend.

## Verification and release status

The final source suite passed all **14 tests**. Model-screen browser evidence is saved in `docs/screenshots/adaptability-models.jpg`.

The final 1.1.0 frontend and Windows desktop release built successfully. Integration checks against the newly rebuilt frozen backend also passed. The executable is at `Design/src-tauri/target-adaptive/release/atmosight.exe`; the adjacent packaged sidecar must stay with it.

Source checks cover model routing, mapped-versus-canonical unit equivalence, original-value preservation, prohibited/duplicate mappings, unrelated-schema analysis, interval/unit guards, aliases, reference metrics, station/date boundaries, malformed configurations, upload size and extreme numeric bounds. Model probabilities are compared with numerical tolerance because parallel tree accumulation can differ at floating-point rounding precision.

The frozen-backend integration checks cover the three-model registry, all three prediction routes, SHAP reconstruction, artifact provenance, mapped units, original preservation and quality-only analysis. Browser verification exercised the manual mapping workflow with a three-row fixture: two classified rows, one preserved negative-value error, a station date gap, reference confusion matrix and quality statistics. The model evidence screen displays the final scores and separate station experiment correctly.

The update is built as a portable Windows desktop release in a separate output directory, preserving the previous running release. Native launch of the updated shell and installer installation are separate from frozen-backend and browser verification; they should not be described as completed merely because compilation succeeds.

## How to start and reproduce

Close the previous Atmosight app and any development backend on port 8000. Open:

`Design\src-tauri\target-adaptive\release\atmosight.exe`

Keep the release directory together with its backend executable. The packaged app needs no Python, Node or Rust installation; its Windows runtime uses WebView2. This update is unsigned and was built without creating a new installer.

Developer commands from the repository root:

```powershell
backend/.venv/Scripts/python.exe -m unittest backend.test_api backend.test_adaptability -q
backend/.venv/Scripts/python.exe -m backend.train_sensor_models
backend/.venv/Scripts/python.exe -m backend.evaluate_station_transfer
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build-adaptive-desktop.ps1
```

The sensor-training and station-evaluation commands regenerate research artifacts; ordinary users should simply start the app. Existing baseline training, missingness and noise evidence remain documented in the earlier validation report.

## What remains outside the implemented adaptability

The app does not automatically learn arbitrary columns, infer scientific equivalence from names, support arbitrary sensor subsets with individually trained models, calculate a different jurisdiction's AQI, retrain online, harmonize new labels, forecast future air quality, or establish regional validity.

A realistic next phase would add controlled, versioned retraining with explicit targets and units, untouched temporal/regional evaluation, station-aware splits, calibration and comparison against the current models. Hourly aggregation would require coverage and timezone rules; ppm conversion would require gas identity and physical conditions. These are future features, not behavior provided by uploading a file today.

## Implementation references

- `backend/import_analysis.py`: schema inspection, mapping, units, quality and reference evaluation.
- `backend/app.py`: model registry, selection, validation, batching and prediction.
- `backend/train_sensor_models.py`: sensor-specific training and station experiments.
- `backend/evaluate_station_transfer.py`: separate baseline station experiment.
- `backend/artifacts/sensor_evaluation.json` and `baseline_station_evaluation.json`: machine-readable evidence.
- `Design/src/components/ImportWizard.tsx`: guided import configuration.
- `Design/src/App.tsx`: results, exports, model evidence and history.
- `backend/test_adaptability.py` and `test_frozen_adaptability.py`: verification.
- `scripts/build-adaptive-desktop.ps1`: separate packaged release.
