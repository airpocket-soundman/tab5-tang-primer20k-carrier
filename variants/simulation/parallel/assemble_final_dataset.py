"""Normalize the corrected680ohm model matrix for the review-page generator."""
from pathlib import Path
import copy
import json
H=Path(__file__).resolve().parent
rows=[]
for variant in ('lite-a-dual','lite-b-barrel','lite-c-dnp'):
    source='lite-a-dual' if variant=='lite-b-barrel' else variant
    data=json.loads((H/(source+'-final680.json')).read_text())
    assert len(data['results'])==150
    for r in data['results']:
        x=copy.deepcopy(r);x['variant']=variant
        x['exact_corner']=x['corner'];x['corner']='fast' if x['corner'].startswith('fast') else 'controlled' if x['corner'].startswith('controlled') else 'slow'
        e=x['pin_extrema_V']['GPIO_receiver'];x['max_V']=e['max'];x['min_V']=min(e['min_rising'],e['min_falling_by_linearity'])
        for e in x['pin_extrema_V'].values():e['min']=min(e['min_rising'],e['min_falling_by_linearity'])
        x['switch_voltage_ok']=x['switch_design_envelope_ok']
        rows.append(x)
(H/'resistor-qualification-final680.json').write_text(json.dumps({'results':rows,'unique_spice_solves':300,'physical_channel_cases':450,'scope':'Final680ohm; corrected TI IBIS per-port capacitance plus package. A/B reuse identical physical paths. Historical330 recommendation superseded.'},indent=2)+'\n')
print('final680 cases',len(rows),'unique300')
