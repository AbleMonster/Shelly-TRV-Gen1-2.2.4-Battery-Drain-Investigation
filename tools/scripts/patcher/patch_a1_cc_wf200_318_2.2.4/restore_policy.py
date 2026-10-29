#!/usr/bin/env python3
"""Versioned authoritative A1R construction rule, retaining historical assets.
Source-generated stackless origin classifier; never an opaque edited image.
"""
from pathlib import Path
import hashlib,json,struct,subprocess,sys
ROOT=Path(__file__).resolve().parents[4];HERE=Path(__file__).resolve().parent
H=lambda b:hashlib.sha256(b).hexdigest()
OLD_ALL='80346b95c69bff29ddf580deb0c1bb24aa4ac372a8e790e7b020e947edee4dc3'
OLD_A1='0bb530cfda66b4c45ada8d864d623ff4f952405a4da0f8f00f368a9f6116030d'
SITE=0x103878;CONTINUE=0x10387e;START=0x1046dc
PRE=bytes.fromhex('01208ef80400')
CALLS={0x17494:0x17498,0x1b65a:0x1b65e,0x6d822:0x6d826,0x19d74:0x19d78,0x1cfb2:0x1cfb6}
def need(v,s):
 if not v:raise ValueError(s)
def target(b,a):
 x,y=struct.unpack_from('<HH',b,a);need(x&0xf800==0xf000 and y&0xd000==0x9000,'A1R B.W encoding')
 s=x>>10&1;n=s<<24|(1^((y>>13)&1)^s)<<23|(1^((y>>11)&1)^s)<<22|(x&1023)<<12|(y&2047)<<1
 return a+4+n-(1<<25 if s else 0)
def apply(parent,out,kind='AllKnown'):
 need(kind in ['AllKnown','A1'],'A1R profile');need(H(parent)==(OLD_ALL if kind=='AllKnown' else OLD_A1),'A1R exact historical parent')
 need(len(parent)==(START if kind=='AllKnown' else 0x104630),'A1R historical extent')
 need(parent[SITE:CONTINUE]==PRE,'A1R saved-policy preimage')
 # Caller instructions/H180 preimages are immutable local stock records;
 # their exact bytes also bind normalized LR provenance.
 stock=(ROOT/'extracted/program_1_0x00000000.bin').read_bytes()
 need(H(stock)=='4dc770fe535008ef150f3a144354169199e1a0e235173abcc3f7387b95ee9b5c','A1R stock identity')
 for call,ret in CALLS.items():need(parent[call-8:call+4]==stock[call-8:call+4] and call+4==ret,'A1R caller preimage '+hex(call))
 out=Path(out);out.mkdir(parents=True,exist_ok=True)
 source=(HERE/'a1r_restore.S').read_bytes();(out/'a1r_restore.S').write_bytes(source)
 subprocess.run(['clang','--target=arm-none-eabi','-mcpu=cortex-m4','-mthumb','-c',str(out/'a1r_restore.S'),'-o',str(out/'a1r_restore.o')],check=True)
 sys.path.insert(0,str(ROOT/'builds/build_pmd210_static_2026-10-17'));from elf_tools import elf
 text,sym=elf(out/'a1r_restore.o');end=sym['a1r_program_end'];need(end%4==0 and START<end<0x130a98,'A1R helper geometry')
 need(sym['a1r_restore_origin']&~1==START,'A1R helper address')
 hook=text[SITE:CONTINUE];ext=text[START:end]
 need(target(text,SITE)==START and hook[4:]==bytes.fromhex('00bf'),'A1R detour')
 # Local labels were emitted within one .text section: no external relocation.
 need(text[START:START+2]!=bytes.fromhex('ffff'),'A1R emitted helper')
 app=bytearray(parent)+bytearray(b'\xff'*(end-len(parent)));app[SITE:CONTINUE]=hook;app[START:end]=ext
 manifest={'revision':'A1R timed-override restore','parent_kind':kind,'parent_sha256':H(parent),'source_sha256':H(source),'object_sha256':H((out/'a1r_restore.o').read_bytes()),'application_sha256':H(app),'site':hex(SITE),'before':PRE.hex(),'after':hook.hex(),'helper':[hex(START),hex(end)],'helper_bytes':len(ext),'helper_sha256':H(ext),'helper_hex':ext.hex(),'temporary_return_PCs':[hex(v) for v in CALLS.values()],'native_continue':hex(CONTINUE),'new_stack_bytes':0,'new_RAM_bytes':0,'bounded_origin_only':True,'generation_publication':'unchanged including repeated H180','recovery':'unchanged','generic_persistent':'unchanged'}
 (out/'a1r-manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n');return bytes(app),manifest
