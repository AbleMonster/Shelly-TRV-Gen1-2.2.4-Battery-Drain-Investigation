#!/usr/bin/env python3
"""Independent read-only A1 application verifier. Does not import builder or
its hook inventory. Expectations come from staged component contracts and raw
ELF relocation verification. No application/GBL is constructed here."""
from pathlib import Path
import hashlib,struct,json,runpy,argparse
ROOT=Path(__file__).resolve().parents[4];Q=ROOT/'build_a1_cc_wf200_318_final_2026-10-20'
R=runpy.run_path(str(Q/'linked-assets/verify_linked_assets.py'))
EXPORTS=R['exports'];ASSETS=(Q/'linked-assets/adapter-assets.text').read_bytes();R['verify'](ASSETS)
BASELINE=(ROOT/'build_cc_wf200_318_2026-10-19/SHTRV-01_2.2.4_C-C_WF200_3.18.0_EXPERIMENTAL.bin').read_bytes()
STOCK=(ROOT/'extracted/program_1_0x00000000.bin').read_bytes();CORE=(ROOT/'build_a1_executable_core_2026-10-20/core.text').read_bytes();START=(ROOT/'build_a1_cc_wf200_318_integration_2026-10-20/startup-adapter.text').read_bytes()
H=lambda b:hashlib.sha256(b).hexdigest()
assert H(BASELINE)=='f323d1b1ea062f086217e189e8cb15bcb18063e3d02f40b4fe1c842161fcb353'
assert H(STOCK)=='4dc770fe535008ef150f3a144354169199e1a0e235173abcc3f7387b95ee9b5c'
assert H(CORE)=='73843b24a7bc3d537c569c6bad34cf2a521664993c2685e1a6dd4858b591d6fb'
assert H(START)=='40232842f14ee5128746cb67318205344b31db8f7033bb1b5542374997482105'
FIX=json.loads((ROOT/'build_wf200_318_relocation_qualification_2026-10-18/relocation-manifest.json').read_text())
HOOKS=[]
plans=['owner-component/staged-hook-map.json','transport-component/staged-hook-map.json','pm-component/hook-plan.json','g18-component/lower-hook-plan.json','g18-component/upper-hook-plan.json','g18-component/worker-hook-plan.json']
for path in plans:
 for h in json.loads((Q/path).read_text())['hooks']:
  address=int(h.get('site',h.get('address')),16);kind=h.get('branch',h.get('kind'));target=h.get('helper',h.get('native_target',h.get('target')))
  pre=bytes.fromhex(h.get('combined',h.get('preimage',h.get('bytes',h.get('stock')))))
  assert BASELINE[address:address+len(pre)]==pre,('baseline preimage mismatch',hex(address),path)
  if kind.startswith('BL'):kind='BL'
  elif kind.startswith('B.W'):kind='B.W'
  HOOKS.append({'address':address,'kind':kind,'target':target,'preimage':pre,'source':path})
# Five startup/storage seams independently specified, absent component plans.
for a,kind,target,pre in [(0,'u32',0x2007ff80,'00000820'),(0x254,'u32',0x2007ff80,'00000820'),(0x206,'B.W',0x1019e0,'a3f5803a'),(0x1198,'B.W','prod_startup_entry','90b589b0'),(0x141c,'B.W','prod_startup_return','bd4690bd')]:
 assert BASELINE[a:a+4]==bytes.fromhex(pre);HOOKS.append({'address':a,'kind':kind,'target':target,'preimage':bytes.fromhex(pre),'source':'manual startup/storage contract'})
assert len(HOOKS)==93 and len({x['address'] for x in HOOKS})==93

def branch_target(data,a,kind):
 h1,h2=struct.unpack_from('<HH',data,a);assert h1&0xf800==0xf000,('bad branch prefix',hex(a));assert h2&0xd000==(0xd000 if kind=='BL' else 0x9000),('wrong branch kind',hex(a),kind)
 s=h1>>10&1;v=s<<24|(1^((h2>>13&1)^s))<<23|(1^((h2>>11&1)^s))<<22|(h1&1023)<<12|(h2&2047)<<1
 if s:v-=1<<25
 return a+4+v

def verify_application(data):
 """Return proof summary, or raise AssertionError. Safe for mutation fixtures."""
 assert len(data)==0x101a00+len(ASSETS),('application extent',len(data))
 assert data[0x100900:0x1019de]==CORE,'isolated core mutation'
 assert data[0x1019e0:0x1019fc]==START,'stackless startup adapter mutation'
 assert data[0x101a00:]==ASSETS,'linked production adapter mutation'
 assert branch_target(data,0x1019e0+10,'BL')==0x10149c,'wrong initializer target'
 assert branch_target(data,0x1019e0+24,'B.W')==0x20a,'wrong startup resume'
 authorized=bytearray(len(data));hook_results=[]
 for h in HOOKS:
  a=h['address'];kind=h['kind'];target=h['target'];width=len(h['preimage'])
  if kind in ['BL','B.W']:
   t=EXPORTS[target] if isinstance(target,str) and target in EXPORTS else int(target,0) if isinstance(target,str) else target
   assert branch_target(data,a,kind)==t&~1,('wrong hook target',hex(a),target)
  elif kind=='Thumb pointer literal':
   assert struct.unpack_from('<I',data,a)[0]==EXPORTS[target] and EXPORTS[target]&1,('wrong Thumb callback',hex(a))
  elif kind=='u32':assert struct.unpack_from('<I',data,a)[0]==target,('wrong storage literal',hex(a))
  elif kind=='literal replacement':assert data[a:a+width]==bytes.fromhex(target),('wrong frame adjustment',hex(a))
  else:raise AssertionError(('unknown hook encoding',kind))
  assert not any(authorized[a:a+width]),('overlapping hook',hex(a));authorized[a:a+width]=b'\1'*width
  hook_results.append({'site':hex(a),'kind':kind,'target':target,'bytes':data[a:a+width].hex(),'source':h['source']})
 for a,b in [(0x100900,0x1019de),(0x1019e0,0x1019fc),(0x101a00,len(data))]:authorized[a:b]=b'\1'*(b-a)
 # Each gap is separately checked; no extra storage or code is accepted.
 assert data[len(BASELINE):0x100900]==b'\xff'*(0x100900-len(BASELINE))
 assert data[0x1019de:0x1019e0]==b'\xff'*2 and data[0x1019fc:0x101a00]==b'\xff'*4
 for a,x in enumerate(data):
  before=BASELINE[a] if a<len(BASELINE) else 0xff
  if x!=before:assert authorized[a],('unauthorized changed byte',hex(a),before,x)
 # Explicit protected composition checks, in addition to global baseline diff.
 sec=data[0xada20:0xf9e70];assert len(sec)==312400 and H(sec)=='886d009b3852cb41f7c67c85de5c9bf2e6d67614e10d668b4fa1e18734078cb9','official SEC mutation'
 assert data[0x1003d0:0x1007d8]==BASELINE[0x1003d0:0x1007d8],'relocated object mutation'
 assert H(data[0x1003d0:0x1007d8])==FIX['relocation']['destination_after_pointer_fixups']['sha256']
 assert data[0x1007d8:0x1008ec]==BASELINE[0x1007d8:0x1008ec],'C-C helper mutation'
 for f in FIX['external_fixups']+FIX['internal_fixups']:
  a=int(f['future_site'],0);assert data[a:a+4]==bytes.fromhex(f['new_word_le']),('relocation fixup mutation',hex(a))
 for f in FIX['excluded_original_candidates']:
  a=int(f['future_site'],0);assert data[a:a+4]==bytes.fromhex(f['old_word_le'])
 assert struct.unpack_from('<I',data,0x5788c)[0]==0xada20 and struct.unpack_from('<I',data,0x578ac)[0]==312400
 for a,t in FIX['unchanged_startup_literals'].items():assert struct.unpack_from('<I',data,int(a,0))[0]==int(t,0)
 assert data[0xf9e70:len(STOCK)]==BASELINE[0xf9e70:len(STOCK)],'stale suffix/stock suffix mutation'
 # Existing C-C lower hooks now reach the composed G18 adapters exactly.
 for a,s in [(0x57fc4,'g18_c3_shared'),(0x58120,'g18_c4_shared')]:assert branch_target(data,a,'BL')==EXPORTS[s]&~1
 return {'result':'PASS','scope':'application static composition only; no GBL/device verdict','bytes':len(data),'sha256':H(data),'hooks':hook_results,'hook_count':len(hook_results),'radio_fixups':54,'excluded_candidates_unchanged':6,'unexplained_changed_bytes':0,'core_sha256':H(CORE),'assets_sha256':H(ASSETS),'baseline_sha256':H(BASELINE)}

def negative_controls(data):
 tests=[]
 for label,a in [('C-C helper mutation',0x1007d8),('radio relocated object mutation',0x1003d0),('official SEC mutation',0xada20),('core mutation',0x100900),('startup initializer mutation',0x1019e0),('unexplained application mutation',0x500),('wrong native hook target',0x1634+2),('wrong relocation pointer',int(FIX['external_fixups'][0]['future_site'],0)),('wrong MSP reservation',0),('wrong lower receive publication',0x2182+2)]:
  m=bytearray(data);m[a]^=1
  try:verify_application(m)
  except (AssertionError,ValueError,struct.error):tests.append({'mutation':label,'site':hex(a),'result':'REJECTED'});continue
  raise AssertionError(('negative accepted',label))
 return tests
def _instruction_site(name,pattern,occurrence=0):
 import re,subprocess
 rows=[]
 # Resolve function definitions from RAW object symbol/section tables, not manifest.
 for o in R['objs']:
  symbols=[s for s in o['symbols'] if s['name']==name and s['section']==o['text_section']]
  if not symbols:continue
  sym=symbols[0];start=sym['value']&~1;size=sym['size'];end=start+size if size else len(o['text'])
  text=subprocess.check_output(['/usr/bin/objdump','-d',str(o['path'])],text=True)
  for line in text.splitlines():
   m=re.match(r'^\s*([0-9a-f]+):\s+((?:(?:[0-9a-f]{4}|[0-9a-f]{2})\s+)+)\s*([a-z][\w.]*)\s*(.*)',line)
   if not m:continue
   a=int(m[1],16);instruction=m[3]+' '+m[4].split('@')[0].strip()
   if start<=a<end and re.search(pattern,instruction):
    encoded=b''.join(int(t,16).to_bytes(len(t)//2,'little') for t in m[2].split());assert o['text'][a:a+len(encoded)]==encoded
    rows.append((0x101a00+o['offset']+a,instruction,encoded))
  if len(rows)>occurrence:return rows[occurrence]
 # The frozen core has a separate linked native view, validated by its immutable text.
 text=(ROOT/'build_a1_executable_core_2026-10-20/core-disassembly.txt').read_text();active=False
 for line in text.splitlines():
  h=re.match(r'^[0-9a-f]+ <([^>]+)>:',line)
  if h:active=h[1]==name
  if not active:continue
  m=re.match(r'^\s*([0-9a-f]+):\s+((?:[0-9a-f]{4}\s+)+)\s*([a-z][\w.]*)\s*(.*)',line)
  if m:
   a=int(m[1],16);instruction=m[3]+' '+m[4].split('@')[0].strip()
   if re.search(pattern,instruction):
    encoded=b''.join(int(t,16).to_bytes(2,'little') for t in m[2].split());assert CORE[a-0x100900:a-0x100900+len(encoded)]==encoded;rows.append((a,instruction,encoded))
 if len(rows)>occurrence:return rows[occurrence]
 raise AssertionError(('missing exact corruption subject',name,pattern,occurrence))

def _records(gbl):
 records=[];off=0
 while off<len(gbl):
  assert off+8<=len(gbl),'truncated tag header';tag,n=struct.unpack_from('<II',gbl,off);assert n<=len(gbl)-off-8,'truncated tag payload'
  records.append((tag,gbl[off+8:off+8+n]));off+=8+n
 assert off==len(gbl);return records

def verify_gbl(gbl):
 import zlib
 baseline=(ROOT/'build_cc_wf200_318_2026-10-19/SHTRV-01_2.2.4_C-C_WF200_3.18.0_EXPERIMENTAL.gbl').read_bytes()
 old=_records(baseline);new=_records(gbl);assert len(old)==len(new)==6
 assert [t for t,p in old]==[t for t,p in new]
 assert new[-1][0]==0xfc0404fc and len(new[-1][1])==4
 assert zlib.crc32(gbl)&0xffffffff==0x2144df1c,'bad whole-file residue'
 assert int.from_bytes(gbl[-4:],'little')==zlib.crc32(gbl[:-4])&0xffffffff,'bad terminal CRC'
 for i,((tag,p),(ot,op)) in enumerate(zip(new,old)):
  if i==3:
   assert tag==0xfd0303fd and p[:4]==b'\0'*4;result=verify_application(p[4:])
  elif i==5:pass
  else:assert p==op,('unrelated GBL payload mutation',i)
 assert len(new[4][1])==30876 and int.from_bytes(new[4][1][:4],'little')==0x130a98
 assert H(new[4][1][4:])=='662bd549f050ab81a120d3daa07646652c38880b9d2bfa988ff6bee7f731e33e'
 return {'result':'PASS','bytes':len(gbl),'sha256':H(gbl),'crc32':hex(zlib.crc32(gbl)&0xffffffff),'record_count':6,'application':result}

def _in_memory_container(app):
 import zlib
 baseline=(ROOT/'build_cc_wf200_318_2026-10-19/SHTRV-01_2.2.4_C-C_WF200_3.18.0_EXPERIMENTAL.gbl').read_bytes();out=bytearray()
 for i,(tag,p) in enumerate(_records(baseline)):
  if i==3:p=p[:4]+app
  if i==5:
   out+=struct.pack('<II',tag,4);out+=struct.pack('<I',zlib.crc32(out)&0xffffffff)
  else:out+=struct.pack('<II',tag,len(p))+p
 return out

def supplemental_corruption_controls(app):
 """Separate corruption suite, NOT canonical36 semantic/fault-injection tests."""
 tests=[]
 def reject(number,label,site=None,subject=None,fn=verify_application,blob=app):
  b=bytearray(blob)
  if subject:
   site,ins,old=_instruction_site(*subject);assert app[site:site+len(old)]==old
  else:ins='raw typed hook/literal/qualified payload byte';old=b[site:site+1]
  b[site]^=1
  try:fn(b)
  except (AssertionError,ValueError,IndexError,struct.error):tests.append({'category':number,'subject':label,'site':hex(site),'instruction':ins,'before':old.hex(),'mutation':'xor low instruction/data bit','result':'REJECTED'});return
  raise AssertionError(('corruption accepted',number,label))
 entries=[
 (1,'vector MSP reservation',0,None),(2,'CRT MSP reservation',0x254,None),(3,'startup initializer dispatch',0x206,None),(4,'initializer state address MOVW',0x1019e2,None),
 (5,'initializer state zero store',None,('a1_init',r'str')),(6,'incoming PRIMASK save',None,('a1_claim_add',r'mrs.*primask')),(7,'incoming PRIMASK restoration',None,('a1_claim_add',r'msr.*primask')),(8,'atomic publication DMB',None,('a1_claim_add',r'dmb')),
 (9,'core wrapper stack save ABI',None,('a1_owner_leave',r'push')),(10,'owner capability check',None,('prod_owner_enter',r'cmp')),(11,'private R9 carrier store',None,('prod_b6c_entry',r'str.*r9')),(12,'CONNECT shadow frame allocation',None,('prod_connect_entry',r'sub.*sp')),
 (13,'child owner/token retirement guard',None,('body_a1_child_leave',r'cmp')),(14,'sender capacity check',None,('production_lower_send',r'ldrh.*0x206')),(15,'command publication send routing',0x1f90,None),(16,'ambiguous abort fail-stop reason',None,('production_abort_ambiguous',r'movw')),
 (17,'raw pre-validation credit debit bypass',0x2132,None),(18,'raw RX minimum extent comparison',None,('production_decode',r'cmp')),(19,'SecureLink decode routing',0x2182,None),(20,'validated confirmation attribution',None,('body_a1_command_confirm',r'cmp')),
 (21,'timeout waiter adapter',0x1f10,None),(22,'generic speculative debit bypass',0x1f4e,None),(23,'PDS speculative debit bypass',0x1e4c,None),(24,'phase epoch invalidation store',None,('production_phase_end_body',r'str.*0x7c')),
 (25,'stale PM generation guard',None,('body_a1_pm_complete',r'cmp')),(26,'desired intent/version publication',None,('body_a1_desired_publish',r'str')),(27,'claim ownership retirement',None,('body_a1_claim_retire',r'cmp')),
 (28,'C3 private stamp allocation adapter',None,('g18_alloc',r'add')),(29,'upper stamped C3 consumer',0x59324,None),(30,'guarded JOIN handoff',0x63904,None),(31,'outer/child release disposition',None,('prod_owner_leave',r'cmp')),
 (32,'shared current-byte flags atomic store',None,('prod_shared_flags_rmw',r'strb')),(33,'qualified C-C helper preservation',0x1007d8,None),(34,'qualified radio host-object preservation',0x1003d0,None),(35,'official SEC preservation',0xada20,None)]
 for n,label,site,subject in entries:reject(n,label,site,subject)
 # Category36 is checked before file emission using a complete IN-MEMORY TLV.
 gbl=_in_memory_container(app);proof=verify_gbl(gbl)
 reject(36,'container checksum integrity',len(gbl)-1,fn=verify_gbl,blob=gbl)
 import zlib
 bad=bytearray(gbl);o=0
 for i in range(5):
  tag,n=struct.unpack_from('<II',bad,o)
  if i==4:bad[o+8]^=4;break
  o+=8+n
 bad[-4:]=struct.pack('<I',zlib.crc32(bad[:-4])&0xffffffff)
 try:verify_gbl(bad)
 except AssertionError:tests.append({'category':'36b','subject':'second PROGRAM position with repaired CRC','result':'REJECTED'})
 else:raise AssertionError('container geometry mutation accepted')
 # The protected SEC mutation is also rejected after a valid CRC repair.
 badapp=bytearray(app);badapp[0xada20]^=1;badgbl=_in_memory_container(badapp)
 try:verify_gbl(badgbl)
 except AssertionError:tests.append({'category':'35b','subject':'SEC mutation in complete container with repaired CRC','result':'REJECTED'})
 else:raise AssertionError('SEC mutation with repaired CRC accepted')
 settlement=[]
 entries=[('phase-cookie current epoch',('settlement_guard',r'ldr.*0x7c')),('current PM generation',('settlement_guard',r'ldr.*0x44')),('executor command-phase snapshot',('production_settle_fresh_body',r'ldr.*0x20')),('ticket consumed retirement',('production_physical_release_body',r'str.*0x28')),('shared byte merge store',('prod_shared_flags_rmw',r'strb')),('RX pre-retirement P predicate',('settlement_guard',r'ldr.*0x18')),('E/S physical permission publication',('production_physical_release_body',r'strb')),('phase-end epoch publication',('production_phase_end_body',r'str.*0x7c'))]
 for label,subject in entries:
  site,ins,old=_instruction_site(*subject);assert app[site:site+len(old)]==old;b=bytearray(app);b[site]^=1
  try:verify_application(b)
  except AssertionError:settlement.append({'subject':label,'site':hex(site),'instruction':ins,'before':old.hex(),'result':'REJECTED'})
  else:raise AssertionError(('settlement corruption accepted',label))
 return {'result':'PASS','scope':'SUPPLEMENTAL production corruption categories, separate from canonical36 semantic controls and component tests','precontainer_categories':35,'container_category':36,'category_count':36,'corruptions_rejected':len(tests),'cases':tests,'settlement_corruption_controls':settlement,'in_memory_container_positive':{'result':proof['result'],'bytes':proof['bytes'],'sha256':proof['sha256'],'record_count':proof['record_count']},'gbl_file_written':False}

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('application');ap.add_argument('--output',default=str(Q/'working/independent-application-verification.json'));args=ap.parse_args();data=Path(args.application).read_bytes();result=verify_application(data);result['negative_controls']=negative_controls(data);result['supplemental_corruption_controls']=supplemental_corruption_controls(data);Path(args.output).write_text(json.dumps(result,indent=2)+'\n');print('INDEPENDENT APPLICATION PASS',len(data),'bytes',result['hook_count'],'hooks',len(result['negative_controls']),'negative controls')
