# Verification report

Checks performed 18 October 2026 (Asia/Karachi). Build/test claims below come from actual commands.

| Check | Actual result |
| --- | --- |
| Original source preservation | PASS: 320 inventoried source hashes unchanged; no original edits/moves/deletions. |
| Dataset | PASS: 8,742,141 bytes; SHA-256 67c308463abab12507f0c9892549fedfc099221025cbcb3e308be170b5a6a0ad. |
| Dataset license | PASS: public Kaggle metadata reports CC0: Public Domain, version 12; selected metadata saved. |
| Fresh clone setup | PASS: fresh virtual environment, Python dependency install and npm ci; pip check passed. |
| Model rebuild | PASS in the new folder and independently in the fresh clone; unchanged training/evaluation code. |
| Baseline acceptance | PASS: accuracy 0.7811548405630566 and macro F1 0.764960569573612, matching expected values to 12 decimal places. |
| Station holdout | PASS: separate pipeline accuracy 0.7459730657512543, macro F1 0.7320514058468884. |
| Unit tests | PASS: all 26 existing unittest cases; older log reported 24. Passed in the new folder and fresh clone. |
| Backend HTTP smoke | PASS: health HTTP 200 and POST /predict routed to baseline in the fresh clone. |
| Frontend | PASS: npm ci, dev-server HTTP 200 and production TypeScript/Vite build. |
| Frozen sidecar | PASS: PyInstaller build and existing frozen integration smoke, all three model routes, SHAP, provenance and mapping. |
| Native Tauri | PASS: release executable built with tauri build --no-bundle; Rust 1.99.0, Cargo 1.99.0. Native visual interaction and NSIS installer creation/installation are UNVERIFIED. |
| Browser QA | PASS: all 16 historical UI checks; no page errors. |
| Real HTTP QA | PASS: registry, model routing, malformed input rejection, station/city/cleaned dataset uploads, oversized hourly CSV rejection, and complete 108,035-row station-day analysis. |
| Large browser QA | PASS: rendered/paginated 108,035 rows; exported all 108,035 rows (144,822,923 bytes); 99,569 valid, 8,466 invalid; no page errors. |
| Archived experiment evidence | PASS: all 89 results files retain their original SHA-256 hashes. |
| Isolated study wrapper | PASS: all four phase prerequisite checks and actual initial verify phase. Full 160-forest CV/test refitting and regenerated report are UNVERIFIED. |
| Model binaries | Excluded from Git and removed from final clean folder. Baseline is approximately 117 MB; rebuild locally. |

## Environment and scope

Windows, Python 3.12.14, Node 24.21.0, npm 11.19.0. The Windows Store python alias was unusable; an explicit available Python 3.12 runtime was prepended to PATH for fresh setup. No environment was copied. requirements-lock.txt records the resulting installed versions.

The fresh validation clone lives outside this repository. Its initial setup/build/model/unit/API checks use the cleaned source and included station_day.csv. The optional historical QA tools additionally read original extra datasets via ATMOSIGHT_DATASET_DIR; these inputs are not redistributed. The original bundled Playwright 1.62.1 was used for browser QA; the same pinned optional dependency subsequently installed successfully in the clone. The optional QA lockfile first failed with ECONNRESET, then succeeded on a cache-preferred retry.

The native executable was compiled in the new folder from its freshly rebuilt sidecar/models. The sidecar runtime smoke passed; native visual interaction and installer testing were not performed. Build outputs and dependencies are removed from the delivered folder, so recreate them with the documented commands.

## Preserved evidence and scientific limits

The archived manifest protects a wider original deployment including excluded model binaries and old scripts. Its original preservation guard must not be bypassed to reuse old results. scripts/reproduce.py creates a separate snapshot/results directory and successfully initialized a new manifest. That snapshot captures the first invocation; later root changes do not silently change the snapshot. Use a new checkout for a changed study. The complete study was not refitted during cleanup. The preserved 2-of-8 decision result is historical evidence.

## Nonfatal warnings and corrected operational failures

- Vite reported a chart chunk over 500 kB; the production build passed.
- npm reported Recharts 2 deprecation; both dependency audits reported zero vulnerabilities.
- PyInstaller warned about optional tbb12.dll; the packaged-backend integration smoke passed.
- Initial Git reads encountered original ownership protection; per-command safe.directory was used for reads, without changing global/original configuration.
- The original repository has no commits, so its author log lookup failed.
- Initial new-repository commits lacked an author identity; the supplied name/email were configured locally.
- An initial index cleanup failed because staged files had changed; the sole new unpublished commit was reconstructed, and the final component history follows the requested order.
- PowerShell rg wildcards in argument paths were rejected in several exploratory searches; later searches targeted directories with -g filters.
- A non-escalated sibling Git status could not access its work tree; the authorized sibling operation succeeded.
- Public Kaggle lookup initially failed DNS in the restricted network context; the authorized public metadata request succeeded.

## Final delivery checks

Final Git status, Git object counts, source scan, physical file sizes, Markdown references and archived hashes are recorded after cleanup in FINAL_CHECKS.json. No remote was added and no push was attempted. The repository has no application LICENSE at the owner's request. The two named final reports were absent; no draft was substituted.
