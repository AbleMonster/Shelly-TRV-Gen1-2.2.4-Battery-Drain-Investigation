#!/usr/bin/env python3
"""Independent final container parser. No firmware-builder imports."""
from pathlib import Path
import argparse,struct,zlib,hashlib,importlib.util,json
ROOT=Path(__file__).resolve().parents[4];Q=ROOT/'builds/build_b21_obs_2026-10-28'
H=lambda b:hashlib.sha256(b).hexdigest()
def need(x,s):
 if not x:raise ValueError(s)
def parse(g):
 p=0;r=[]
 while p<len(g):
  need(p+8<=len(g),'truncated header');t,n=struct.unpack_from('<II',g,p);need(n<=len(g)-p-8,'truncated record');r.append((t,g[p+8:p+8+n],p));p+=8+n
 need([t for t,_,_ in r]==[0x03a617eb,0xf40a0af4,0xf50909f5,0xfd0303fd,0xfd0303fd,0xfc0404fc],'record order')
 need(len(r[-1][1])==4,'END extent');need(struct.unpack('<I',r[-1][1])[0]==zlib.crc32(g[:-4]),'END CRC');need(zlib.crc32(g)==0x2144df1c,'whole CRC residue');return r

def verify(g,app):
 base=(ROOT/'builds/build_a1r_all_known_2026-10-28/final/SHTRV-01_2.2.4_A1R_C-C_B2_MQTT_WF200_3.18.0_EXPERIMENTAL.gbl').read_bytes()
 need(H(base)=='5f81869922c9b2eed4eb2f730ed53f5a66cf8b09d5f7d12205a4f6fbcd7392d9','old GBL identity');br=parse(base);r=parse(g)
 for i in [0,1,2,4]:need(r[i][:2]==br[i][:2],'metadata/bootloader/secondPROGRAM modified')
 need(r[3][1]==bytes(4)+app,'application extraction mismatch');need(len(app)<0x130a98,'PROGRAM overlap')
 need(struct.unpack_from('<I',r[4][1])[0]==0x130a98 and len(r[4][1])-4==0x7898,'second PROGRAM geometry')
 sp=importlib.util.spec_from_file_location('independent_final_a1r',Path(__file__).parent/'independent_verify.py');v=importlib.util.module_from_spec(sp);sp.loader.exec_module(v);v.verify(r[3][1][4:])
 sec=app[0xada20:0xf9e70];need(H(sec)=='886d009b3852cb41f7c67c85de5c9bf2e6d67614e10d668b4fa1e18734078cb9','official SEC extraction')
 return dict(status='PASS',GBL_size=len(g),GBL_sha256=H(g),application_size=len(app),application_sha256=H(app),application_CRC32=f'{zlib.crc32(app):08X}',stored_GBL_CRC32=f'{struct.unpack("<I",r[-1][1])[0]:08X}',calculated_GBL_CRC32=f'{zlib.crc32(g[:-4]):08X}',whole_file_CRC32=f'{zlib.crc32(g):08X}',WF200_SEC_sha256=H(sec),PROGRAM1=[0,len(app)],PROGRAM2=[0x130a98,0x138330],APPINFO_bootloader_OTHER_RECORDS='exact qualified old container',records=[{'tag':hex(t),'body_bytes':len(b),'file_offset':hex(p)}for t,b,p in r])

def controls(g,app):
 rows=[];rs=parse(g)
 def reject(name,c):
  try:verify(bytes(c),app)
  except (ValueError,struct.error):rows.append(dict(name=name,rejected=True));return
  raise AssertionError('malformed accepted '+name)
 reject('truncation',g[:-1]);reject('trailing',g+b'X');c=bytearray(g);c[-1]^=1;reject('stored CRC',c)
 for name,idx,off in [('HEADER',0,0),('APPINFO',1,0),('BOOTLOADER',2,4),('PROGRAM load',3,0),('host application',3,4+0x40000),('official SEC',3,4+0xada20),('SECOND PROGRAM',4,4),('A1R hook',3,4+0x103878),('A1R classifier',3,4+0x1046dc),('observer event',3,4+0x104718),('research ID',3,4+0x1050b0)]:
  c=bytearray(g);c[rs[idx][2]+8+off]^=1;c[-4:]=struct.pack('<I',zlib.crc32(c[:-4]));reject('repairedCRC '+name,c)
 return rows
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('application',type=Path);p.add_argument('gbl',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args();app=a.application.read_bytes();g=a.gbl.read_bytes();j=verify(g,app);j['malformed_controls']=controls(g,app);a.out.write_text(json.dumps(j,indent=2,sort_keys=True)+'\n');print(json.dumps({k:v for k,v in j.items()if k not in ['records','malformed_controls']}))
