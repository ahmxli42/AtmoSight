# Degraded aware training experiment

Protocol recorded before training on 15 October 2026. Results pending.

## Purpose and research question

Does training a Random Forest on a mix of clean and synthetically degraded observations improve six-category air-quality classification on sparse, noisy and incomplete readings relative to clean-only training? A negative or mixed result is valid. The application and deployed artifacts must not change.

## Repository inspection

The source dataset is `Dataset/station_day.csv` (8,742,141 bytes). `backend/train.py` defines the exact filtering, six features, six ordered categories, median imputer and 200-tree balanced Random Forest. `backend/train_sensor_models.py` exposes the matching unrestricted configuration through `pipeline(limited=False)`. `backend/noise_evaluation.py` supplies the multiplicative-noise precedent; `backend/evaluate_station_transfer.py` specifies GroupShuffleSplit with seed 42. Those last two scripts modify deployed metadata when executed and will not be executed or imported. Existing tests cover API integrity, adaptability and large imports.

## Fixed design and clarifications

- Use the existing filtering and fixed random stratified 80/20 split with seed 42, plus the existing station-held-out GroupShuffleSplit with seed 42.
- The filtered data contain 87,025 rows, including 272 rows with all six pollutants missing. The user explicitly approved retaining these rows and disclosing them as an exception. Every degraded row with an original observation must retain at least one; no measurement is invented for naturally all-missing rows.
- Run exactly replace, replace with flags, augment, and augment with flags. The flags are six missingness indicators calculated before imputation for both models.
- Replace: B replaces half of training rows, one quarter moderate and one quarter severe (integer rounding disclosed); A uses the same number of clean rows.
- Augment: B receives clean plus one moderate and one severe copy. The user explicitly approved three unchanged copies for A, giving equal training-row counts and label counts. This duplicated control is not identical to fitting A once because bootstrap sampling operates on the duplicated population.
- Clean means no additional simulated degradation; natural missingness remains. Fit imputation medians on clean training rows only. Inside CV, fit them on the fold-training subset only, never its validation fold.
- Use the exact unrestricted baseline classifier, 200 balanced trees, default depth and minimum leaf size 1. Do not tune hyperparameters. Use seeds 42, 43, 44, 45 and 46 for final model randomness and degradation; splits remain fixed.
- For each protocol, perform five-fold StratifiedKFold validation within the training portion, shuffled with seed 42. CV uses one fixed degradation/model seed schedule across the five folds; variability there is across folds, not five seed replicates. Evaluate clean, moderate and severe validation conditions. Complete CV before held-out testing.
- Generate each evaluation-condition matrix once per seed/fold and share it between A and B and across variants. Record hashes of those paired matrices.

## Degradation operators

Apply to observed values before imputation: multiplicative Gaussian noise clipped nonnegative; independent cell masking; then joint gas removal for selected rows. Moderate uses sigma 0.10, masking probability 0.15, gas-removal fraction 0.20. Severe uses sigma 0.30, masking 0.40, gas removal 0.50. Gas columns are SO2, NO2, CO and O3. Select the specified fraction of rows without replacement, rounded down. Labels never change.

If a previously observed row becomes entirely missing, restore one noisy originally observed value, preferring PM2.5/PM10 when available. If neither PM was originally observed, restoring a gas is necessary; report these repairs because the at-least-one-observation constraint can reduce realized gas absence. Record operator selection rates and realized missingness rather than claiming the final missing rate equals the independent masking probability.

## Metrics and prespecified decision rule

Report accuracy, macro F1, all six per-class F1 values, and the fraction of predictions within one ordinal category. Category order is Good, Satisfactory, Moderate, Poor, Very Poor, Severe. Use all six labels for F1, including zeros for absent categories. Report mean and sample standard deviation over five seeds, paired B minus A mean/sample SD, and the number of seeds with a strictly positive difference. Include severe confusion matrices for both models.

For **each variant and each test protocol**, call degraded-aware training **helps** only if (1) mean severe macro-F1 difference B minus A is greater than one sample standard deviation of the paired differences, and (2) mean clean accuracy loss is no more than 0.01 (one percentage point). Otherwise state **did not help under the prespecified rule**. Apply this rule to all eight comparisons; do not choose or promote only a winner. This heuristic is not a statistical-significance test, and overlapping fixed test rows across seeds are not independent new datasets.

## Interpretation and limitations planned before results

Use repair-affected versus other severe rows as a descriptive diagnostic, with sample sizes, to investigate whether the at-least-one-value constraint concentrates difficult cases. Do not tune on that diagnostic. No compact sensitivity or optional specialist extension is scheduled. Simulated errors, one India dataset, no time split, no Pakistani data, natural all-missing rows, reused historical partitions and within-station dependence limit generalization. No trained model is deployed by this experiment.

## Reproducibility and preservation

New code and outputs stay under `experiments/robustness/`; documentation stays under `docs/`. A nested ignore file excludes model binaries. Record hashes of the dataset, pre-existing deployed artifacts and active app/backend source before the experiment and verify them afterward. Save per-run results, parameters, seeds, folds, split IDs, preprocessing medians, timing and library versions. The final report will replace this pending section with results produced by the recorded commands while preserving the prespecified protocol.
