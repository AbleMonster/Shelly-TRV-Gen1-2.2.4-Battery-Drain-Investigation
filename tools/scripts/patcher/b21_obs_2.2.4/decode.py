#!/usr/bin/env python3
"""Decode an explicitly saved /status JSON file. No network capabilities."""
import argparse
import json
import re
from pathlib import Path

KINDS={1:'PM52_ISSUE',2:'PM52_RESULT',3:'C3_START',4:'C3_COMMIT',5:'C4',
       6:'A1_FIRST_COMMIT',7:'A1_SECOND_COMMIT',9:'FIRST_BAD_SAMPLE'}

def decode(document):
    obj=document['pm52_cmd66']
    if obj.get('v')!=1 or not isinstance(obj.get('w'),str) or not re.fullmatch(r'[0-9a-fA-F]{1024}',obj['w']):
        raise ValueError('Unsupported or malformed observer payload')
    s=[int(obj['w'][i:i+8],16) for i in range(0,1024,8)]
    if s[:3]!=[0x504d3636,1,512]: raise ValueError('Observer header mismatch')
    if s[7]>12 or s[8]>=12: raise ValueError('Invalid ring indices')
    start=(s[8]-s[7])%12
    records=[]
    for j in range(s[7]):
        r=s[32+8*((start+j)%12):40+8*((start+j)%12)]
        records.append(dict(zip(('seq','tick','epoch','kind','a','b','c','d'),r)))
    faults=[]
    if not(s[3]&1): faults.append('No frozen first q=1 event')
    if s[3]&~1: faults.append('Overflow, ambiguity, wrap, or unknown flag')
    if not s[5] or s[6]!=1 or s[22]!=s[5]: faults.append('Connection/sample epoch not unambiguously connected')
    if s[21]&~0x3ff or (s[21]&0x300)!=0x300: faults.append('Sample not valid and fresh')
    if s[16]!=0: faults.append('cmd66 did not succeed')
    if not (301<=s[19]<=600 and ((s[17]-s[18])&0xffffffff)==s[19]
            and s[20]==600//s[19]==1 and (s[21]&255)==1):
        faults.append('Sample arithmetic is not a qualifying full-width q=1')
    if not records or any(r['seq']==0 for r in records) or any(a['seq']>=b['seq'] for a,b in zip(records,records[1:])):
        faults.append('Missing or non-monotonic ring chronology')
    if records and (records[-1]['seq']!=s[4] or records[-1]['kind']!=9): faults.append('Fault record is missing or not final')
    if records and records[-1]['kind']==9:
        fault=records[-1]
        if fault['epoch']!=s[22] or [fault[k] for k in ('a','b','c','d')]!=s[17:21]:
            faults.append('Fault record does not match the coherent sample header')
    if not s[23] or s[23]>=s[4]: faults.append('Missing cmd66 issue chronology')
    if records and any(r['kind'] not in KINDS for r in records): faults.append('Unknown record type')
    report={'header':{'flags':s[3],'sequence':s[4],'epoch':s[5],'connected':s[6],
                      'count':s[7],'head':s[8],'pending_issue':s[9],
                      'latest_issue':s[12],'latest_result_issue':s[13],'latest_native_result':s[14]},
            'sample':{'status':s[16],'C':s[17],'P':s[18],'delta':s[19],'q':s[20],
                      'R':s[21]&255,'epoch':s[22],'query_issue_seq':s[23]},
            'a1':dict(zip(('pm_generation','desired_version','confirmed_version','completed_generation','confirmed_lo','confirmed_hi'),s[24:30])),
            'bssid_bytes':(s[30].to_bytes(4,'little')+s[31].to_bytes(4,'little')[:2]).hex(':'),
            'records':[dict(r,type=KINDS.get(r['kind'],'UNKNOWN')) for r in records],
            'raw_words':s,'classification':'CASE C — INCONCLUSIVE','reasons':faults}
    if faults: return report
    same=[r for r in records if r['epoch']==s[5] and r['seq']<=s[4]]
    issue=next((r for r in same if r['kind']==1 and r['seq']==s[12]),None)
    result=next((r for r in same if r['kind']==2 and r['a']==s[12]),None)
    commit=next((r for r in same if r['kind']==6 and r['d']==s[12]),None)
    expected_lo=0x00140101 # little-endian mode=1,strategy=1,LI=20
    expected_hi=0 # timeout=0 and native reserved bytes zero
    if (issue and result and commit and s[12]==s[13] and s[14]==0
        and issue['a']==expected_lo and issue['b']==0x100 and result['b']==0
        and issue['seq']<result['seq']<commit['seq']<s[23]
        and commit['a']==1 and commit['b']==issue['c']
        and commit['c']==s[25]==s[26] and commit['b']==s[24]
        and s[28]==expected_lo and s[29]==expected_hi and not s[9]):
        report['classification']='CASE A — EXPECTED PM52 SUCCESS PRECEDES FRESH q=1'
        report['reasons']=['Command success and accepted A1 first commit both precede cmd66 issue; not a physical listen-interval readback']
    elif (issue and result and s[12]==s[13] and result['b']==s[14]
          and issue['seq']<result['seq']<s[4] and result['b']!=0 and not s[9]):
        report['classification']='CASE B — PM52 FAILURE PRECEDES FRESH q=1'
        report['reasons']=[f"Native result {result['b']:#x}; timeout only if native code identifies it"]
    elif (issue and result and commit and s[12]==s[13] and result['b']==s[14]
          and issue['seq']<result['seq']<commit['seq']<s[4]
          and commit['a']==0 and not s[9]):
        report['classification']='CASE B — A1 REJECTED COMPLETION PRECEDES FRESH q=1'
        report['reasons']=['Rejection does not alone distinguish stale generation from other native validation failure']
    else:
        report['reasons']=['Missing matching issue/result/accepted commit, superseded state, or unexpected tuple; no automatic success inference']
    return report

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('saved_status',type=Path)
    args=parser.parse_args()
    try: print(json.dumps(decode(json.loads(args.saved_status.read_text())),indent=2))
    except (ValueError,KeyError,TypeError) as e: parser.exit(2,f'Decode rejected: {e}\n')

if __name__=='__main__': main()
