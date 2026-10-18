from pathlib import Path
import hashlib
p=Path(__file__).resolve().parents[1]/'Dataset/station_day.csv'
expected='67c308463abab12507f0c9892549fedfc099221025cbcb3e308be170b5a6a0ad'
actual=hashlib.sha256(p.read_bytes()).hexdigest()
if actual!=expected: raise SystemExit('FAIL: dataset SHA-256 mismatch')
print('PASS: station_day.csv SHA-256 '+actual)
