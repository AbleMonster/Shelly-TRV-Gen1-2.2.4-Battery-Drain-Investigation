#!/usr/bin/env python3
"""Link isolated adapter assets only. Never reads/writes an application or GBL."""
from pathlib import Path
import struct,json,re,hashlib,subprocess,argparse
def sha(b):return hashlib.sha256(b).hexdigest()

def parse(p):
 b=p.read_bytes(); assert b[:7]==b'\x7fELF\x01\x01\x01'
 so=struct.unpack_from('<I',b,32)[0]; es,ns,si=struct.unpack_from('<HHH',b,46)
 hs=[struct.unpack_from('<10I',b,so+i*es) for i in range(ns)]
 st=b[hs[si][4]:hs[si][4]+hs[si][5]]
 def name(h):return st[h[0]:].split(b'\0',1)[0].decode()
 ti=next(i for i,h in enumerate(hs) if name(h)=='.text');h=hs[ti];text=b[h[4]:h[4]+h[5]]
 sh=next(h for h in hs if h[1]==2); strings=b[hs[sh[6]][4]:hs[sh[6]][4]+hs[sh[6]][5]]
 sy=[]
 for off in range(sh[4],sh[4]+sh[5],sh[9]):
  n,v,z,info,other,sect=struct.unpack_from('<IIIBBH',b,off);sy.append((strings[n:].split(b'\0',1)[0].decode(),v,z,info,sect))
 rel=[]
 for h in hs:
  if h[1]==9 and h[7]==ti:
   for off in range(h[4],h[4]+h[5],h[9]):
    ro,ri=struct.unpack_from('<II',b,off);rel.append((ro,ri&255,ri>>8))
 return {'path':str(p),'hash':sha(b),'text':text,'ti':ti,'sy':sy,'rel':rel}

def branch(a,t,jump=False):
 d=t-a-4; assert not d&1 and -(1<<24)<=d<(1<<24)
 v=d&0x1ffffff;s=v>>24;j1=1^((v>>23)&1)^s;j2=1^((v>>22)&1)^s
 return struct.pack('<HH',0xf000|(s<<10)|((v>>12)&1023),(0x9000 if jump else 0xd000)|(j1<<13)|(j2<<11)|((v>>1)&2047))

def main():
 root=Path(__file__).resolve().parents[4]
 out=root/'build_a1_cc_wf200_318_final_2026-10-20'/'linked-assets';out.mkdir(exist_ok=True)
 q=out.parent
 names=['settlement-source/bindings.o','settlement-source/public-wrappers.o','owner-component/owner.o','owner-component/owner-wrappers.o','g18-component/lower.o','g18-component/upper.o','g18-component/worker.o','g18-component/worker-hooks.o','pm-component/pm.o','pm-component/hooks.o','transport-component/transport.o','transport-component/transport-wrappers.o','runtime-component/runtime.o','runtime-component/bind.o','runtime-component/memory.o','shared-rmw/shared-rmw.o']
 objs=[parse(q/n) for n in names];base=0x101a00;data=bytearray();symbols={};funcs=[]
 for o in objs:
  while len(data)%4:data.append(0xff)
  o['off']=len(data);data.extend(o['text'])
  for nm,v,z,info,sect in o['sy']:
   if sect==o['ti'] and nm and not nm.startswith('$') and (info>>4):
    if nm in symbols:raise ValueError(('duplicate global',nm))
    symbols[nm]=base+o['off']+v
    if (info&15)==2:funcs.append({'name':nm,'address':hex((base+o['off']+v)&~1),'bytes':z,'object':o['path']})
 aliases={n:int(a,16) for n,a in re.findall(r'PROVIDE\((\w+) = (0x[0-9A-Fa-f]+)\)',(q/'settlement-source/native-aliases.ld').read_text())}
 aliases.update(__aeabi_memcpy=0x7d801,__aeabi_memcpy4=0x7d801)
 relocs=[]
 for o in objs:
  for off,kind,idx in o['rel']:
   nm,v,z,info,sect=o['sy'][idx]
   dest=(base+o['off']+v) if sect==o['ti'] else symbols.get(nm,aliases.get(nm))
   if dest is None:raise ValueError(('unresolved',nm,o['path']))
   loc=o['off']+off;old=bytes(data[loc:loc+4])
   if kind in (10,30):
    a,b=struct.unpack('<HH',old);s=(a>>10)&1;add=(s<<24)|((1^((b>>13)&1)^s)<<23)|((1^((b>>11)&1)^s)<<22)|((a&1023)<<12)|((b&2047)<<1)
    if s:add-=1<<25
    if add!=-4:raise ValueError(('unexpected branch addend',nm,add))
    new=branch(base+loc,dest&~1,kind==30)
   elif kind==2:
    add=struct.unpack('<I',old)[0];new=struct.pack('<I',(dest+add)&0xffffffff)
   else:raise ValueError(('unsupported relocation',kind,nm))
   data[loc:loc+4]=new;relocs.append({'site':hex(base+loc),'type':kind,'target':hex(dest),'symbol':nm,'old':old.hex(),'new':new.hex(),'object':o['path']})
 manifest={'kind':'ISOLATED LINKED ASSETS; NOT APPLICATION','base':hex(base),'end':hex(base+len(data)),'bytes':len(data),'sha256':sha(data),'objects':[{'path':o['path'],'sha256':o['hash'],'base':hex(base+o['off']),'text_bytes':len(o['text'])} for o in objs],'symbols':{n:hex(a) for n,a in symbols.items()},'functions':funcs,'relocations':relocs,'native_aliases':{n:hex(a) for n,a in aliases.items()}}
 (out/'adapter-assets.text').write_bytes(data);(out/'asset-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
 print('ISOLATED ASSETS',len(data),'bytes',len(relocs),'relocations',hex(base+len(data)))
if __name__=='__main__':main()
