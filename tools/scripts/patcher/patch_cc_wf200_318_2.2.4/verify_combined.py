#!/usr/bin/env python3
"""Independent offline verifier; no builder imports, firmware writes or device I/O.

Only --report writes JSON metadata. Negative fixtures exist in memory only.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import zlib

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / 'build_cc_wf200_318_2026-10-19'
NAME = 'SHTRV-01_2.2.4_C-C_WF200_3.18.0_EXPERIMENTAL'
PROGRAM, END = 0xFD0303FD, 0xFC0404FC
TAGS = [0x03A617EB, 0xF40A0AF4, 0xF50909F5, PROGRAM, PROGRAM, END]
PIN = {
 'original/2.2.4/SHTRV-01_build_2.2.4.gbl': (1106384,'5c4a0b222a313350952f6b1200a855833402f168bd286090c23bd4d018ab918f'),
 'extracted/program_1_0x00000000.bin': (1049548,'4dc770fe535008ef150f3a144354169199e1a0e235173abcc3f7387b95ee9b5c'),
 'extracted/program_2_0x00130A98.bin': (30872,'662bd549f050ab81a120d3daa07646652c38880b9d2bfa988ff6bee7f731e33e'),
 'original/WF200/wfx-firmware/wfm_wf200_C0.sec': (312400,'886d009b3852cb41f7c67c85de5c9bf2e6d67614e10d668b4fa1e18734078cb9'),
}
DOCUMENTS = {
 'docs/local/rea_report/patch-c-design-2026-10-14.md':'ed800b890fc8bd1de5893540adc9a0ada53d8b7a9fb5a95d0da9250a7a598d7d',
 'docs/local/rea_report/patch-c-prebuild-qualification-2026-10-14.md':'523ab60f079e2d3d9543a8481334034f8f025caa2c599668fd22bdcb06b6e18c',
 'tools/scripts/patcher/patch_cc_2.2.4/build_patch_cc_gbl.py':'6ac460d3ab633f5284db790dfdaa88bc4ff53db50e28a7c7d663002b3525fe34',
 'build_wf200_318_relocation_qualification_2026-10-18/relocation-manifest.json':'fa76bb67067153523b1fb71e18d5667b7fad43634174024b982cdb12c1dc9bba',
}

def check(ok, why):
    if not ok:
        raise ValueError(why)

def sha(data):
    return hashlib.sha256(data).hexdigest()

def word(data, at=0):
    check(at >= 0 and at+4 <= len(data), 'word extent')
    return int.from_bytes(data[at:at+4], 'little')

def gbl(data, integrity=True):
    records=[]
    p=0
    while p < len(data):
        check(p+8 <= len(data), 'truncated record')
        tag,n=struct.unpack_from('<II',data,p)
        q=p+8+n
        check(q<=len(data), 'record outside container')
        records.append((p,tag,data[p+8:q]))
        p=q
    check([x[1] for x in records]==TAGS, 'stock tag order/uniqueness')
    check(len(records[-1][2])==4, 'END CRC length')
    check(all(len(records[i][2])>=4 for i in (3,4)), 'PROGRAM address field')
    if integrity:
        check(zlib.crc32(data[:-4])==word(data,len(data)-4), 'GBL END CRC')
        check(zlib.crc32(data)==0x2144DF1C, 'GBL full residue')
    return records

def decode_bl(data, site):
    check(len(data)>=4, 'BL extent')
    a,b=struct.unpack_from('<HH',data)
    check(a&0xF800==0xF000 and b&0xD000==0xD000, 'Thumb BL encoding')
    s=(a>>10)&1
    i1=1^(((b>>13)&1)^s)
    i2=1^(((b>>11)&1)^s)
    disp=(s<<24)|(i1<<23)|(i2<<22)|((a&1023)<<12)|((b&2047)<<1)
    if s: disp-=1<<25
    return site+4+disp

def encode_bl(site, target):
    d=target-(site+4)
    check(d%2==0 and -(1<<24)<=d<(1<<24), 'BL reach/alignment')
    v=d&0x1FFFFFF
    s=(v>>24)&1
    j1=1^(((v>>23)&1)^s)
    j2=1^(((v>>22)&1)^s)
    return struct.pack('<HH',0xF000|(s<<10)|((v>>12)&1023),
                       0xD000|(j1<<13)|(j2<<11)|((v>>1)&2047))

def context(input_overrides=None):
    input_overrides = input_overrides or {}
    inputs={}
    for name,(size,h) in PIN.items():
        data=input_overrides.get(name, (ROOT/name).read_bytes())
        check(len(data)==size and sha(data)==h, 'immutable input '+name)
        inputs[name]=data
    docs={}
    for name,h in DOCUMENTS.items():
        data=(ROOT/name).read_bytes()
        check(sha(data)==h, 'evidence pin '+name)
        docs[name]=data
    stock_gbl,stock,second,sec=inputs.values()
    r=gbl(stock_gbl)
    check(word(r[3][2])==0 and r[3][2][4:]==stock, 'stock extraction first')
    check(word(r[4][2])==0x130A98 and r[4][2][4:]==second, 'stock extraction second')
    design=docs[next(iter(DOCUMENTS))].decode()
    qtext=docs['docs/local/rea_report/patch-c-prebuild-qualification-2026-10-14.md'].decode()
    sites=[]
    section=design.split('### C-C\n',1)[1].split('### C-D\n',1)[0]
    for line in section.splitlines():
        cells=[x.strip().strip('`') for x in line.strip('|').split('|')]
        if len(cells)==6 and re.fullmatch('0x[0-9a-fA-F]+',cells[0]):
            at=int(cells[0],16); old=bytes.fromhex(cells[2]); new=bytes.fromhex(cells[3])
            check(len(old)==len(new) and stock[at:at+len(old)]==old, 'CC stock preimage')
            rows=[x for x in qtext.splitlines() if x.startswith('|`'+hex(at)+'`|')]
            check(len(rows)==1 and '`'+old.hex()+'`' in rows[0] and '`'+new.hex()+'`' in rows[0], 'CC cross-report site')
            sites.append((at,old,new))
    helpers=[]
    section=design.split('### C-C complete appended bytes\n',1)[1].split('### C-D appended bytes\n',1)[0]
    for line in section.splitlines():
        cells=[x.strip().strip('`') for x in line.strip('|').split('|')]
        if len(cells)==4 and re.fullmatch('0x[0-9a-fA-F]+',cells[0]):
            at=int(cells[0],16); n=int(cells[1]); code=bytes.fromhex(cells[3])
            check(len(code)==n, 'CC helper declared extent')
            check(f'|`0x{at:X}`|{n}|`{code.hex()}`|' in qtext, 'CC cross-report helper')
            helpers.append((at,code))
    check(len(sites)==15 and len(helpers)==10, 'CC 15 sites / 10 helpers')
    check(sum(len(o)for _,o,_ in sites)==82, 'CC site footprint')
    check(sum(sum(a!=b for a,b in zip(o,n))for _,o,n in sites)==77, 'legacy CC changed bytes')
    check(helpers[0][0]==0x1003D0 and helpers[-1][0]+len(helpers[-1][1])==0x1004E4, 'CC legacy helper range')
    check(all(a+len(c)==b for (a,c),(b,_) in zip(helpers,helpers[1:])), 'CC contiguous helpers')
    m=json.loads(docs['build_wf200_318_relocation_qualification_2026-10-18/relocation-manifest.json'])
    check(m['qualification']=='QUALIFIED FOR CONSTRUCTION', 'relocation qualified verdict')
    check(len(m['external_fixups'])==51 and len(m['internal_fixups'])==3 and len(m['excluded_original_candidates'])==6, '51/3/6 relocation counts')
    check(sha(stock[0xF9A70:0xF9E78])=='18811686eadef8707f7977a48db8fd78a1891ee65cbf15d67432910e2ac63475','relocation source')
    # Expected candidate is constructed ONLY in memory from immutable evidence.
    expected=bytearray(stock+b'\xff'*(0x1008EC-len(stock)))
    expected[0x1003D0:0x1007D8]=stock[0xF9A70:0xF9E78]
    fixes=[]
    for kind in ('external_fixups','internal_fixups'):
        for f in m[kind]:
            p=int(f['source'],16); q=int(f['future_site'],16)
            old=bytes.fromhex(f['old_word_le']); new=bytes.fromhex(f['new_word_le'])
            check(f['classification']=='PROVEN REQUIRED FIXUP' and len(old)==len(new)==4 and stock[p:p+4]==old, 'relocation preimage/class')
            check(word(new)==word(old)+0x6960==int(f['new_target'],16), 'relocation target delta')
            check(q==(p if kind=='external_fixups' else p+0x6960), 'relocation site delta')
            expected[q:q+4]=new
            fixes.append((kind,p,q,old,new))
    expected[0xADA20:0xF9E70]=sec
    check(stock[0x578AC:0x578B0]==bytes.fromhex('50c00400'), 'old WF length')
    expected[0x578AC:0x578B0]=bytes.fromhex('50c40400')
    check(sha(expected[0x1003D0:0x1007D8])=='a94ece8f7c3203ca638eab513cde4d47f922b2b1819006041387abb5c7bb4564', 'relocated destination')
    for a,code in helpers:
        expected[a+0x408:a+0x408+len(code)]=code
    hook_map=[]
    for at,old,new in sites:
        relocated=new
        a,b=struct.unpack_from('<HH',new)
        if a&0xF800==0xF000 and b&0xD000==0xD000:
            target=decode_bl(new,at)
            check(target in {a for a,_ in helpers}, 'legacy BL helper entry')
            relocated=encode_bl(at,target+0x408)+new[4:]
            check(decode_bl(relocated,at)==target+0x408, 'BL roundtrip')
            hook_map.append({'site':hex(at),'legacy_target':hex(target),'combined_target':hex(target+0x408),'legacy_hex':new.hex(),'combined_hex':relocated.hex(),'return_address':hex(at+4)})
        expected[at:at+len(relocated)]=relocated
    check(len(hook_map)==11, 'exact eleven relocated BL hooks/four non-BL sites')
    for f in m['excluded_original_candidates']:
        p=int(f['source'],16)
        check(f['classification']=='PROVEN NOT A FIXUP' and expected[p:p+4]==stock[p:p+4]==bytes.fromhex(f['old_word_le']), 'excluded reference preserved')
    consumer_checks=0
    for f in m['external_fixups']+m['internal_fixups']+m['excluded_original_candidates']:
        for ref in f['consumer_xrefs']:
            at=int(ref['instruction'],16); code=bytes.fromhex(ref['stock_instruction_bytes'])
            check(stock[at:at+len(code)]==code==expected[at:at+len(code)], 'qualified relocation consumer unchanged')
            consumer_checks+=1
    literals=[]
    returns=[]
    for a,code in helpers:
        # Qualified helpers end executable code at BX LR or POP {...,PC}.
        ret=[i for i in range(0,len(code)-1,2) if code[i:i+2]==b'\x70\x47' or int.from_bytes(code[i:i+2],'little')&0xFF00==0xBD00]
        check(ret, 'qualified helper return instruction')
        end_code=min(ret)+2
        returns.append({'old_helper':hex(a),'new_helper':hex(a+0x408),'return_offset':hex(end_code-2),'return_hex':code[end_code-2:end_code].hex()})
        for i in range(0,end_code,2):
            h=int.from_bytes(code[i:i+2],'little')
            if h&0xF800==0x4800:
                target=((a+i+4)&~3)+4*(h&255)
                translated=(((a+0x408)+i+4)&~3)+4*(h&255)
                check(translated==target+0x408 and a+end_code<=target<=a+len(code)-4, 'local LDR literal translation')
                literals.append({'old_instruction':hex(a+i),'new_instruction':hex(a+0x408+i),'old_pool':hex(target),'new_pool':hex(translated),'literal_word':hex(word(code,target-a))})
    return dict(stock_gbl=stock_gbl,stock=stock,second=second,sec=sec,m=m,sites=sites,helpers=helpers,fixes=fixes,expected=bytes(expected),hooks=hook_map,literals=literals,returns=returns,consumer_checks=consumer_checks,original_records=r)

def verify(data, c, standalone=None):
    r=gbl(data)
    stock=c['stock']; original=c['original_records']; expected=c['expected']
    check(len(data)==len(c['stock_gbl'])+0x520, 'container growth 0x520')
    check(word(r[3][2])==0 and len(r[3][2])==0x1008F0, 'first PROGRAM address/body length')
    app=r[3][2][4:]
    check(len(app)==0x1008EC, 'application end')
    check(standalone is None or standalone==app, 'standalone/GBL exact equality')
    for i in (0,1,2,4):
        check(r[i][1:]==original[i][1:], 'unrelated record/address/payload '+str(i))
    check(r[3][0]==original[3][0], 'first PROGRAM offset')
    check(r[4][0]==original[4][0]+0x520 and r[5][0]==original[5][0]+0x520, 'following container offsets')
    check(app[0xADA20:0xF9E70]==c['sec'], 'official SEC unchanged')
    check(app[0xF9E70:0xF9E78]==stock[0xF9E70:0xF9E78], 'stale source suffix')
    check(app[0x1003CC:0x1003D0]==b'\xff'*4, 'alignment gap')
    check(sha(app[0x1003D0:0x1007D8])=='a94ece8f7c3203ca638eab513cde4d47f922b2b1819006041387abb5c7bb4564', 'relocated block hash')
    check(word(app,0x5788C)==0xADA20 and word(app,0x578AC)==0x4C450, 'loader base and length')
    for kind,p,q,old,new in c['fixes']:
        check(app[q:q+4]==new, 'required relocation '+hex(q))
    for f in c['m']['excluded_original_candidates']:
        p=int(f['source'],16);check(app[p:p+4]==stock[p:p+4], 'excluded literal '+hex(p))
    for h in c['hooks']:
        p=int(h['site'],16);check(app[p:p+len(bytes.fromhex(h['combined_hex']))]==bytes.fromhex(h['combined_hex']), 'CC hook '+hex(p))
        check(decode_bl(app[p:p+4],p)==int(h['combined_target'],16), 'CC hook target')
    for p,code in c['helpers']:
        check(app[p+0x408:p+0x408+len(code)]==code, 'CC helper incl returns/literals '+hex(p+0x408))
    check(app==expected, 'exhaustive stock-authorized application reconstruction')
    for site,value in c['m']['unchanged_startup_literals'].items():
        p=int(site,16);check(word(app,p)==int(value,16), 'startup fixed bound')
    check(app[0xFF118:0x1003CC]==stock[0xFF118:0x1003CC], 'RAM initialization source')
    # Exact equality above excludes A1 and every other unlisted mutation.
    changes=[]; start=None; total=0
    for p in range(len(app)+1):
        changed=p<len(app) and (p>=len(stock) or app[p]!=stock[p])
        if changed:
            total+=1
            if start is None:start=p
        elif start is not None:
            changes.append({'start':hex(start),'end_exclusive':hex(p),'bytes':p-start,'candidate_sha256':sha(app[start:p])});start=None
    return {'result':'PASS_INDEPENDENT_STATIC','candidate_gbl':{'bytes':len(data),'sha256':sha(data),'stored_crc32':f'{word(data,len(data)-4):08x}','calculated_crc32':f'{zlib.crc32(data[:-4]):08x}','whole_container_crc_residue':f'{zlib.crc32(data):08x}'},'candidate_application':{'bytes':len(app),'sha256':sha(app)},'standalone_application_equal':standalone is not None,'standalone_sha256':sha(standalone) if standalone is not None else None,'second_PROGRAM':{'load_address':'0x130a98','bytes':len(c['second']),'sha256':sha(r[4][2][4:])},'official_SEC_sha256':sha(app[0xADA20:0xF9E70]),'unchanged_relocation_consumer_instruction_records':c['consumer_checks'],'relocation_external':51,'relocation_internal':3,'excluded_unchanged':6,'cc_ranges':15,'cc_BL_hooks_retargeted':11,'cc_non_BL_ranges_unchanged':4,'cc_helpers':10,'cc_helper_bytes':276,'cc_helper_range':['0x1007d8','0x1008ec'],'helper_bytes_identical_to_qualified_CC':True,'hooks':c['hooks'],'helper_literal_pool_translation':c['literals'],'helper_return_instructions':c['returns'],'all_unlisted_bytes_stock':True,'no_A1_or_observer_changes':True,'exact_diff_runs':changes,'changed_or_appended_bytes':total,'gbl_records':[{'tag':hex(t),'offset':hex(p),'body_bytes':len(b),'body_sha256':sha(b)}for p,t,b in r],'evidence_pins':DOCUMENTS,'immutable_inputs':{k:{'bytes':n,'sha256':h}for k,(n,h)in PIN.items()}}

def negative_controls(data,c):
    r=gbl(data); base=r[3][0]+12
    f=c['m']['external_fixups'][0]; first_hook=c['hooks'][0]
    helper0=c['helpers'][0][1]
    cases=[
      ('REQUIRED01 old CC helper at1003D0 overwrites relocation',base+0x1003D0,helper0),
      ('REQUIRED02 hook retains old helper target',base+int(first_hook['site'],16),bytes.fromhex(first_hook['legacy_hex'])),
      ('REQUIRED03 rebased branch wrong target',base+int(first_hook['site'],16),encode_bl(int(first_hook['site'],16),int(first_hook['combined_target'],16)+2)),
      ('REQUIRED04 missing external relocation fixup',base+int(f['source'],16),bytes.fromhex(f['old_word_le'])),
      ('REQUIRED05 SEC protected-byte corruption',base+0xADA20+200,None),
      ('REQUIRED06 wrong SEC full-container length',base+0x578AC,bytes.fromhex('50c00400')),
      ('REQUIRED07 second PROGRAM wrong load address',r[4][0]+8,(0x130A9C).to_bytes(4,'little')),
      ('REQUIRED09 helper overlaps relocated block',base+0x1007D4,helper0),
      ('REQUIRED10 unauthorized host byte',base+0x100,None),
      ('WF base wrong',base+0x5788C,None),
      ('internal relocation wrong',base+int(c['m']['internal_fixups'][0]['future_site'],16),None),
      ('excluded candidate changed',base+int(c['m']['excluded_original_candidates'][0]['source'],16),None),
      ('stale source suffix changed',base+0xF9E70,None),
      ('alignment gap changed',base+0x1003CC,None),
      ('second PROGRAM payload changed',r[4][0]+12,None),
      ('unrelated tag changed',r[0][0]+8,None),
      ('CC non-BL logic wrong',base+0x1E0FC,None),
      ('CC helper return wrong',base+0x1007D8+34,None),
      ('CC helper RAM literal wrong',base+0x1007D8+44,None),
      ('startup copy length wrong',base+0x750,None),
    ]
    result=[]
    for label,at,replacement in cases:
        bad=bytearray(data)
        if replacement is None:bad[at]^=1
        else:bad[at:at+len(replacement)]=replacement
        bad[-4:]=zlib.crc32(bad[:-4]).to_bytes(4,'little')
        try:verify(bytes(bad),c)
        except ValueError as exc:result.append({'case':label,'result':'REJECTED','reason':str(exc),'in_memory_only':True,'CRC_repaired':True})
        else:raise ValueError('negative unexpectedly accepted: '+label)
    name='extracted/program_1_0x00000000.bin'
    bad_stock=bytearray(c['stock']);bad_stock[0x100]^=1
    try:context({name:bytes(bad_stock)})
    except ValueError as exc:result.append({'case':'REQUIRED08 stale stock preimage identity','result':'REJECTED','reason':str(exc),'in_memory_only':True,'CRC_repaired':None})
    else:raise ValueError('stale stock preimage accepted')
    bad=bytearray(data);bad[-1]^=1
    try:verify(bytes(bad),c)
    except ValueError as exc:result.append({'case':'END CRC wrong','result':'REJECTED','reason':str(exc),'in_memory_only':True,'CRC_repaired':False})
    else:raise ValueError('CRC negative accepted')
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--candidate',type=Path,default=OUT/(NAME+'.gbl'))
    p.add_argument('--standalone',type=Path,help='optional application exported by builder')
    p.add_argument('--report',type=Path)
    p.add_argument('--negative-controls',action='store_true')
    a=p.parse_args()
    c=context();data=a.candidate.read_bytes()
    standalone=a.standalone.read_bytes() if a.standalone else None
    result=verify(data,c,standalone)
    if a.negative_controls:result['negative_controls']=negative_controls(data,c)
    if a.report:
        check(a.report.suffix.lower()=='.json','report extension must be JSON metadata')
        a.report.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items()if k in ('result','candidate_gbl','candidate_application','second_PROGRAM')},indent=2))
    if a.negative_controls:print('negative controls rejected:',len(result['negative_controls']))

if __name__=='__main__':
    main()
