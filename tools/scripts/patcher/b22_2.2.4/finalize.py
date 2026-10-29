#!/usr/bin/env python3
"""Copy experimental outputs only after frozen software and independent container gates."""
from pathlib import Path
import hashlib,json,shutil,zlib,struct
R=Path(__file__).resolve().parents[4];Q=R/'builds/build_b22_2026-10-28';K=Q/'qualification';H=lambda b:hashlib.sha256(b).hexdigest()
def need(x,m):
 if not x:raise ValueError(m)
def main():
 pre=json.loads((K/'pre-container-gate.json').read_text());ind=json.loads((K/'independent/final-container-gate.json').read_text())
 need(pre['status']=='PASS' and ind['status']=='PASS' and ind['unexplained_container_changes']==0 and ind['application']['unexplained_application_bytes']==0,'mandatory gates')
 for p,h in pre['pins'].items():need(H((R/p).read_bytes())==h,'frozen qualification changed '+p)
 a=(Q/'build_a/application.bin').read_bytes();b=(Q/'build_b/application.bin').read_bytes();need(a==b and H(a)==pre['application_SHA256']==ind['application']['application_sha256'],'app binding')
 name='SHTRV-01_2.2.4_B2.2_EXPERIMENTAL';ga=(Q/'build_a'/f'{name}.gbl').read_bytes();gb=(Q/'build_b'/f'{name}.gbl').read_bytes()
 need(ga==gb and H(ga)==ind['GBL']['GBL_SHA256'],'GBL binding');need(zlib.crc32(ga)==0x2144df1c and struct.unpack('<I',ga[-4:])[0]==zlib.crc32(ga[:-4]),'CRC');need(zlib.crc32(a)==int(ind['application']['application_crc32'],16),'application CRC')
 need(json.loads((Q/'evidence/protected-after.json').read_text())['status']=='PASS','protected artifacts')
 out=Q/'final';out.mkdir(exist_ok=True)
 for suffix,data in [('.bin',a),('.gbl',ga)]:
  p=out/(name+suffix);need(not p.exists() or p.read_bytes()==data,'existing final differs');p.write_bytes(data)
 result=dict(status='B2.2 OFFLINE RELEASE-CANDIDATE GO',application=ind['application'],GBL=ind['GBL'],component_count=9,observer_free=True,hardware_qualified=False,battery_drain_elimination_proven=False,protected_artifacts='PASS',independent_container='PASS',frozen_qualification_pins='PASS')
 (K/'final-gate.json').write_text(json.dumps(result,indent=2)+'\n');(out/'SHA256SUMS').write_text(''.join(H(p.read_bytes())+'  '+p.name+'\n'for p in [out/(name+'.bin'),out/(name+'.gbl')]))
 print(result['status']);print(H(ga),name+'.gbl')
if __name__=='__main__':main()
