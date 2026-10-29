#!/usr/bin/env python3
"""Container emission is gated by completed final-application qualification."""
import argparse,hashlib,importlib.util,json,struct,zlib
from pathlib import Path
R=Path(__file__).resolve().parents[4];Q=R/'builds/build_b22_2026-10-28'
s=importlib.util.spec_from_file_location('b22build',Path(__file__).with_name('build.py'));b=importlib.util.module_from_spec(s);s.loader.exec_module(b)
def pack(app,records):
 out=bytearray()
 for i,(t,v)in enumerate(records):
  if i==3:v=bytes(4)+app
  if i==5:
   out+=struct.pack('<II',t,4);out+=struct.pack('<I',zlib.crc32(out));break
  out+=struct.pack('<II',t,len(v))+v
 return bytes(out)
def main():
 gate=json.loads((Q/'qualification/pre-container-gate.json').read_text());b.need(gate['status']=='PASS','pre-container gate')
 for n,h in gate['pins'].items():b.need(b.H((R/n).read_bytes())==h,'qualified input/source/result changed '+n)
 a=(Q/'build_a/application.bin').read_bytes();c=(Q/'build_b/application.bin').read_bytes();b.need(a==c and b.H(a)==gate['application_SHA256'],'determinism/qualification image')
 parent=Path(str(b.P)+'.bin').read_bytes();pg=Path(str(b.P)+'.gbl').read_bytes();records=b.parents(b.STOCK.read_bytes(),parent,pg,b.SG.read_bytes())
 results=[]
 for label,app in [('build_a',a),('build_b',c)]:
  b.validate_claim(app,json.loads((Q/label/'construction-manifest.json').read_text()))
  hs={q['name']:(Q/label/f'component_{i+6}/helper.bin').read_bytes()for i,q in enumerate(b.SPECS)};b.result(parent,app,hs);g=pack(app,records);b.parse(g)
  p=Q/label/'SHTRV-01_2.2.4_B2.2_EXPERIMENTAL.gbl';b.need(not p.exists()or p.read_bytes()==g,'existing container differs');p.write_bytes(g)
  results.append(dict(build=label,size=len(g),SHA256=b.H(g),END_CRC=f'{struct.unpack("<I",g[-4:])[0]:08X}',residue=f'{zlib.crc32(g):08X}'))
 b.need(results[0]['SHA256']==results[1]['SHA256'],'GBL nondeterminism');b.dump(Q/'qualification/container-construction.json',dict(status='PASS',results=results,independent_verification='REQUIRED before final copy'))
 print(json.dumps(results,indent=2))
if __name__=='__main__':main()
