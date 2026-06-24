from src.webapp.app import _scan_only, _ensure_seeding, _seeded
import time
_ensure_seeding()
while not _seeded(): time.sleep(1)
sigs = _scan_only()
print('Total signals:', len(sigs))
for s in sigs:
    print(s['pair'], s['tf'], s['direction'], s.get('time'), s.get('conf'))
