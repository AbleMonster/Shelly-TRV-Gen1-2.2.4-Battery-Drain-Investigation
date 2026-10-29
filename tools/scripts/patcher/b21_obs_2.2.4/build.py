#!/usr/bin/env python3
"""Pinned additive offline application constructor. Never emits a GBL."""
from pathlib import Path
import argparse,hashlib,json,struct,subprocess,sys,zlib,re
ROOT=Path(__file__).resolve().parents[4];HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'builds/build_pmd210_static_2026-10-17'))
from elf_tools import elf
BASE=ROOT/'builds/build_a1r_all_known_2026-10-28/final'
NAME='SHTRV-01_2.2.4_A1R_C-C_B2_MQTT_WF200_3.18.0'
BSHA='31ddd06a0229fee0b0b58dcbbd28ced1e4fbab0b6dc218c76c9d93673f4961e0'
GSHA='5f81869922c9b2eed4eb2f730ed53f5a66cf8b09d5f7d12205a4f6fbcd7392d9'
SHA=lambda b:hashlib.sha256(b).hexdigest()
HOOKS={0x1bd6:('00f05bf9','pm_issue',4),0x1bda:('03461846','pm_result',4),0x1e104:('e3f7d6fd','stats_issue',4),0x1e108:('78637b6b','stats_result',4),0x1e132:('4ff416723b6b'.lower(),'fresh_sample',10),0x57fc4:(None,'connect_begin',4),0x58120:(None,'disconnect',4),0x102f88:('30bc84f30088','connect_commit',6),0x103aee:('78b32069','commit_first',4),0x103b84:('054612a8','commit_second',4),0x1019f8:('fef607bc','observer_init',4),0x19e8c:('03461a46','status_export',4)}
# Full exact preimages are frozen in source, including composed destinations.
HOOKS[0x1e132]=('4ff416723b6bb2fbf3f3','fresh_sample',10)
HOOKS[0x57fc4]=('aaf0d2ff','connect_begin',4)
HOOKS[0x58120]=('aaf036ff','disconnect',4)

def assembly():
 a='.syntax unified\n.cpu cortex-m4\n.thumb\n.text\n'
 native=[0x20a,0x1e90,0x1bde,0x1cb4,0x1e10c,0x1e13c,0x102f6c,0x102f8e,0x102f90,0x103af2,0x103b50,0x103b88,0x19e90]
 for p in sorted(set(HOOKS)|set(native)):
  if p in native:a+=f'.org {p},0xff\nnative_{p:x}:\n'
  if p in HOOKS:
   pre,n,size=HOOKS[p]
   a+=f'.org {p},0xff\nhook_{p:x}: b.w {n}\n'+(' nop\n'*((size-4)//2))
 a+='''.org 0x104718,0xff
.global extension_start
extension_start:
.macro addr reg,value
 movw \\reg,#(\\value & 65535)
 movt \\reg,#(\\value >> 16)
.endm
.macro save
 push.w {r0-r3,r12,lr}
 mrs r0,APSR
 mrs r1,PRIMASK
 push {r0,r1}
 cpsid i
.endm
.macro restore
 pop {r0,r1}
 dmb sy
 msr PRIMASK,r1
 msr APSR_nzcvq,r0
 pop.w {r0-r3,r12,lr}
.endm
.macro live done
 addr r0,0x2007fd80
 ldr r2,[r0]
 addr r3,0x504d3636
 cmp r2,r3
 bne.w \\done
 ldr r2,[r0,#12]
 tst r2,#1
 bne.w \\done
.endm
.macro seq done
 ldr r2,[r0,#16]
 cmn r2,#1
 bne 991f
 ldr r3,[r0,#12]
 orr r3,r3,#8
 str r3,[r0,#12]
 b.w \\done
991: adds r2,#1
 str r2,[r0,#16]
.endm
.macro event kind,done
 seq \\done
 ldr r3,[r0,#32]
 add.w r1,r0,#128
 add.w r1,r1,r3,lsl #5
 str r2,[r1]
 addr r12,0x20001858
 ldr r2,[r12]
 str r2,[r1,#4]
 ldr r2,[r0,#20]
 str r2,[r1,#8]
 movs r2,#\\kind
 str r2,[r1,#12]
 adds r3,#1
 cmp r3,#12
 it eq
 moveq r3,#0
 str r3,[r0,#32]
 ldr r2,[r0,#28]
 cmp r2,#12
 beq 992f
 adds r2,#1
 str r2,[r0,#28]
 b 993f
992: ldr r2,[r0,#12]
 orr r2,r2,#2
 str r2,[r0,#12]
993:
.endm
.macro ambiguous
 ldr r2,[r0,#12]
 orr r2,r2,#4
 str r2,[r0,#12]
.endm
.global observer_init
.thumb_func
observer_init:
 mrs r12,APSR
 mrs r3,PRIMASK
 cpsid i
 addr r0,0x2007fd80
 movs r1,#0
 movs r2,#128
1: str r1,[r0],#4
 subs r2,#1
 bne 1b
 addr r0,0x2007fd80
 movs r1,#1
 str r1,[r0,#4]
 movw r1,#512
 str r1,[r0,#8]
 dmb sy
 addr r1,0x504d3636
 str r1,[r0]
 msr PRIMASK,r3
 msr APSR_nzcvq,r12
 b.w 0x20a
.global pm_issue
.thumb_func
pm_issue:
 save
 live pm_issue_done
 event 1,pm_issue_done
 ldr r2,[r0,#36]
 cbz r2,1f
 ambiguous
1: ldr r2,[r1]
 str r2,[r0,#36]
 str r2,[r0,#48]
 str r7,[r0,#40]
 ldr r2,[r0,#20]
 str r2,[r0,#44]
 ldr r3,[sp,#12]
 ldr r2,[r3]
 str r2,[r1,#16]
 ldrb r2,[r3,#4]
 ldrb r3,[r3,#1]
 cmp r3,#1
 it eq
 orreq r2,r2,#256
 str r2,[r1,#20]
 addr r3,0x2007ff80
 ldr r2,[r3,#68]
 str r2,[r1,#24]
 ldr r2,[r3,#28]
 str r2,[r1,#28]
pm_issue_done:
 restore
 movw lr,#0x1bdb
 b.w 0x1e90
.global pm_result
.thumb_func
pm_result:
 save
 live pm_result_done
 event 2,pm_result_done
 ldr r2,[r0,#40]
 cmp r2,r7
 bne 1f
 ldr r2,[r0,#44]
 ldr r3,[r0,#20]
 cmp r2,r3
 bne 1f
 ldr r2,[r0,#36]
 cbz r2,1f
 b 2f
1: ambiguous
 movs r2,#0
2: str r2,[r1,#16]
 str r2,[r0,#52]
 movs r2,#0
 str r2,[r0,#36]
 ldr r2,[sp,#8]
 str r2,[r1,#20]
 str r2,[r0,#56]
 addr r3,0x2007ff80
 ldr r2,[r3,#68]
 str r2,[r1,#24]
 ldr r2,[r3,#32]
 str r2,[r1,#28]
pm_result_done:
 restore
 mov r3,r0
 mov r0,r3
 b.w 0x1bde
.global stats_issue
.thumb_func
stats_issue:
 save
 live stats_issue_done
 seq stats_issue_done
 str r2,[r0,#92]
 ldr r2,[r0,#20]
 str r2,[r0,#88]
 ldr r2,[r0,#24]
 cmp r2,#1
 ite eq
 moveq r2,#256
 movne r2,#0
 str r2,[r0,#84]
 mvn r2,#1
 str r2,[r0,#64]
stats_issue_done:
 restore
 movw lr,#0xe109
 movt lr,#1
 b.w 0x1cb4
.global stats_result
.thumb_func
stats_result:
 save
 live stats_result_done
 seq stats_result_done
 ldr r2,[sp,#8]
 str r2,[r0,#64]
 cmp r2,#0
 bne 1f
 ldr r2,[r0,#88]
 ldr r3,[r0,#20]
 cmp r2,r3
 bne 1f
 ldr r2,[r0,#24]
 cmp r2,#1
 beq stats_result_done
1: movs r2,#0
 str r2,[r0,#84]
stats_result_done:
 restore
 str r0,[r7,#52]
 ldr r3,[r7,#52]
 b.w 0x1e10c
.global fresh_sample
.thumb_func
fresh_sample:
 save
 /* Replay original division and provide exact native outgoing registers,
  * even after observer freeze. Entry saved r2=C,r3=actualdelta. */
 movw r2,#600
 ldr r3,[r7,#48]
 udiv r3,r2,r3
 str r2,[sp,#16]
 /* Keep entryC in r12 until private capture, outputq in savedr3. */
 ldr r12,[sp,#16]
 /* C was overwritten above; recover entry C from native operand is forbidden.
  * Save entry C in original savedr12 slot temporarily? handled below. */
 b.w fresh_capture
'''
 # Rewrite fresh prologue to retain C using r1 temporary after save.
 a=a[:a.index('.global fresh_sample')]+'''.global fresh_sample
.thumb_func
fresh_sample:
 save
 ldr r1,[sp,#16]
 movw r2,#600
 ldr r3,[r7,#48]
 udiv r3,r2,r3
 str r2,[sp,#16]
 /* r1entryC and r3q retained on private header stores before scratch reuse. */
 addr r0,0x2007fd80
 ldr r2,[r0]
 addr r12,0x504d3636
 cmp r2,r12
 bne fresh_done
 ldr r2,[r0,#12]
 tst r2,#1
 bne fresh_done
 str r1,[r0,#68]
 ldr r2,[sp,#20]
 str r2,[r0,#76]
 sub r1,r1,r2
 str r1,[r0,#72]
 str r3,[r0,#80]
 ldr r2,[r0,#84]
 and r2,r2,#256
 uxtb r1,r3
 orr r2,r2,r1
 orr r2,r2,#512
 str r2,[r0,#84]
 /* Savedr3 becomes exactly native quotient for continuation1E13C. */
 str r3,[sp,#20]
 seq fresh_done
 ldr r2,[r0,#80]
 cmp r2,#1
 bne fresh_done
 ldr r2,[r0,#64]
 cmp r2,#0
 bne fresh_bad_epoch
 ldr r2,[r0,#84]
 tst r2,#256
 beq fresh_bad_epoch
 ldr r2,[r0,#88]
 ldr r3,[r0,#20]
 cmp r2,r3
 bne fresh_bad_epoch
 ldr r2,[r0,#24]
 cmp r2,#1
 bne fresh_bad_epoch
 ldr r2,[r0,#36]
 cbz r2,fresh_snapshot
fresh_bad_epoch:
 ambiguous
fresh_snapshot:
 addr r3,0x2007ff80
 ldr r2,[r3,#68]
 str r2,[r0,#96]
 ldr r2,[r3,#56]
 str r2,[r0,#100]
 ldr r2,[r3,#112]
 str r2,[r0,#104]
 ldr r2,[r3,#120]
 str r2,[r0,#108]
 ldr r2,[r3,#60]
 str r2,[r0,#112]
 ldr r2,[r3,#64]
 str r2,[r0,#116]
 event 9,fresh_done
 ldr r2,[r0,#68]
 str r2,[r1,#16]
 ldr r2,[r0,#72]
 str r2,[r1,#20]
 ldr r2,[r0,#76]
 str r2,[r1,#24]
 ldr r2,[r0,#80]
 str r2,[r1,#28]
 ldr r2,[r0,#12]
 orr r2,r2,#1
 dmb sy
 str r2,[r0,#12]
fresh_done:
 /* Frozen/invalid observer bypass still owes nativeq replay. Recompute only
  * on bypass where savedr3 stilldelta; preserve savedAPSR across this code. */
 movw r2,#600
 ldr r3,[r7,#48]
 udiv r3,r2,r3
 str r2,[sp,#16]
 str r3,[sp,#20]
 restore
 b.w 0x1e13c
.global connect_begin
.thumb_func
connect_begin:
 save
 live connect_begin_done
 event 3,connect_begin_done
 ldr r2,[r0,#20]
 cmn r2,#1
 beq epoch_wrap_connect
 adds r2,#1
 str r2,[r0,#20]
 str r2,[r1,#8]
 movs r2,#2
 str r2,[r0,#24]
 str r7,[r0,#60]
 ldr r3,[r7,#4]
 ldr r2,[r3,#8]
 str r2,[r0,#120]
 str r2,[r1,#16]
 ldrh r2,[r3,#12]
 str r2,[r0,#124]
 str r2,[r1,#20]
 addr r3,0x2007ff80
 ldr r2,[r3,#84]
 str r2,[r1,#24]
 ldr r2,[r3,#88]
 str r2,[r1,#28]
 b connect_begin_done
epoch_wrap_connect:
 ldr r2,[r0,#12]
 orr r2,r2,#16
 str r2,[r0,#12]
connect_begin_done:
 restore
 movw lr,#0x7fc9
 movt lr,#5
 b.w 0x102f6c
.global connect_commit
.thumb_func
connect_commit:
 save
 live connect_commit_done
 event 4,connect_commit_done
 ldr r2,[r0,#60]
 cmp r2,r7
 bne 1f
 ldr r2,[r0,#24]
 cmp r2,#2
 bne 1f
 movs r2,#1
 str r2,[r0,#24]
 b 2f
1: ambiguous
 movs r2,#0
 str r2,[r0,#24]
2: str r2,[r1,#16]
 movs r2,#0
 str r2,[r0,#60]
 str r2,[r1,#20]
 addr r3,0x2007ff80
 ldr r2,[r3,#84]
 str r2,[r1,#24]
 ldr r2,[r3,#88]
 str r2,[r1,#28]
connect_commit_done:
 restore
 pop {r4,r5}
 msr APSR_nzcvq,r4
 b.w 0x102f8e
.global disconnect
.thumb_func
disconnect:
 save
 live disconnect_done
 event 5,disconnect_done
 ldr r2,[r0,#20]
 cmn r2,#1
 beq epoch_wrap_disconnect
 adds r2,#1
 str r2,[r0,#20]
 str r2,[r1,#8]
 movs r2,#0
 str r2,[r0,#24]
 str r2,[r0,#60]
 ldr r3,[r7,#4]
 ldr r2,[r3,#4]
 str r2,[r1,#16]
 ldrh r2,[r3,#8]
 str r2,[r1,#20]
 ldrh r2,[r3,#10]
 str r2,[r1,#24]
 movs r2,#0
 str r2,[r1,#28]
 b disconnect_done
epoch_wrap_disconnect:
 ldr r2,[r0,#12]
 orr r2,r2,#16
 str r2,[r0,#12]
disconnect_done:
 restore
 movw lr,#0x8125
 movt lr,#5
 b.w 0x102f90
'''
 for name,kind in [('commit_first',6),('commit_second',7)]:
  a+=f'''.global {name}
.thumb_func
{name}:
 save
 live {name}_done
 event {kind},{name}_done
 ldr r2,[sp,#8]
 str r2,[r1,#16]
 ldr r2,[sp,#44]
 str r2,[r1,#20]
 ldr r2,[sp,#48]
 str r2,[r1,#24]
 ldr r2,[r0,#52]
 str r2,[r1,#28]
{name}_done:
 restore
'''
  if kind==6:a+=' cbz r0,1f\n ldr r0,[r4,#16]\n b.w 0x103af2\n1: b.w 0x103b50\n'
  else:a+=' mov r5,r0\n add r0,sp,#72\n b.w 0x103b88\n'
 a+='''.global status_export
.thumb_func
status_export:
 save
 ldr r2,[sp,#4]
 ldr r0,[sp,#8]
 mov r1,r7
 bl obs_export
 str r0,[sp,#8]
 restore
 mov r3,r0
 mov r2,r3
 b.w 0x19e90
.balign 4
'''
 return a

def validate_inputs(b,g):
 assert SHA(b)==BSHA and SHA(g)==GSHA,'immutable baseline identity'
 for at,(pre,_,n) in HOOKS.items():assert b[at:at+n].hex()==pre,('preimage',hex(at))

def validate_frozen(override=None):
 pins=json.loads((HERE/'frozen-inputs.json').read_text())['pins']
 for n,h in pins.items():
  value=(override or {}).get(n,(ROOT/n).read_bytes())
  assert SHA(value)==h,('frozen source/result',n)

def main():
 p=argparse.ArgumentParser();p.add_argument('stock',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args();o=a.out;o.mkdir(parents=True,exist_ok=True)
 validate_frozen()
 import importlib.util
 spec=importlib.util.spec_from_file_location('qualified_b21_pipeline',ROOT/'tools/scripts/patcher/all_known_fixes_2.2.4/build.py');bp=importlib.util.module_from_spec(spec);spec.loader.exec_module(bp)
 rebuilt,_,_=bp.construct(a.stock,o/'b21-parent')
 assert SHA(rebuilt)==BSHA,'B2.1 reconstruction identity'
 b=(BASE/(NAME+'_EXPERIMENTAL.bin')).read_bytes();g=(BASE/(NAME+'_EXPERIMENTAL.gbl')).read_bytes();validate_inputs(b,g);assert rebuilt==b
 cmd=['clang','--target=arm-none-eabi','-mcpu=cortex-m4','-mthumb','-Os','-ffreestanding','-fno-builtin','-fno-unwind-tables','-fno-asynchronous-unwind-tables','-fno-stack-protector','-fno-jump-tables']
 subprocess.run(cmd+['-S',str(HERE/'readout.c'),'-o',str(o/'readout-compiler.s')],check=True)
 s=re.sub(r'b\.w 0x([0-9a-f]+)',lambda m:'b.w native_'+m[1],assembly())
 for line in (o/'readout-compiler.s').read_text().splitlines():
  if line.strip().startswith(('.section','.fnstart','.fnend','.cantunwind','.eabi_attribute','.ident','.addrsig','.save','.setfp','.pad','.globl')):continue
  s+=line+'\n'
 s+='\n.balign 4\nextension_end:\n'
 s='\n'.join(line for line in s.splitlines() if not line.startswith('.global '))+'\n'
 (o/'observer.S').write_text(s);subprocess.run(cmd+['-c',str(o/'observer.S'),'-o',str(o/'observer.o')],check=True)
 # Resolve only clang's two local absolute MOVW/MOVT prefix-address relocations.
 raw=bytearray((o/'observer.o').read_bytes());eh=struct.unpack_from('<16sHHIIIIIHHHHHH',raw);sh=[struct.unpack_from('<10I',raw,eh[6]+i*eh[11]) for i in range(eh[12])];names=raw[sh[eh[13]][4]:sh[eh[13]][4]+sh[eh[13]][5]]
 nm=lambda h: bytes(names[h[0]:]).split(b'\0',1)[0].decode()
 ti=next(i for i,h in enumerate(sh) if nm(h)=='.text');st=next(h for h in sh if h[1]==2);symbols=[struct.unpack_from('<IIIBBH',raw,x) for x in range(st[4],st[4]+st[5],st[9])];relocs=[]
 for i,h in enumerate(sh):
  if h[1]!=9 or h[5]==0:continue
  assert h[7]==ti
  for x in range(h[4],h[4]+h[5],h[9]):
   pos,info=struct.unpack_from('<II',raw,x);kind=info&255;sv=symbols[info>>8];assert kind in(47,48) and sv[5]==ti
   target=sv[1];loc=sh[ti][4]+pos;a,bx=struct.unpack_from('<HH',raw,loc)
   imm=((a&15)<<12)|(((a>>10)&1)<<11)|(((bx>>12)&7)<<8)|(bx&255);assert imm==0
   value=(target if kind==47 else target>>16)&65535
   a=(a&~0x40f)|((value>>12)&15)|(((value>>11)&1)<<10);bx=(bx&~0x70ff)|(((value>>8)&7)<<12)|(value&255)
   struct.pack_into('<HH',raw,loc,a,bx);relocs.append({'site':hex(pos),'kind':kind,'target':hex(target)})
  struct.pack_into('<I',raw,eh[6]+i*eh[11]+20,0)
 assert len(relocs)==2
 (o/'observer.o').write_bytes(raw);(o/'local-relocations.json').write_text(json.dumps(relocs,indent=2)+'\n')
 text,sym=elf(o/'observer.o');end=sym['extension_end'];assert end<0x130a98
 app=bytearray(b)+bytearray(b'\xff'*(end-len(b)));changes=[]
 def write(at,v,why):
  old=b[at:at+len(v)] if at<len(b) else b'';app[at:at+len(v)]=v;changes.append({'address':hex(at),'end':hex(at+len(v)),'before':old.hex(),'after':v.hex(),'owner':why})
 for at,(_,name,n) in HOOKS.items():write(at,text[at:at+n],name)
 for at in (0,0x254):assert b[at:at+4]==bytes.fromhex('80ff0720');write(at,struct.pack('<I',0x2007fd80),'private512_MSP_reservation')
 write(len(b),text[len(b):end],'observer_code')
 path=o/'working.bin';path.write_bytes(app)
 sy={k:hex(v) for k,v in sym.items()};(o/'symbols.json').write_text(json.dumps(sy,sort_keys=True,indent=2)+'\n')
 m={'baseline_app_sha256':BSHA,'baseline_gbl_sha256':GSHA,'app_sha256':SHA(app),'app_size':len(app),'app_crc32':f'{zlib.crc32(app):08x}','observer_RAM':[hex(0x2007fd80),hex(0x2007ff80)],'extension':[hex(len(b)),hex(end)],'changes':changes,'object_sha256':SHA((o/'observer.o').read_bytes()),'assembly_sha256':SHA(s.encode()),'qualified':False,'research_build':'B2.1_OBS','native_version_changed':False,'parent_reconstruction_manifest_sha256':SHA((o/'b21-parent/construction-manifest.json').read_bytes())}
 (o/'construction-manifest.json').write_text(json.dumps(m,sort_keys=True,indent=2)+'\n');print(json.dumps({k:v for k,v in m.items() if k not in ('changes',)},indent=2))
if __name__=='__main__':main()
