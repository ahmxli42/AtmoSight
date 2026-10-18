"""Add a reproducible synthetic noise stress test without retraining the saved model."""
import json
import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, f1_score
from backend.train import ROOT, ARTIFACTS, FEATURES, CATEGORIES

raw = pd.read_csv(ROOT / 'Dataset' / 'station_day.csv')
data = raw.dropna(subset=['AQI_Bucket']).drop_duplicates(subset=['StationId','Date'])
data = data[data.AQI_Bucket.isin(CATEGORIES)].copy()
data[FEATURES] = data[FEATURES].apply(pd.to_numeric, errors='coerce')
data = data.loc[~(data[FEATURES] < 0).any(axis=1)]
_, x_test, _, y_test = train_test_split(data[FEATURES], data.AQI_Bucket, test_size=.2, stratify=data.AQI_Bucket, random_state=42)
model = joblib.load(ARTIFACTS / 'baseline.joblib')['model']
metadata = json.loads((ARTIFACTS / 'metadata.json').read_text(encoding='utf-8'))
metadata['noise_stress'] = []
rng = np.random.default_rng(42)
for scale in [.1, .3, .5]:
    noisy = x_test * np.maximum(0, 1 + rng.normal(0, scale, size=x_test.shape))
    pred = model.predict(noisy)
    metadata['noise_stress'].append({'relative_std': scale, 'accuracy': accuracy_score(y_test,pred), 'macro_f1': f1_score(y_test,pred,average='macro')})
(ARTIFACTS / 'metadata.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
print(json.dumps(metadata['noise_stress'], indent=2))
