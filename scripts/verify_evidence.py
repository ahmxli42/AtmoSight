from pathlib import Path
import hashlib, json
root=Path(__file__).resolve().parents[1]
manifest=json.loads((root/'MANIFEST.json').read_text(encoding='utf-8'))
records=[x for x in manifest['inventory'] if x['path'].startswith('experiments/robustness/results/') and x['include']]
for item in records:
    p=root/item['path']
    if hashlib.sha256(p.read_bytes()).hexdigest()!=item['sha256']:raise SystemExit('FAIL: changed '+item['path'])
print(f'PASS: {len(records)} archived experiment files match original SHA-256 hashes')
