> Cleanup note: the commands below document the original run. The preserved manifest intentionally refuses the cleaned deployment. Use scripts/reproduce.py from the root README to initialize a separate study workspace without altering archived evidence.

# Degraded aware Random Forest comparison

This isolated experiment compares clean-only A with degraded-aware B. It must not modify the app or deployed models. The study definition is in `protocol.json`; the report is `docs/ROBUSTNESS_EXPERIMENT.md` at the repository root.

## Run from the repository root

```powershell
backend/.venv/Scripts/python.exe -m unittest experiments.robustness.test_robustness backend.test_api backend.test_adaptability backend.test_large_imports -q
backend/.venv/Scripts/python.exe -m experiments.robustness.run --phase cv
backend/.venv/Scripts/python.exe -m experiments.robustness.run --phase test
backend/.venv/Scripts/python.exe -m experiments.robustness.run --phase verify
backend/.venv/Scripts/python.exe -m experiments.robustness.report
```

There are 40 paired CV runs and 40 paired final-test runs, totaling 160 fitted forests. Each pair evaluates both arms on three identical conditions. Running a phase again skips completed pairs. A partial pair may be repeated after interruption; its incomplete data never enter the report. Do not launch concurrent runners for the same phase.

The runner refuses to combine changed core code/protocol, changed deployed files, or changed data with previous results. Preserve completed experiment outputs before designing a different study; do not erase their manifest to bypass this guard. Final testing requires all CV pairs. Reporting requires all 80 pairs and checks evaluation hashes across variants.

The source study preserves 272 naturally all-missing rows as an approved exception. Augment mode uses three clean copies for A and clean/moderate/severe for B. The nested ignore file excludes model binaries; this runner holds trained forests in memory and saves evidence only.

Runtime fields measure wall time, including suspension while a fit is active. They are not CPU-time benchmarks. See the final report for any long-interval disclosure.
