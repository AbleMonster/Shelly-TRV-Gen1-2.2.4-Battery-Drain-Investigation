#!/usr/bin/env python3
"""Read-only final container qualification. No builder/recipe import."""
from pathlib import Path
import json,hashlib,struct,zlib,runpy
ROOT=Path(__file__).resolve().parents[4];P=ROOT/'build_a1_cc_wf200_318_final_2026-10-20'
N='SHTRV-01_2.2.4_A1_C-C_WF200_3.18.0_EXPERIMENTAL'
H=lambda b:hashlib.sha256(b).hexdigest()
baseline=(ROOT/'build_cc_wf200_318_2026-10-19/SHTRV-01_2.2.4_C-C_WF200_3.18.0_EXPERIMENTAL.gbl').read_bytes()
assert H(baseline)=='7243fd580c817797d552e2ee8518ae5dfc3eef9cab6b729e9289e6f727a4a99b'
gbl=(P/(N+'.gbl')).read_bytes();appfile=(P/(N+'.bin')).read_bytes()
V=runpy.run_path(str(Path(__file__).with_name('verify_production.py')))
proof=V['verify_gbl'](gbl)
# Independently enumerate record file/load geometry from the produced file.
records=[];pos=0
while pos<len(gbl):
 tag,size=struct.unpack_from('<II',gbl,pos);end=pos+8+size;assert end<=len(gbl)
 body=gbl[pos+8:end];record={'file_offset':hex(pos),'tag':hex(tag),'payload_bytes':size}
 if tag==0xfd0303fd:
  addr=struct.unpack_from('<I',body)[0];record.update(load=hex(addr),program_bytes=size-4,end=hex(addr+size-4))
  if addr==0:app=body[4:]
 records.append(record);pos=end
assert app==appfile and H(app)=='0bb530cfda66b4c45ada8d864d623ff4f952405a4da0f8f00f368a9f6116030d'
assert H(gbl)=='d91adb9138a528c090210f9a1776565fcfb55b17b2af7d8d46c83d8d1204e379'
sec=app[0xada20:0xf9e70];official=(ROOT/'original/WF200/wfx-firmware/wfm_wf200_C0.sec').read_bytes();assert sec==official
assert struct.unpack_from('<I',app,0)[0]==struct.unpack_from('<I',app,0x254)[0]==0x2007ff80
assert app[0x100900:0x1019de]==(ROOT/'build_a1_executable_core_2026-10-20/core.text').read_bytes()
# Parse/CRC failure and protected mutation rejection against final container.
neg=[]
for name,at in [('terminal CRC',len(gbl)-1),('PROGRAM payload',0x6548+12+0x500),('SEC byte',0x6548+12+0xada20)]:
 b=bytearray(gbl);b[at]^=1
 if name!='terminal CRC':b[-4:]=struct.pack('<I',zlib.crc32(b[:-4])&0xffffffff)
 try:V['verify_gbl'](b)
 except AssertionError:neg.append({'name':name,'repaired_CRC':name!='terminal CRC','rejected':True})
 else:raise AssertionError(name)
result={'result':'PASS','authority':'independent parser/raw-object/hook reconstruction from immutable baseline and produced GBL; builder recipe not used','GBL':{'filename':N+'.gbl','bytes':len(gbl),'sha256':H(gbl),'stored_END_CRC32':f'{struct.unpack_from("<I",gbl,len(gbl)-4)[0]:08X}','calculated_END_CRC32':f'{zlib.crc32(gbl[:-4])&0xffffffff:08X}','whole_file_CRC32_residue':f'{zlib.crc32(gbl)&0xffffffff:08X}'},'application':{'bytes':len(app),'sha256':H(app),'CRC32':f'{zlib.crc32(app)&0xffffffff:08X}','extraction_equal':True,'unexplained_changed_bytes':0},'SEC':{'bytes':len(sec),'sha256':H(sec),'byte_equal_official':True},'records':records,'radio_fixups':proof['application']['radio_fixups'],'hook_count':proof['application']['hook_count'],'negative_controls':neg,'device_contact':False}
(P/'final-independent-verification.json').write_text(json.dumps(result,indent=2)+'\n')
print('FINAL INDEPENDENT GBL PASS',len(gbl),H(gbl))
