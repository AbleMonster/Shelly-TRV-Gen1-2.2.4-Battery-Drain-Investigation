from pathlib import Path
import argparse,os,subprocess,tempfile,shutil,sys,struct,json
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3]
sys.path.insert(0,str(ROOT/'builds/build_pmd210_static_2026-10-17'));from elf_tools import elf
p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);a=p.parse_args();b=a.build.resolve()
raw=(b/'observer.o').read_bytes();v=bytearray(raw);struct.pack_into('<H',v,16,2);view=b/'target-view.elf';view.write_bytes(v);assert elf(view)[0]==elf(b/'observer.o')[0]
with tempfile.TemporaryDirectory(prefix='otime-target-',dir='/private/tmp') as d:
 td=Path(d);shutil.copyfile(view,td/'target.elf')
 env=dict(os.environ,JAVA_HOME='/Library/Java/JavaVirtualMachines/temurin-21.jdk/Contents/Home',JAVA_TOOL_OPTIONS=f'-Duser.home={td} -Dapplication.settingsdir={td}/settings -Dapplication.cachedir={td}/cache')
 app=b/'working.bin'
 cmd=['/Users/fam.klein/Desktop/ghidra_12.1.4_PUBLIC/support/analyzeHeadless',str(td),'PMHistory','-import',str(td/'target.elf'),'-processor','ARM:LE:32:Cortex','-readOnly','-noanalysis','-scriptPath',str(HERE),'-postScript','PMHistoryExecute.java',str(b/'symbols.json'),str(ROOT/'builds/build_a1r_all_known_2026-10-28/final/SHTRV-01_2.2.4_A1R_C-C_B2_MQTT_WF200_3.18.0_EXPERIMENTAL.bin'),str(app),str(b/'target-results.json')]
 r=subprocess.run(cmd,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT);(b/'target.log').write_text(r.stdout)
 if r.returncode or not (b/'target-results.json').exists():raise RuntimeError(r.stdout[-7000:])
 j=json.loads((b/'target-results.json').read_text());print({k:v for k,v in j.items() if k not in ('cases','snapshots')});assert j['status']=='PASS' and j['passed']==356
