"""Scan Git source files; generated dependencies and model binaries are excluded."""
from pathlib import Path
import json, re, subprocess
root=Path(__file__).resolve().parents[1]
names=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=root).decode().split('\0')
patterns={
 'personal_path':rb'(?i)(?:[a-z]:[\\/](?:users|documents and settings)[\\/]|/Users/|/home/)',
 'machine_root':rb'(?i)[a-z]:\\(?:ML-Based-Air-Classification-System|atmosight-clean)',
 'private_key':rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
 'known_token':rb'(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,}|AKIA[A-Z0-9]{16}|sk-[A-Za-z0-9_-]{30,})',
 'literal_credential':rb'(?i)(?:password|api_key|access_token|secret_key)\s*[=:]\s*["\'][^"\'\r\n]{8,}["\']',
}
findings=[];size=0;count=0
for name in sorted(set(filter(None,names))):
 p=root/name
 if not p.is_file():continue
 b=p.read_bytes();count+=1;size+=len(b)
 if len(b)>50_000_000:findings.append({'file':name,'rule':'over_50_MB'})
 if p.name.startswith('.env') or p.suffix in {'.joblib','.pkl','.pickle'}:findings.append({'file':name,'rule':'excluded_file'})
 # Patterns themselves are source code, not credentials/paths.
 if name=='scripts/verify_repository.py':continue
 for rule,pattern in patterns.items():
  if re.search(pattern,b):findings.append({'file':name,'rule':rule})
print(json.dumps({'source_files':count,'bytes':size,'findings':findings},indent=2))
if findings:raise SystemExit(1)
