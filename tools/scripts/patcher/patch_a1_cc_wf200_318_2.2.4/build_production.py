#!/usr/bin/env python3
"""Fail-closed staged A1 composition. No network or device operations.
The final GBL path is unavailable until whole-application controls PASS.
"""
from pathlib import Path
import hashlib,json,struct,zlib,argparse
ROOT=Path(__file__).resolve().parents[4]
OUT=ROOT/'build_a1_cc_wf200_318_final_2026-10-20'
BASE=ROOT/'build_cc_wf200_318_2026-10-19'
NAME='SHTRV-01_2.2.4_A1_C-C_WF200_3.18.0_EXPERIMENTAL'
PINS={
 'build_cc_wf200_318_2026-10-19/SHTRV-01_2.2.4_C-C_WF200_3.18.0_EXPERIMENTAL.bin':'f323d1b1ea062f086217e189e8cb15bcb18063e3d02f40b4fe1c842161fcb353',
 'build_cc_wf200_318_2026-10-19/SHTRV-01_2.2.4_C-C_WF200_3.18.0_EXPERIMENTAL.gbl':'7243fd580c817797d552e2ee8518ae5dfc3eef9cab6b729e9289e6f727a4a99b',
 'build_a1_executable_core_2026-10-20/core.text':'73843b24a7bc3d537c569c6bad34cf2a521664993c2685e1a6dd4858b591d6fb',
 'extracted/program_1_0x00000000.bin':'4dc770fe535008ef150f3a144354169199e1a0e235173abcc3f7387b95ee9b5c',
 'original/WF200/wfx-firmware/wfm_wf200_C0.sec':'886d009b3852cb41f7c67c85de5c9bf2e6d67614e10d668b4fa1e18734078cb9'}
def sha(x):return hashlib.sha256(x).hexdigest()
def require(x,m):
 if not x:raise ValueError(m)
def pinned():
 d={}
 for p,h in PINS.items():
  d[p]=(ROOT/p).read_bytes();require(sha(d[p])==h,'INPUT HASH '+p)
 return d

def construct():
 inputs=pinned();baseline=inputs[next(iter(PINS))]
 inventory=json.loads((OUT/'final-hook-inventory.json').read_text())
 require(not inventory['issues'] and not inventory['stale_asset_objects'],'Unqualified hook inventory')
 hooks=inventory['hooks'];require(all(h['replacement'] is not None for h in hooks),'Incomplete encodings')
 assets=(OUT/'linked-assets/adapter-assets.text').read_bytes()
 am=json.loads((OUT/'linked-assets/asset-manifest.json').read_text())
 require(sha(assets)==am['sha256'] and int(am['base'],16)==0x101a00,'Assets changed')
 core=inputs['build_a1_executable_core_2026-10-20/core.text']
 startup=(ROOT/'build_a1_cc_wf200_318_integration_2026-10-20/startup-adapter.text').read_bytes()
 require(len(core)==4318 and len(startup)==28,'Frozen components size')
 end=0x101a00+len(assets);require(end<0x130a98 and end%4==0,'First PROGRAM overlap/alignment')
 app=bytearray(baseline)+bytearray(b'\xff'*(end-len(baseline)));recipe=[];used=set()
 def put(at,data,kind):
  r=set(range(at,at+len(data)));require(not used.intersection(r),'Overlapping write '+hex(at));used.update(r)
  require(at+len(data)<=len(app),'Write extent');app[at:at+len(data)]=data
  recipe.append({'start':hex(at),'end':hex(at+len(data)),'class':kind,'bytes':len(data),'sha256':sha(data)})
 # All hook preimages checked against immutable baseline before any write.
 for h in hooks:
  a=int(h['site'],16);old=bytes.fromhex(h['baseline_preimage']);new=bytes.fromhex(h['replacement'])
  require(len(new)==len(old)==h['bytes'] and baseline[a:a+len(old)]==old,'HOOK PREIMAGE '+hex(a))
 for h in hooks:
  a=int(h['site'],16);kind='startup/MSP reservation' if a in (0,0x206,0x254) else 'A1 production hook'
  put(a,bytes.fromhex(h['replacement']),kind)
 # Explicit gap provenance; previous baseline extent ends exactly at C-C end.
 for a,b in [(len(baseline),0x100900),(0x1019de,0x1019e0),(0x1019fc,0x101a00)]:
  require(b>=a,'Padding range');put(a,bytes([255])*(b-a),'integration alignment padding')
 put(0x100900,core,'frozen A1 core insertion')
 put(0x1019e0,startup,'qualified A1 initializer integration')
 put(0x101a00,assets,'production settlement/owner/PM/G18 adapters and veneers')
 # Protected radio and helper bytes must remain exact; shared C-C stock hooks
 # are the only allowed C-C instruction replacements and are in hook inventory.
 require(app[0xada20:0xf9e70]==inputs['original/WF200/wfx-firmware/wfm_wf200_C0.sec'],'Protected radio changed')
 require(app[0x1003d0:0x1008ec]==baseline[0x1003d0:0x1008ec],'Relocation/C-C helper overwritten')
 require(app[0xff118:0x1003cc]==baseline[0xff118:0x1003cc],'Reset copy source changed')
 changed=[];start=None;lastclass=None
 classes={i:r['class'] for r in recipe for i in range(int(r['start'],16),int(r['end'],16))}
 for i,v in enumerate(app):
  different=i>=len(baseline) or v!=baseline[i]
  c=classes.get(i) if different else None
  require(not different or c,'Unexplained application byte '+hex(i))
  if start is not None and c!=lastclass:
   changed.append({'start':hex(start),'end':hex(i),'bytes':i-start,'class':lastclass});start=None
  if c is not None and start is None:start=i
  lastclass=c
 if start is not None:changed.append({'start':hex(start),'end':hex(len(app)),'bytes':len(app)-start,'class':lastclass})
 manifest={'status':'WORKING APPLICATION; NOT FOR DEVICE TEST','application_sha256':sha(app),'application_bytes':len(app),'core_sha256':sha(core),'assets_sha256':sha(assets),'startup_sha256':sha(startup),'hook_inventory_sha256':sha((OUT/'final-hook-inventory.json').read_bytes()),'recipe':sorted(recipe,key=lambda r:int(r['start'],16)),'changed_ranges':changed,'unexplained_changed_bytes':0,'immutable_inputs':PINS}
 return bytes(app),manifest

def pack_gbl(app):
 raw=(BASE/'SHTRV-01_2.2.4_C-C_WF200_3.18.0_EXPERIMENTAL.gbl').read_bytes();out=bytearray();p=0;programs=0
 while p<len(raw):
  tag,n=struct.unpack_from('<II',raw,p);record=raw[p:p+8+n];body=raw[p+8:p+8+n];require(len(record)==8+n,'Baseline GBL truncation')
  if tag==0xfd0303fd:
   programs+=1
   if programs==1:
    require(body[:4]==bytes(4),'First PROGRAM load');body=bytes(4)+app;record=struct.pack('<II',tag,len(body))+body
  if tag==0xfc0404fc:
   require(p+8+n==len(raw) and n==4,'END');record=struct.pack('<II',tag,4);out+=record;out+=struct.pack('<I',zlib.crc32(out))
  else:out+=record
  p+=8+n
 require(programs==2 and zlib.crc32(out)==0x2144df1c,'Final GBL geometry/CRC')
 return bytes(out)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--final',action='store_true');args=ap.parse_args()
 gate=json.loads((OUT/'settlement-qualification.json').read_text());require(gate['verdict']=='SETTLEMENT ABI QUALIFIED','Settlement gate')
 v=json.loads((OUT/'linked-assets/independent-linked-assets.json').read_text());require(v['result']=='PASS','Asset verifier')
 a,m=construct();b,n=construct();require((a,m)==(b,n),'Nondeterministic application')
 debug=OUT/'working';debug.mkdir(exist_ok=True)
 (debug/'NOT-FOR-DEVICE-TEST.bin').write_bytes(a);(debug/'construction-manifest.json').write_text(json.dumps(m,indent=2)+'\n')
 if args.final:
  freeze=json.loads((OUT/'production-freeze.json').read_text())
  for path,digest in freeze['pins'].items():require(sha((ROOT/path).read_bytes())==digest,'Frozen production input '+path)
  q=json.loads((OUT/'verification-results.json').read_text());require(q['application_sha256']==sha(a) and q['ready_for_GBL'] is True,'Whole application gate')
  neg=json.loads((OUT/'negative-controls.json').read_text());require(neg['canonical_executed']==36 and neg['canonical_passed']==36 and neg['malformed_constructions_rejected']==36,'Canonical whole firmware controls')
  g=pack_gbl(a);require(g==pack_gbl(b),'Nondeterministic GBL')
  for p,data in [(OUT/(NAME+'.bin'),a),(OUT/(NAME+'.gbl'),g)]:
   require(not p.exists() or p.read_bytes()==data,'Existing output differs');p.write_bytes(data)
  print(json.dumps({'application':sha(a),'GBL':sha(g),'GBL_bytes':len(g),'CRC32':hex(struct.unpack_from('<I',g,len(g)-4)[0]),'deterministic':True},indent=2))
 else:print('WORKING APPLICATION ONLY',len(a),sha(a))
if __name__=='__main__':main()
