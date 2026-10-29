#!/usr/bin/env python3
"""Offline pre-container gate for exact B2.1_OBS. No device/network access."""
from pathlib import Path
import json,hashlib,importlib.util,sys,struct,subprocess
ROOT=Path(__file__).resolve().parents[4];HERE=Path(__file__).resolve().parent;Q=ROOT/'builds/build_b21_obs_2026-10-28'
H=lambda b:hashlib.sha256(b).hexdigest()
def load(p):return json.loads(p.read_text())
def module(p,n):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def emit(n,j):(Q/n).write_text(json.dumps(j,indent=2,sort_keys=True)+'\n')
def compare(a,b):
 if a!=b:raise ValueError('mismatched construction')
def main():
 b=module(HERE/'build.py','constructor');v=module(HERE/'independent_verify.py','review');b.validate_frozen();app=(Q/'build1/working.bin').read_bytes();ah=H(app);parent=(b.BASE/(b.NAME+'_EXPERIMENTAL.bin')).read_bytes();pg=(b.BASE/(b.NAME+'_EXPERIMENTAL.gbl')).read_bytes();b.validate_inputs(parent,pg)
 # All original checksum inventories remain immutable and revalidated.
 count={}
 for name in ['build_a1r_all_known_2026-10-28','build_pm52_cmd66_observer_2026-10-26']:
  d=ROOT/'builds'/name;rows=(d/'SHA256SUMS').read_text().splitlines()
  for row in rows:
   h,n=row.split('  ',1);assert H((d/n).read_bytes())==h,n
  count[name]=len(rows)
 raw=v.verify(app);raw['controls']=v.controls(app);emit('independent-review.json',raw)
 t=load(Q/'target-results.json');assert t['result']=='PASS' and t['passed']==t['tests']==151 and t['executed_candidate_sha256']==ah and t.get('observer_initialized') is True
 assert H((Q/'target-vectors.json').read_bytes())==t['vectors_sha256'] and H((Q/'target-symbols.json').read_bytes())==t['symbols_sha256']
 assert (Q/'target-vectors.json').read_bytes()==(ROOT/'builds/build_a1r_all_known_2026-10-28/target-vectors.json').read_bytes()
 # Executed ELF loadable instruction sections independently unpacked and bound.
 data=(Q/'candidate-analysis.elf').read_bytes();eh=struct.unpack_from('<16sHHIIIIIHHHHHH',data);ranges=[]
 for i in range(eh[12]):
  sh=struct.unpack_from('<10I',data,eh[6]+i*eh[11])
  if sh[1]==1 and sh[2]&4:
   assert data[sh[4]:sh[4]+sh[5]]==app[sh[3]:sh[3]+sh[5]];ranges.append([hex(sh[3]),hex(sh[3]+sh[5])])
 assert ranges==[['0x0','0xada20'],['0xf9e70','0x1050f4']]
 ot=load(Q/'build1/target-results.json');assert ot['status']=='PASS' and ot['passed']==356 and ot['application_sha256']==ah and ot['maximum_event_stack']==32
 assert ot['maximum_event_instructions']<=122
 for f,key,c in [('B2-target-results.json','single_call_parity_cases',2060),('MQTT-target-results.json','passed',258),('B2mixed-target-results.json','passed',2)]:
  j=load(Q/'regression'/f);assert j.get('status',j.get('result'))=='PASS' and j[key]==c and j['application_sha256']==ah
 assert load(Q/'regression/B2-target-results.json')['unmasked_preemption_cut_cases']==102
 assert load(Q/'regression/B2mixed-target-results.json')['transitions']==10
 assert load(Q/'CC-regression-results.json')['status']=='PASS'
 subprocess.run([sys.executable,str(HERE/'test_decode.py')],check=True)
 decoder=module(HERE/'decode.py','decoder');dec=[]
 for ob,prefix in zip(ot['snapshots'],['CASE A','CASE B','CASE B','CASE C']):
  result=decoder.decode({'research_build':'B2.1_OBS','pm52_cmd66':ob});assert result['classification'].startswith(prefix);dec.append(result)
 emit('decoder-results.json',{'status':'PASS','methods':8,'target_snapshots':dec})
 # Bind the emitted object code to actual patched instructions and extension.
 obj=(Q/'build1/observer.o').read_bytes();eh=struct.unpack_from('<16sHHIIIIIHHHHHH',obj)
 sections=[struct.unpack_from('<10I',obj,eh[6]+i*eh[11]) for i in range(eh[12])]
 text=next(sh for sh in sections if sh[1]==1 and sh[2]&4);emitted=obj[text[4]:text[4]+text[5]]
 assert emitted[0x104718:len(app)]==app[0x104718:]
 for a,(n,_) in v.SITES.items():assert emitted[a:a+n]==app[a:a+n]
 # Unchanged emitted formatter stack and exact compiler delta, not guessed C ABI.
 old=ROOT/'builds/build_pm52_cmd66_observer_2026-10-26/build1';s=(old/'readout-compiler.s').read_text()
 s=s.replace('#3041','#3013').replace('#26\n','#54\n').replace('\\\"pm52_cmd66', '\\\"research_build\\\":\\\"B2.1_OBS\\\",\\\"pm52_cmd66').replace('obs_export.prefix, 27','obs_export.prefix, 55')
 assert s==(Q/'build1/readout-compiler.s').read_text(),'unexpected formatter compile difference'
 # New loggers32 are same-parent dominated by retained prior descendants;
 # actual A1R classifier adds0 frames and changes none of these ancestry bytes.
 oldmem=load(ROOT/'builds/build_pm52_cmd66_observer_2026-10-26/independent-memory-stack.json');mem=dict(oldmem,application_sha256=ah,application_size=len(app),status='PASS; exact relocated event code and unchanged formatter frame',new_RAM_bytes=512,new_flash_bytes=len(app)-len(parent),readout_build_ID_extra_bytes=28)
 mem.pop('external_branch_initial_failure_corrected',None);mem.pop('hook_and_startup_branches_independently_decoded',None);mem['independently_decoded_hook_branches']=12;mem['independently_compared_native_continuation_branches']=13
 assert mem['HTTP_headroom']==1776 and mem['MSP_headroom']==42488
 emit('memory-stack.json',mem)
 names=['working.bin','observer.o','observer.S','readout-compiler.s','symbols.json','local-relocations.json','construction-manifest.json']
 identities={}
 for n in names:
  a=(Q/'build1'/n).read_bytes();compare(a,(Q/'build2'/n).read_bytes());identities[n]={'sha256':H(a),'bytes':len(a)}
 for n in ['working.bin','a1r_restore.o','a1r_restore.S','a1r-manifest.json','construction-manifest.json','additional-fixes.o','additional-fixes.S','additional-fixes.text','symbols.json','reused-cc-construction.json','reused-a1-construction.json']:
  a=(Q/'build1/b21-parent'/n).read_bytes();compare(a,(Q/'build2/b21-parent'/n).read_bytes());identities['b21-parent/'+n]={'sha256':H(a),'bytes':len(a)}
 emit('determinism.json',{'status':'PASS','files':identities})
 negatives=[]
 def reject(n,fn):
  try:fn()
  except (AssertionError,ValueError,struct.error):negatives.append({'case':n,'rejected':True});return
  raise ValueError('negative accepted '+n)
 stock=(ROOT/'original/2.2.4/SHTRV-01_build_2.2.4.gbl').read_bytes()
 # Same pinned stock validator used by reconstruction, before compile/output.
 bp=module(ROOT/'tools/scripts/patcher/all_known_fixes_2.2.4/build.py','b21');ba=(bp.A/'SHTRV-01_2.2.4_A1_C-C_WF200_3.18.0_EXPERIMENTAL.bin').read_bytes();bg=(bp.A/'SHTRV-01_2.2.4_A1_C-C_WF200_3.18.0_EXPERIMENTAL.gbl').read_bytes();sec=(ROOT/'original/WF200/wfx-firmware/wfm_wf200_C0.sec').read_bytes()
 reject('wrong stock',lambda:bp.validate(b'wrong',ba,bg,sec))
 historical=(ROOT/'builds/build_all_known_fixes_2026-10-23/SHTRV-01_2.2.4_A1_C-C_B2_MQTT_WF200_3.18.0_EXPERIMENTAL.bin').read_bytes();reject('historical B2 not B2.1',lambda:b.validate_inputs(historical,pg))
 pins=load(HERE/'frozen-inputs.json')['pins']
 for label,needle in [('wrong A1R source','a1r_restore.S'),('wrong observer source','pm52_cmd66_observer_2.2.4/build.py'),('wrong integrated observer source','b21_obs_2.2.4/build.py'),('changed ID source','b21_obs_2.2.4/readout.c')]:
  n=next(n for n in pins if n.endswith(needle));bad=(ROOT/n).read_bytes()+b'X';reject(label,lambda n=n,bad=bad:b.validate_frozen({n:bad}))
 n='tools/scripts/patcher/b21_obs_2.2.4/build.py';src=(ROOT/n).read_bytes()
 for label,bad in [('changed RAM address',src.replace(b'0x2007fd80',b'0x2007fd84')),('observer/A1R overlap',src.replace(b'0x2007fd80',b'0x2007ff80'))]:
  assert src!=bad;reject(label,lambda bad=bad:b.validate_frozen({n:bad}))
 reject('mismatched second construction',lambda:compare(app,app[:-1]+bytes([app[-1]^1])))
 negatives+=raw['controls'];emit('negative-controls.json',{'status':'PASS','cases':negatives})
 paths=[p for p in HERE.iterdir() if p.is_file()]+[Q/'build1'/n for n in names]+[Q/n for n in ['target-results.json','target-vectors.json','target-symbols.json','A1RExecute.java','run_target.py','run_components.py','candidate-analysis.elf','verify_cc_regression.py','CC-regression-results.json','independent-review.json','memory-stack.json','negative-controls.json','decoder-results.json','regression/B2-target-results.json','regression/MQTT-target-results.json','regression/B2mixed-target-results.json']]+[Q/'build1/target-results.json']
 emit('pre-container-gate.json',{'status':'PASS','application_sha256':ah,'source_result_pins':{str(p.relative_to(ROOT)):H(p.read_bytes()) for p in paths},'historical_checksums_revalidated':count,'A1R_cases':151,'observer_cases':356,'B2_cases':2060,'B2_cuts':102,'MQTT_cases':258,'CC':'PASS','device_contact':False})
 print('PRE-CONTAINER PASS',ah)
if __name__=='__main__':main()
