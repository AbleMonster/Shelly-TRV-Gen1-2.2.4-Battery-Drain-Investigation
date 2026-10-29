#!/usr/bin/env python3
"""Current versioned A1R entry; historical build_production remains reproducible.
Constructs an application only. GBL release is owned by the final All-Known gate.
"""
from pathlib import Path
import argparse,importlib.util,json
ROOT=Path(__file__).resolve().parents[4]
def module(p,n):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def construct(stock,out):
 b=module(ROOT/'tools/scripts/patcher/all_known_fixes_2.2.4/build.py','a1r_stock_reconstruction')
 base=(b.A/'SHTRV-01_2.2.4_A1_C-C_WF200_3.18.0_EXPERIMENTAL.bin').read_bytes()
 g=(b.A/'SHTRV-01_2.2.4_A1_C-C_WF200_3.18.0_EXPERIMENTAL.gbl').read_bytes()
 sec=(ROOT/'original/WF200/wfx-firmware/wfm_wf200_C0.sec').read_bytes()
 raw=Path(stock).read_bytes();b.validate(raw,base,g,sec);out=Path(out);out.mkdir(parents=True,exist_ok=True)
 parent=b.reconstruct_qualified_baseline(raw,base,out)
 rule=module(Path(__file__).parent/'restore_policy.py','a1r_source_rule')
 app,m=rule.apply(parent,out,'A1');(out/'A1R-working.bin').write_bytes(app)
 return app,m
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('stock',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args();_,m=construct(a.stock,a.out);print(json.dumps(m,indent=2))
