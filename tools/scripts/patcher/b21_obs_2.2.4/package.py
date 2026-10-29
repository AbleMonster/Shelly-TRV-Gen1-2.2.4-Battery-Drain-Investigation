#!/usr/bin/env python3
"""Gated B2.1_OBS package; creates no artifact until independent checks pass."""
from pathlib import Path
import argparse,struct,json,hashlib,zlib,importlib.util
ROOT=Path(__file__).resolve().parents[4];HERE=Path(__file__).resolve().parent;Q=ROOT/'builds/build_b21_obs_2026-10-28';NAME='SHTRV-01_2.2.4_B2.1_OBS_EXPERIMENTAL'
H=lambda b:hashlib.sha256(b).hexdigest()
def mod(p,n):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def main():
 p=argparse.ArgumentParser();p.add_argument('--out',required=True,type=Path);a=p.parse_args();gate=json.loads((Q/'pre-container-gate.json').read_text());assert gate['status']=='PASS'
 for n,h in gate['source_result_pins'].items():assert H((ROOT/n).read_bytes())==h,n
 app=(Q/'build1/working.bin').read_bytes();assert H(app)==gate['application_sha256'] and app==(Q/'build2/working.bin').read_bytes()
 v=mod(HERE/'verify_gbl.py','independent_container');base=(ROOT/'builds/build_a1r_all_known_2026-10-28/final/SHTRV-01_2.2.4_A1R_C-C_B2_MQTT_WF200_3.18.0_EXPERIMENTAL.gbl').read_bytes();assert H(base)=='5f81869922c9b2eed4eb2f730ed53f5a66cf8b09d5f7d12205a4f6fbcd7392d9'
 g=bytearray()
 for i,(t,b,_) in enumerate(v.parse(base)):
  if i==3:b=bytes(4)+app
  if t==0xfc0404fc:g+=struct.pack('<II',t,4);g+=struct.pack('<I',zlib.crc32(g))
  else:g+=struct.pack('<II',t,len(b))+b
 g=bytes(g);r=v.verify(g,app);r['malformed_controls']=v.controls(g,app)
 a.out.mkdir(parents=True,exist_ok=True)
 for n,b in [(NAME+'.bin',app),(NAME+'.gbl',g)]:
  f=a.out/n;assert not f.exists() or f.read_bytes()==b;f.write_bytes(b)
 (a.out/'container-manifest.json').write_text(json.dumps(r,indent=2,sort_keys=True)+'\n');print({k:v for k,v in r.items() if k not in ['records','malformed_controls']})
if __name__=='__main__':main()
