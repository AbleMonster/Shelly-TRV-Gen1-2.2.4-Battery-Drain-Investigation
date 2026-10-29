#!/usr/bin/env python3
"""B2.2 exact-construction/negative checks. Does not emit a GBL."""
import copy,hashlib,importlib.util,json,struct,zlib
from pathlib import Path
R=Path(__file__).resolve().parents[4];Q=R/'builds/build_b22_2026-10-28'
s=importlib.util.spec_from_file_location('b22builder',Path(__file__).with_name('build.py'));b=importlib.util.module_from_spec(s);s.loader.exec_module(b)
H=b.H
parent=Path(str(b.P)+'.bin').read_bytes();pg=Path(str(b.P)+'.gbl').read_bytes();stock=b.STOCK.read_bytes();sg=b.SG.read_bytes();app=(Q/'build_a/application.bin').read_bytes();app2=(Q/'build_b/application.bin').read_bytes()
helpers={q['name']:(Q/'build_a'/f'component_{i+6}/helper.bin').read_bytes()for i,q in enumerate(b.SPECS)}
b.parents(stock,parent,pg,sg);b.result(parent,app,helpers)
files=['application.bin','construction-manifest.json']+[f'component_{i}/{n}'for i in range(6,10)for n in ['helper.S','helper.o','helper.bin','disassembly.txt']]
for n in files:b.need((Q/'build_a'/n).read_bytes()==(Q/'build_b'/n).read_bytes(),'second construction mismatch '+n)
rows=[]
def reject(name,f):
 try:f()
 except (ValueError,struct.error,AssertionError):rows.append(dict(name=name,rejected=True));return
 raise ValueError('negative accepted '+name)
def mutate(d,i):return d[:i]+bytes([d[i]^1])+d[i+1:]
reject('wrong stock parent',lambda:b.parents(mutate(stock,100),parent,pg,sg))
reject('wrong stock GBL',lambda:b.parents(stock,parent,pg,mutate(sg,100)))
reject('wrong B2.1 parent',lambda:b.parents(stock,mutate(parent,100),pg,sg))
obs=(R/'builds/build_b21_obs_2026-10-28/final/SHTRV-01_2.2.4_B2.1_OBS_EXPERIMENTAL.bin').read_bytes()
reject('B2.1_OBS parent',lambda:b.parents(stock,obs,pg,sg))
reject('prepatched parent',lambda:b.parents(stock,app,pg,sg))
reject('occupied helper region',lambda:b.parents(stock,parent+b'X'*100,pg,sg))
for q in b.SPECS:
 src=(R/q['source']).read_bytes()
 reject('corrupt helper source '+q['name'],lambda q=q,src=src:b.need(H(mutate(src,0))==q['source_sha'],'source'))
 for a,old,new,t,link in q['hooks']:
  for i in range(len(bytes.fromhex(old))):reject(f'corrupt patch site {a+i:x}',lambda a=a,i=i:b.parents(stock,mutate(parent,a+i),pg,sg))
 for i in range(len(helpers[q['name']])):
  h=dict(helpers);h[q['name']]=mutate(h[q['name']],i);reject(f'corrupt helper {q["name"]} {i}',lambda h=h:b.result(parent,app,h))
for name,key,val in [('helper overlap','start',0x104740),('wrong helper geometry','end',0x10510a),('wrong helper hash','helper_sha','0'*64)]:
 specs=copy.deepcopy(b.SPECS);specs[0][key]=val;reject(name,lambda specs=specs:b.layout(specs))
for name,t in [('wrong branch target',0x104742),('branch range violation',0x2104740)]:
 specs=copy.deepcopy(b.SPECS);h=list(specs[2]['hooks'][0]);h[3]=t;specs[2]['hooks'][0]=tuple(h);reject(name,lambda specs=specs:b.layout(specs))
reject('RAM overlap',lambda:b.layout(ram=(0x2007ff00,0x20080000)))
reject('observer RAM presence',lambda:b.layout(ram=(0x2007fd80,0x20080000)))
reject('wrong SEC parent',lambda:b.parents(stock,mutate(parent,0xada20),pg,sg))
reject('corrupt SEC final',lambda:b.result(parent,mutate(app,0xada20),helpers))
reject('wrong SEC geometry',lambda:b.result(parent,app[:0xada20]+app[0xada21:],helpers))
reject('wrong PROGRAM geometry',lambda:b.result(parent,app+b'\xff',helpers))
reject('malformed GBL',lambda:b.parse(pg[:-1]))
reject('bad END CRC',lambda:b.parse(mutate(pg,len(pg)-1)))
claim=json.loads((Q/'build_a/construction-manifest.json').read_text());b.validate_claim(app,claim);wrongclaim=dict(claim);wrongclaim['application_CRC32']='00000000';reject('bad application CRC',lambda:b.validate_claim(app,wrongclaim))
reject('unexpected byte difference',lambda:b.result(parent,mutate(app,0x40000),helpers))
reject('unexpected extension padding',lambda:b.result(parent,mutate(app,0x104720),helpers))
reject('deterministic mismatch',lambda:b.need(app==mutate(app2,100),'determinism'))
# A correct outer CRC cannot disguise changed second-PROGRAM bytes.
r=b.parse(pg);c=bytearray(pg);p=0
for i,(tag,body)in enumerate(r):
 if i==4:c[p+12]^=1
 p+=8+len(body)
c[-4:]=struct.pack('<I',zlib.crc32(c[:-4]));reject('second PROGRAM mutation repaired CRC',lambda:b.parents(stock,parent,bytes(c),sg))
result=dict(status='PASS',application_SHA256=H(app),application_CRC32=f'{zlib.crc32(app):08X}',deterministic_files=files,negative_count=len(rows),negative_controls=rows,GBL='NOT CONSTRUCTED; component and interaction gates still required')
(Q/'qualification').mkdir(exist_ok=True);b.dump(Q/'qualification/construction-controls.json',result);print('PASS',len(files),'identical files',len(rows),'negative controls')
