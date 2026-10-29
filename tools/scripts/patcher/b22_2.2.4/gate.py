#!/usr/bin/env python3
"""Freeze complete composed-application qualification before any GBL construction."""
from pathlib import Path
import hashlib,json
R=Path(__file__).resolve().parents[4];Q=R/'builds/build_b22_2026-10-28';K=Q/'qualification';H=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def load(n):return json.loads((K/n).read_text())
def need(x,m):
 if not x:raise ValueError(m)
app=Q/'build_a/application.bin';sha=H(app);need(sha=='7ee593265c76abd8cd628a81133d4b1310c1ae24c9ebe2ca3f2c2948acfc64f9' and app.read_bytes()==(Q/'build_b/application.bin').read_bytes(),'qualified image identity')
base=load('native_base/summary.json');need(base['application_sha256']==sha,'base binding');v=base['suites']
need(v['A1R']['passed']==v['A1R']['tests']==151 and v['A1R']['result']=='PASS','A1R')
need(v['B2']['status']=='PASS' and v['B2']['single_call_parity_cases']==2060 and v['B2']['unmasked_preemption_cut_cases']==102,'B2')
need(v['B2Mixed']['status']=='PASS' and v['B2Mixed']['transitions']==10,'mixed')
need(v['MQTT']['status']=='PASS' and v['MQTT']['passed']==258,'MQTT')
need(v['CC']['status']=='PASS' and v['CC']['actual_byte_predicate_cases']==512 and v['CC']['integer_delta_cases']==10000,'CC')
c=load('native_candidates/summary.json');need(c['status']=='PASS' and c['application_sha256']==sha,'candidates');counts=c['counts']
for key,n in {'P01_retained':128,'P01_additional_interaction':6,'P02_native':90,'P02_late_flag_native_calls':480,'P03_pairs':64,'P03_native_executions':128,'Calibration_native':68,'Calibration_scalar':66535,'Calibration_queue':104,'Calibration_countdown':30,'Calibration_retained_negatives':42,'battery_percentage':10002,'OTA_empty_argument_native_gate':2,'boot_3000mV_native_cutpoint':4,'shutdown_native_countdown_cutpoint':3}.items():need(counts[key]==n,key)
for file,h in c['results'].items():need(H(K/'native_candidates'/file)==h,'candidate result pin '+file)
motor=load('native_base/motor-interaction-results.json');sleep=load('native_base/sleep-admission-results.json');iface=load('native_base/interface-composition-results.json')
for d,n,key in [(motor,10,'cases'),(sleep,48,'cases'),(iface,7,'rows')]:need(d['status']=='PASS' and d['application_sha256']==sha and len(d[key])==n,'interaction/flow')
ind=load('independent/application-gate.json');need(ind['status']=='PASS APPLICATION GATE' and ind['independent_results_equal'] and ind['build_a_application']==sha and ind['build_b_application']==sha and ind['observer_native_sites_verified']==14 and ind['negative_controls']==274,'independent application')
ctl=load('construction-controls.json');need(ctl['status']=='PASS' and ctl['negative_count']==286 and all(x['rejected']for x in ctl['negative_controls']),'construction negatives')
need(load('deterministic-applications.json')['status']=='PASS','four builds')
rows=iface['rows']+[
 dict(interaction='P02 + ordinary display/I2C',status='PASS',qualification_kind='native wrapper/state machine with MMIO events',proof='90 native fixtures +480lateflags, final4AF0/C484/BFEC and bounded retirement; six display callsites unchanged',limits='Electrical display/bus events supplied; no physical bus recovery claim'),
 dict(interaction='P03 + PA8 notification + sleep veto',status='PASS',qualification_kind='paired native GPIO/SDIO wrapper and native sleep admission',proof='64pairs for exact mask;48native selector/callback/DIN admission cases; notification enable and callback bytes unchanged',limits='No actual WFI or IRQ electrical event; pending flag behavior preserved by byte contract'),
 dict(interaction='Calibration Restore Guard + B2/motor',status='PASS',qualification_kind='native stable-interface composition',proof='68guardnative/104queue/30countdown +10actual3708/B2cleanup cases; only enqueue escalation return changes, motor primitive and B2ownership unchanged',limits='Guard fixture models physical motor count and enqueue endpoint; teardown separately executes actual transaction instructions')]
need(len(rows)==10 and all(r['status']=='PASS'for r in rows),'all10interactions')
flows=[('boot','4native3000mVbootcutpoints;P01boot;guardboot-origin;A1Rinitialization'),('association','retainedA1R151normalization and accepted/cancelledgenerations'),('reconnect','retainedA1R151cancellation/reconnect scenarios'),('thermostat regulation','nativeguardordinaryposition/recloseorigins and retainedtarget/setter interfaces'),('manual valve position','native3944 guard origin cases;actualmotor/B2 transaction'),('target temperature','guardindependenttarget origin +nativeposition/motor interfaces'),('full calibration','native3E04/1F404restore guard68 +queue/countdown models'),('failed calibration then independent retry','guardfailure/nativeorigin and104queue scenarios;no independentretry right removed'),('charger','P01VBUSsample cadence;10002nativepercentageflags cases'),('low voltage','4boot3000mV +3shutdowncountdown nativecutpoints'),('normal sleep','48native6BBC/selector/PA8admission cases;EMentryendpoint only'),('Final-Sleep','A1R151retainedstale/readfailure/writefailure lifecycle cases'),('OTA-related paths','2nativeHTTPOTAvoltagegate cutpoints and retainedtemporaryorigin1CFB2/A1R')]
matrix=dict(status='PASS',application_sha256=sha,interactions=rows,representative_flows=[dict(flow=n,status='PASS',evidence=e)for n,e in flows],scope='Bounded native cutpoints and explicit stable-interface composition; not whole-device boot/radio/mechanical/OTA/residency execution. Native endpoint/adaptor limitations are retained in per-suite scopes.')
(K/'integration-matrix.json').write_text(json.dumps(matrix,indent=2)+'\n')
# Freeze code, actual inputs/results, manifests and all checked app/object/source outputs.
pins={}
for folder in [R/'tools/scripts/patcher/b22_2.2.4',K,Q/'build_a',Q/'build_b',Q/'reproduction_a',Q/'reproduction_b']:
 for p in folder.rglob('*'):
  if p.is_file() and p.suffix in ['.py','.java','.json','.S','.bin','.o'] and p.name!='pre-container-gate.json' and '__pycache__' not in p.parts:pins[str(p.relative_to(R))]=H(p)
for p in [R/'tools/scripts/patcher/calibration_restore_guard_2.2.4/restore_guard.S',R/'analysis/evidence/p01-p02-patch-qualification-2026-10-28/p01/v2/pa3_release.S',R/'analysis/evidence/p01-p02-patch-qualification-2026-10-28/p02/timeout_retire.S',R/'analysis/evidence/p01-p02-patch-qualification-2026-10-28/p03/gpio_mask.S']:pins[str(p.relative_to(R))]=H(p)
g=dict(status='PASS',application_SHA256=sha,required_components=9,component_regressions='PASS',interaction_tests=10,representative_flow_cutpoints=13,independent_application='PASS',negative_controls='286builder +274independent; overlapping sets not pooled',pins=pins,GBL_emission_authorized=True,hardware_qualification=False)
(K/'pre-container-gate.json').write_text(json.dumps(g,indent=2,sort_keys=True)+'\n');print('PASS pre-container gate',len(pins),'pins;10interactions/13flowcutpoints')
