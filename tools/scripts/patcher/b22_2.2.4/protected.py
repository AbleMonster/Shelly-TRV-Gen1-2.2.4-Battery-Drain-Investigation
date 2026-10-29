#!/usr/bin/env python3
"""Check retained historical inventories without altering them."""
import hashlib,json,argparse
from pathlib import Path
R=Path(__file__).resolve().parents[4];Q=R/'builds/build_b22_2026-10-28';H=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def check(out):
 old=json.loads((R/'analysis/evidence/p01-p02-patch-qualification-2026-10-28/protected-artifacts-final.json').read_text());rows=[]
 for prev in old['historical_inventories']:
  p=R/prev['inventory'];bad=[];n=0
  for l in p.read_text().splitlines():
   h,f=l.split(maxsplit=1);q=p.parent/f.lstrip('*')
   if not q.is_file():bad.append({'file':f.lstrip('*'),'error':'missing'})
   elif H(q)!=h:bad.append({'file':f.lstrip('*'),'error':'SHA256 mismatch'})
   else:n+=1
  assert H(p)==prev['inventory_sha256'] and n==prev['files_matching'] and bad==prev['mismatches'],str(p)
  rows.append({'inventory':str(p.relative_to(R)),'SHA256':H(p),'matches':n,'retained_unresolved':bad})
 evidence=[]
 for root in ['p01-p02-patch-qualification-2026-10-28','peripheral-lifecycle-audit-2026-10-28','battery-analysis-2026-10-28','auto-calibration-2026-10-28','calibration-self-requeue-2026-10-28']:
  p=R/'analysis/evidence'/root/'SHA256SUMS';n=0
  for l in p.read_text().splitlines():
   h,f=l.split(maxsplit=1);q=p.parent/f.lstrip('*');assert q.is_file() and H(q)==h,str(q);n+=1
  evidence.append(dict(inventory=str(p.relative_to(R)),SHA256=H(p),files=n))
 d=dict(status='PASS',historical_inventories=rows,evidence_inventories=evidence,network_or_devices_contacted=False);out.write_text(json.dumps(d,indent=2)+'\n');print('PASS',len(rows),'build inventories',sum(x['matches'] for x in rows),'matches; evidence',sum(x['files']for x in evidence))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();check(a.out)
