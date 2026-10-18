"""Generate the complete report from completed run files only."""
import csv
import json
from datetime import datetime, timezone
import numpy as np
from .core import HERE, ROOT, FEATURES, CATEGORIES, PROTOCOL, protected_files, file_hash

OUT=HERE/'results'
METRICS=['accuracy','macro_f1','within_one']+[f'f1_{c}' for c in CATEGORIES]
NAMES={'replace':'Replace without flags','replace_flags':'Replace with flags','augment':'Augment without flags','augment_flags':'Augment with flags'}

def table(headers,rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+['| '+' | '.join(map(str,r))+' |' for r in rows])+'\n'
def ms(x):return f'{np.mean(x)*100:.2f} ± {np.std(x,ddof=1)*100:.2f}'
def decision_rule(severe_differences,clean_accuracy_differences):
    return bool(np.mean(severe_differences)>np.std(severe_differences,ddof=1) and np.mean(clean_accuracy_differences)>=-.01)
def summary(records,protocol,variant,condition,metric):
    group=sorted([r for r in records if r['protocol']==protocol and r['variant']==variant],key=lambda r:r['seed'])
    a=np.array([r['models']['A']['results'][condition][metric] for r in group]);b=np.array([r['models']['B']['results'][condition][metric] for r in group]);delta=b-a
    return {'a':a,'b':b,'delta':delta,'wins':int((delta>0).sum())}

def main():
    manifest=json.loads((OUT/'manifest.json').read_text())
    cv=[json.loads(p.read_text()) for p in sorted((OUT/'cv').glob('*.json'))]
    tests=[json.loads(p.read_text()) for p in sorted((OUT/'test').glob('*.json'))]
    expected={(p,u,v) for p in ['random','station'] for u in range(5) for v in PROTOCOL['variants']}
    for name,records in [('cv',cv),('test',tests)]:
        if len(records)!=40:raise RuntimeError(f'{name}: expected 40 complete paired runs, got {len(records)}')
        keys={(r['protocol'],int(r['unit'].removeprefix('fold'))-1 if name=='cv' else PROTOCOL['test_seeds'].index(r['seed']),r['variant']) for r in records}
        assert keys==expected
        for p in ['random','station']:
            for unit in {r['unit'] for r in records if r['protocol']==p}:
                hashes=[r['raw_evaluation_hashes'] for r in records if r['protocol']==p and r['unit']==unit]
                assert all(h==hashes[0] for h in hashes)
        assert all(r['paired_input_verified'] for r in records)
    assert protected_files()==manifest['protected_hashes']
    (OUT/'report_manifest.json').write_text(json.dumps({
        'generated_utc':datetime.now(timezone.utc).isoformat(),
        'report_code_sha256':file_hash(HERE/'report.py'),
        'test_code_sha256':file_hash(HERE/'test_robustness.py'),
        'cv_pairs':len(cv),'test_pairs':len(tests),
        'paired_hashes_across_variants_verified':True,
        'protected_files_unchanged':True},indent=2))
    rows=[]
    for phase,records in [('cv',cv),('test',tests)]:
        for r in records:
            for arm in ['A','B']:
                for cond,values in r['models'][arm]['results'].items():
                    rows.append({'phase':phase,'protocol':r['protocol'],'unit':r['unit'],'seed':r['seed'],'variant':r['variant'],'model':arm,'condition':cond,**{m:values[m] for m in METRICS}})
    with (OUT/'metrics.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    aggregates=[];decisions=[]
    for phase,records in [('cv',cv),('test',tests)]:
        for protocol in ['random','station']:
            for variant in PROTOCOL['variants']:
                for cond in ['clean','moderate','severe']:
                    for metric in METRICS:
                        s=summary(records,protocol,variant,cond,metric)
                        aggregates.append({'phase':phase,'protocol':protocol,'variant':variant,'condition':cond,'metric':metric,
                            'a_mean':float(s['a'].mean()),'a_sd':float(s['a'].std(ddof=1)),
                            'b_mean':float(s['b'].mean()),'b_sd':float(s['b'].std(ddof=1)),
                            'paired_difference_mean':float(s['delta'].mean()),'paired_difference_sd':float(s['delta'].std(ddof=1)),
                            'b_wins':s['wins'],'replicates':5})
                if phase=='test':
                    severe=summary(records,protocol,variant,'severe','macro_f1')
                    clean=summary(records,protocol,variant,'clean','accuracy')
                    benefit=severe['delta'].mean()>severe['delta'].std(ddof=1)
                    clean_ok=clean['delta'].mean()>=-.01
                    decisions.append({'protocol':protocol,'variant':variant,'severe_macro_f1_delta':float(severe['delta'].mean()),
                        'severe_delta_sd':float(severe['delta'].std(ddof=1)),'clean_accuracy_delta':float(clean['delta'].mean()),
                        'severe_b_wins':severe['wins'],'benefit_exceeds_sd':bool(benefit),'clean_loss_within_one_point':bool(clean_ok),
                        'helps':decision_rule(severe['delta'],clean['delta'])})
    with (OUT/'summary.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(aggregates[0]));writer.writeheader();writer.writerows(aggregates)
    (OUT/'decisions.json').write_text(json.dumps(decisions,indent=2))
    original=json.loads((ROOT/'backend/artifacts/metadata.json').read_text())
    reproduced=next(r for r in tests if r['protocol']=='random' and r['variant']=='replace' and r['seed']==42)['models']['A']['results']['clean']
    reproduction={'old_accuracy':original['accuracy'],'new_accuracy':reproduced['accuracy'],
        'old_macro_f1':original['macro_f1'],'new_macro_f1':reproduced['macro_f1'],
        'match_to_12_decimals':all(abs(original[k]-reproduced[k])<1e-12 for k in ['accuracy','macro_f1'])}
    (OUT/'baseline_reproduction.json').write_text(json.dumps(reproduction,indent=2))
    chunks=['# Degraded aware training experiment\n',
        'Completed research report. Protocol recorded before training on 15 October 2026; execution continued into 16 October. The deployed app, datasets and model artifacts were not changed.\n',
        '## 1 Purpose and research question\n',
        'Does a Random Forest trained on clean plus simulated degraded readings perform better on noisy, sparse and incomplete six-pollutant data than the same classifier trained without added degradation? All four requested variants and both fixed test protocols are reported.\n']
    passed=sum(d['helps'] for d in decisions)
    chunks+=['**Main result:** '+str(passed)+' of the eight variant–protocol comparisons met the prespecified rule. A failed rule means “did not help under this rule,” even if severe-condition performance improved. The detailed results below separate robustness gains from clean-data losses.\n',
        '## 2 Background and repository inspection\n',
        'Atmosight originally trained a 200-tree balanced six-pollutant forest on India station-day data with training-only median imputation. Missingness and multiplicative-noise stress tests already existed, but they did not train a degraded-aware counterpart. Low-cost monitors can lose individual readings or entire gas channels, motivating a controlled paired comparison. Synthetic failures are an experimental proxy rather than a physical sensor calibration model.\n',
        '`backend/train.py` supplied feature/category constants and the filtering sequence. `backend/train_sensor_models.py: pipeline(limited=False)` supplied the exact unrestricted classifier configuration through a cloned estimator. The multiplicative Gaussian operator follows `backend/noise_evaluation.py`. Split definitions match `backend/train.py` and `backend/evaluate_station_transfer.py`. The last two evaluation scripts with metadata-writing side effects were inspected but not executed/imported.\n',
        '## 3 Data and filtering\n',
        'File: `Dataset/station_day.csv`. SHA-256: `'+manifest['protected_hashes']['Dataset/station_day.csv']+'`. CSV source-row IDs are saved in the manifest for both fixed partitions. Rows follow the existing filter in exactly the same order. “Clean” means no extra synthetic degradation; it does not mean complete or error-free measurements.\n',
        table(['Stage','Rows'],manifest['filter_counts'].items()),
        table(['Class','Filtered count'],manifest['class_distribution'].items())]
    splitrows=[]
    for name,s in manifest['splits'].items():
        splitrows.append([name,s['train_rows'],s['test_rows'],s['train_all_missing'],s['test_all_missing']])
    chunks += [table(['Protocol','Train','Test','All missing train','All missing test'],splitrows),
        'The 272 naturally all-missing rows remain, as explicitly approved by the user. They are the exception to retaining an observed value: fabricating a measurement would violate the experiment. All other degraded rows retain at least one originally observed pollutant.\n',
        '## 4 Preprocessing and leakage controls\n',
        'Inputs are PM2.5, PM10, SO2, NO2, CO and O3 only. AQI, AQI_Bucket, StationId and Date never enter the predictor. AQI_Bucket is the target; StationId is used only for splitting; dates/source row numbers are audit identifiers. Each fit uses medians learned from its clean training subset, shared unchanged by A and B and all evaluation conditions. In CV those medians are fitted separately within each fold training subset. Optional flags are computed from pre-imputation missingness and appended to both arms. No normalization, imputation or learning uses held-out statistics.\n',
        'SimpleImputer keeps empty features so the feature layout cannot change. In an entirely empty training column its fallback is zero; the recorded fold medians show whether this arose. Natural missingness in the source is preserved. Training and evaluation source indices are disjoint, and the station protocol also verifies no station overlap against the existing station-ID lists. Adding six flags changes the feature count from 6 to 12; with the unchanged max_features=sqrt setting, this also changes the candidate-feature count per split from 2 to 3. Both A and B receive the same setting within a variant; comparisons across flag variants therefore include this feature-sampling change.\n',
        '## 5 Degradation operators\n',
        table(['Condition','Noise sigma','Cell mask p','Gas-row fraction'],[['Moderate',.1,.15,.2],['Severe',.3,.4,.5]]),
        'Order: (1) multiply observed x by 1 + N(0,sigma) and clip at zero; (2) independently mask observed cells with probability p; (3) choose floor(fraction × rows) rows without replacement and remove SO2, NO2, CO and O3 jointly. Noise represents proportional concentration error; random masking represents intermittent dropout; joint gas removal represents a PM-only device. Labels are unchanged.\n',
        'If the process erases every value from a previously observed row, restore one of its noisy originally observed values, preferring a particulate measurement. If the row originally had no PM value, a gas must be restored. This safeguard can reduce realized gas absence and masking. The operator rates below distinguish Bernoulli mask rate, selected gas rows, final missingness and rescue events. Natural all-missing rows are never filled by this operator.\n']
    degrows=[]
    for protocol in ['random','station']:
        base=[r for r in tests if r['protocol']==protocol and r['variant']=='replace']
        for cond in ['moderate','severe']:
            stats=[r['evaluation_degradation'][cond] for r in base]
            degrows.append([protocol,cond,ms([s['random_mask_observed_fraction'] for s in stats]),ms([s['gas_selection_fraction'] for s in stats]),ms([s['final_missing_fraction'] for s in stats]),ms([s['final_all_gases_missing_fraction'] for s in stats]),f"{np.mean([s['rescued_rows'] for s in stats]):.1f}",f"{np.mean([s['rescued_with_gas'] for s in stats]):.1f}"])
    chunks += [table(['Protocol','Condition','Mask %','Gas selected %','Final missing %','All gases missing %','Rescued rows mean','Gas rescues mean'],degrows),
        '## 6 Models and training construction\n',
        'Both arms reuse the baseline RandomForestClassifier: n_estimators=200, criterion=gini, max_depth=None, min_samples_split=2, min_samples_leaf=1, max_features=sqrt, bootstrap=True, class_weight=balanced, n_jobs=-1. Full estimator parameters are recorded in `results/manifest.json`. No compact sensitivity or specialist extension was run. Only classifier fitting is needed; SHAP and anomaly models are not part of this comparison. Models are evaluated in memory and then released, so no new model binaries are required.\n',
        'Replace variants: A receives N unchanged rows. B keeps N total rows and replaces floor(N/2) rows selected without replacement: floor(N/4) moderate and the remaining replaced rows severe. The labels and class counts remain exactly equal. Augment variants: A receives three clean copies (3N rows), while B receives clean + moderate + severe copies (3N rows), with identical repeated labels. The equal-size clean-duplication control was explicitly approved. Bootstrap resampling means this A can differ from the single-copy A; it is not claimed to be an independent threefold increase in information.\n',
        f"Baseline reproduction check, random protocol / replace without flags / seed 42: original stored clean accuracy {original['accuracy']:.8%}, refitted A {reproduced['accuracy']:.8%}; original macro F1 {original['macro_f1']:.8%}, refitted A {reproduced['macro_f1']:.8%}. Match to 12 decimal places: {reproduction['match_to_12_decimals']}. This is a final audit check, not a tuning step; see results/baseline_reproduction.json.\n",
        '## 7 Prespecified variants\n',table(['Variant','Training mode','Missingness flags'],[[NAMES[v],'Augment 3N' if v.startswith('augment') else 'Replace N','Six flags for both arms' if v.endswith('flags') else 'None'] for v in PROTOCOL['variants']]),
        '## 8 Validation and test protocols\n',
        'Protocol 1 uses the existing stratified random 80/20 split, random_state=42. Protocol 2 uses the existing GroupShuffleSplit, n_splits=1, test_size=0.2, random_state=42 (87 training stations and 22 test stations). Changing final experiment seeds never changes either partition. These historical partitions have been used by previous project work; they are not newly collected blind external test data.\n',
        'For each protocol, five-fold StratifiedKFold(shuffle=True, random_state=42) runs only inside its training partition. CV fold f uses model/degradation seed 42 + f×10000, for f=1..5. A validation row is never augmented into its fold training data. Validation is evaluated clean, moderate and severe. CV variability is across folds; it is not five seeds on one validation set, and the inner folds are not station-grouped.\n',
        'After all CV runs completed, final fitting/evaluation used seeds 42,43,44,45,46. Each evaluation condition is created once for the protocol/seed (or CV fold), shared across variants, transformed using the same clean-training imputer, then passed as the same read-only matrix to A and B. Raw and transformed SHA-256 hashes verify identical inputs. Independent offsets distinguish training noise (+101/+202) from evaluation noise (+1001/+2001). No metric-driven tuning or selection occurred.\n',
        '## 9 Metrics and uncertainty\n',
        'Accuracy and macro F1 describe exact category classification; per-class F1 shows class-specific tradeoffs. Within-one-category uses the order Good, Satisfactory, Moderate, Poor, Very Poor, Severe and counts absolute ordinal distance ≤1; it is not a concentration error bound. All six classes enter F1, with zero_division=0. Tables show percentages as mean ± sample SD (ddof=1). Paired differences are B−A in percentage points; wins count strictly positive differences, so ties are not wins. Seed SD describes algorithm/degradation variability on fixed rows and is not a population confidence interval.\n',
        '## 10 Prespecified decision rule\n',
        'For each variant/protocol, **helps** requires mean severe macro-F1(B−A) > sample SD of the five paired severe macro-F1 differences **and** mean clean accuracy(B−A) ≥ −1 percentage point. Otherwise report **did not help under the rule**. This is the user’s fixed practical rule, not a significance test. It was recorded before any training in protocol.json and the preserved `results/prespecified_document.md`; its SHA-256 is `'+manifest['prespecified_document_sha256']+'`.\n',
        table(['Protocol','Variant','Severe F1 gain pp','Paired SD pp','Clean accuracy change pp','Severe F1 wins','Decision'],[[d['protocol'],NAMES[d['variant']],f"{100*d['severe_macro_f1_delta']:.2f}",f"{100*d['severe_delta_sd']:.2f}",f"{100*d['clean_accuracy_delta']:.2f}",f"{d['severe_b_wins']}/5",'Helps' if d['helps'] else 'Did not help'] for d in decisions]),
        '## 11 Full results\n']
    explanations=[]
    for d in decisions:
        failed=[]
        if not d['benefit_exceeds_sd']:failed.append('the severe macro-F1 gain did not exceed its paired SD')
        if not d['clean_loss_within_one_point']:failed.append('mean clean accuracy fell by more than one percentage point')
        explanations.append(f"- **{d['protocol']} / {NAMES[d['variant']]}:** severe macro F1 changed by {d['severe_macro_f1_delta']*100:+.2f} points and clean accuracy by {d['clean_accuracy_delta']*100:+.2f} points. "+('Both rule conditions passed.' if not failed else 'The rule failed because '+' and '.join(failed)+'.'))
    chunks.insert(-1,'\n'.join(explanations)+'\n')
    for phase,records,replicate in [('Final tests',tests,'seeds'),('Cross validation',cv,'folds')]:
        chunks.append(f'### {phase}\nMean ± sample SD across five {replicate}. Each metric includes its paired difference and B wins.\n')
        for protocol in ['random','station']:
            for metric,title in [('accuracy','Accuracy'),('macro_f1','Macro F1'),('within_one','Within one category')]:
                result=[]
                for variant in PROTOCOL['variants']:
                    for cond in ['clean','moderate','severe']:
                        s=summary(records,protocol,variant,cond,metric)
                        result.append([NAMES[variant],cond,ms(s['a']),ms(s['b']),ms(s['delta']),f"{s['wins']}/5"])
                chunks.append(f'#### {protocol.title()} protocol {title}\n'+table(['Variant','Condition','A %','B %','B−A pp','B wins'],result))
    chunks+=['### Severe confusion matrices\nRows are actual labels, columns predicted labels in the displayed order. Counts are summed over five seeds, so each held-out observation contributes five predictions; these are not five independent datasets. Individual seed matrices remain in run JSON files.\n']
    for protocol in ['random','station']:
        for variant in PROTOCOL['variants']:
            for arm in ['A','B']:
                matrix=np.sum([r['models'][arm]['results']['severe']['confusion_matrix'] for r in tests if r['protocol']==protocol and r['variant']==variant],axis=0)
                chunks.append(f'#### {protocol} {NAMES[variant]} Model {arm}\n'+table(['Actual / predicted']+CATEGORIES,[[c]+list(row) for c,row in zip(CATEGORIES,matrix)]))
    chunks+=['## 12 Interpretation and diagnostic\n',
        'The decision table is the primary conclusion; improvements on severe inputs alone do not satisfy a rule that also protects clean accuracy. Compare replace and augment within each protocol rather than claiming one universal winner. Missingness flags may let the trees distinguish median-filled values from genuinely median-valued observations; degraded training may trade clean-data discrimination for stability. These mechanisms are plausible explanations, not causal findings from this experiment.\n',
        'A prespecified descriptive check separates severe rows that required rescue after losing every observed value from other rows. These groups differ in original information content, so this is not a randomized ablation of the rescue procedure. The naturally-all-missing subgroup is also shown and overlaps the not-rescued group; the three rows are not a disjoint partition. The table reports mean accuracy difference, not a new tuning objective.\n']
    diagnostic=[]
    for protocol in ['random','station']:
        for variant in PROTOCOL['variants']:
            group=[r for r in tests if r['protocol']==protocol and r['variant']==variant]
            for subgroup in ['rescued','not_rescued','naturally_all_missing']:
                entries=[(r['models']['A']['results']['severe']['repair_diagnostic'][subgroup],r['models']['B']['results']['severe']['repair_diagnostic'][subgroup]) for r in group]
                deltas=[b['metrics']['accuracy']-a['metrics']['accuracy'] for a,b in entries if a['rows']]
                diagnostic.append([protocol,NAMES[variant],subgroup,f"{np.mean([a['rows'] for a,b in entries]):.1f}",ms(deltas) if len(deltas)>1 else 'Not estimable'])
    chunks.append(table(['Protocol','Variant','Subgroup','Rows mean','Accuracy B−A pp'],diagnostic))
    chunks+=['## 13 Limitations\n',
        'Degradation is simulated, and actual faults can be biased, correlated, drifting, censored or season-specific. Gas absence and row rescue interact. There is one India dataset, no time-based split and no Pakistani data. Natural missingness and 272 all-missing rows limit interpretation of “clean.” Augmentation repeats observations and does not create independent data. CV strata preserve classes but do not hold out stations within folds. Final seed repetitions reuse fixed test rows; no confidence interval or formal multiple-comparison test is claimed. Class labels are assumed valid and unchanged. Historical partitions have prior project exposure. Real-sensor reliability, probability calibration and regional transfer remain unverified. Optional compact and PM-specialist comparisons were not run. No app integration or deployment validation is claimed for these experimental classifiers.\n',
        '## 14 Reproducibility and verification\n',
        'Commands run from `<repository-root>`:\n\n```powershell\nbackend/.venv/Scripts/python.exe -m unittest experiments.robustness.test_robustness backend.test_api backend.test_adaptability backend.test_large_imports -q\nbackend/.venv/Scripts/python.exe -m experiments.robustness.run --phase cv\nbackend/.venv/Scripts/python.exe -m experiments.robustness.run --phase test\nbackend/.venv/Scripts/python.exe -m experiments.robustness.run --phase verify\nbackend/.venv/Scripts/python.exe -m experiments.robustness.report\n```\n',
        'The initial combined test command passed 23 tests. A decision-rule boundary test was then added and all seven experiment tests passed separately. Final combined verification passed 24 tests; its output is recorded in results/tests.txt using the test command above followed by `2>&1 | Tee-Object -FilePath experiments/robustness/results/tests.txt`. Tests cover purity, realized operator rates, nonnegative noise, original missingness preservation, retention/rescue exception, training-only medians, flags, identical read-only paired inputs, labels/row counts, feature restrictions, disjoint partitions, baseline settings and both decision thresholds. The experiment’s runtime assertions additionally check paired matrix hashes and actual station IDs. Existing frozen-service integration was not rerun because deployed files were unchanged; preservation is verified by hashes.\n',
        'During this session, `backend/.venv/Scripts/python.exe -m experiments.robustness.finish_run` queued the listed test, verification and reporting commands after all 40 CV checkpoints existed. It is an execution helper, not a separate scientific protocol. Do not run it alongside another final-test runner.\n',
        'An initial CV launch failed before training because its output directory had not been created. The initialization was fixed before the first completed run; that failure produced no result numbers.\n',
        table(['Library','Version'],manifest['libraries'].items()),
        'Hardware observed during execution: Intel Core i5-1145G7 (4 physical cores, 8 logical processors), 24,838,364 KiB visible RAM. Other applications were running; this is not an isolated benchmark. The read-only hardware query is recorded in environment.json.\n']
    timings=[]
    for phase,records in [('CV',cv),('Test',tests)]:
        for protocol in ['random','station']:
            for variant in PROTOCOL['variants']:
                selected=[r for r in records if r['protocol']==protocol and r['variant']==variant]
                timings.append([phase,protocol,NAMES[variant],f"{sum(r['seconds'] for r in selected)/60:.2f}"])
    chunks.append(table(['Phase','Protocol','Variant','Recorded pair elapsed minutes'],timings))
    chunks.append(f"Total recorded pair elapsed time: {sum(r['seconds'] for r in cv+tests)/60:.2f} minutes. These perf_counter intervals measure wall time, not CPU time, and may include host/session suspension while a fit was active. Long elapsed intervals occurred during CV; their precise causes were not independently verified. Do not interpret the summed intervals as uninterrupted training compute. Tests, reporting and initialization are outside the pair timer. Manifest started UTC: {manifest['started_utc']}. Report generated UTC: {datetime.now(timezone.utc).isoformat()}.\n")
    arm_times=[(r['phase'],r['protocol'],r['unit'],r['variant'],arm,r['models'][arm]['seconds']) for r in cv+tests for arm in ['A','B']]
    chunks.append(table(['Phase','Protocol','Unit','Variant','Arm','Elapsed seconds over 600'],[[*r[:5],f'{r[5]:.2f}'] for r in arm_times if r[5]>600]) if any(r[5]>600 for r in arm_times) else 'No individual arm exceeded 600 elapsed seconds.\n')
    chunks+=['### File inventory\n',
        '- `experiments/robustness/core.py`: reused definitions, filtering, operators, preprocessing, metrics and preservation hashes.\n- `run.py`: resumable CV/test runner; it rejects mixed code/data and requires complete CV before tests.\n- `protocol.json`: immutable experiment choices.\n- `test_robustness.py`: automated experiment controls.\n- `report.py`: generates every report table from run outputs.\n- `.gitignore`: local binary exclusions. No model binary is saved.\n- `results/manifest.json`: filtering, classes, exact split source-row IDs, library/estimator configuration and hashes.\n- `results/prespecified_document.md`: report snapshot before training.\n- `results/cv/*.json`: 40 paired fold/variant records, 80 trained forests.\n- `results/test/*.json`: 40 paired seed/variant records, 80 trained forests.\n- `results/metrics.csv`: all 480 arm/condition records with per-class metrics.\n- `results/summary.csv`: all 432 aggregated metric records with paired SD and wins.\n- `results/decisions.json`: eight fixed-rule outcomes.\n- `results/preservation_check.json`: final protected-file verification.\n- `docs/ROBUSTNESS_EXPERIMENT.md`: this complete narrative and tables.\n',
        'Additional experiment files: `docs/ROBUSTNESS_RUN_GUIDE.md` documents execution/resume; `finish_run.py` queues final phases; `environment.json` records hardware; `results/tests.txt` records the final test suite; `results/report_manifest.json` records report/test code hashes and integrity checks. The Markdown file under results is an immutable pre-run evidence snapshot, not a maintained document.\n',
        f"All {len(manifest['protected_hashes'])} protected dataset, deployed-artifact and active source/configuration files matched their pre-run SHA-256 values at report generation. Run files contain model seeds, fold identifiers, medians, paired input hashes, row counts and degradation statistics.\n",
        '## 15 Next steps\n',
        'Keep deployment unchanged. A follow-up could lock a temporal and external-region test set, evaluate real sensor dropout/noise, assess calibration and class-specific costs, and repeat with grouped inner CV. If compact forests or specialist comparisons are desired, preregister them as separate sensitivity experiments and report every result. Do not use this test set to select a new degradation recipe and then present its score as independent validation.\n',
        '## Appendix Per class F1 for every condition\n',
        'Each row reports A and B mean ± sample SD, paired B−A in percentage points and B wins. Test rows vary across five seeds; CV rows vary across five folds. All class-specific results are included.\n']
    for phase,records in [('Test',tests),('CV',cv)]:
        for protocol in ['random','station']:
            rows=[]
            for variant in PROTOCOL['variants']:
                for cond in ['clean','moderate','severe']:
                    for category in CATEGORIES:
                        s=summary(records,protocol,variant,cond,f'f1_{category}')
                        rows.append([NAMES[variant],cond,category,ms(s['a']),ms(s['b']),ms(s['delta']),f"{s['wins']}/5"])
            chunks.append(f'### {phase} {protocol}\n'+table(['Variant','Condition','Class','A F1 %','B F1 %','B−A pp','B wins'],rows))
    (ROOT/'docs/ROBUSTNESS_EXPERIMENT.md').write_text('\n'.join(chunks),encoding='utf-8')
    print(json.dumps(decisions,indent=2))

if __name__=='__main__':main()
