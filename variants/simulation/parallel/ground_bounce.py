"""Shared-return inductance sensitivity for eight simultaneous outputs."""
from pathlib import Path
import json
import numpy as np
from ngspice_shared import Spice
H=Path(__file__).resolve().parent;s=Spice();rows=[]
for label,current,edge in [('weak_4mA_3ns',.032,3e-9),('strong_40mA_half_ns',.32,.5e-9)]:
    lines=['Eight simultaneous outputs shared return envelope',f'Ireturn 0 chipgnd PULSE(0 {current} 10n {edge} {edge} 40n 100n)','Lreturn chipgnd g 3n','Rreturn g 0 .05','Cfringe chipgnd 0 20p','.tran 10p 100n 0 10p','.save v(chipgnd)','.end']
    assert s.load(lines)==0;s.run();t=s.vector('time');v=s.vector('v(chipgnd)')
    rows.append({'case':label,'assumed_shared_return_L_nH':3,'assumed_shared_R_ohm':.05,'8line_total_current_A':current,'edge_ns':edge*1e9,'max_ground_V':float(v.max()),'min_ground_V':float(v.min()),'scope':'Explicit package/connector return sensitivity, not extracted measured shared package model'})
    if label.startswith('weak'):
        np.savetxt(H/'ground-bounce.csv',np.column_stack([t[::10],v[::10]]),delimiter=',',header='time_s,chip_ground_V',comments='')
        (H/'ground-bounce.cir').write_text('\n'.join(lines)+'\n')
(H/'ground-bounce.json').write_text(json.dumps({'results':rows,'limits':['The 3nH shared-return and simultaneous-current waveform are sensitivity assumptions, not the complete ESP32-P4/GW2A package IBIS power model.','The strong ideal-current stress exceeds supply compliance: its multi-volt ringing is a model-domain warning, not a prediction that real chip ground will reach that voltage.','Input thresholds and local supply references move with package ground; figures are not simply added as independent worst-case noise guarantees.']},indent=2)+'\n')
print(rows)
