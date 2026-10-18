> Cleanup note: historical report; archived results are preserved. See the root README and scripts/reproduce.py for this repository. Old build paths describe earlier local releases; build outputs and original protected model binaries are excluded.

# Degraded aware training experiment

Completed research report. Protocol recorded before training on 15 October 2026; execution continued into 16 October. The deployed app, datasets and model artifacts were not changed.

## 1 Purpose and research question

Does a Random Forest trained on clean plus simulated degraded readings perform better on noisy, sparse and incomplete six-pollutant data than the same classifier trained without added degradation? All four requested variants and both fixed test protocols are reported.

**Main result:** 2 of the eight variant–protocol comparisons met the prespecified rule. A failed rule means “did not help under this rule,” even if severe-condition performance improved. The detailed results below separate robustness gains from clean-data losses.

## 2 Background and repository inspection

Atmosight originally trained a 200-tree balanced six-pollutant forest on India station-day data with training-only median imputation. Missingness and multiplicative-noise stress tests already existed, but they did not train a degraded-aware counterpart. Low-cost monitors can lose individual readings or entire gas channels, motivating a controlled paired comparison. Synthetic failures are an experimental proxy rather than a physical sensor calibration model.

`backend/train.py` supplied feature/category constants and the filtering sequence. `backend/train_sensor_models.py: pipeline(limited=False)` supplied the exact unrestricted classifier configuration through a cloned estimator. The multiplicative Gaussian operator follows `backend/noise_evaluation.py`. Split definitions match `backend/train.py` and `backend/evaluate_station_transfer.py`. The last two evaluation scripts with metadata-writing side effects were inspected but not executed/imported.

## 3 Data and filtering

File: `Dataset/station_day.csv`. SHA-256: `67c308463abab12507f0c9892549fedfc099221025cbcb3e308be170b5a6a0ad`. CSV source-row IDs are saved in the manifest for both fixed partitions. Rows follow the existing filter in exactly the same order. “Clean” means no extra synthetic degradation; it does not mean complete or error-free measurements.

| Stage | Rows |
| --- | --- |
| raw | 108035 |
| after_nonmissing_target | 87025 |
| after_station_date_deduplication | 87025 |
| after_recognized_categories | 87025 |
| after_numeric_coercion | 87025 |
| after_negative_filter | 87025 |
| naturally_all_missing | 272 |

| Class | Filtered count |
| --- | --- |
| Good | 5510 |
| Satisfactory | 23636 |
| Moderate | 29417 |
| Poor | 11493 |
| Very Poor | 11762 |
| Severe | 5207 |

| Protocol | Train | Test | All missing train | All missing test |
| --- | --- | --- | --- | --- |
| random | 69620 | 17405 | 216 | 56 |
| station | 71877 | 15148 | 203 | 69 |

The 272 naturally all-missing rows remain, as explicitly approved by the user. They are the exception to retaining an observed value: fabricating a measurement would violate the experiment. All other degraded rows retain at least one originally observed pollutant.

## 4 Preprocessing and leakage controls

Inputs are PM2.5, PM10, SO2, NO2, CO and O3 only. AQI, AQI_Bucket, StationId and Date never enter the predictor. AQI_Bucket is the target; StationId is used only for splitting; dates/source row numbers are audit identifiers. Each fit uses medians learned from its clean training subset, shared unchanged by A and B and all evaluation conditions. In CV those medians are fitted separately within each fold training subset. Optional flags are computed from pre-imputation missingness and appended to both arms. No normalization, imputation or learning uses held-out statistics.

SimpleImputer keeps empty features so the feature layout cannot change. In an entirely empty training column its fallback is zero; the recorded fold medians show whether this arose. Natural missingness in the source is preserved. Training and evaluation source indices are disjoint, and the station protocol also verifies no station overlap against the existing station-ID lists. Adding six flags changes the feature count from 6 to 12; with the unchanged max_features=sqrt setting, this also changes the candidate-feature count per split from 2 to 3. Both A and B receive the same setting within a variant; comparisons across flag variants therefore include this feature-sampling change.

## 5 Degradation operators

| Condition | Noise sigma | Cell mask p | Gas-row fraction |
| --- | --- | --- | --- |
| Moderate | 0.1 | 0.15 | 0.2 |
| Severe | 0.3 | 0.4 | 0.5 |

Order: (1) multiply observed x by 1 + N(0,sigma) and clip at zero; (2) independently mask observed cells with probability p; (3) choose floor(fraction × rows) rows without replacement and remove SO2, NO2, CO and O3 jointly. Noise represents proportional concentration error; random masking represents intermittent dropout; joint gas removal represents a PM-only device. Labels are unchanged.

If the process erases every value from a previously observed row, restore one of its noisy originally observed values, preferring a particulate measurement. If the row originally had no PM value, a gas must be restored. This safeguard can reduce realized gas absence and masking. The operator rates below distinguish Bernoulli mask rate, selected gas rows, final missingness and rescue events. Natural all-missing rows are never filled by this operator.

| Protocol | Condition | Mask % | Gas selected % | Final missing % | All gases missing % | Rescued rows mean | Gas rescues mean |
| --- | --- | --- | --- | --- | --- | --- | --- |
| random | moderate | 15.03 ± 0.11 | 20.00 ± 0.00 | 33.58 ± 0.09 | 20.47 ± 0.04 | 214.0 | 1.0 |
| random | severe | 40.02 ± 0.12 | 50.00 ± 0.00 | 62.48 ± 0.05 | 51.96 ± 0.08 | 2137.0 | 3.6 |
| station | moderate | 14.97 ± 0.09 | 20.00 ± 0.00 | 30.60 ± 0.10 | 20.72 ± 0.03 | 110.6 | 2.4 |
| station | severe | 40.07 ± 0.11 | 50.00 ± 0.00 | 60.77 ± 0.11 | 52.32 ± 0.13 | 1513.0 | 7.2 |

## 6 Models and training construction

Both arms reuse the baseline RandomForestClassifier: n_estimators=200, criterion=gini, max_depth=None, min_samples_split=2, min_samples_leaf=1, max_features=sqrt, bootstrap=True, class_weight=balanced, n_jobs=-1. Full estimator parameters are recorded in `results/manifest.json`. No compact sensitivity or specialist extension was run. Only classifier fitting is needed; SHAP and anomaly models are not part of this comparison. Models are evaluated in memory and then released, so no new model binaries are required.

Replace variants: A receives N unchanged rows. B keeps N total rows and replaces floor(N/2) rows selected without replacement: floor(N/4) moderate and the remaining replaced rows severe. The labels and class counts remain exactly equal. Augment variants: A receives three clean copies (3N rows), while B receives clean + moderate + severe copies (3N rows), with identical repeated labels. The equal-size clean-duplication control was explicitly approved. Bootstrap resampling means this A can differ from the single-copy A; it is not claimed to be an independent threefold increase in information.

Baseline reproduction check, random protocol / replace without flags / seed 42: original stored clean accuracy 78.11548406%, refitted A 78.11548406%; original macro F1 76.49605696%, refitted A 76.49605696%. Match to 12 decimal places: True. This is a final audit check, not a tuning step; see results/baseline_reproduction.json.

## 7 Prespecified variants

| Variant | Training mode | Missingness flags |
| --- | --- | --- |
| Replace without flags | Replace N | None |
| Replace with flags | Replace N | Six flags for both arms |
| Augment without flags | Augment 3N | None |
| Augment with flags | Augment 3N | Six flags for both arms |

## 8 Validation and test protocols

Protocol 1 uses the existing stratified random 80/20 split, random_state=42. Protocol 2 uses the existing GroupShuffleSplit, n_splits=1, test_size=0.2, random_state=42 (87 training stations and 22 test stations). Changing final experiment seeds never changes either partition. These historical partitions have been used by previous project work; they are not newly collected blind external test data.

For each protocol, five-fold StratifiedKFold(shuffle=True, random_state=42) runs only inside its training partition. CV fold f uses model/degradation seed 42 + f×10000, for f=1..5. A validation row is never augmented into its fold training data. Validation is evaluated clean, moderate and severe. CV variability is across folds; it is not five seeds on one validation set, and the inner folds are not station-grouped.

After all CV runs completed, final fitting/evaluation used seeds 42,43,44,45,46. Each evaluation condition is created once for the protocol/seed (or CV fold), shared across variants, transformed using the same clean-training imputer, then passed as the same read-only matrix to A and B. Raw and transformed SHA-256 hashes verify identical inputs. Independent offsets distinguish training noise (+101/+202) from evaluation noise (+1001/+2001). No metric-driven tuning or selection occurred.

## 9 Metrics and uncertainty

Accuracy and macro F1 describe exact category classification; per-class F1 shows class-specific tradeoffs. Within-one-category uses the order Good, Satisfactory, Moderate, Poor, Very Poor, Severe and counts absolute ordinal distance ≤1; it is not a concentration error bound. All six classes enter F1, with zero_division=0. Tables show percentages as mean ± sample SD (ddof=1). Paired differences are B−A in percentage points; wins count strictly positive differences, so ties are not wins. Seed SD describes algorithm/degradation variability on fixed rows and is not a population confidence interval.

## 10 Prespecified decision rule

For each variant/protocol, **helps** requires mean severe macro-F1(B−A) > sample SD of the five paired severe macro-F1 differences **and** mean clean accuracy(B−A) ≥ −1 percentage point. Otherwise report **did not help under the rule**. This is the user’s fixed practical rule, not a significance test. It was recorded before any training in protocol.json and the preserved `results/prespecified_document.md`; its SHA-256 is `4e186a69da62832c85a14601cf241b5d72d361ce6b52e09b0abd8ab8b6a342c1`.

| Protocol | Variant | Severe F1 gain pp | Paired SD pp | Clean accuracy change pp | Severe F1 wins | Decision |
| --- | --- | --- | --- | --- | --- | --- |
| random | Replace without flags | -2.06 | 0.46 | -0.58 | 0/5 | Did not help |
| random | Replace with flags | -0.20 | 0.94 | -0.50 | 3/5 | Did not help |
| random | Augment without flags | -1.58 | 0.41 | -0.20 | 0/5 | Did not help |
| random | Augment with flags | 0.40 | 0.43 | -0.19 | 4/5 | Did not help |
| station | Replace without flags | 0.42 | 0.73 | -0.90 | 4/5 | Did not help |
| station | Replace with flags | 1.24 | 0.82 | -0.98 | 5/5 | Helps |
| station | Augment without flags | 0.82 | 0.34 | -0.83 | 5/5 | Helps |
| station | Augment with flags | 0.60 | 0.61 | -0.78 | 4/5 | Did not help |

- **random / Replace without flags:** severe macro F1 changed by -2.06 points and clean accuracy by -0.58 points. The rule failed because the severe macro-F1 gain did not exceed its paired SD.
- **random / Replace with flags:** severe macro F1 changed by -0.20 points and clean accuracy by -0.50 points. The rule failed because the severe macro-F1 gain did not exceed its paired SD.
- **random / Augment without flags:** severe macro F1 changed by -1.58 points and clean accuracy by -0.20 points. The rule failed because the severe macro-F1 gain did not exceed its paired SD.
- **random / Augment with flags:** severe macro F1 changed by +0.40 points and clean accuracy by -0.19 points. The rule failed because the severe macro-F1 gain did not exceed its paired SD.
- **station / Replace without flags:** severe macro F1 changed by +0.42 points and clean accuracy by -0.90 points. The rule failed because the severe macro-F1 gain did not exceed its paired SD.
- **station / Replace with flags:** severe macro F1 changed by +1.24 points and clean accuracy by -0.98 points. Both rule conditions passed.
- **station / Augment without flags:** severe macro F1 changed by +0.82 points and clean accuracy by -0.83 points. Both rule conditions passed.
- **station / Augment with flags:** severe macro F1 changed by +0.60 points and clean accuracy by -0.78 points. The rule failed because the severe macro-F1 gain did not exceed its paired SD.

## 11 Full results

### Final tests
Mean ± sample SD across five seeds. Each metric includes its paired difference and B wins.

#### Random protocol Accuracy
| Variant | Condition | A % | B % | B−A pp | B wins |
| --- | --- | --- | --- | --- | --- |
| Replace without flags | clean | 78.11 ± 0.11 | 77.53 ± 0.13 | -0.58 ± 0.15 | 0/5 |
| Replace without flags | moderate | 68.89 ± 0.22 | 67.40 ± 0.36 | -1.49 ± 0.20 | 0/5 |
| Replace without flags | severe | 51.50 ± 0.42 | 49.07 ± 0.20 | -2.43 ± 0.39 | 0/5 |
| Replace with flags | clean | 78.29 ± 0.10 | 77.79 ± 0.13 | -0.50 ± 0.20 | 0/5 |
| Replace with flags | moderate | 68.32 ± 0.25 | 67.15 ± 0.23 | -1.17 ± 0.17 | 0/5 |
| Replace with flags | severe | 50.14 ± 0.67 | 48.84 ± 0.14 | -1.30 ± 0.69 | 0/5 |
| Augment without flags | clean | 77.87 ± 0.14 | 77.67 ± 0.14 | -0.20 ± 0.25 | 1/5 |
| Augment without flags | moderate | 68.55 ± 0.33 | 67.58 ± 0.30 | -0.97 ± 0.31 | 0/5 |
| Augment without flags | severe | 51.14 ± 0.51 | 49.44 ± 0.29 | -1.70 ± 0.37 | 0/5 |
| Augment with flags | clean | 78.07 ± 0.07 | 77.88 ± 0.17 | -0.19 ± 0.18 | 1/5 |
| Augment with flags | moderate | 67.98 ± 0.34 | 67.43 ± 0.35 | -0.54 ± 0.35 | 0/5 |
| Augment with flags | severe | 49.77 ± 0.26 | 49.27 ± 0.46 | -0.50 ± 0.28 | 0/5 |

#### Random protocol Macro F1
| Variant | Condition | A % | B % | B−A pp | B wins |
| --- | --- | --- | --- | --- | --- |
| Replace without flags | clean | 76.51 ± 0.10 | 75.84 ± 0.09 | -0.67 ± 0.05 | 0/5 |
| Replace without flags | moderate | 65.85 ± 0.38 | 64.61 ± 0.29 | -1.25 ± 0.31 | 0/5 |
| Replace without flags | severe | 47.29 ± 0.48 | 45.23 ± 0.40 | -2.06 ± 0.46 | 0/5 |
| Replace with flags | clean | 76.81 ± 0.09 | 76.11 ± 0.13 | -0.70 ± 0.20 | 0/5 |
| Replace with flags | moderate | 65.32 ± 0.21 | 64.39 ± 0.24 | -0.93 ± 0.19 | 0/5 |
| Replace with flags | severe | 45.25 ± 0.98 | 45.05 ± 0.29 | -0.20 ± 0.94 | 3/5 |
| Augment without flags | clean | 76.32 ± 0.19 | 75.94 ± 0.28 | -0.38 ± 0.44 | 1/5 |
| Augment without flags | moderate | 65.59 ± 0.47 | 64.97 ± 0.39 | -0.62 ± 0.52 | 1/5 |
| Augment without flags | severe | 47.27 ± 0.56 | 45.69 ± 0.30 | -1.58 ± 0.41 | 0/5 |
| Augment with flags | clean | 76.60 ± 0.04 | 76.20 ± 0.24 | -0.40 ± 0.24 | 0/5 |
| Augment with flags | moderate | 64.99 ± 0.39 | 64.93 ± 0.42 | -0.06 ± 0.58 | 3/5 |
| Augment with flags | severe | 45.11 ± 0.42 | 45.51 ± 0.46 | 0.40 ± 0.43 | 4/5 |

#### Random protocol Within one category
| Variant | Condition | A % | B % | B−A pp | B wins |
| --- | --- | --- | --- | --- | --- |
| Replace without flags | clean | 99.03 ± 0.01 | 99.03 ± 0.01 | -0.00 ± 0.02 | 1/5 |
| Replace without flags | moderate | 96.59 ± 0.07 | 96.22 ± 0.06 | -0.37 ± 0.08 | 0/5 |
| Replace without flags | severe | 90.48 ± 0.17 | 88.77 ± 0.40 | -1.71 ± 0.42 | 0/5 |
| Replace with flags | clean | 99.02 ± 0.02 | 99.02 ± 0.03 | -0.00 ± 0.04 | 2/5 |
| Replace with flags | moderate | 95.97 ± 0.06 | 96.19 ± 0.15 | 0.22 ± 0.13 | 5/5 |
| Replace with flags | severe | 88.17 ± 0.49 | 88.55 ± 0.46 | 0.38 ± 0.61 | 3/5 |
| Augment without flags | clean | 99.00 ± 0.02 | 99.02 ± 0.02 | 0.01 ± 0.03 | 3/5 |
| Augment without flags | moderate | 96.51 ± 0.07 | 96.25 ± 0.04 | -0.26 ± 0.08 | 0/5 |
| Augment without flags | severe | 90.26 ± 0.12 | 88.84 ± 0.26 | -1.42 ± 0.22 | 0/5 |
| Augment with flags | clean | 99.00 ± 0.02 | 99.02 ± 0.02 | 0.02 ± 0.04 | 3/5 |
| Augment with flags | moderate | 95.91 ± 0.14 | 96.21 ± 0.11 | 0.30 ± 0.22 | 5/5 |
| Augment with flags | severe | 88.22 ± 0.32 | 88.75 ± 0.32 | 0.53 ± 0.22 | 5/5 |

#### Station protocol Accuracy
| Variant | Condition | A % | B % | B−A pp | B wins |
| --- | --- | --- | --- | --- | --- |
| Replace without flags | clean | 74.50 ± 0.12 | 73.60 ± 0.08 | -0.90 ± 0.18 | 0/5 |
| Replace without flags | moderate | 66.04 ± 0.26 | 64.63 ± 0.20 | -1.41 ± 0.17 | 0/5 |
| Replace without flags | severe | 50.35 ± 0.62 | 48.02 ± 0.56 | -2.33 ± 0.71 | 0/5 |
| Replace with flags | clean | 74.32 ± 0.08 | 73.34 ± 0.21 | -0.98 ± 0.25 | 0/5 |
| Replace with flags | moderate | 65.33 ± 0.32 | 64.28 ± 0.37 | -1.05 ± 0.30 | 0/5 |
| Replace with flags | severe | 48.89 ± 0.65 | 47.80 ± 0.42 | -1.09 ± 0.48 | 0/5 |
| Augment without flags | clean | 74.43 ± 0.21 | 73.60 ± 0.20 | -0.83 ± 0.31 | 0/5 |
| Augment without flags | moderate | 65.89 ± 0.41 | 64.73 ± 0.15 | -1.16 ± 0.34 | 0/5 |
| Augment without flags | severe | 49.94 ± 0.41 | 48.32 ± 0.56 | -1.62 ± 0.26 | 0/5 |
| Augment with flags | clean | 74.07 ± 0.07 | 73.29 ± 0.22 | -0.78 ± 0.26 | 0/5 |
| Augment with flags | moderate | 64.98 ± 0.34 | 64.40 ± 0.22 | -0.58 ± 0.15 | 0/5 |
| Augment with flags | severe | 48.59 ± 0.71 | 48.01 ± 0.38 | -0.58 ± 0.56 | 0/5 |

#### Station protocol Macro F1
| Variant | Condition | A % | B % | B−A pp | B wins |
| --- | --- | --- | --- | --- | --- |
| Replace without flags | clean | 73.09 ± 0.13 | 72.17 ± 0.16 | -0.93 ± 0.23 | 0/5 |
| Replace without flags | moderate | 63.01 ± 0.32 | 62.56 ± 0.27 | -0.45 ± 0.34 | 0/5 |
| Replace without flags | severe | 45.02 ± 0.55 | 45.44 ± 0.53 | 0.42 ± 0.73 | 4/5 |
| Replace with flags | clean | 72.97 ± 0.13 | 71.90 ± 0.25 | -1.07 ± 0.24 | 0/5 |
| Replace with flags | moderate | 62.69 ± 0.45 | 62.31 ± 0.42 | -0.38 ± 0.30 | 0/5 |
| Replace with flags | severe | 43.99 ± 1.02 | 45.23 ± 0.43 | 1.24 ± 0.82 | 5/5 |
| Augment without flags | clean | 72.88 ± 0.23 | 72.15 ± 0.34 | -0.73 ± 0.41 | 0/5 |
| Augment without flags | moderate | 62.85 ± 0.59 | 62.70 ± 0.23 | -0.15 ± 0.39 | 1/5 |
| Augment without flags | severe | 44.92 ± 0.55 | 45.75 ± 0.51 | 0.82 ± 0.34 | 5/5 |
| Augment with flags | clean | 72.65 ± 0.10 | 71.89 ± 0.26 | -0.76 ± 0.34 | 0/5 |
| Augment with flags | moderate | 62.45 ± 0.59 | 62.29 ± 0.29 | -0.16 ± 0.31 | 1/5 |
| Augment with flags | severe | 44.81 ± 0.75 | 45.41 ± 0.35 | 0.60 ± 0.61 | 4/5 |

#### Station protocol Within one category
| Variant | Condition | A % | B % | B−A pp | B wins |
| --- | --- | --- | --- | --- | --- |
| Replace without flags | clean | 97.97 ± 0.09 | 97.82 ± 0.09 | -0.15 ± 0.15 | 1/5 |
| Replace without flags | moderate | 95.73 ± 0.12 | 95.05 ± 0.17 | -0.68 ± 0.07 | 0/5 |
| Replace without flags | severe | 89.67 ± 0.25 | 87.68 ± 0.30 | -1.99 ± 0.27 | 0/5 |
| Replace with flags | clean | 98.02 ± 0.06 | 97.79 ± 0.18 | -0.23 ± 0.22 | 1/5 |
| Replace with flags | moderate | 94.89 ± 0.15 | 94.93 ± 0.22 | 0.04 ± 0.15 | 2/5 |
| Replace with flags | severe | 87.27 ± 0.67 | 87.53 ± 0.25 | 0.25 ± 0.48 | 3/5 |
| Augment without flags | clean | 98.04 ± 0.12 | 97.80 ± 0.09 | -0.24 ± 0.20 | 0/5 |
| Augment without flags | moderate | 95.72 ± 0.16 | 95.08 ± 0.17 | -0.64 ± 0.07 | 0/5 |
| Augment without flags | severe | 89.47 ± 0.30 | 87.92 ± 0.22 | -1.55 ± 0.39 | 0/5 |
| Augment with flags | clean | 98.06 ± 0.04 | 97.70 ± 0.11 | -0.36 ± 0.09 | 0/5 |
| Augment with flags | moderate | 94.75 ± 0.23 | 94.94 ± 0.13 | 0.20 ± 0.17 | 4/5 |
| Augment with flags | severe | 86.86 ± 0.34 | 87.76 ± 0.15 | 0.90 ± 0.35 | 5/5 |

### Cross validation
Mean ± sample SD across five folds. Each metric includes its paired difference and B wins.

#### Random protocol Accuracy
| Variant | Condition | A % | B % | B−A pp | B wins |
| --- | --- | --- | --- | --- | --- |
| Replace without flags | clean | 78.50 ± 0.45 | 77.95 ± 0.32 | -0.55 ± 0.15 | 0/5 |
| Replace without flags | moderate | 68.72 ± 0.29 | 67.42 ± 0.23 | -1.30 ± 0.47 | 0/5 |
| Replace without flags | severe | 51.27 ± 0.50 | 49.16 ± 0.39 | -2.11 ± 0.70 | 0/5 |
| Replace with flags | clean | 78.70 ± 0.43 | 78.10 ± 0.38 | -0.60 ± 0.28 | 0/5 |
| Replace with flags | moderate | 68.02 ± 0.32 | 67.25 ± 0.21 | -0.77 ± 0.49 | 1/5 |
| Replace with flags | severe | 49.86 ± 0.32 | 48.91 ± 0.34 | -0.95 ± 0.65 | 1/5 |
| Augment without flags | clean | 78.16 ± 0.34 | 77.96 ± 0.38 | -0.20 ± 0.09 | 0/5 |
| Augment without flags | moderate | 68.35 ± 0.29 | 67.61 ± 0.28 | -0.73 ± 0.38 | 0/5 |
| Augment without flags | severe | 50.95 ± 0.45 | 49.16 ± 0.54 | -1.79 ± 0.75 | 0/5 |
| Augment with flags | clean | 78.35 ± 0.34 | 78.28 ± 0.32 | -0.07 ± 0.07 | 1/5 |
| Augment with flags | moderate | 67.63 ± 0.25 | 67.36 ± 0.42 | -0.27 ± 0.43 | 2/5 |
| Augment with flags | severe | 49.37 ± 0.21 | 48.96 ± 0.58 | -0.41 ± 0.69 | 1/5 |

#### Random protocol Macro F1
| Variant | Condition | A % | B % | B−A pp | B wins |
| --- | --- | --- | --- | --- | --- |
| Replace without flags | clean | 77.00 ± 0.51 | 76.41 ± 0.35 | -0.59 ± 0.24 | 0/5 |
| Replace without flags | moderate | 65.60 ± 0.40 | 64.68 ± 0.28 | -0.92 ± 0.61 | 0/5 |
| Replace without flags | severe | 46.58 ± 1.09 | 45.31 ± 0.42 | -1.27 ± 1.08 | 0/5 |
| Replace with flags | clean | 77.18 ± 0.49 | 76.57 ± 0.43 | -0.61 ± 0.45 | 0/5 |
| Replace with flags | moderate | 64.95 ± 0.43 | 64.55 ± 0.29 | -0.40 ± 0.64 | 1/5 |
| Replace with flags | severe | 44.79 ± 0.97 | 45.09 ± 0.34 | 0.29 ± 1.19 | 2/5 |
| Augment without flags | clean | 76.65 ± 0.44 | 76.33 ± 0.42 | -0.32 ± 0.13 | 0/5 |
| Augment without flags | moderate | 65.25 ± 0.37 | 64.97 ± 0.19 | -0.28 ± 0.29 | 1/5 |
| Augment without flags | severe | 46.38 ± 1.00 | 45.31 ± 0.69 | -1.06 ± 0.90 | 1/5 |
| Augment with flags | clean | 76.86 ± 0.42 | 76.66 ± 0.40 | -0.20 ± 0.03 | 0/5 |
| Augment with flags | moderate | 64.58 ± 0.39 | 64.83 ± 0.38 | 0.24 ± 0.37 | 3/5 |
| Augment with flags | severe | 44.22 ± 0.85 | 45.05 ± 0.71 | 0.83 ± 0.98 | 4/5 |

#### Random protocol Within one category
| Variant | Condition | A % | B % | B−A pp | B wins |
| --- | --- | --- | --- | --- | --- |
| Replace without flags | clean | 99.10 ± 0.04 | 99.06 ± 0.05 | -0.04 ± 0.02 | 0/5 |
| Replace without flags | moderate | 96.57 ± 0.09 | 96.09 ± 0.19 | -0.49 ± 0.22 | 0/5 |
| Replace without flags | severe | 90.56 ± 0.32 | 88.77 ± 0.25 | -1.79 ± 0.37 | 0/5 |
| Replace with flags | clean | 99.09 ± 0.07 | 99.06 ± 0.03 | -0.03 ± 0.06 | 1/5 |
| Replace with flags | moderate | 96.03 ± 0.13 | 95.98 ± 0.16 | -0.05 ± 0.27 | 2/5 |
| Replace with flags | severe | 88.51 ± 0.24 | 88.60 ± 0.30 | 0.09 ± 0.35 | 4/5 |
| Augment without flags | clean | 99.08 ± 0.05 | 99.10 ± 0.05 | 0.03 ± 0.04 | 4/5 |
| Augment without flags | moderate | 96.50 ± 0.10 | 96.24 ± 0.12 | -0.26 ± 0.15 | 0/5 |
| Augment without flags | severe | 90.50 ± 0.32 | 88.86 ± 0.42 | -1.65 ± 0.62 | 0/5 |
| Augment with flags | clean | 99.08 ± 0.07 | 99.08 ± 0.05 | 0.01 ± 0.05 | 3/5 |
| Augment with flags | moderate | 95.87 ± 0.14 | 96.15 ± 0.06 | 0.27 ± 0.19 | 5/5 |
| Augment with flags | severe | 88.07 ± 0.23 | 88.66 ± 0.40 | 0.59 ± 0.47 | 4/5 |

#### Station protocol Accuracy
| Variant | Condition | A % | B % | B−A pp | B wins |
| --- | --- | --- | --- | --- | --- |
| Replace without flags | clean | 78.34 ± 0.25 | 77.75 ± 0.30 | -0.59 ± 0.24 | 0/5 |
| Replace without flags | moderate | 69.08 ± 0.39 | 67.13 ± 0.54 | -1.94 ± 0.36 | 0/5 |
| Replace without flags | severe | 53.74 ± 0.57 | 49.66 ± 0.21 | -4.08 ± 0.61 | 0/5 |
| Replace with flags | clean | 78.63 ± 0.30 | 78.11 ± 0.29 | -0.51 ± 0.21 | 0/5 |
| Replace with flags | moderate | 68.38 ± 0.43 | 66.96 ± 0.48 | -1.42 ± 0.48 | 0/5 |
| Replace with flags | severe | 51.77 ± 1.20 | 49.50 ± 0.20 | -2.28 ± 1.17 | 0/5 |
| Augment without flags | clean | 78.08 ± 0.31 | 78.01 ± 0.32 | -0.07 ± 0.32 | 2/5 |
| Augment without flags | moderate | 68.78 ± 0.49 | 67.43 ± 0.26 | -1.35 ± 0.41 | 0/5 |
| Augment without flags | severe | 53.43 ± 0.66 | 49.81 ± 0.54 | -3.62 ± 0.29 | 0/5 |
| Augment with flags | clean | 78.30 ± 0.27 | 78.24 ± 0.12 | -0.06 ± 0.16 | 2/5 |
| Augment with flags | moderate | 67.82 ± 0.55 | 67.24 ± 0.28 | -0.58 ± 0.53 | 1/5 |
| Augment with flags | severe | 51.23 ± 1.25 | 49.52 ± 0.48 | -1.71 ± 1.50 | 1/5 |

#### Station protocol Macro F1
| Variant | Condition | A % | B % | B−A pp | B wins |
| --- | --- | --- | --- | --- | --- |
| Replace without flags | clean | 76.49 ± 0.20 | 75.79 ± 0.34 | -0.70 ± 0.34 | 0/5 |
| Replace without flags | moderate | 65.12 ± 0.40 | 63.90 ± 0.49 | -1.23 ± 0.52 | 0/5 |
| Replace without flags | severe | 46.09 ± 0.56 | 45.01 ± 0.34 | -1.09 ± 0.59 | 0/5 |
| Replace with flags | clean | 76.84 ± 0.20 | 76.23 ± 0.30 | -0.61 ± 0.21 | 0/5 |
| Replace with flags | moderate | 64.80 ± 0.28 | 63.73 ± 0.46 | -1.07 ± 0.51 | 0/5 |
| Replace with flags | severe | 45.40 ± 1.28 | 44.73 ± 0.43 | -0.68 ± 1.16 | 1/5 |
| Augment without flags | clean | 76.25 ± 0.28 | 76.04 ± 0.34 | -0.21 ± 0.31 | 1/5 |
| Augment without flags | moderate | 64.92 ± 0.48 | 64.28 ± 0.30 | -0.64 ± 0.37 | 0/5 |
| Augment without flags | severe | 46.16 ± 0.62 | 45.03 ± 0.39 | -1.13 ± 0.54 | 0/5 |
| Augment with flags | clean | 76.48 ± 0.27 | 76.32 ± 0.18 | -0.17 ± 0.28 | 2/5 |
| Augment with flags | moderate | 64.29 ± 0.44 | 64.06 ± 0.31 | -0.23 ± 0.27 | 1/5 |
| Augment with flags | severe | 45.16 ± 0.58 | 44.74 ± 0.24 | -0.42 ± 0.53 | 1/5 |

#### Station protocol Within one category
| Variant | Condition | A % | B % | B−A pp | B wins |
| --- | --- | --- | --- | --- | --- |
| Replace without flags | clean | 99.11 ± 0.07 | 99.12 ± 0.03 | 0.01 ± 0.04 | 2/5 |
| Replace without flags | moderate | 96.76 ± 0.07 | 96.13 ± 0.17 | -0.63 ± 0.11 | 0/5 |
| Replace without flags | severe | 91.83 ± 0.33 | 89.17 ± 0.31 | -2.66 ± 0.11 | 0/5 |
| Replace with flags | clean | 99.10 ± 0.05 | 99.08 ± 0.04 | -0.01 ± 0.03 | 2/5 |
| Replace with flags | moderate | 96.15 ± 0.18 | 96.10 ± 0.12 | -0.05 ± 0.22 | 3/5 |
| Replace with flags | severe | 89.80 ± 0.69 | 88.99 ± 0.24 | -0.82 ± 0.81 | 1/5 |
| Augment without flags | clean | 99.08 ± 0.06 | 99.08 ± 0.08 | 0.00 ± 0.04 | 2/5 |
| Augment without flags | moderate | 96.69 ± 0.11 | 96.33 ± 0.15 | -0.36 ± 0.09 | 0/5 |
| Augment without flags | severe | 91.65 ± 0.28 | 89.26 ± 0.20 | -2.39 ± 0.28 | 0/5 |
| Augment with flags | clean | 99.07 ± 0.07 | 99.08 ± 0.08 | 0.00 ± 0.01 | 2/5 |
| Augment with flags | moderate | 95.95 ± 0.21 | 96.22 ± 0.11 | 0.27 ± 0.21 | 4/5 |
| Augment with flags | severe | 89.44 ± 0.48 | 88.99 ± 0.11 | -0.46 ± 0.56 | 1/5 |

### Severe confusion matrices
Rows are actual labels, columns predicted labels in the displayed order. Counts are summed over five seeds, so each held-out observation contributes five predictions; these are not five independent datasets. Individual seed matrices remain in run JSON files.

#### random Replace without flags Model A
| Actual / predicted | Good | Satisfactory | Moderate | Poor | Very Poor | Severe |
| --- | --- | --- | --- | --- | --- | --- |
| Good | 1901 | 3509 | 68 | 29 | 3 | 0 |
| Satisfactory | 3388 | 16268 | 3848 | 117 | 10 | 4 |
| Moderate | 1150 | 9524 | 15878 | 2507 | 337 | 19 |
| Poor | 186 | 1461 | 4626 | 3265 | 1804 | 153 |
| Very Poor | 73 | 659 | 2524 | 2362 | 4788 | 1354 |
| Severe | 47 | 255 | 709 | 482 | 1001 | 2716 |

#### random Replace without flags Model B
| Actual / predicted | Good | Satisfactory | Moderate | Poor | Very Poor | Severe |
| --- | --- | --- | --- | --- | --- | --- |
| Good | 1941 | 2838 | 591 | 68 | 53 | 19 |
| Satisfactory | 2419 | 13666 | 6439 | 648 | 340 | 123 |
| Moderate | 696 | 7609 | 16134 | 3260 | 1391 | 325 |
| Poor | 145 | 1115 | 4407 | 3058 | 2383 | 387 |
| Very Poor | 80 | 490 | 2147 | 2207 | 5385 | 1451 |
| Severe | 25 | 203 | 531 | 398 | 1535 | 2518 |

#### random Replace with flags Model A
| Actual / predicted | Good | Satisfactory | Moderate | Poor | Very Poor | Severe |
| --- | --- | --- | --- | --- | --- | --- |
| Good | 2192 | 3231 | 40 | 40 | 7 | 0 |
| Satisfactory | 3904 | 15971 | 3598 | 148 | 10 | 4 |
| Moderate | 1379 | 9664 | 16233 | 1783 | 343 | 13 |
| Poor | 250 | 1610 | 5535 | 2164 | 1817 | 119 |
| Very Poor | 119 | 782 | 3604 | 1333 | 4592 | 1330 |
| Severe | 68 | 290 | 1248 | 224 | 898 | 2482 |

#### random Replace with flags Model B
| Actual / predicted | Good | Satisfactory | Moderate | Poor | Very Poor | Severe |
| --- | --- | --- | --- | --- | --- | --- |
| Good | 1959 | 2822 | 580 | 75 | 57 | 17 |
| Satisfactory | 2423 | 13506 | 6515 | 685 | 372 | 134 |
| Moderate | 710 | 7512 | 16135 | 3280 | 1460 | 318 |
| Poor | 151 | 1131 | 4439 | 2949 | 2441 | 384 |
| Very Poor | 80 | 500 | 2149 | 2175 | 5446 | 1410 |
| Severe | 26 | 199 | 529 | 409 | 1539 | 2508 |

#### random Augment without flags Model A
| Actual / predicted | Good | Satisfactory | Moderate | Poor | Very Poor | Severe |
| --- | --- | --- | --- | --- | --- | --- |
| Good | 1974 | 3408 | 83 | 38 | 7 | 0 |
| Satisfactory | 3480 | 16082 | 3833 | 227 | 10 | 3 |
| Moderate | 1194 | 9431 | 15548 | 2885 | 339 | 18 |
| Poor | 194 | 1462 | 4496 | 3434 | 1750 | 159 |
| Very Poor | 75 | 653 | 2510 | 2411 | 4757 | 1354 |
| Severe | 50 | 247 | 694 | 515 | 998 | 2706 |

#### random Augment without flags Model B
| Actual / predicted | Good | Satisfactory | Moderate | Poor | Very Poor | Severe |
| --- | --- | --- | --- | --- | --- | --- |
| Good | 2009 | 2817 | 552 | 64 | 45 | 23 |
| Satisfactory | 2381 | 13698 | 6437 | 641 | 337 | 141 |
| Moderate | 746 | 7422 | 16273 | 3292 | 1377 | 305 |
| Poor | 147 | 1157 | 4334 | 3107 | 2416 | 334 |
| Very Poor | 78 | 478 | 2103 | 2251 | 5407 | 1443 |
| Severe | 32 | 195 | 518 | 437 | 1497 | 2531 |

#### random Augment with flags Model A
| Actual / predicted | Good | Satisfactory | Moderate | Poor | Very Poor | Severe |
| --- | --- | --- | --- | --- | --- | --- |
| Good | 2195 | 3203 | 43 | 53 | 15 | 1 |
| Satisfactory | 4037 | 15724 | 3613 | 222 | 32 | 7 |
| Moderate | 1482 | 9522 | 15994 | 2054 | 339 | 24 |
| Poor | 279 | 1582 | 5319 | 2410 | 1756 | 149 |
| Very Poor | 134 | 777 | 3376 | 1524 | 4409 | 1540 |
| Severe | 84 | 287 | 1094 | 270 | 891 | 2584 |

#### random Augment with flags Model B
| Actual / predicted | Good | Satisfactory | Moderate | Poor | Very Poor | Severe |
| --- | --- | --- | --- | --- | --- | --- |
| Good | 1997 | 2825 | 552 | 65 | 46 | 25 |
| Satisfactory | 2397 | 13604 | 6489 | 647 | 354 | 144 |
| Moderate | 738 | 7378 | 16250 | 3303 | 1431 | 315 |
| Poor | 150 | 1171 | 4356 | 3053 | 2443 | 322 |
| Very Poor | 80 | 484 | 2105 | 2203 | 5450 | 1438 |
| Severe | 32 | 198 | 503 | 425 | 1529 | 2523 |

#### station Replace without flags Model A
| Actual / predicted | Good | Satisfactory | Moderate | Poor | Very Poor | Severe |
| --- | --- | --- | --- | --- | --- | --- |
| Good | 755 | 3845 | 55 | 0 | 0 | 0 |
| Satisfactory | 563 | 11974 | 2567 | 21 | 5 | 0 |
| Moderate | 334 | 9142 | 15149 | 1779 | 284 | 17 |
| Poor | 71 | 1672 | 5273 | 3028 | 1543 | 173 |
| Very Poor | 71 | 705 | 2814 | 2532 | 3910 | 1183 |
| Severe | 34 | 174 | 702 | 694 | 1352 | 3319 |

#### station Replace without flags Model B
| Actual / predicted | Good | Satisfactory | Moderate | Poor | Very Poor | Severe |
| --- | --- | --- | --- | --- | --- | --- |
| Good | 1860 | 2357 | 366 | 35 | 30 | 7 |
| Satisfactory | 1557 | 9006 | 4026 | 275 | 186 | 80 |
| Moderate | 773 | 6751 | 15033 | 2623 | 1255 | 270 |
| Poor | 154 | 1201 | 5039 | 2856 | 2191 | 319 |
| Very Poor | 96 | 462 | 2639 | 2292 | 4567 | 1159 |
| Severe | 39 | 100 | 502 | 542 | 2045 | 3047 |

#### station Replace with flags Model A
| Actual / predicted | Good | Satisfactory | Moderate | Poor | Very Poor | Severe |
| --- | --- | --- | --- | --- | --- | --- |
| Good | 1107 | 3484 | 57 | 3 | 4 | 0 |
| Satisfactory | 910 | 11563 | 2616 | 34 | 7 | 0 |
| Moderate | 484 | 9085 | 15312 | 1526 | 287 | 11 |
| Poor | 91 | 1748 | 5983 | 2314 | 1504 | 120 |
| Very Poor | 88 | 752 | 3827 | 1679 | 3832 | 1037 |
| Severe | 40 | 195 | 1551 | 340 | 1245 | 2904 |

#### station Replace with flags Model B
| Actual / predicted | Good | Satisfactory | Moderate | Poor | Very Poor | Severe |
| --- | --- | --- | --- | --- | --- | --- |
| Good | 1876 | 2334 | 366 | 35 | 35 | 9 |
| Satisfactory | 1566 | 8912 | 4069 | 290 | 207 | 86 |
| Moderate | 786 | 6710 | 15018 | 2609 | 1311 | 271 |
| Poor | 149 | 1181 | 5079 | 2810 | 2235 | 306 |
| Very Poor | 96 | 466 | 2659 | 2280 | 4621 | 1093 |
| Severe | 40 | 106 | 487 | 561 | 2111 | 2970 |

#### station Augment without flags Model A
| Actual / predicted | Good | Satisfactory | Moderate | Poor | Very Poor | Severe |
| --- | --- | --- | --- | --- | --- | --- |
| Good | 857 | 3744 | 53 | 1 | 0 | 0 |
| Satisfactory | 869 | 11584 | 2649 | 22 | 6 | 0 |
| Moderate | 517 | 8891 | 15141 | 1860 | 279 | 17 |
| Poor | 96 | 1640 | 5256 | 3086 | 1509 | 173 |
| Very Poor | 79 | 683 | 2780 | 2613 | 3892 | 1168 |
| Severe | 37 | 170 | 702 | 721 | 1381 | 3264 |

#### station Augment without flags Model B
| Actual / predicted | Good | Satisfactory | Moderate | Poor | Very Poor | Severe |
| --- | --- | --- | --- | --- | --- | --- |
| Good | 1863 | 2356 | 347 | 39 | 30 | 20 |
| Satisfactory | 1585 | 9002 | 3959 | 321 | 183 | 80 |
| Moderate | 723 | 6776 | 15084 | 2613 | 1248 | 261 |
| Poor | 155 | 1170 | 5043 | 2921 | 2159 | 312 |
| Very Poor | 116 | 474 | 2502 | 2287 | 4685 | 1151 |
| Severe | 38 | 99 | 471 | 561 | 2065 | 3041 |

#### station Augment with flags Model A
| Actual / predicted | Good | Satisfactory | Moderate | Poor | Very Poor | Severe |
| --- | --- | --- | --- | --- | --- | --- |
| Good | 1637 | 2949 | 50 | 12 | 7 | 0 |
| Satisfactory | 1493 | 10944 | 2616 | 62 | 13 | 2 |
| Moderate | 768 | 8823 | 15216 | 1595 | 286 | 17 |
| Poor | 115 | 1728 | 5885 | 2420 | 1483 | 129 |
| Very Poor | 97 | 751 | 3755 | 1782 | 3766 | 1064 |
| Severe | 46 | 195 | 1535 | 383 | 1300 | 2816 |

#### station Augment with flags Model B
| Actual / predicted | Good | Satisfactory | Moderate | Poor | Very Poor | Severe |
| --- | --- | --- | --- | --- | --- | --- |
| Good | 1870 | 2346 | 345 | 44 | 31 | 19 |
| Satisfactory | 1602 | 8922 | 3997 | 340 | 191 | 78 |
| Moderate | 742 | 6722 | 15056 | 2645 | 1278 | 262 |
| Poor | 152 | 1167 | 5103 | 2861 | 2157 | 320 |
| Very Poor | 115 | 482 | 2527 | 2290 | 4667 | 1134 |
| Severe | 39 | 100 | 473 | 564 | 2112 | 2987 |

## 12 Interpretation and diagnostic

The decision table is the primary conclusion; improvements on severe inputs alone do not satisfy a rule that also protects clean accuracy. Compare replace and augment within each protocol rather than claiming one universal winner. Missingness flags may let the trees distinguish median-filled values from genuinely median-valued observations; degraded training may trade clean-data discrimination for stability. These mechanisms are plausible explanations, not causal findings from this experiment.

A prespecified descriptive check separates severe rows that required rescue after losing every observed value from other rows. These groups differ in original information content, so this is not a randomized ablation of the rescue procedure. The naturally-all-missing subgroup is also shown and overlaps the not-rescued group; the three rows are not a disjoint partition. The table reports mean accuracy difference, not a new tuning objective.

| Protocol | Variant | Subgroup | Rows mean | Accuracy B−A pp |
| --- | --- | --- | --- | --- |
| random | Replace without flags | rescued | 2137.0 | -6.15 ± 0.87 |
| random | Replace without flags | not_rescued | 15268.0 | -1.91 ± 0.45 |
| random | Replace without flags | naturally_all_missing | 56.0 | 0.00 ± 0.00 |
| random | Replace with flags | rescued | 2137.0 | -4.49 ± 0.75 |
| random | Replace with flags | not_rescued | 15268.0 | -0.85 ± 0.80 |
| random | Replace with flags | naturally_all_missing | 56.0 | 0.00 ± 0.00 |
| random | Augment without flags | rescued | 2137.0 | -4.44 ± 1.12 |
| random | Augment without flags | not_rescued | 15268.0 | -1.31 ± 0.45 |
| random | Augment without flags | naturally_all_missing | 56.0 | 0.00 ± 0.00 |
| random | Augment with flags | rescued | 2137.0 | -3.24 ± 1.22 |
| random | Augment with flags | not_rescued | 15268.0 | -0.12 ± 0.38 |
| random | Augment with flags | naturally_all_missing | 56.0 | 0.00 ± 0.00 |
| station | Replace without flags | rescued | 1513.0 | -7.39 ± 1.84 |
| station | Replace without flags | not_rescued | 13635.0 | -1.77 ± 0.69 |
| station | Replace without flags | naturally_all_missing | 69.0 | 0.00 ± 0.00 |
| station | Replace with flags | rescued | 1513.0 | -5.90 ± 0.86 |
| station | Replace with flags | not_rescued | 13635.0 | -0.55 ± 0.50 |
| station | Replace with flags | naturally_all_missing | 69.0 | 0.00 ± 0.00 |
| station | Augment without flags | rescued | 1513.0 | -7.04 ± 1.39 |
| station | Augment without flags | not_rescued | 13635.0 | -1.02 ± 0.31 |
| station | Augment without flags | naturally_all_missing | 69.0 | 0.00 ± 0.00 |
| station | Augment with flags | rescued | 1513.0 | -6.10 ± 1.38 |
| station | Augment with flags | not_rescued | 13635.0 | 0.04 ± 0.68 |
| station | Augment with flags | naturally_all_missing | 69.0 | 0.00 ± 0.00 |

## 13 Limitations

Degradation is simulated, and actual faults can be biased, correlated, drifting, censored or season-specific. Gas absence and row rescue interact. There is one India dataset, no time-based split and no Pakistani data. Natural missingness and 272 all-missing rows limit interpretation of “clean.” Augmentation repeats observations and does not create independent data. CV strata preserve classes but do not hold out stations within folds. Final seed repetitions reuse fixed test rows; no confidence interval or formal multiple-comparison test is claimed. Class labels are assumed valid and unchanged. Historical partitions have prior project exposure. Real-sensor reliability, probability calibration and regional transfer remain unverified. Optional compact and PM-specialist comparisons were not run. No app integration or deployment validation is claimed for these experimental classifiers.

## 14 Reproducibility and verification

Commands run from `<repository-root>`:

```powershell
backend/.venv/Scripts/python.exe -m unittest experiments.robustness.test_robustness backend.test_api backend.test_adaptability backend.test_large_imports -q
backend/.venv/Scripts/python.exe -m experiments.robustness.run --phase cv
backend/.venv/Scripts/python.exe -m experiments.robustness.run --phase test
backend/.venv/Scripts/python.exe -m experiments.robustness.run --phase verify
backend/.venv/Scripts/python.exe -m experiments.robustness.report
```

The initial combined test command passed 23 tests. A decision-rule boundary test was then added and all seven experiment tests passed separately. Final combined verification passed 24 tests; its output is recorded in results/tests.txt using the test command above followed by `2>&1 | Tee-Object -FilePath experiments/robustness/results/tests.txt`. Tests cover purity, realized operator rates, nonnegative noise, original missingness preservation, retention/rescue exception, training-only medians, flags, identical read-only paired inputs, labels/row counts, feature restrictions, disjoint partitions, baseline settings and both decision thresholds. The experiment’s runtime assertions additionally check paired matrix hashes and actual station IDs. Existing frozen-service integration was not rerun because deployed files were unchanged; preservation is verified by hashes.

During this session, `backend/.venv/Scripts/python.exe -m experiments.robustness.finish_run` queued the listed test, verification and reporting commands after all 40 CV checkpoints existed. It is an execution helper, not a separate scientific protocol. Do not run it alongside another final-test runner.

An initial CV launch failed before training because its output directory had not been created. The initialization was fixed before the first completed run; that failure produced no result numbers.

| Library | Version |
| --- | --- |
| python | 3.12.14 |
| numpy | 2.2.6 |
| pandas | 2.2.3 |
| scipy | 1.15.3 |
| sklearn | 1.6.1 |

Hardware observed during execution: Intel Core i5-1145G7 (4 physical cores, 8 logical processors), 24,838,364 KiB visible RAM. Other applications were running; this is not an isolated benchmark. The read-only hardware query is recorded in environment.json.

| Phase | Protocol | Variant | Recorded pair elapsed minutes |
| --- | --- | --- | --- |
| CV | random | Replace without flags | 3.67 |
| CV | random | Replace with flags | 3.01 |
| CV | random | Augment without flags | 8.93 |
| CV | random | Augment with flags | 379.15 |
| CV | station | Replace without flags | 3.36 |
| CV | station | Replace with flags | 248.38 |
| CV | station | Augment without flags | 610.38 |
| CV | station | Augment with flags | 9.01 |
| Test | random | Replace without flags | 4.41 |
| Test | random | Replace with flags | 3.34 |
| Test | random | Augment without flags | 10.35 |
| Test | random | Augment with flags | 134.84 |
| Test | station | Replace without flags | 2.43 |
| Test | station | Replace with flags | 1.94 |
| Test | station | Augment without flags | 6.38 |
| Test | station | Augment with flags | 6.02 |

Total recorded pair elapsed time: 1435.60 minutes. These perf_counter intervals measure wall time, not CPU time, and may include host/session suspension while a fit was active. Long elapsed intervals occurred during CV; their precise causes were not independently verified. Do not interpret the summed intervals as uninterrupted training compute. Tests, reporting and initialization are outside the pair timer. Manifest started UTC: 2026-10-15T12:48:53.800684+00:00. Report generated UTC: 2026-10-16T12:44:58.556187+00:00.

| Phase | Protocol | Unit | Variant | Arm | Elapsed seconds over 600 |
| --- | --- | --- | --- | --- | --- |
| cv | random | fold1 | augment_flags | B | 22294.81 |
| cv | station | fold2 | replace_flags | B | 14736.31 |
| test | random | seed42 | augment_flags | B | 7595.74 |

### File inventory

- `experiments/robustness/core.py`: reused definitions, filtering, operators, preprocessing, metrics and preservation hashes.
- `run.py`: resumable CV/test runner; it rejects mixed code/data and requires complete CV before tests.
- `protocol.json`: immutable experiment choices.
- `test_robustness.py`: automated experiment controls.
- `report.py`: generates every report table from run outputs.
- `.gitignore`: local binary exclusions. No model binary is saved.
- `results/manifest.json`: filtering, classes, exact split source-row IDs, library/estimator configuration and hashes.
- `results/prespecified_document.md`: report snapshot before training.
- `results/cv/*.json`: 40 paired fold/variant records, 80 trained forests.
- `results/test/*.json`: 40 paired seed/variant records, 80 trained forests.
- `results/metrics.csv`: all 480 arm/condition records with per-class metrics.
- `results/summary.csv`: all 432 aggregated metric records with paired SD and wins.
- `results/decisions.json`: eight fixed-rule outcomes.
- `results/preservation_check.json`: final protected-file verification.
- `docs/ROBUSTNESS_EXPERIMENT.md`: this complete narrative and tables.

Additional experiment files: `docs/ROBUSTNESS_RUN_GUIDE.md` documents execution/resume; `finish_run.py` queues final phases; `environment.json` records hardware; `results/tests.txt` records the final test suite; `results/report_manifest.json` records report/test code hashes and integrity checks. The Markdown file under results is an immutable pre-run evidence snapshot, not a maintained document.

All 59 protected dataset, deployed-artifact and active source/configuration files matched their pre-run SHA-256 values at report generation. Run files contain model seeds, fold identifiers, medians, paired input hashes, row counts and degradation statistics.

## 15 Next steps

Keep deployment unchanged. A follow-up could lock a temporal and external-region test set, evaluate real sensor dropout/noise, assess calibration and class-specific costs, and repeat with grouped inner CV. If compact forests or specialist comparisons are desired, preregister them as separate sensitivity experiments and report every result. Do not use this test set to select a new degradation recipe and then present its score as independent validation.

## Appendix Per class F1 for every condition

Each row reports A and B mean ± sample SD, paired B−A in percentage points and B wins. Test rows vary across five seeds; CV rows vary across five folds. All class-specific results are included.

### Test random
| Variant | Condition | Class | A F1 % | B F1 % | B−A pp | B wins |
| --- | --- | --- | --- | --- | --- | --- |
| Replace without flags | clean | Good | 72.11 ± 0.16 | 70.42 ± 0.43 | -1.69 ± 0.50 | 0/5 |
| Replace without flags | clean | Satisfactory | 80.91 ± 0.06 | 80.12 ± 0.26 | -0.79 ± 0.29 | 0/5 |
| Replace without flags | clean | Moderate | 81.19 ± 0.09 | 80.69 ± 0.24 | -0.50 ± 0.27 | 0/5 |
| Replace without flags | clean | Poor | 65.03 ± 0.42 | 64.20 ± 0.31 | -0.83 ± 0.41 | 0/5 |
| Replace without flags | clean | Very Poor | 78.25 ± 0.25 | 78.25 ± 0.22 | -0.00 ± 0.16 | 3/5 |
| Replace without flags | clean | Severe | 81.58 ± 0.16 | 81.37 ± 0.51 | -0.21 ± 0.61 | 2/5 |
| Replace without flags | moderate | Good | 51.31 ± 1.49 | 55.54 ± 0.39 | 4.23 ± 1.64 | 5/5 |
| Replace without flags | moderate | Satisfactory | 72.65 ± 0.10 | 70.95 ± 0.62 | -1.70 ± 0.52 | 0/5 |
| Replace without flags | moderate | Moderate | 72.83 ± 0.10 | 71.68 ± 0.47 | -1.15 ± 0.38 | 0/5 |
| Replace without flags | moderate | Poor | 54.02 ± 0.51 | 50.98 ± 0.66 | -3.04 ± 0.45 | 0/5 |
| Replace without flags | moderate | Very Poor | 69.44 ± 0.49 | 67.63 ± 0.66 | -1.81 ± 0.77 | 0/5 |
| Replace without flags | moderate | Severe | 74.88 ± 0.59 | 70.87 ± 0.57 | -4.00 ± 0.84 | 0/5 |
| Replace without flags | severe | Good | 31.02 ± 1.05 | 35.88 ± 1.63 | 4.86 ± 1.27 | 5/5 |
| Replace without flags | severe | Satisfactory | 58.82 ± 0.31 | 55.16 ± 0.29 | -3.67 ± 0.38 | 0/5 |
| Replace without flags | severe | Moderate | 55.64 ± 0.49 | 54.08 ± 0.49 | -1.56 ± 0.43 | 0/5 |
| Replace without flags | severe | Poor | 32.24 ± 1.10 | 28.94 ± 0.72 | -3.30 ± 1.20 | 0/5 |
| Replace without flags | severe | Very Poor | 48.60 ± 1.33 | 47.14 ± 0.89 | -1.45 ± 1.49 | 1/5 |
| Replace without flags | severe | Severe | 57.44 ± 1.08 | 50.19 ± 1.81 | -7.25 ± 1.47 | 0/5 |
| Replace with flags | clean | Good | 73.15 ± 0.21 | 71.03 ± 0.45 | -2.13 ± 0.43 | 0/5 |
| Replace with flags | clean | Satisfactory | 81.26 ± 0.09 | 80.59 ± 0.28 | -0.67 ± 0.29 | 0/5 |
| Replace with flags | clean | Moderate | 81.14 ± 0.11 | 80.93 ± 0.19 | -0.21 ± 0.23 | 1/5 |
| Replace with flags | clean | Poor | 64.90 ± 0.33 | 64.32 ± 0.14 | -0.58 ± 0.34 | 0/5 |
| Replace with flags | clean | Very Poor | 78.49 ± 0.11 | 78.17 ± 0.24 | -0.31 ± 0.31 | 1/5 |
| Replace with flags | clean | Severe | 81.92 ± 0.14 | 81.63 ± 0.54 | -0.29 ± 0.54 | 1/5 |
| Replace with flags | moderate | Good | 52.94 ± 1.27 | 55.58 ± 0.76 | 2.64 ± 1.28 | 5/5 |
| Replace with flags | moderate | Satisfactory | 72.45 ± 0.28 | 70.69 ± 0.46 | -1.76 ± 0.57 | 0/5 |
| Replace with flags | moderate | Moderate | 72.00 ± 0.26 | 71.43 ± 0.38 | -0.56 ± 0.36 | 0/5 |
| Replace with flags | moderate | Poor | 51.83 ± 0.53 | 50.13 ± 0.51 | -1.70 ± 0.50 | 0/5 |
| Replace with flags | moderate | Very Poor | 69.15 ± 0.45 | 67.81 ± 0.54 | -1.34 ± 0.76 | 0/5 |
| Replace with flags | moderate | Severe | 73.56 ± 0.31 | 70.68 ± 0.84 | -2.87 ± 1.04 | 0/5 |
| Replace with flags | severe | Good | 32.66 ± 0.69 | 36.06 ± 1.61 | 3.40 ± 1.02 | 5/5 |
| Replace with flags | severe | Satisfactory | 57.88 ± 0.36 | 54.79 ± 0.32 | -3.10 ± 0.41 | 0/5 |
| Replace with flags | severe | Moderate | 54.41 ± 0.77 | 54.00 ± 0.39 | -0.42 ± 0.88 | 2/5 |
| Replace with flags | severe | Poor | 25.14 ± 2.20 | 27.99 ± 0.39 | 2.85 ± 2.24 | 5/5 |
| Replace with flags | severe | Very Poor | 47.27 ± 1.34 | 47.20 ± 0.65 | -0.06 ± 1.61 | 3/5 |
| Replace with flags | severe | Severe | 54.15 ± 2.57 | 50.26 ± 1.32 | -3.89 ± 1.27 | 0/5 |
| Augment without flags | clean | Good | 72.10 ± 0.33 | 70.73 ± 0.94 | -1.37 ± 1.13 | 0/5 |
| Augment without flags | clean | Satisfactory | 80.66 ± 0.10 | 80.27 ± 0.07 | -0.40 ± 0.16 | 0/5 |
| Augment without flags | clean | Moderate | 80.94 ± 0.10 | 80.91 ± 0.13 | -0.04 ± 0.12 | 1/5 |
| Augment without flags | clean | Poor | 64.59 ± 0.37 | 64.52 ± 0.28 | -0.07 ± 0.53 | 2/5 |
| Augment without flags | clean | Very Poor | 78.11 ± 0.23 | 78.11 ± 0.23 | -0.00 ± 0.35 | 2/5 |
| Augment without flags | clean | Severe | 81.53 ± 0.36 | 81.12 ± 0.55 | -0.41 ± 0.74 | 2/5 |
| Augment without flags | moderate | Good | 51.39 ± 1.49 | 57.17 ± 0.56 | 5.78 ± 1.81 | 5/5 |
| Augment without flags | moderate | Satisfactory | 72.45 ± 0.28 | 71.00 ± 0.37 | -1.45 ± 0.39 | 0/5 |
| Augment without flags | moderate | Moderate | 72.42 ± 0.36 | 71.83 ± 0.20 | -0.59 ± 0.28 | 0/5 |
| Augment without flags | moderate | Poor | 53.60 ± 0.80 | 50.65 ± 1.24 | -2.95 ± 1.06 | 0/5 |
| Augment without flags | moderate | Very Poor | 69.27 ± 0.50 | 67.97 ± 0.42 | -1.30 ± 0.47 | 0/5 |
| Augment without flags | moderate | Severe | 74.42 ± 0.78 | 71.19 ± 0.63 | -3.23 ± 0.41 | 0/5 |
| Augment without flags | severe | Good | 31.65 ± 0.89 | 36.85 ± 0.63 | 5.21 ± 1.02 | 5/5 |
| Augment without flags | severe | Satisfactory | 58.57 ± 0.42 | 55.45 ± 0.32 | -3.11 ± 0.18 | 0/5 |
| Augment without flags | severe | Moderate | 54.96 ± 0.69 | 54.58 ± 0.60 | -0.38 ± 0.59 | 1/5 |
| Augment without flags | severe | Poor | 32.69 ± 1.36 | 29.19 ± 0.50 | -3.50 ± 1.35 | 0/5 |
| Augment without flags | severe | Very Poor | 48.48 ± 1.12 | 47.35 ± 0.86 | -1.13 ± 1.13 | 1/5 |
| Augment without flags | severe | Severe | 57.27 ± 1.22 | 50.68 ± 1.25 | -6.59 ± 1.05 | 0/5 |
| Augment with flags | clean | Good | 73.13 ± 0.29 | 71.62 ± 0.57 | -1.50 ± 0.75 | 0/5 |
| Augment with flags | clean | Satisfactory | 81.05 ± 0.06 | 80.75 ± 0.08 | -0.30 ± 0.14 | 0/5 |
| Augment with flags | clean | Moderate | 80.98 ± 0.15 | 81.02 ± 0.17 | 0.04 ± 0.26 | 2/5 |
| Augment with flags | clean | Poor | 64.73 ± 0.20 | 64.43 ± 0.27 | -0.30 ± 0.36 | 1/5 |
| Augment with flags | clean | Very Poor | 78.07 ± 0.09 | 78.08 ± 0.39 | 0.01 ± 0.32 | 2/5 |
| Augment with flags | clean | Severe | 81.65 ± 0.24 | 81.31 ± 0.42 | -0.34 ± 0.20 | 0/5 |
| Augment with flags | moderate | Good | 52.80 ± 1.33 | 57.70 ± 0.53 | 4.89 ± 1.67 | 5/5 |
| Augment with flags | moderate | Satisfactory | 72.10 ± 0.42 | 70.82 ± 0.43 | -1.28 ± 0.25 | 0/5 |
| Augment with flags | moderate | Moderate | 71.87 ± 0.21 | 71.64 ± 0.21 | -0.23 ± 0.22 | 0/5 |
| Augment with flags | moderate | Poor | 51.57 ± 0.76 | 50.33 ± 1.07 | -1.24 ± 1.10 | 1/5 |
| Augment with flags | moderate | Very Poor | 68.57 ± 0.57 | 67.88 ± 0.48 | -0.68 ± 0.60 | 0/5 |
| Augment with flags | moderate | Severe | 73.02 ± 0.62 | 71.24 ± 0.43 | -1.79 ± 0.90 | 0/5 |
| Augment with flags | severe | Good | 31.99 ± 0.33 | 36.63 ± 0.64 | 4.63 ± 0.42 | 5/5 |
| Augment with flags | severe | Satisfactory | 57.46 ± 0.35 | 55.19 ± 0.36 | -2.27 ± 0.19 | 0/5 |
| Augment with flags | severe | Moderate | 54.35 ± 0.52 | 54.47 ± 0.74 | 0.12 ± 0.64 | 3/5 |
| Augment with flags | severe | Poor | 26.72 ± 1.51 | 28.81 ± 0.72 | 2.09 ± 0.93 | 5/5 |
| Augment with flags | severe | Very Poor | 45.91 ± 1.17 | 47.37 ± 0.70 | 1.45 ± 0.99 | 5/5 |
| Augment with flags | severe | Severe | 54.23 ± 2.90 | 50.58 ± 1.09 | -3.66 ± 2.93 | 1/5 |

### Test station
| Variant | Condition | Class | A F1 % | B F1 % | B−A pp | B wins |
| --- | --- | --- | --- | --- | --- | --- |
| Replace without flags | clean | Good | 71.67 ± 0.32 | 71.91 ± 1.00 | 0.24 ± 0.98 | 2/5 |
| Replace without flags | clean | Satisfactory | 77.47 ± 0.16 | 76.22 ± 0.29 | -1.26 ± 0.40 | 0/5 |
| Replace without flags | clean | Moderate | 79.64 ± 0.18 | 78.98 ± 0.22 | -0.66 ± 0.38 | 0/5 |
| Replace without flags | clean | Poor | 58.22 ± 0.27 | 56.80 ± 0.50 | -1.42 ± 0.63 | 0/5 |
| Replace without flags | clean | Very Poor | 70.59 ± 0.22 | 69.88 ± 0.29 | -0.71 ± 0.46 | 1/5 |
| Replace without flags | clean | Severe | 80.97 ± 0.40 | 79.21 ± 0.39 | -1.76 ± 0.53 | 0/5 |
| Replace without flags | moderate | Good | 50.32 ± 1.70 | 59.42 ± 0.78 | 9.11 ± 1.48 | 5/5 |
| Replace without flags | moderate | Satisfactory | 68.69 ± 0.37 | 67.22 ± 0.27 | -1.47 ± 0.40 | 0/5 |
| Replace without flags | moderate | Moderate | 72.33 ± 0.33 | 71.32 ± 0.27 | -1.02 ± 0.19 | 0/5 |
| Replace without flags | moderate | Poor | 49.12 ± 0.48 | 45.67 ± 0.42 | -3.45 ± 0.45 | 0/5 |
| Replace without flags | moderate | Very Poor | 62.27 ± 0.54 | 59.99 ± 0.73 | -2.28 ± 0.32 | 0/5 |
| Replace without flags | moderate | Severe | 75.34 ± 0.43 | 71.75 ± 0.80 | -3.60 ± 0.58 | 0/5 |
| Replace without flags | severe | Good | 23.30 ± 0.46 | 40.72 ± 1.55 | 17.42 ± 1.80 | 5/5 |
| Replace without flags | severe | Satisfactory | 56.16 ± 0.68 | 51.45 ± 0.74 | -4.71 ± 0.78 | 0/5 |
| Replace without flags | severe | Moderate | 56.88 ± 0.63 | 55.36 ± 0.47 | -1.52 ± 0.78 | 0/5 |
| Replace without flags | severe | Poor | 30.56 ± 1.07 | 28.01 ± 0.94 | -2.55 ± 1.77 | 0/5 |
| Replace without flags | severe | Very Poor | 42.71 ± 1.02 | 42.50 ± 1.04 | -0.21 ± 0.30 | 2/5 |
| Replace without flags | severe | Severe | 60.53 ± 0.69 | 54.62 ± 1.19 | -5.91 ± 0.94 | 0/5 |
| Replace with flags | clean | Good | 73.91 ± 0.36 | 73.08 ± 0.77 | -0.83 ± 0.60 | 0/5 |
| Replace with flags | clean | Satisfactory | 77.55 ± 0.21 | 76.46 ± 0.39 | -1.08 ± 0.51 | 0/5 |
| Replace with flags | clean | Moderate | 79.74 ± 0.12 | 79.06 ± 0.26 | -0.68 ± 0.33 | 0/5 |
| Replace with flags | clean | Poor | 57.44 ± 0.36 | 56.10 ± 0.38 | -1.34 ± 0.37 | 0/5 |
| Replace with flags | clean | Very Poor | 69.54 ± 0.35 | 68.30 ± 0.21 | -1.24 ± 0.34 | 0/5 |
| Replace with flags | clean | Severe | 79.67 ± 0.38 | 78.41 ± 0.50 | -1.26 ± 0.58 | 0/5 |
| Replace with flags | moderate | Good | 54.46 ± 2.07 | 61.26 ± 0.96 | 6.80 ± 1.86 | 5/5 |
| Replace with flags | moderate | Satisfactory | 68.53 ± 0.65 | 67.06 ± 0.50 | -1.47 ± 0.57 | 0/5 |
| Replace with flags | moderate | Moderate | 71.32 ± 0.23 | 71.03 ± 0.39 | -0.29 ± 0.46 | 1/5 |
| Replace with flags | moderate | Poor | 46.48 ± 0.40 | 44.99 ± 0.93 | -1.49 ± 1.01 | 1/5 |
| Replace with flags | moderate | Very Poor | 61.18 ± 0.65 | 59.15 ± 0.57 | -2.03 ± 0.38 | 0/5 |
| Replace with flags | moderate | Severe | 74.19 ± 0.24 | 70.38 ± 0.68 | -3.82 ± 0.83 | 0/5 |
| Replace with flags | severe | Good | 29.57 ± 5.69 | 40.92 ± 1.50 | 11.36 ± 5.66 | 5/5 |
| Replace with flags | severe | Satisfactory | 55.11 ± 0.73 | 51.16 ± 0.82 | -3.95 ± 0.55 | 0/5 |
| Replace with flags | severe | Moderate | 54.64 ± 0.93 | 55.23 ± 0.18 | 0.59 ± 0.79 | 3/5 |
| Replace with flags | severe | Poor | 26.21 ± 0.79 | 27.62 ± 0.37 | 1.41 ± 0.95 | 4/5 |
| Replace with flags | severe | Very Poor | 42.36 ± 0.94 | 42.52 ± 0.97 | 0.16 ± 0.59 | 2/5 |
| Replace with flags | severe | Severe | 56.07 ± 2.39 | 53.94 ± 1.46 | -2.13 ± 2.75 | 2/5 |
| Augment without flags | clean | Good | 71.04 ± 0.21 | 72.38 ± 0.72 | 1.35 ± 0.60 | 5/5 |
| Augment without flags | clean | Satisfactory | 77.03 ± 0.12 | 76.38 ± 0.31 | -0.64 ± 0.40 | 0/5 |
| Augment without flags | clean | Moderate | 79.94 ± 0.26 | 78.99 ± 0.16 | -0.95 ± 0.38 | 0/5 |
| Augment without flags | clean | Poor | 59.29 ± 0.65 | 56.69 ± 0.59 | -2.60 ± 0.86 | 0/5 |
| Augment without flags | clean | Very Poor | 70.13 ± 0.22 | 69.85 ± 0.43 | -0.27 ± 0.29 | 1/5 |
| Augment without flags | clean | Severe | 79.89 ± 0.25 | 78.62 ± 1.09 | -1.26 ± 1.09 | 0/5 |
| Augment without flags | moderate | Good | 50.29 ± 1.87 | 60.24 ± 1.32 | 9.94 ± 1.56 | 5/5 |
| Augment without flags | moderate | Satisfactory | 68.37 ± 0.54 | 67.46 ± 0.41 | -0.91 ± 0.62 | 0/5 |
| Augment without flags | moderate | Moderate | 72.45 ± 0.28 | 71.36 ± 0.15 | -1.08 ± 0.21 | 0/5 |
| Augment without flags | moderate | Poor | 49.39 ± 0.57 | 46.02 ± 0.74 | -3.37 ± 1.05 | 0/5 |
| Augment without flags | moderate | Very Poor | 61.93 ± 0.58 | 59.74 ± 0.68 | -2.20 ± 0.45 | 0/5 |
| Augment without flags | moderate | Severe | 74.66 ± 0.89 | 71.40 ± 0.86 | -3.26 ± 1.22 | 0/5 |
| Augment without flags | severe | Good | 24.08 ± 1.05 | 40.79 ± 1.20 | 16.71 ± 1.12 | 5/5 |
| Augment without flags | severe | Satisfactory | 55.37 ± 0.62 | 51.43 ± 0.76 | -3.94 ± 0.69 | 0/5 |
| Augment without flags | severe | Moderate | 56.83 ± 0.66 | 55.75 ± 0.77 | -1.08 ± 0.20 | 0/5 |
| Augment without flags | severe | Poor | 30.77 ± 0.86 | 28.49 ± 0.52 | -2.27 ± 0.60 | 0/5 |
| Augment without flags | severe | Very Poor | 42.58 ± 0.92 | 43.41 ± 0.57 | 0.83 ± 0.71 | 4/5 |
| Augment without flags | severe | Severe | 59.90 ± 1.09 | 54.60 ± 0.69 | -5.30 ± 1.06 | 0/5 |
| Augment with flags | clean | Good | 73.62 ± 0.16 | 73.83 ± 0.29 | 0.21 ± 0.41 | 4/5 |
| Augment with flags | clean | Satisfactory | 77.18 ± 0.15 | 76.62 ± 0.26 | -0.56 ± 0.24 | 0/5 |
| Augment with flags | clean | Moderate | 79.74 ± 0.09 | 78.86 ± 0.33 | -0.88 ± 0.35 | 0/5 |
| Augment with flags | clean | Poor | 57.38 ± 0.39 | 55.96 ± 0.61 | -1.42 ± 0.88 | 0/5 |
| Augment with flags | clean | Very Poor | 69.00 ± 0.13 | 68.36 ± 0.38 | -0.64 ± 0.49 | 0/5 |
| Augment with flags | clean | Severe | 78.94 ± 0.43 | 77.70 ± 0.77 | -1.25 ± 1.15 | 0/5 |
| Augment with flags | moderate | Good | 54.87 ± 2.63 | 60.80 ± 0.83 | 5.94 ± 2.44 | 5/5 |
| Augment with flags | moderate | Satisfactory | 67.84 ± 0.71 | 67.49 ± 0.21 | -0.35 ± 0.81 | 1/5 |
| Augment with flags | moderate | Moderate | 71.17 ± 0.22 | 71.31 ± 0.24 | 0.14 ± 0.11 | 5/5 |
| Augment with flags | moderate | Poor | 46.62 ± 0.73 | 45.01 ± 0.91 | -1.61 ± 0.45 | 0/5 |
| Augment with flags | moderate | Very Poor | 60.80 ± 0.38 | 58.62 ± 0.57 | -2.18 ± 0.53 | 0/5 |
| Augment with flags | moderate | Severe | 73.40 ± 0.29 | 70.51 ± 1.18 | -2.90 ± 1.40 | 0/5 |
| Augment with flags | severe | Good | 37.07 ± 3.31 | 40.76 ± 0.95 | 3.69 ± 2.60 | 4/5 |
| Augment with flags | severe | Satisfactory | 54.02 ± 0.77 | 51.17 ± 0.78 | -2.85 ± 1.06 | 0/5 |
| Augment with flags | severe | Moderate | 54.57 ± 0.72 | 55.55 ± 0.54 | 0.98 ± 0.50 | 5/5 |
| Augment with flags | severe | Poor | 26.87 ± 0.49 | 27.91 ± 0.34 | 1.04 ± 0.49 | 5/5 |
| Augment with flags | severe | Very Poor | 41.68 ± 0.97 | 43.11 ± 0.53 | 1.43 ± 0.91 | 5/5 |
| Augment with flags | severe | Severe | 54.63 ± 1.54 | 53.94 ± 0.80 | -0.69 ± 1.99 | 3/5 |

### CV random
| Variant | Condition | Class | A F1 % | B F1 % | B−A pp | B wins |
| --- | --- | --- | --- | --- | --- | --- |
| Replace without flags | clean | Good | 73.08 ± 0.72 | 72.16 ± 1.30 | -0.92 ± 0.95 | 1/5 |
| Replace without flags | clean | Satisfactory | 81.27 ± 0.47 | 80.51 ± 0.52 | -0.77 ± 0.20 | 0/5 |
| Replace without flags | clean | Moderate | 81.26 ± 0.39 | 80.81 ± 0.33 | -0.44 ± 0.19 | 0/5 |
| Replace without flags | clean | Poor | 65.72 ± 1.06 | 65.31 ± 0.73 | -0.41 ± 0.81 | 1/5 |
| Replace without flags | clean | Very Poor | 78.95 ± 0.75 | 78.62 ± 0.31 | -0.34 ± 0.69 | 1/5 |
| Replace without flags | clean | Severe | 81.70 ± 1.10 | 81.07 ± 0.87 | -0.64 ± 0.57 | 0/5 |
| Replace without flags | moderate | Good | 51.10 ± 1.22 | 56.27 ± 1.48 | 5.17 ± 1.36 | 5/5 |
| Replace without flags | moderate | Satisfactory | 72.62 ± 0.21 | 71.15 ± 0.45 | -1.47 ± 0.54 | 0/5 |
| Replace without flags | moderate | Moderate | 72.48 ± 0.34 | 71.33 ± 0.51 | -1.16 ± 0.50 | 0/5 |
| Replace without flags | moderate | Poor | 53.80 ± 1.03 | 50.51 ± 1.04 | -3.29 ± 1.00 | 0/5 |
| Replace without flags | moderate | Very Poor | 69.48 ± 0.97 | 68.14 ± 1.32 | -1.34 ± 1.13 | 1/5 |
| Replace without flags | moderate | Severe | 74.11 ± 1.50 | 70.70 ± 1.51 | -3.41 ± 0.66 | 0/5 |
| Replace without flags | severe | Good | 29.35 ± 4.03 | 37.06 ± 1.70 | 7.70 ± 4.11 | 5/5 |
| Replace without flags | severe | Satisfactory | 58.57 ± 1.28 | 55.25 ± 0.38 | -3.32 ± 1.37 | 0/5 |
| Replace without flags | severe | Moderate | 55.92 ± 0.63 | 54.28 ± 0.41 | -1.64 ± 0.72 | 0/5 |
| Replace without flags | severe | Poor | 31.96 ± 0.96 | 29.37 ± 0.52 | -2.59 ± 1.46 | 0/5 |
| Replace without flags | severe | Very Poor | 47.69 ± 2.15 | 46.53 ± 1.42 | -1.16 ± 2.07 | 2/5 |
| Replace without flags | severe | Severe | 56.01 ± 1.16 | 49.37 ± 1.94 | -6.64 ± 0.96 | 0/5 |
| Replace with flags | clean | Good | 73.84 ± 0.83 | 72.85 ± 1.37 | -0.99 ± 1.03 | 0/5 |
| Replace with flags | clean | Satisfactory | 81.72 ± 0.45 | 80.85 ± 0.58 | -0.86 ± 0.36 | 0/5 |
| Replace with flags | clean | Moderate | 81.44 ± 0.42 | 80.89 ± 0.38 | -0.55 ± 0.21 | 0/5 |
| Replace with flags | clean | Poor | 65.62 ± 0.90 | 64.99 ± 0.81 | -0.64 ± 0.74 | 1/5 |
| Replace with flags | clean | Very Poor | 78.92 ± 0.76 | 78.69 ± 0.19 | -0.23 ± 0.65 | 2/5 |
| Replace with flags | clean | Severe | 81.54 ± 1.24 | 81.16 ± 1.18 | -0.38 ± 0.71 | 2/5 |
| Replace with flags | moderate | Good | 52.45 ± 1.05 | 56.47 ± 1.88 | 4.02 ± 1.71 | 5/5 |
| Replace with flags | moderate | Satisfactory | 72.58 ± 0.15 | 70.97 ± 0.53 | -1.60 ± 0.67 | 0/5 |
| Replace with flags | moderate | Moderate | 71.47 ± 0.52 | 71.24 ± 0.42 | -0.23 ± 0.46 | 1/5 |
| Replace with flags | moderate | Poor | 51.09 ± 1.21 | 49.91 ± 1.07 | -1.19 ± 1.17 | 1/5 |
| Replace with flags | moderate | Very Poor | 68.88 ± 0.98 | 67.99 ± 1.03 | -0.89 ± 0.96 | 1/5 |
| Replace with flags | moderate | Severe | 73.24 ± 1.49 | 70.70 ± 1.33 | -2.54 ± 0.97 | 0/5 |
| Replace with flags | severe | Good | 31.37 ± 2.47 | 37.07 ± 1.98 | 5.70 ± 2.64 | 5/5 |
| Replace with flags | severe | Satisfactory | 57.79 ± 0.85 | 54.88 ± 0.49 | -2.91 ± 0.62 | 0/5 |
| Replace with flags | severe | Moderate | 54.34 ± 0.83 | 54.12 ± 0.30 | -0.22 ± 1.06 | 3/5 |
| Replace with flags | severe | Poor | 26.36 ± 2.25 | 28.76 ± 0.71 | 2.40 ± 2.91 | 4/5 |
| Replace with flags | severe | Very Poor | 46.21 ± 1.50 | 46.46 ± 1.47 | 0.25 ± 2.03 | 2/5 |
| Replace with flags | severe | Severe | 52.70 ± 2.65 | 49.24 ± 1.83 | -3.46 ± 3.18 | 1/5 |
| Augment without flags | clean | Good | 72.88 ± 0.70 | 72.29 ± 0.49 | -0.59 ± 0.55 | 0/5 |
| Augment without flags | clean | Satisfactory | 81.01 ± 0.40 | 80.53 ± 0.46 | -0.48 ± 0.19 | 0/5 |
| Augment without flags | clean | Moderate | 80.94 ± 0.27 | 80.99 ± 0.27 | 0.05 ± 0.07 | 4/5 |
| Augment without flags | clean | Poor | 65.00 ± 1.03 | 64.99 ± 1.09 | -0.00 ± 0.15 | 3/5 |
| Augment without flags | clean | Very Poor | 78.58 ± 0.66 | 78.40 ± 0.75 | -0.17 ± 0.25 | 1/5 |
| Augment without flags | clean | Severe | 81.51 ± 1.08 | 80.78 ± 1.17 | -0.73 ± 0.54 | 1/5 |
| Augment without flags | moderate | Good | 50.78 ± 1.25 | 57.47 ± 0.78 | 6.69 ± 1.12 | 5/5 |
| Augment without flags | moderate | Satisfactory | 72.41 ± 0.18 | 71.13 ± 0.47 | -1.27 ± 0.59 | 0/5 |
| Augment without flags | moderate | Moderate | 72.11 ± 0.48 | 71.69 ± 0.22 | -0.42 ± 0.54 | 1/5 |
| Augment without flags | moderate | Poor | 53.21 ± 1.33 | 50.88 ± 1.44 | -2.33 ± 0.98 | 0/5 |
| Augment without flags | moderate | Very Poor | 69.17 ± 0.90 | 68.01 ± 0.61 | -1.16 ± 0.39 | 0/5 |
| Augment without flags | moderate | Severe | 73.83 ± 1.76 | 70.62 ± 2.28 | -3.20 ± 1.20 | 0/5 |
| Augment without flags | severe | Good | 28.85 ± 3.72 | 37.26 ± 1.83 | 8.41 ± 2.81 | 5/5 |
| Augment without flags | severe | Satisfactory | 58.43 ± 1.46 | 55.13 ± 0.54 | -3.30 ± 1.87 | 0/5 |
| Augment without flags | severe | Moderate | 55.34 ± 0.85 | 54.51 ± 0.72 | -0.83 ± 0.96 | 1/5 |
| Augment without flags | severe | Poor | 32.07 ± 1.16 | 29.12 ± 0.85 | -2.94 ± 1.35 | 0/5 |
| Augment without flags | severe | Very Poor | 47.61 ± 2.11 | 46.27 ± 0.79 | -1.34 ± 1.64 | 0/5 |
| Augment without flags | severe | Severe | 55.96 ± 1.54 | 49.60 ± 1.21 | -6.37 ± 1.86 | 0/5 |
| Augment with flags | clean | Good | 73.49 ± 0.31 | 72.94 ± 0.49 | -0.55 ± 0.27 | 0/5 |
| Augment with flags | clean | Satisfactory | 81.35 ± 0.39 | 81.18 ± 0.30 | -0.17 ± 0.15 | 1/5 |
| Augment with flags | clean | Moderate | 81.13 ± 0.32 | 81.22 ± 0.31 | 0.09 ± 0.19 | 3/5 |
| Augment with flags | clean | Poor | 65.10 ± 0.98 | 65.11 ± 1.02 | 0.01 ± 0.18 | 3/5 |
| Augment with flags | clean | Very Poor | 78.55 ± 0.75 | 78.41 ± 0.72 | -0.14 ± 0.26 | 2/5 |
| Augment with flags | clean | Severe | 81.52 ± 1.23 | 81.09 ± 1.13 | -0.44 ± 0.23 | 0/5 |
| Augment with flags | moderate | Good | 52.24 ± 1.04 | 57.43 ± 1.01 | 5.20 ± 0.68 | 5/5 |
| Augment with flags | moderate | Satisfactory | 72.10 ± 0.16 | 70.85 ± 0.52 | -1.25 ± 0.63 | 0/5 |
| Augment with flags | moderate | Moderate | 71.23 ± 0.42 | 71.29 ± 0.35 | 0.06 ± 0.43 | 3/5 |
| Augment with flags | moderate | Poor | 50.67 ± 1.02 | 50.30 ± 1.79 | -0.37 ± 1.99 | 3/5 |
| Augment with flags | moderate | Very Poor | 68.58 ± 1.23 | 68.19 ± 0.63 | -0.40 ± 0.79 | 2/5 |
| Augment with flags | moderate | Severe | 72.69 ± 1.72 | 70.91 ± 2.21 | -1.78 ± 1.29 | 0/5 |
| Augment with flags | severe | Good | 31.15 ± 1.57 | 36.85 ± 2.09 | 5.70 ± 2.26 | 5/5 |
| Augment with flags | severe | Satisfactory | 57.44 ± 0.80 | 54.82 ± 0.57 | -2.63 ± 1.30 | 0/5 |
| Augment with flags | severe | Moderate | 53.94 ± 0.69 | 54.50 ± 0.57 | 0.56 ± 0.78 | 5/5 |
| Augment with flags | severe | Poor | 25.79 ± 2.10 | 28.65 ± 0.98 | 2.86 ± 2.23 | 5/5 |
| Augment with flags | severe | Very Poor | 45.65 ± 1.85 | 46.20 ± 0.96 | 0.55 ± 2.03 | 3/5 |
| Augment with flags | severe | Severe | 51.36 ± 2.24 | 49.28 ± 1.27 | -2.08 ± 1.45 | 0/5 |

### CV station
| Variant | Condition | Class | A F1 % | B F1 % | B−A pp | B wins |
| --- | --- | --- | --- | --- | --- | --- |
| Replace without flags | clean | Good | 71.31 ± 1.01 | 70.00 ± 0.96 | -1.31 ± 0.75 | 0/5 |
| Replace without flags | clean | Satisfactory | 81.48 ± 0.29 | 80.89 ± 0.47 | -0.58 ± 0.22 | 0/5 |
| Replace without flags | clean | Moderate | 80.96 ± 0.37 | 80.45 ± 0.35 | -0.51 ± 0.22 | 0/5 |
| Replace without flags | clean | Poor | 65.10 ± 1.48 | 64.09 ± 1.28 | -1.00 ± 0.83 | 1/5 |
| Replace without flags | clean | Very Poor | 78.97 ± 0.56 | 78.72 ± 0.38 | -0.24 ± 0.23 | 1/5 |
| Replace without flags | clean | Severe | 81.12 ± 0.37 | 80.59 ± 0.39 | -0.53 ± 0.22 | 0/5 |
| Replace without flags | moderate | Good | 49.99 ± 1.05 | 54.18 ± 1.73 | 4.19 ± 2.09 | 5/5 |
| Replace without flags | moderate | Satisfactory | 74.01 ± 0.29 | 71.50 ± 0.62 | -2.51 ± 0.44 | 0/5 |
| Replace without flags | moderate | Moderate | 72.24 ± 0.48 | 70.85 ± 0.79 | -1.38 ± 0.70 | 0/5 |
| Replace without flags | moderate | Poor | 53.32 ± 0.76 | 50.09 ± 0.87 | -3.23 ± 0.24 | 0/5 |
| Replace without flags | moderate | Very Poor | 69.67 ± 0.88 | 67.74 ± 0.61 | -1.94 ± 0.43 | 0/5 |
| Replace without flags | moderate | Severe | 71.50 ± 0.91 | 69.02 ± 0.77 | -2.47 ± 0.71 | 0/5 |
| Replace without flags | severe | Good | 22.86 ± 1.07 | 35.50 ± 0.65 | 12.64 ± 1.51 | 5/5 |
| Replace without flags | severe | Satisfactory | 63.86 ± 0.46 | 56.55 ± 0.46 | -7.31 ± 0.83 | 0/5 |
| Replace without flags | severe | Moderate | 55.45 ± 0.90 | 54.10 ± 0.38 | -1.36 ± 0.86 | 1/5 |
| Replace without flags | severe | Poor | 31.79 ± 1.13 | 29.28 ± 0.75 | -2.51 ± 0.71 | 0/5 |
| Replace without flags | severe | Very Poor | 50.24 ± 1.46 | 48.63 ± 0.58 | -1.61 ± 0.96 | 0/5 |
| Replace without flags | severe | Severe | 52.36 ± 1.27 | 46.00 ± 1.85 | -6.36 ± 2.10 | 0/5 |
| Replace with flags | clean | Good | 72.93 ± 1.24 | 71.32 ± 0.87 | -1.61 ± 0.74 | 0/5 |
| Replace with flags | clean | Satisfactory | 81.94 ± 0.40 | 81.39 ± 0.47 | -0.54 ± 0.36 | 0/5 |
| Replace with flags | clean | Moderate | 81.14 ± 0.49 | 80.73 ± 0.31 | -0.41 ± 0.30 | 0/5 |
| Replace with flags | clean | Poor | 65.16 ± 1.65 | 64.23 ± 1.59 | -0.93 ± 0.52 | 0/5 |
| Replace with flags | clean | Very Poor | 78.93 ± 0.50 | 78.85 ± 0.68 | -0.08 ± 0.19 | 2/5 |
| Replace with flags | clean | Severe | 80.93 ± 0.82 | 80.87 ± 0.51 | -0.06 ± 0.84 | 2/5 |
| Replace with flags | moderate | Good | 51.59 ± 1.78 | 54.64 ± 1.43 | 3.05 ± 1.27 | 5/5 |
| Replace with flags | moderate | Satisfactory | 73.19 ± 0.95 | 71.28 ± 0.51 | -1.90 ± 0.91 | 0/5 |
| Replace with flags | moderate | Moderate | 71.45 ± 0.33 | 70.80 ± 0.62 | -0.65 ± 0.44 | 0/5 |
| Replace with flags | moderate | Poor | 52.22 ± 1.13 | 49.21 ± 0.79 | -3.02 ± 0.80 | 0/5 |
| Replace with flags | moderate | Very Poor | 69.57 ± 0.64 | 67.67 ± 0.53 | -1.90 ± 0.35 | 0/5 |
| Replace with flags | moderate | Severe | 70.81 ± 1.00 | 68.78 ± 0.80 | -2.03 ± 1.01 | 0/5 |
| Replace with flags | severe | Good | 28.77 ± 3.89 | 35.05 ± 0.44 | 6.28 ± 3.66 | 5/5 |
| Replace with flags | severe | Satisfactory | 61.50 ± 2.33 | 56.28 ± 0.50 | -5.22 ± 2.24 | 0/5 |
| Replace with flags | severe | Moderate | 53.65 ± 1.30 | 54.25 ± 0.32 | 0.60 ± 1.36 | 3/5 |
| Replace with flags | severe | Poor | 29.01 ± 1.08 | 29.00 ± 0.81 | -0.01 ± 0.60 | 2/5 |
| Replace with flags | severe | Very Poor | 49.64 ± 1.72 | 48.38 ± 0.87 | -1.27 ± 0.99 | 0/5 |
| Replace with flags | severe | Severe | 49.84 ± 2.53 | 45.41 ± 2.02 | -4.44 ± 2.29 | 0/5 |
| Augment without flags | clean | Good | 71.43 ± 0.77 | 70.80 ± 1.43 | -0.63 ± 0.90 | 1/5 |
| Augment without flags | clean | Satisfactory | 81.21 ± 0.37 | 81.14 ± 0.39 | -0.07 ± 0.34 | 2/5 |
| Augment without flags | clean | Moderate | 80.70 ± 0.46 | 80.82 ± 0.34 | 0.12 ± 0.39 | 3/5 |
| Augment without flags | clean | Poor | 64.83 ± 1.39 | 64.26 ± 1.44 | -0.57 ± 0.72 | 1/5 |
| Augment without flags | clean | Very Poor | 78.66 ± 0.42 | 78.56 ± 0.45 | -0.10 ± 0.34 | 2/5 |
| Augment without flags | clean | Severe | 80.64 ± 0.43 | 80.64 ± 0.86 | 0.00 ± 0.70 | 2/5 |
| Augment without flags | moderate | Good | 49.95 ± 0.73 | 55.71 ± 0.72 | 5.76 ± 1.11 | 5/5 |
| Augment without flags | moderate | Satisfactory | 73.58 ± 0.59 | 71.59 ± 0.29 | -2.00 ± 0.66 | 0/5 |
| Augment without flags | moderate | Moderate | 72.00 ± 0.47 | 71.31 ± 0.21 | -0.70 ± 0.32 | 0/5 |
| Augment without flags | moderate | Poor | 53.09 ± 0.85 | 50.16 ± 1.04 | -2.93 ± 1.03 | 0/5 |
| Augment without flags | moderate | Very Poor | 69.60 ± 0.73 | 67.96 ± 0.71 | -1.64 ± 0.72 | 0/5 |
| Augment without flags | moderate | Severe | 71.31 ± 0.79 | 68.97 ± 0.74 | -2.34 ± 0.62 | 0/5 |
| Augment without flags | severe | Good | 23.79 ± 0.59 | 35.01 ± 2.08 | 11.22 ± 1.94 | 5/5 |
| Augment without flags | severe | Satisfactory | 63.39 ± 0.85 | 56.72 ± 0.92 | -6.67 ± 0.56 | 0/5 |
| Augment without flags | severe | Moderate | 55.49 ± 0.88 | 54.57 ± 0.66 | -0.92 ± 0.68 | 0/5 |
| Augment without flags | severe | Poor | 31.54 ± 1.12 | 28.47 ± 0.87 | -3.07 ± 1.67 | 0/5 |
| Augment without flags | severe | Very Poor | 49.94 ± 0.87 | 48.72 ± 0.98 | -1.21 ± 0.47 | 0/5 |
| Augment without flags | severe | Severe | 52.83 ± 1.20 | 46.68 ± 0.94 | -6.15 ± 1.70 | 0/5 |
| Augment with flags | clean | Good | 72.40 ± 1.05 | 71.66 ± 1.24 | -0.75 ± 0.50 | 0/5 |
| Augment with flags | clean | Satisfactory | 81.70 ± 0.44 | 81.51 ± 0.37 | -0.19 ± 0.10 | 0/5 |
| Augment with flags | clean | Moderate | 80.85 ± 0.35 | 80.98 ± 0.30 | 0.13 ± 0.11 | 4/5 |
| Augment with flags | clean | Poor | 64.56 ± 1.67 | 64.35 ± 1.31 | -0.20 ± 0.70 | 3/5 |
| Augment with flags | clean | Very Poor | 78.65 ± 0.60 | 78.61 ± 0.39 | -0.04 ± 0.33 | 2/5 |
| Augment with flags | clean | Severe | 80.75 ± 0.52 | 80.80 ± 0.99 | 0.05 ± 0.63 | 3/5 |
| Augment with flags | moderate | Good | 50.51 ± 1.28 | 55.77 ± 0.59 | 5.26 ± 1.04 | 5/5 |
| Augment with flags | moderate | Satisfactory | 72.43 ± 1.08 | 71.45 ± 0.38 | -0.97 ± 1.13 | 1/5 |
| Augment with flags | moderate | Moderate | 71.20 ± 0.30 | 71.14 ± 0.40 | -0.06 ± 0.24 | 2/5 |
| Augment with flags | moderate | Poor | 51.94 ± 1.24 | 49.86 ± 1.01 | -2.07 ± 0.81 | 0/5 |
| Augment with flags | moderate | Very Poor | 69.22 ± 0.77 | 67.77 ± 0.60 | -1.45 ± 0.85 | 1/5 |
| Augment with flags | moderate | Severe | 70.45 ± 0.74 | 68.34 ± 0.66 | -2.11 ± 0.70 | 0/5 |
| Augment with flags | severe | Good | 28.93 ± 2.73 | 35.04 ± 1.05 | 6.12 ± 3.44 | 5/5 |
| Augment with flags | severe | Satisfactory | 60.91 ± 2.42 | 56.35 ± 0.98 | -4.56 ± 3.14 | 1/5 |
| Augment with flags | severe | Moderate | 53.51 ± 1.25 | 54.40 ± 0.54 | 0.89 ± 1.37 | 3/5 |
| Augment with flags | severe | Poor | 29.11 ± 1.35 | 28.32 ± 0.59 | -0.79 ± 1.75 | 2/5 |
| Augment with flags | severe | Very Poor | 48.66 ± 1.28 | 48.39 ± 0.60 | -0.27 ± 0.82 | 3/5 |
| Augment with flags | severe | Severe | 49.86 ± 2.04 | 45.96 ± 1.04 | -3.90 ± 2.67 | 0/5 |
