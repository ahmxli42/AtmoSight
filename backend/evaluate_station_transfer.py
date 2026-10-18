"""Fair station-transfer comparison; evaluation pipelines are separate from shipped models."""
import json
import pandas as pd
import sklearn
from sklearn.model_selection import GroupShuffleSplit
from sklearn.metrics import accuracy_score,f1_score,classification_report,confusion_matrix
from backend.train import ROOT,ARTIFACTS,FEATURES,CATEGORIES
from backend.train_sensor_models import pipeline

data=pd.read_csv(ROOT/'Dataset/station_day.csv').dropna(subset=['AQI_Bucket']).drop_duplicates(['StationId','Date'])
data=data[data.AQI_Bucket.isin(CATEGORIES)].copy()
data[FEATURES]=data[FEATURES].apply(pd.to_numeric,errors='coerce')
data=data.loc[~(data[FEATURES]<0).any(axis=1)].reset_index(drop=True)
train,test=next(GroupShuffleSplit(n_splits=1,test_size=.2,random_state=42).split(data,groups=data.StationId.fillna('Unknown')))
train_stations=sorted(data.loc[train,'StationId'].dropna().unique().tolist())
test_stations=sorted(data.loc[test,'StationId'].dropna().unique().tolist())
assert not set(train_stations)&set(test_stations)
for identifier in ['pm25','pm_pair']:
    path=ARTIFACTS/f'{identifier}.json';meta=json.loads(path.read_text(encoding='utf-8'))
    meta['scikit_learn_version']=sklearn.__version__
    meta['station_holdout'].update(training_station_ids=train_stations,test_station_ids=test_stations)
    path.write_text(json.dumps(meta,indent=2),encoding='utf-8')
model=pipeline(limited=False).fit(data.loc[train,FEATURES],data.loc[train,'AQI_Bucket'])
pred=model.predict(data.loc[test,FEATURES])
meta={'accuracy':accuracy_score(data.loc[test,'AQI_Bucket'],pred),'macro_f1':f1_score(data.loc[test,'AQI_Bucket'],pred,average='macro'),
    'classification_report':classification_report(data.loc[test,'AQI_Bucket'],pred,output_dict=True),
    'confusion_matrix':confusion_matrix(data.loc[test,'AQI_Bucket'],pred,labels=CATEGORIES).tolist(),
    'test_rows':len(test),'train_rows':len(train),'training_stations':len(train_stations),'test_stations':len(test_stations),
    'training_station_ids':train_stations,'test_station_ids':test_stations,
    'description':'Separate six-feature pipeline trained on 87 stations, tested on 22 unseen stations; training-only imputation. Seed 42. No shipped model replacement.'}
(ARTIFACTS/'baseline_station_evaluation.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
print(json.dumps({k:meta[k] for k in ['accuracy','macro_f1','test_rows','training_stations','test_stations']},indent=2))
