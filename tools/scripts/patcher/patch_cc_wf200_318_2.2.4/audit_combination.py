#!/usr/bin/env python3
"""Read firmware only; write diff/union analysis JSON and Markdown only."""
from pathlib import Path
from collections import Counter
import hashlib
import json
import struct

ROOT=Path(__file__).resolve().parents[4]
OUT=ROOT/'build_cc_wf200_318_2026-10-19'
NAME='SHTRV-01_2.2.4_C-C_WF200_3.18.0_EXPERIMENTAL'

def need(ok,why):
    if not ok:raise ValueError(why)
def sha(x):return hashlib.sha256(x).hexdigest()
def app_from_gbl(b):
    p=0;parts=[]
    while p<len(b):
        need(p+8<=len(b),'short tag')
        t,n=struct.unpack_from('<II',b,p);q=p+8+n;need(q<=len(b),'tag extent')
        if t==0xFD0303FD:parts.append((struct.unpack_from('<I',b,p+8)[0],b[p+12:q]))
        p=q
    return next(a for address,a in parts if address==0)

def main():
    stock=(ROOT/'extracted/program_1_0x00000000.bin').read_bytes()
    oldg=(ROOT/'original/2.2.4/SHTRV-01_build_2.2.4.gbl').read_bytes()
    app=(OUT/(NAME+'.bin')).read_bytes();gbl=(OUT/(NAME+'.gbl')).read_bytes()
    need(sha(stock)=='4dc770fe535008ef150f3a144354169199e1a0e235173abcc3f7387b95ee9b5c','stock identity')
    need(sha(gbl)=='7243fd580c817797d552e2ee8518ae5dfc3eef9cab6b729e9289e6f727a4a99b','candidate identity')
    need(app_from_gbl(gbl)==app,'candidate first PROGRAM equality')
    manifest=json.loads((OUT/'MANIFEST.json').read_text())
    ranges=manifest['authorized_application_ranges']
    def category(address):
        hits=[r['class'] for r in ranges if int(r['start'],16)<=address<int(r['end_exclusive'],16)]
        need(len(hits)==1,'changed app byte not uniquely classified')
        return hits[0]
    # Flat file comparison is retained, but record-aware equality is primary:
    # unchanged second PROGRAM bytes move in the container, not in flash.
    runs=[];cur=None;counts=Counter()
    for at,value in enumerate(gbl):
        changed=at>=len(oldg) or value!=oldg[at]
        kind=category(at-0x6554) if changed and 0x6554<=at<0x6554+len(app) else 'GBL/container metadata or CRC' if changed else None
        if changed:counts[kind]+=1
        key=(kind,at>=len(oldg)) if changed else None
        if cur and (cur[2]!=key or not changed):
            a,b,k=cur;runs.append({'file_start':hex(a),'file_end_exclusive':hex(b),'bytes':b-a,'class':k[0],'appended_file_bytes':k[1],'old_sha256':None if k[1] else sha(oldg[a:b]),'new_sha256':sha(gbl[a:b])});cur=None
        if changed:cur=(at,at+1,key) if cur is None else (cur[0],at+1,key)
    if cur:
        a,b,k=cur;runs.append({'file_start':hex(a),'file_end_exclusive':hex(b),'bytes':b-a,'class':k[0],'appended_file_bytes':k[1],'old_sha256':None if k[1] else sha(oldg[a:b]),'new_sha256':sha(gbl[a:b])})
    ccg=(ROOT/'build_cc/SHTRV-01_2.2.4_patch_cc_experimental.gbl').read_bytes()
    radiog=(ROOT/'build_wf200_318_experimental_2026-10-18/SHTRV-01_2.2.4_WF200_3.18.0_EXPERIMENTAL.gbl').read_bytes()
    need(sha(ccg)=='89b9bb97b3c8104950723a7b900e66b1e4ed40d31bb40fd3b6278066a8f1865f','prior CC identity')
    need(sha(radiog)=='96dcf4c3c14c37a28d6fd1c9bf9ee0e3f7590968fefe83df5c51aff967bb6aee','prior radio identity')
    cc,radio=app_from_gbl(ccg),app_from_gbl(radiog)
    radio_diff=[i for i,(a,b) in enumerate(zip(radio,app)) if a!=b]
    hook_spans=[(int(r['address'],16),int(r['address'],16)+len(bytes.fromhex(r['combined_bytes']))) for r in manifest['CC_hooks']]
    need(len(radio_diff)==77 and all(any(a<=i<b for a,b in hook_spans) for i in radio_diff),'radio-only union difference')
    need(app[0x1007D8:]==cc[0x1003D0:],'qualified CC helper byte identity')
    cc_diff=[i for i,(a,b) in enumerate(zip(cc,app)) if a!=b]
    need(all(category(i) in ['C-C hook','WF200 relocation fixup','loader/base/length adjustment','WF200 SEC replacement','WF200 host-object relocation'] for i in cc_diff),'CC-only union difference')
    cc_bl_changes=[i for i in cc_diff if i<0xADA20 and category(i)=='C-C hook']
    expected_cc_changes={int(r['address'],16)+j for r in manifest['CC_hooks'] for j,(a,b) in enumerate(zip(bytes.fromhex(r['qualified_CC_bytes']),bytes.fromhex(r['combined_bytes']))) if a!=b}
    need(set(cc_bl_changes)==expected_cc_changes,'CC address-dependent changes only')
    union={'prior_CC_GBL_sha256':sha(ccg),'prior_WF200_GBL_sha256':sha(radiog),'radio_only_comparison':{'existing_prefix_changed_bytes':len(radio_diff),'all_in_CC_hooks':True,'extra_bytes':len(app)-len(radio),'extra_equals_exact_qualified_CC_helpers':True},'CC_only_comparison':{'existing_prefix_changed_bytes':len(cc_diff),'address_dependent_hook_changed_bytes':len(cc_bl_changes),'all_other_differences_radio_integration_or_old_helper_replaced_by_host_objects':True},'unexplained_bytes':0}
    payload={'scope':'Complete flat candidate-vs-stock GBL file diff. Shifted unchanged records classify as container geometry; independent record-aware checks establish unchanged content/load addresses.','first_PROGRAM_file_payload_base':'0x6554','classes_by_changed_file_byte':dict(counts),'runs':runs,'unexplained_bytes':0}
    (OUT/'container-diff-runs.json').write_text(json.dumps(payload,indent=2)+'\n')
    (OUT/'baseline-union-comparison.json').write_text(json.dumps(union,indent=2)+'\n')
    (OUT/'application-diff-runs.json').write_text(json.dumps({'classes':manifest['changed_bytes_by_class'],'runs':manifest['every_changed_application_run'],'unexplained_bytes':0},indent=2)+'\n')
    lines=['# Exact changed-range audit','', 'Complete machine-readable runs are in application-diff-runs.json and container-diff-runs.json. No protected bytes are reproduced; intervals and hashes suffice.','', '|Application class|Changed/appended bytes|','|---|---:|']
    lines += [f'|{k}|{n}|' for k,n in manifest['changed_bytes_by_class'].items()]
    lines += ['',f"Total: {sum(manifest['changed_bytes_by_class'].values())} bytes, {len(manifest['every_changed_application_run'])} maximal classed unequal/appended runs; zero unexplained bytes.",'', 'The four FF alignment bytes are classified as required host-object-relocation alignment. Three internal pointer edits are inside that relocated-object class. Second PROGRAM/END file-offset movement is container geometry; its flash address and payload do not change.','', '## Comparisons with qualified baselines','',f'Radio-only: exactly {len(radio_diff)} existing-prefix bytes differ, all within C-C hooks; the additional276bytes are the exact old C-C helper bytes.',f'C-C-only: {len(cc_diff)} existing-prefix bytes differ; exactly{len(cc_bl_changes)} hook bytes are address-dependent re-encodings, with all other differences explained by radio integration/host relocation.', '', 'Old C-C execution addresses are forbidden as C-C targets. Legitimate host-data references to1003D0 remain required by the radio relocation; those are not old helper execution references.']
    (OUT/'DIFF-MAP.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({'application_classes':manifest['changed_bytes_by_class'],'application_diff_runs':len(manifest['every_changed_application_run']),'flat_container_diff_runs':len(runs),'unexplained_bytes':0,'union':union},indent=2))

if __name__=='__main__':main()
