#!/usr/bin/env python3
"""Exact nine-component B2.2 builder. Application stage only; separate gated GBL stage."""
import argparse,hashlib,importlib.util,json,shutil,struct,subprocess,zlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];HERE=Path(__file__).parent
E=ROOT/'analysis/evidence/p01-p02-patch-qualification-2026-10-28'
P=ROOT/'builds/build_a1r_all_known_2026-10-28/final/SHTRV-01_2.2.4_A1R_C-C_B2_MQTT_WF200_3.18.0_EXPERIMENTAL'
STOCK=ROOT/'extracted/program_1_0x00000000.bin';SG=ROOT/'original/2.2.4/SHTRV-01_build_2.2.4.gbl'
SHA_STOCK='4dc770fe535008ef150f3a144354169199e1a0e235173abcc3f7387b95ee9b5c';SHA_SG='5c4a0b222a313350952f6b1200a855833402f168bd286090c23bd4d018ab918f'
SHA_PARENT='31ddd06a0229fee0b0b58dcbbd28ced1e4fbab0b6dc218c76c9d93673f4961e0';SHA_PG='5f81869922c9b2eed4eb2f730ed53f5a66cf8b09d5f7d12205a4f6fbcd7392d9'
SHA_SEC='886d009b3852cb41f7c67c85de5c9bf2e6d67614e10d668b4fa1e18734078cb9'
H=lambda b:hashlib.sha256(b).hexdigest()
COMPONENTS=['A1R','C-C','B2 serialization','MQTT PUBLISH validation','official WF200 3.18.0','Calibration Restore Guard','P01','P02','P03']
SPECS=[dict(name='Calibration Restore Guard',source='tools/scripts/patcher/calibration_restore_guard_2.2.4/restore_guard.S',source_sha='ed2bda4fed60f7029eb484fd30b92dfc531e016344150d07176771f9c10775c7',start=0x1050f4,end=0x105108,helper_sha='96d32d67868ec02a30f6f05268d5913691604a78d2d1bc8b95ee86d47801d736',hooks=[(0x3ba4,'1bf06afc','01f1a6fa',0x1050f4,True)]),dict(name='P01',source=str((E/'p01/v2/pa3_release.S').relative_to(ROOT)),source_sha='a7764f1dca0a467d9a90b77a459a8c7f9f7f648837e4ce200910fef4b9c92fd0',start=0x104880,end=0x1048bc,helper_sha='9cfe0661017f28c6d208e48268f51f4aac1f8c0d294f383ea606c34591d4cf69',hooks=[(0x141f6,'00232ce0','f0f045bb',0x104884,False),(0x14232,'f7f7effb','f0f025fb',0x104880,True)]),dict(name='P02',source=str((E/'p02/timeout_retire.S').relative_to(ROOT)),source_sha='7cf47dbcdb351ee0e1a3fcc73cdab34c942c5e4c5902fc547b194ac50061afd4',start=0x104740,end=0x1047c8,helper_sha='667b1d787831f082b62d5f9011ad1a6a2fff2dc89abc0e8bef62b7bc18760fb9',hooks=[(0x4b74,'97f92f30','fff0e4bd',0x104740,False)]),dict(name='P03',source=str((E/'p03/gpio_mask.S').relative_to(ROOT)),source_sha='8d15d7d4ef2309277cc73fbf9ca7f0a5ce050587729f0c4c0a241d5ba170d094',start=0x104840,end=0x104854,helper_sha='e2f3f335df3208a5cbb0c91b7c6cd96b1196feef96d9faae10b216c5c66dd9f9',hooks=[(0x58970,'0a20fff771fd','abf066bf00bf',0x104840,False)])]
def need(x,m):
 if not x:raise ValueError(m)
def dump(p,d):p.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n')
def module(p,name):
 s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def branch(raw,pc,link=False):
 x,y=struct.unpack('<HH',raw);need(x&0xf800==0xf000 and y&0xd000==(0xd000 if link else 0x9000),'branch encoding');s=x>>10&1;n=s<<24|(1^(y>>13&1)^s)<<23|(1^(y>>11&1)^s)<<22|(x&1023)<<12|(y&2047)<<1
 return pc+4+n-(1<<25 if s else 0)
def parse(g):
 p=0;r=[]
 while p<len(g):
  need(p+8<=len(g),'record header');t,n=struct.unpack_from('<II',g,p);need(n<=len(g)-p-8,'record extent');r.append((t,g[p+8:p+8+n]));p+=8+n
 need([t for t,b in r]==[0x03a617eb,0xf40a0af4,0xf50909f5,0xfd0303fd,0xfd0303fd,0xfc0404fc],'record order');need(len(r[-1][1])==4 and struct.unpack('<I',r[-1][1])[0]==zlib.crc32(g[:-4]) and zlib.crc32(g)==0x2144df1c,'GBL CRC');return r
def layout(specs=SPECS,ram=(0x2007ff80,0x20080000)):
 need(specs==SPECS,'unauthorized component geometry');need(ram==(0x2007ff80,0x20080000),'RAM/observer overlap')
 ranges=[]
 for q in specs:
  need(0x104718<=q['start']<q['end']<=0x105108 and q['start']%2==q['end']%2==0,'helper geometry');ranges.append((q['start'],q['end']))
  for a,old,new,t,link in q['hooks']:
   need(abs(t-(a+4))<0x1000000 and t%2==0,'branch range');need(branch(bytes.fromhex(new[:8]),a,link)==t,'branch destination');ranges.append((a,a+len(bytes.fromhex(new))))
 for i,(a,z) in enumerate(ranges):
  for c,d in ranges[i+1:]:need(z<=c or d<=a,'overlap')
def parents(stock,parent,pg,sg):
 need(H(stock)==SHA_STOCK,'wrong stock application');need(H(sg)==SHA_SG,'wrong stock GBL');need(H(parent)==SHA_PARENT and len(parent)==0x104718,'wrong/prepatched/occupied parent');need(H(pg)==SHA_PG,'wrong B2.1 GBL')
 r=parse(pg);sr=parse(sg);need(r[3][1]==bytes(4)+parent,'parent extraction');need(len(r[4][1])==0x789c and struct.unpack_from('<I',r[4][1])[0]==0x130a98,'PROGRAM2 geometry')
 for i in [0,1,2,4]:need(r[i]==sr[i],'stock metadata/secondPROGRAM')
 need(H(parent[0xada20:0xf9e70])==SHA_SEC,'SEC');need(struct.unpack_from('<I',parent)[0]==0x2007ff80 and struct.unpack_from('<I',parent,0x254)[0]==0x2007ff80,'MSP')
 for q in SPECS:
  for a,old,new,t,link in q['hooks']:need(parent[a:a+len(bytes.fromhex(old))]==bytes.fromhex(old)==stock[a:a+len(bytes.fromhex(old))],'native preimage')
 return r

def result(parent,app,helpers):
 layout();need(len(app)==0x105108,'first PROGRAM extent');expected=bytearray(parent)+bytearray(b'\xff'*(0x105108-len(parent)))
 for q in SPECS:
  h=helpers[q['name']];need(H(h)==q['helper_sha'] and len(h)==q['end']-q['start'],'helper identity');expected[q['start']:q['end']]=h
  for a,old,new,t,link in q['hooks']:expected[a:a+len(bytes.fromhex(new))]=bytes.fromhex(new)
 need(app==expected,'unexpected application byte/FF gap');need(H(app[0xada20:0xf9e70])==SHA_SEC,'SEC preservation')
 return dict(status='PASS',application_size=len(app),application_SHA256=H(app),application_CRC32=f'{zlib.crc32(app):08X}',components=COMPONENTS,first_PROGRAM=[0,len(app)],second_PROGRAM=[0x130a98,0x138330],new_RAM=0,MSP='0x2007ff80',unexplained_application_bytes=0)

def validate_claim(app,claim):
 need(claim['application_size']==len(app),'application size claim')
 need(claim['application_SHA256']==H(app),'application SHA claim')
 need(claim['application_CRC32']==f'{zlib.crc32(app):08X}','application CRC claim')

def construct(out):
 stock=STOCK.read_bytes();parent=Path(str(P)+'.bin').read_bytes();pg=Path(str(P)+'.gbl').read_bytes();sg=SG.read_bytes();parents(stock,parent,pg,sg);layout();need(not out.exists(),'output must be clean/new');out.mkdir(parents=True)
 elf=module(ROOT/'builds/build_pmd210_static_2026-10-17/elf_tools.py','retained_elf');helpers={};records=[]
 for i,q in enumerate(SPECS):
  src=(ROOT/q['source']).read_bytes();need(H(src)==q['source_sha'],'source identity');d=out/f'component_{i+6}';d.mkdir();(d/'helper.S').write_bytes(src)
  subprocess.run(['clang','--target=arm-none-eabi','-mcpu=cortex-m4','-mthumb','-c','helper.S','-o','helper.o'],cwd=d,check=True)
  raw,sym=elf.elf(d/'helper.o');h=raw[q['start']:q['end']];need(H(h)==q['helper_sha'],'emitted helper contract')
  for a,old,new,t,link in q['hooks']:need(raw[a:a+len(bytes.fromhex(new))]==bytes.fromhex(new),'emitted hook contract')
  (d/'helper.bin').write_bytes(h);helpers[q['name']]=h
  dis=subprocess.check_output(['/usr/bin/objdump','-d','--triple=thumbv7em-none-eabi',f'--start-address={q["start"]}',f'--stop-address={q["end"]}','helper.o'],cwd=d,text=True);(d/'disassembly.txt').write_text(dis)
  records.append(dict(**q,object_SHA256=H((d/'helper.o').read_bytes())))
 app=bytearray(parent)+bytearray(b'\xff'*(0x105108-len(parent)))
 for q in SPECS:
  app[q['start']:q['end']]=helpers[q['name']]
  for a,old,new,t,link in q['hooks']:app[a:a+len(bytes.fromhex(new))]=bytes.fromhex(new)
 app=bytes(app);manifest=result(parent,app,helpers);manifest['component_construction']=records;manifest['parent_SHA256']=SHA_PARENT;manifest['stock_SHA256']=SHA_STOCK
 (out/'application.bin').write_bytes(app);dump(out/'construction-manifest.json',manifest);return manifest
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();print(json.dumps(construct(a.out.resolve()),indent=2))
