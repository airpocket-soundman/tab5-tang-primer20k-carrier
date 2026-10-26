"""Record the parent's purpose-driven review and final evidence bindings."""
from pathlib import Path
import hashlib
import json

H=Path(__file__).resolve().parent;ROOT=H.parents[1]
def read(p):return json.loads(p.read_text(encoding='utf-8'))
original=read(ROOT/'cost-study/2026-10-25/preserved-design-hashes.json')
assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==sha for p,sha in original.items())
geometry=read(H/'geometry-after-revision.json')
parallel=read(H/'parallel/final-summary.json')
power=read(H/'power/final-summary.json')
mechanical=read(H/'mechanical/clearance.json')
rows={}
for name,r in geometry.items():
    assert r['parallel_copper_unchanged'] and r['core5V_copper_unchanged'],name
    assert parallel['variants'][name]['series_ohm_model']==680,name
    assert parallel['variants'][name]['PoC_initial_1MHz_models']=='pass',name
    assert power['variants'][name]['poc_minimum_model_status']=='pass',name
    assert mechanical['variants'][name]['pass_clearance'],name
    audit=read(ROOT/'variants/validation'/f'{name}-independent-audit.json')
    assert audit['ok'] and audit['pcb_sha256']==r['source_pcb_sha256'],name
    rows[name]={'pcb_sha256_LF':r['source_pcb_sha256'],'independent_audit_checks':len(audit['checks']),
                'minimum_modeled_conditions':'pass','fabrication_decision':'conditional PoC candidate',
                'hardware_functionality':'not demonstrated until assembled-board bringup',
                'parallel_copper_unchanged':True,'core5V_copper_unchanged':True,
                'power_model_binding':'Original power circuit and Core5V copper retained. New HPD pull-up consumes <0.1mA within declared local3V3 <=10mA envelope; no model result is relabelled as a complete-board vendor simulation.'}
report={'date':'2026-10-25','reviewer':'parent agent independent review, beyond child-agent self-evaluations',
 'objective':'Tab5 parallel communication + powered official Core DDR3/accelerator; HDMI optional',
 'preserved_original_files':len(original),'variants':rows,
 'findings_and_disposition':[
  {'finding':'Switch CioOn duplicated per-port is not necessarily worst-case overshoot','action':'Per-port IBIS C_comp+package facts and capacitance sensitivity required; resistor revised to680ohm. Initial1MHz/weak-drive/SLOW only; fast-source stresses remain visible.'},
  {'finding':'HPD analysis originally tied Core and local3V3 power-off together','action':'Independent rail-collapse case exposed filter-capacitor injection; added10k resistor at Core input and reran powered levels/offrail sensitivity. No unsupported GPIO injection-current guarantee.'},
  {'finding':'Low ESR can reduce buck phase margin; minimum C7 ESR unspecified','action':'Added2mohm combined corner and250ms hold; small modeled phase margin remains a limitation rather than declaring all-corner stability.'},
  {'finding':'C11 effective MLCC capacitance may be below tolerance-only value','action':'Requested6.6uF effective-capacitance/slow-loop sensitivity for actual0->5->10mA load.'},
  {'finding':'Corrupt-looking socket rendering does not establish collision','action':'Used official Core STEP component bounds; swept mounting pose, lowered HDMI capacitor/ESD bodies, retained manufacturer-mounted-height uncertainty.'},
  {'finding':'Whole-Core DDR3 and final GPU functionality are not implemented in related repositories','action':'Reviewed Linux source/DeviceTree/mockdriver and GPU RTL separately. FactoryDDR test is a bringup reference, not proof of final GPU/DDR functionality.'}],
 'not_waived':['Fast uncalibrated source-pin stress','LDO typical-model process uncertainty','Core/local-rail asynchronous collapse and unprovided GPIO injection rating','Long reverse polarity','Incomplete branch3D convergence','Physical DDR3/PARLIO/DMA/accelerator bringup'],
 'publication_scope':'Fabrication conditions and simulation evidence, not production qualification or measured PoC success'}
(H/'independent-dynamic-review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Independent review recorded:',len(rows),'variants; original',len(original),'files unchanged')
