#!/usr/bin/env python3
"""Construct only stock2.2.4 + qualified C-C rebased + official WF2003.18.

No network, assembler, Ghidra, prior behavioral-base imports or device access.
Exact immutable inputs/manifests; existing outputs refused. No A1/MIN80/D3.
"""
from pathlib import Path
import ast
import hashlib
import json
import struct
import zlib

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / 'build_cc_wf200_318_2026-10-19'
NAME = 'SHTRV-01_2.2.4_C-C_WF200_3.18.0_EXPERIMENTAL'
PROGRAM, END = 0xFD0303FD, 0xFC0404FC
OLD_HELPER, NEW_HELPER, HELPER_SIZE = 0x1003D0, 0x1007D8, 276
FINAL_END = 0x1008EC
PINS = {
 'original/2.2.4/SHTRV-01_build_2.2.4.gbl': (1106384,'5c4a0b222a313350952f6b1200a855833402f168bd286090c23bd4d018ab918f'),
 'extracted/program_1_0x00000000.bin': (1049548,'4dc770fe535008ef150f3a144354169199e1a0e235173abcc3f7387b95ee9b5c'),
 'extracted/program_2_0x00130A98.bin': (30872,'662bd549f050ab81a120d3daa07646652c38880b9d2bfa988ff6bee7f731e33e'),
 'original/WF200/wfx-firmware/wfm_wf200_C0.sec': (312400,'886d009b3852cb41f7c67c85de5c9bf2e6d67614e10d668b4fa1e18734078cb9'),
}
EVIDENCE_PINS = {
 'tools/scripts/patcher/patch_cc_2.2.4/build_patch_cc_gbl.py': '6ac460d3ab633f5284db790dfdaa88bc4ff53db50e28a7c7d663002b3525fe34',
 'docs/local/rea_report/patch-c-design-2026-10-14.md': 'ed800b890fc8bd1de5893540adc9a0ada53d8b7a9fb5a95d0da9250a7a598d7d',
 'docs/local/rea_report/patch-c-prebuild-qualification-2026-10-14.md': '523ab60f079e2d3d9543a8481334034f8f025caa2c599668fd22bdcb06b6e18c',
 'build_wf200_318_relocation_qualification_2026-10-18/relocation-manifest.json': 'fa76bb67067153523b1fb71e18d5667b7fad43634174024b982cdb12c1dc9bba',
}
SOURCE_HASH = '18811686eadef8707f7977a48db8fd78a1891ee65cbf15d67432910e2ac63475'
DEST_HASH = 'a94ece8f7c3203ca638eab513cde4d47f922b2b1819006041387abb5c7bb4564'

def need(ok, why):
    if not ok:
        raise ValueError(why + '; STOP')

def sha(data):
    return hashlib.sha256(data).hexdigest()

def u32(data, address):
    return struct.unpack_from('<I', data, address)[0]

def parse(data):
    entries = []
    pos = 0
    while pos < len(data):
        need(pos + 8 <= len(data), 'Truncated GBL header')
        tag, size = struct.unpack_from('<II', data, pos)
        end = pos + 8 + size
        need(end <= len(data), 'Truncated GBL body')
        need(tag != PROGRAM or size >= 4, 'Short PROGRAM')
        need(tag != END or (size == 4 and end == len(data)), 'END must be last')
        entries.append((pos, tag, data[pos+8:end], data[pos:end]))
        pos = end
    need(len(entries) == 6 and entries[-1][1] == END, 'GBL six-record structure')
    need(zlib.crc32(data[:-4]) == u32(data,len(data)-4), 'GBL CRC')
    need(zlib.crc32(data) == 0x2144DF1C, 'GBL residue')
    return entries

def decode_bl(site, data):
    if len(data) < 4:
        return None
    a,b = struct.unpack_from('<HH', data)
    if a & 0xF800 != 0xF000 or b & 0xD000 != 0xD000:
        return None
    s = (a >> 10) & 1
    offset = (s << 24) | ((1 ^ ((b >> 13) & 1) ^ s) << 23) | ((1 ^ ((b >> 11) & 1) ^ s) << 22) | ((a & 0x3FF) << 12) | ((b & 0x7FF) << 1)
    if s:
        offset -= 1 << 25
    return site + 4 + offset

def encode_bl(site, target):
    delta = target - (site + 4)
    need(site % 2 == target % 2 == 0 and -(1<<24) <= delta < (1<<24), 'BL reach/alignment')
    bits = delta & 0x1FFFFFF
    sign = (bits >> 24) & 1
    j1 = 1 ^ ((bits >> 23) & 1) ^ sign
    j2 = 1 ^ ((bits >> 22) & 1) ^ sign
    value = struct.pack('<HH', 0xF000 | sign << 10 | (bits >> 12 & 0x3FF), 0xD000 | j1 << 13 | j2 << 11 | (bits >> 1 & 0x7FF))
    need(decode_bl(site,value) == target, 'BL encode roundtrip')
    return value

def load_evidence():
    data = {}
    for path, expected in EVIDENCE_PINS.items():
        raw = (ROOT/path).read_bytes()
        need(sha(raw) == expected, 'Evidence identity: ' + path)
        data[path] = raw
    tree = ast.parse(data[next(iter(EVIDENCE_PINS))].decode())
    literals = {}
    for node in tree.body:
        if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name) and node.targets[0].id in ('SITES','HELPERS'):
            literals[node.targets[0].id] = ast.literal_eval(node.value)
    sites, helpers = literals['SITES'], literals['HELPERS']
    need(len(sites)==15 and len(helpers)==10, 'C-C manifest counts')
    # Reuse only immutable literal manifests, never execute the old builder.
    design = data['docs/local/rea_report/patch-c-design-2026-10-14.md'].decode()
    qualification = data['docs/local/rea_report/patch-c-prebuild-qualification-2026-10-14.md'].decode()
    for site, old, new in sites:
        need(any(hex(site) in line and old in line and new in line for line in design.splitlines()), 'C-C design hook mismatch')
        need(any(hex(site) in line and old in line and new in line for line in qualification.splitlines()), 'C-C qualified hook mismatch')
    for address, size, raw in helpers:
        need(raw in design and raw in qualification and len(bytes.fromhex(raw))==size,'C-C helper report mismatch')
    m = json.loads(data['build_wf200_318_relocation_qualification_2026-10-18/relocation-manifest.json'])
    need(m['qualification']=='QUALIFIED FOR CONSTRUCTION','Relocation qualification')
    need((len(m['external_fixups']),len(m['internal_fixups']),len(m['excluded_original_candidates']))==(51,3,6),'Relocation counts')
    r=m['relocation']
    need(tuple(int(r[k],16) for k in ('source_start','source_end','destination_start','destination_end','delta'))==(0xF9A70,0xF9E78,OLD_HELPER,NEW_HELPER,0x6960),'Relocation geometry')
    return sites,helpers,m

def build(inputs, sites, helpers, relocation):
    need(set(inputs)==set(PINS),'Input set')
    for path, (size, digest) in PINS.items():
        need(len(inputs[path])==size and sha(inputs[path])==digest,'Immutable input: '+path)
    stock_gbl=inputs['original/2.2.4/SHTRV-01_build_2.2.4.gbl']
    stock=inputs['extracted/program_1_0x00000000.bin']
    second=inputs['extracted/program_2_0x00130A98.bin']
    sec=inputs['original/WF200/wfx-firmware/wfm_wf200_C0.sec']
    records=parse(stock_gbl)
    need([(a,t,len(p)) for a,t,p,r in records]==[(0,0x03A617EB,8),(0x10,0xF40A0AF4,0x1C),(0x34,0xF50909F5,0x650C),(0x6548,PROGRAM,0x1003D0),(0x106920,PROGRAM,0x789C),(0x10E1C4,END,4)],'Stock layout')
    need(records[3][2]==bytes(4)+stock and records[4][2]==struct.pack('<I',0x130A98)+second,'Stock extraction equality')
    captured=stock[0xF9A70:0xF9E78]
    need(sha(captured)==SOURCE_HASH,'Captured source identity')
    # Validate all preimages before modifications, and enforce disjoint writes.
    edits=[]
    for row in relocation['external_fixups']:
        at=int(row['source'],16)
        need(row['classification']=='PROVEN REQUIRED FIXUP' and int(row['future_site'],16)==at,'External fixup qualification/site')
        need(stock[at:at+4]==bytes.fromhex(row['old_word_le']),'External preimage')
        need(int(row['new_target'],16)==int(row['target'],16)+0x6960,'External target arithmetic')
        edits.append((at,bytes.fromhex(row['new_word_le']),'WF200 relocation fixup'))
    hook_rows=[];bl_count=0
    helper_entries={a for a,n,raw in helpers}
    for site, old, qualified in sites:
        old,new=bytes.fromhex(old),bytes.fromhex(qualified)
        need(stock[site:site+len(old)]==old,'C-C stock preimage at '+hex(site))
        target=decode_bl(site,new)
        replacement=new
        if target is not None:
            need(target in helper_entries,'Old C-C BL target is not helper entry')
            need(encode_bl(site,target)==new[:4],'Original qualified BL encoding')
            replacement=encode_bl(site,target+0x408)+new[4:]
            bl_count+=1
        edits.append((site,replacement,'C-C hook'))
        hook_rows.append({'address':hex(site),'stock_preimage':old.hex(),'qualified_CC_bytes':new.hex(),'combined_bytes':replacement.hex(),'old_target':None if target is None else hex(target),'new_target':None if target is None else hex(target+0x408),'LR_return_boundary':None if target is None else hex(site+4),'range_continuation':hex(site+len(old))})
    need(bl_count==11,'Exactly11 C-C BL hooks')
    need(stock[0x578AC:0x578B0]==bytes.fromhex('50c00400'),'Loader length preimage')
    edits.append((0x578AC,bytes.fromhex('50c40400'),'loader/base/length adjustment'))
    seen=set()
    for at,raw,kind in edits:
        span=set(range(at,at+len(raw)))
        need(not seen.intersection(span) and at+len(raw)<=0xADA20,'Overlapping/extraneous edit')
        seen.update(span)
    app=bytearray(stock)+bytearray(b'\xff'*(FINAL_END-len(stock)))
    app[OLD_HELPER:NEW_HELPER]=captured
    for row in relocation['internal_fixups']:
        source,site,target,newtarget=(int(row[k],16) for k in ('source','future_site','target','new_target'))
        need(row['classification']=='PROVEN REQUIRED FIXUP' and site==source+0x6960 and newtarget==target+0x6960,'Internal arithmetic')
        need(stock[source:source+4]==bytes.fromhex(row['old_word_le']) and app[site:site+4]==bytes.fromhex(row['old_word_le']),'Internal preimage')
        need(bytes.fromhex(row['new_word_le'])==struct.pack('<I',newtarget),'Internal encoded target')
        app[site:site+4]=bytes.fromhex(row['new_word_le'])
    need(sha(app[OLD_HELPER:NEW_HELPER])==DEST_HASH,'Qualified relocation destination')
    cursor=OLD_HELPER;all_helpers=bytearray()
    for address,size,raw in helpers:
        code=bytes.fromhex(raw)
        need(address==cursor and size==len(code) and (address+0x408)%4==address%4,'Helper continuity/alignment')
        cursor+=size;all_helpers.extend(code)
    need(cursor==0x1004E4 and len(all_helpers)==HELPER_SIZE and NEW_HELPER+len(all_helpers)==FINAL_END,'Helper range')
    app[NEW_HELPER:FINAL_END]=all_helpers
    for at,raw,kind in edits:
        app[at:at+len(raw)]=raw
    app[0xADA20:0xF9E70]=sec
    need(app[0xF9E70:0xF9E78]==stock[0xF9E70:0xF9E78],'Stale source suffix')
    for row in relocation['excluded_original_candidates']:
        at=int(row['source'],16)
        need(app[at:at+4]==stock[at:at+4]==bytes.fromhex(row['old_word_le']),'Excluded fixup changed')
    for at,value in relocation['unchanged_startup_literals'].items():
        need(u32(app,int(at,16))==u32(stock,int(at,16))==int(value,16),'Startup literal changed')
    need(app[0xFF118:0x1003CC]==stock[0xFF118:0x1003CC],'Initializer changed')
    need(app[:4]==stock[:4] and app[0x254:0x258]==stock[0x254:0x258],'MSP reservation changed')
    need(u32(app,0x5788C)==0xADA20 and len(app)==FINAL_END and app[0xADA20:0xF9E70]==sec,'Radio/extent identity')
    # Exact expected prefix: all authorized short edits plus exact SEC only.
    allowed={i for at,raw,kind in edits for i in range(at,at+len(raw))}
    need(not any(a!=b and i not in allowed and not 0xADA20<=i<0xF9E70 for i,(a,b) in enumerate(zip(stock,app))),'Unauthorized application change')
    packed=bytearray()
    for i,(pos,tag,body,record) in enumerate(records):
        if i==3:
            body=bytes(4)+app;packed+=struct.pack('<II',PROGRAM,len(body))+body
        elif i==5:
            packed+=struct.pack('<II',END,4);packed+=struct.pack('<I',zlib.crc32(packed))
        else:packed+=record
    output=bytes(packed);reparsed=parse(output)
    need(reparsed[3][2][4:]==app and len(output)==1107696,'Candidate geometry')
    need(all(reparsed[i][3]==records[i][3] for i in (0,1,2,4)),'Unrelated GBL record changed')
    manifest={'variant':NAME,'qualification':'PENDING INDEPENDENT VERIFICATION','construction_base':'Exact immutable stock; prior GBLs not used as opaque base','immutable_inputs':{k:{'bytes':len(v),'sha256':sha(v)} for k,v in inputs.items()},'evidence_pins':EVIDENCE_PINS,'layout':{'SEC':[hex(0xADA20),hex(0xF9E70)],'host_relocation':[hex(OLD_HELPER),hex(NEW_HELPER)],'rebased_CC':[hex(NEW_HELPER),hex(FINAL_END)],'CC_delta':'0x408','second_PROGRAM_load_address':'0x130A98'},'CC_hooks':hook_rows,'CC_helpers':[{'old_address':hex(a),'new_address':hex(a+0x408),'bytes':n,'sha256':sha(bytes.fromhex(raw))} for a,n,raw in helpers],'relocation_manifest_sha256':EVIDENCE_PINS['build_wf200_318_relocation_qualification_2026-10-18/relocation-manifest.json'],'relocation_counts':{'external':51,'internal':3,'excluded':6},'relocated_block_sha256':sha(app[OLD_HELPER:NEW_HELPER]),'SEC_sha256':sha(sec),'outputs':{NAME+'.bin':{'bytes':len(app),'sha256':sha(app)},NAME+'.gbl':{'bytes':len(output),'sha256':sha(output)}},'GBL_crc32':f'{u32(output,len(output)-4):08X}','whole_container_residue':f'{zlib.crc32(output):08X}','GBL_records':[{'file_offset':hex(a),'tag':hex(t),'body_bytes':len(p),'load_address':hex(u32(p,0)) if t==PROGRAM else None} for a,t,p,r in reparsed],'only_changes':['qualified C-C exact helper bytes +11rebased BL encodings +4unchanged C-C non-BL hooks','qualified WF200 SEC/host-data relocation and length','required PROGRAM length/END CRC'],'excluded':['A1','MIN80','D3 observer','mDNS','new diagnostics','new RAM/startup reservation'],'device_contact':False}
    # Complete disjoint range recipe; no protected-image bytes redistributed.
    authorized=[{'start':hex(at),'end_exclusive':hex(at+len(raw)),'class':kind,
                 'stock_preimage_sha256':sha(stock[at:at+len(raw)]),
                 'candidate_sha256':sha(raw)} for at,raw,kind in edits]
    for a,b,kind in [(0xADA20,0xF9E70,'WF200 SEC replacement'),
                     (0x1003CC,0x1003D0,'WF200 host-object relocation'),
                     (OLD_HELPER,NEW_HELPER,'WF200 host-object relocation'),
                     (NEW_HELPER,FINAL_END,'C-C rebased helper')]:
        authorized.append({'start':hex(a),'end_exclusive':hex(b),'class':kind,
                           'stock_preimage_sha256':sha(stock[a:min(b,len(stock))]) if a<len(stock) else None,
                           'candidate_sha256':sha(app[a:b])})
    authorized.sort(key=lambda x:int(x['start'],16))
    need(all(int(a['end_exclusive'],16)<=int(b['start'],16) for a,b in zip(authorized,authorized[1:])), 'Authorized range overlap')
    changes=[];current=None
    for i in range(len(app)):
        different=i>=len(stock) or app[i]!=stock[i]
        kind=next((r['class'] for r in authorized if int(r['start'],16)<=i<int(r['end_exclusive'],16)),None) if different else None
        need(not different or kind is not None,'Unclassified changed byte')
        key=(kind,i>=len(stock)) if different else None
        if current is not None and (key!=current[2] or not different):
            a,b,k=current
            changes.append({'start':hex(a),'end_exclusive':hex(b),'bytes':b-a,'class':k[0],'appended':k[1],
                            'old_sha256':None if k[1] else sha(stock[a:b]),'new_sha256':sha(app[a:b])})
            current=None
        if different:
            current=(i,i+1,key) if current is None else (current[0],i+1,key)
    if current:
        a,b,k=current
        changes.append({'start':hex(a),'end_exclusive':hex(b),'bytes':b-a,'class':k[0],'appended':k[1],
                        'old_sha256':None if k[1] else sha(stock[a:b]),'new_sha256':sha(app[a:b])})
    manifest['authorized_application_ranges']=authorized
    manifest['every_changed_application_run']=changes
    manifest['changed_bytes_by_class']={k:sum(r['bytes'] for r in changes if r['class']==k) for k in sorted({r['class'] for r in changes})}
    manifest['unexplained_changed_bytes']=0
    manifest['applied_external_fixups']=relocation['external_fixups']
    manifest['applied_internal_fixups']=relocation['internal_fixups']
    return bytes(app),output,manifest

def main():
    destinations=[OUT/(NAME+'.bin'),OUT/(NAME+'.gbl'),OUT/'MANIFEST.json']
    need(not any(p.exists() for p in destinations),'Output already exists')
    sites,helpers,relocation=load_evidence()
    inputs={p:(ROOT/p).read_bytes() for p in PINS}
    app,gbl,manifest=build(inputs,sites,helpers,relocation)
    # Repeat entirely from immutable input to test deterministic construction.
    app2,gbl2,manifest2=build(inputs,sites,helpers,relocation)
    need((app,gbl,manifest)==(app2,gbl2,manifest2),'Nondeterministic construction')
    OUT.mkdir(parents=True,exist_ok=True)
    for p,data in zip(destinations,[app,gbl,(json.dumps(manifest,indent=2)+'\n').encode()]):
        with p.open('xb') as stream:stream.write(data)
    for p,data in inputs.items():need((ROOT/p).read_bytes()==data,'Input changed during build')
    print(json.dumps({'constructed':NAME,'application_sha256':sha(app),'GBL_sha256':sha(gbl),'GBL_bytes':len(gbl),'GBL_crc32':manifest['GBL_crc32'],'deterministic':True,'qualification':'PENDING INDEPENDENT VERIFICATION','device_contact':False},indent=2))

if __name__=='__main__':
    try:
        main()
    except (ValueError,OSError,KeyError,IndexError) as error:
        raise SystemExit('ABORT: '+str(error))
