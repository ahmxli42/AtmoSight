"""Reproducible new baseline; never overwrites the original research artifacts."""
import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import RandomForestClassifier, IsolationForest
from sklearn.impute import SimpleImputer
from sklearn.metrics import accuracy_score, f1_score, classification_report, confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

FEATURES = ['PM2.5', 'PM10', 'SO2', 'NO2', 'CO', 'O3']
CATEGORIES = ['Good', 'Satisfactory', 'Moderate', 'Poor', 'Very Poor', 'Severe']
ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / 'backend' / 'artifacts'

def train():
    raw = pd.read_csv(ROOT / 'Dataset' / 'station_day.csv')
    data = raw.dropna(subset=['AQI_Bucket']).drop_duplicates(subset=['StationId', 'Date'])
    data = data[data.AQI_Bucket.isin(CATEGORIES)].copy()
    data[FEATURES] = data[FEATURES].apply(pd.to_numeric, errors='coerce')
    data = data.loc[~(data[FEATURES] < 0).any(axis=1)]
    x_train, x_test, y_train, y_test = train_test_split(
        data[FEATURES], data.AQI_Bucket, test_size=.2, stratify=data.AQI_Bucket, random_state=42)
    model = Pipeline([('imputer', SimpleImputer(strategy='median')),
                      ('classifier', RandomForestClassifier(n_estimators=200,
                       class_weight='balanced', random_state=42, n_jobs=-1))])
    model.fit(x_train, y_train)
    pred = model.predict(x_test)
    anomaly = IsolationForest(n_estimators=200, contamination=.05, random_state=42, n_jobs=-1)
    anomaly.fit(model['imputer'].transform(x_train))
    metadata = {
        'scikit_learn_version': sklearn.__version__,
        'dataset_sha256': hashlib.sha256((ROOT / 'Dataset' / 'station_day.csv').read_bytes()).hexdigest(),
        'evaluated_at_utc': datetime.now(timezone.utc).isoformat(),
        'name': 'Six-pollutant Random Forest', 'features': FEATURES, 'categories': CATEGORIES,
        'observations': len(data), 'train_rows': len(x_train), 'test_rows': len(x_test),
        'accuracy': accuracy_score(y_test, pred), 'macro_f1': f1_score(y_test, pred, average='macro'),
        'classification_report': classification_report(y_test, pred, output_dict=True),
        'confusion_matrix': confusion_matrix(y_test, pred, labels=CATEGORIES).tolist(),
        'imputation': dict(zip(FEATURES, model['imputer'].statistics_.tolist())),
        'estimators': 200, 'seed': 42, 'calibrated': False,
        'source': 'Kaggle Air Quality Data in India 2015–2020 / station_day.csv',
        'evaluation': 'New local reproduction: stratified random 80/20 split. Training-only global median imputation. Not the historical 77.31% baseline.',
        'limitations': ['Random split is not a held-out station or temporal validation.',
                       'Missing-input robustness and probability calibration have not been validated.',
                       'Isolation Forest flags statistical rarity, not sensor failure.',
                       'Only the six-pollutant model is available. No temporal or PM-only model.'],
        'robustness': [],
    }
    rng = np.random.default_rng(42)
    for fraction in [.1, .3, .5]:
        degraded = x_test.copy()
        degraded = degraded.mask(rng.random(degraded.shape) < fraction)
        degraded_pred = model.predict(degraded)
        metadata['robustness'].append({'missing_fraction': fraction,
            'accuracy': accuracy_score(y_test, degraded_pred),
            'macro_f1': f1_score(y_test, degraded_pred, average='macro')})
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    joblib.dump({'model': model, 'anomaly': anomaly}, ARTIFACTS / 'baseline.joblib', compress=3)
    metadata['artifact_sha256'] = hashlib.sha256((ARTIFACTS / 'baseline.joblib').read_bytes()).hexdigest()
    (ARTIFACTS / 'metadata.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    print(json.dumps({k: metadata[k] for k in ['observations', 'accuracy', 'macro_f1', 'robustness']}, indent=2))

if __name__ == '__main__':
    train()
