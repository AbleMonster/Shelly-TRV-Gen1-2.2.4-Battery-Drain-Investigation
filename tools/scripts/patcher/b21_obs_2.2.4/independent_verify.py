#!/usr/bin/env python3
"""Independent byte/branch/relocation/provenance checker; no builder imports."""
from pathlib import Path
import struct,json,hashlib,importlib.util,argparse
ROOT=Path(__file__).resolve().parents[4]
Q=ROOT/'builds/build_b21_obs_2026-10-28';OLD=ROOT/'builds/build_pm52_cmd66_observer_2026-10-26'
P=ROOT/'builds/build_a1r_all_known_2026-10-28/final/SHTRV-01_2.2.4_A1R_C-C_B2_MQTT_WF200_3.18.0_EXPERIMENTAL.bin'
H=lambda b:hashlib.sha256(b).hexdigest()
EXT=0x104718;END=0x1050f4;EXTH='17734e07e2cfa1d7f8ea1b2c8a40a65589b6eb9c65dada2d40d7c3b7ffdf873c'
# Fixed, independently reviewed seam map, not read from construction manifest.
SITES={0x1bd6:(4,0x104762),0x1bda:(4,0x104842),0x1e104:(4,0x104922),0x1e108:(4,0x1049a4),0x1e132:(10,0x104a22),0x57fc4:(4,0x104b80),0x58120:(4,0x104d40),0x102f88:(6,0x104c64),0x103aee:(4,0x104e18),0x103b84:(4,0x104ed0),0x1019f8:(4,0x104718),0x19e8c:(4,0x104f84)}
def need(x,s):
 if not x:raise ValueError(s)
def branch(b,a):
 x,y=struct.unpack_from('<HH',b,a);need(x&0xf800==0xf000 and y&0xd000==0x9000,'B.W encoding')
 s=x>>10&1;v=s<<24|(1^(y>>13&1)^s)<<23|(1^(y>>11&1)^s)<<22|(x&1023)<<12|(y&2047)<<1
 return a+4+v-(1<<25 if s else 0)
def verify(b):
 base=P.read_bytes();need(H(base)=='31ddd06a0229fee0b0b58dcbbd28ced1e4fbab0b6dc218c76c9d93673f4961e0' and len(base)==EXT,'B2.1 required')
 need(len(b)==END and H(b[EXT:])==EXTH,'reviewed emitted extension')
 allowed=set();ranges=[]
 for a,(n,t) in SITES.items():
  need(branch(b,a)==t,'hook target '+hex(a));need(b[a+4:a+n]==bytes.fromhex('00bf')*((n-4)//2),'hook padding')
  allowed.update(range(a,a+n));ranges.append(dict(start=hex(a),end=hex(a+n),before=base[a:a+n].hex(),after=b[a:a+n].hex(),owner='PM52/cmd66 observer',target=hex(t)))
 for a in [0,0x254]:
  need(base[a:a+4]==bytes.fromhex('80ff0720') and b[a:a+4]==bytes.fromhex('80fd0720'),'MSP reservation')
  allowed.update(range(a,a+4));ranges.append(dict(start=hex(a),end=hex(a+4),before=base[a:a+4].hex(),after=b[a:a+4].hex(),owner='observer RAM reservation'))
 need(all(b[i]==base[i] or i in allowed for i in range(EXT)),'unexpected B2.1 difference')
 need(b[0x1046dc:EXT]==base[0x1046dc:EXT] and b[0x103878:0x10387e]==base[0x103878:0x10387e],'A1R preserved')
 need(H(b[0xada20:0xf9e70])=='886d009b3852cb41f7c67c85de5c9bf2e6d67614e10d668b4fa1e18734078cb9','official SEC')
 # Reconstruct the historical observer image from its pinned actual artifact.
 old=(OLD/'build1'/next(p.name for p in (OLD/'build1').glob('*.bin'))).read_bytes();need(H(old)=='0c2782e8387294bb9f78ae822f6fa7d34f9b36fcbf3efb019727f99fc6d93bc3','historical observer')
 # All event, startup and wrapper bytes are identical modulo thirteen native
 # B.W displacements. Internal branches are PC-relative and unchanged.
 native=[0x104722,0x104802,0x1048e2,0x104964,0x1049e2,0x104b40,0x104c24,0x104d00,0x104dd8,0x104e8c,0x104e90,0x104f44,0x104f7a]
 normalized=bytearray(b[EXT:0x104fbc]);prior=old[0x1046dc:0x104f80]
 reloc=[]
 for a in native:
  need(branch(old,a)==branch(b,a+60),'native continuation moved')
  normalized[a-0x1046dc:a-0x1046dc+4]=old[a:a+4]
  reloc.append(dict(old=hex(a),new=hex(a+60),target=hex(branch(b,a+60))))
 need(normalized==prior,'event implementation changed beyond relocation')
 need(b.count(b'B2.1_OBS')==1 and b',"research_build":"B2.1_OBS","pm52_cmd66":{"v":1,"w":"\0' in b[EXT:],'readout-only ID literal')
 # Reuse independent complete B2.1 stock provenance, verified against actual
 # bytes, then overlay ONLY exact observer seams and appended extension.
 stock=(ROOT/'extracted/program_1_0x00000000.bin').read_bytes();runs=json.loads((ROOT/'builds/build_a1r_all_known_2026-10-28/independent-a1r-byte-provenance.json').read_text())['runs'];classes={}
 for r in runs:
  a=int(r['start'],16);z=int(r['end_exclusive'],16)
  need(base[a:z].hex()==r['replacement'],'retained provenance bytes')
  for i in range(a,z):classes[i]=r['owner']
 for a,(n,_) in SITES.items():
  for i in range(a,a+n):classes[i]='PM52/cmd66 observer'
 for a in [0,0x254]:
  for i in range(a,a+4):classes[i]='observer MSP reservation'
 for i in range(EXT,END):classes[i]='observer relocated code / explicit build-ID readout'
 out=[];start=None;last=None
 for i in range(END+1):
  c=None if i==END or (i<len(stock) and b[i]==stock[i]) else classes.get(i)
  need(i==END or i<len(stock) and b[i]==stock[i] or c is not None,'unexplained stock byte '+hex(i))
  if start is not None and c!=last:
   out.append(dict(start=hex(start),end=hex(i),owner=last,original=stock[start:min(i,len(stock))].hex(),replacement=b[start:i].hex()));start=None
  if c is not None and start is None:start=i
  last=c
 return dict(status='PASS',application_sha256=H(b),application_size=len(b),unexplained_changed_bytes=0,patch_regions=ranges,event_code_relocation_equivalence=reloc,stock_provenance=out,new_RAM=512,new_event_stack=32,new_readout_stack=568)
def controls(b):
 out=[]
 for a in list(SITES)+[b.index(b'B2.1_OBS'),0,0x254,EXT,END-3,0x103878,0x1046dc,0x6c94,0x589fc,0xada20,0xfd760,0x19e40,0x40000]:
  x=bytearray(b);x[a]^=1
  try:verify(x)
  except (ValueError,struct.error):out.append(dict(case=hex(a),rejected=True));continue
  raise ValueError('mutation accepted '+hex(a))
 return out
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('application',type=Path);a=p.parse_args();b=a.application.read_bytes();r=verify(b);r['controls']=controls(b);(Q/'independent-review.json').write_text(json.dumps(r,indent=2)+'\n');print(r['status'],r['application_sha256'])
