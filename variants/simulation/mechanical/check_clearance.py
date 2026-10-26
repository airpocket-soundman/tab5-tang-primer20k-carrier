"""Conservative 3D AABB check using official Core STEP component geometry.

Core STEP uses +Y up; KiCad uses +Y down. At socket rotation 270 degrees:
carrier X = socket X + STEP Y + (15 - native card-edge Y),
carrier Y = socket Y + STEP X. STEP Z remains up (no physical board flip).
Insertion depth and support height are swept rather than silently assuming an
exact mounted pose unavailable as a controlled drawing dimension.
"""
from pathlib import Path
import json
import numpy as np
import sys

HERE=Path(__file__).resolve().parent
geometry=json.loads((HERE/'carrier_geometry.json').read_text(encoding='utf-8'))
core=json.loads((HERE/'core_components.json').read_text(encoding='utf-8'))
components=[p for p in core['parts'] if p['depth']==1]
proposal='--proposal' in sys.argv
if proposal:
    for variant,parts in geometry.items():
        if variant=='lite-c-dnp':continue
        for p in parts:
            if p['ref'] in {f'C{i}' for i in range(12,20)}:
                p['footprint']='C_0402_1005Metric'
                x,y=p['origin_mm'];p['body_xy_mm']=[x-.55,y-.3,x+.55,y+.3]
            if p['ref']=='U6':
                p['footprint']='DFN2510-10L_RCLAMP0524P'
                x,y=p['origin_mm'];p['body_xy_mm']=[x-.55,y-1.3,x+.55,y+1.3]

def height(part):
    f=part['footprint']
    if f.startswith('R_0402'):return .4
    if f.startswith('R_0603'):return .55
    if f.startswith('C_0402'):return .55
    if f.startswith('C_0603'):return .9
    if f.startswith('C_1206'):return 2.
    if f.startswith('LED_'):return .9
    if f.startswith('SOT-23'):return 1.45
    if f.startswith('TSSOP'):return 1.2
    if f.startswith('SSOP'):return 1.75
    if f.startswith('TI_SO'):return 1.75
    if f.startswith('D_SMA') or f.startswith('D_SMB'):return 2.6
    if f.startswith('CP_Elec'):return 7.7
    if f.startswith('CP_EIA'):return 4.
    if 'MS1040' in f:return 4.
    if f.startswith('USB_C'):return 3.5
    if f.startswith('BarrelJack'):return 11.6
    if f.startswith('HDMI_A'):return 6.5
    if f.startswith('Fuse_'):return .9
    if f.startswith('DFN2510'):return .55 # DOWO Rev.G1.00 p4 dimension A max
    if f.startswith('SW_'):return 4.3
    if f.startswith('PinHeader'):return 8.5
    if f.startswith('MountingHole'):return 0.
    raise ValueError('No height envelope for '+part['ref']+' '+f)

report={'scope':__doc__,'proposal_only_not_actual_CAD':proposal,'core_step_sha256':core['step_sha256'],
        'criteria':{'minimum_clearance_mm':.3,'relative_xy_uncertainty_mm':.25,
                    'card_edge_native_Y_sweep_mm':[-.5,4.5],'card_bottom_above_carrier_sweep_mm':[2.3,2.6,2.8,3.,3.3,3.5]},
        'pose_limitations':'These broad sweeps are engineering assumptions from 3.30 reference/contact-gap/1mm card and housing dimensions, not a manufacturer-guaranteed mounted-height tolerance. AABB separation is conservative; overlapping envelopes require physical-detail review or relocation.',
        'variants':{}}
for variant,parts in geometry.items():
    sock=next(p for p in parts if p['ref']=='J4');cx,cy=sock['origin_mm']
    checks=[]
    for part in parts:
        if part['dnp'] or part['back'] or part['ref']=='J4' or part['ref'].startswith('H'):continue
        h=height(part)+.05;a,b,c,d=part['body_xy_mm'];minimum=100.;limiting=None
        for edge in np.arange(-.5,4.5001,.25):
            offset=15-edge
            for r in components:
                x0,y0,z0,x1,y1,z1=r['bounds_mm']
                xb0,xb1=cx+y0+offset,cx+y1+offset
                yb0,yb1=cy+x0,cy+x1
                tol=.25
                if c+tol<xb0 or xb1+tol<a or d+tol<yb0 or yb1+tol<b:continue
                gap=2.3+z0-h
                if gap<minimum:minimum=gap;limiting=dict(core_part=r['name'],core_part_type=r.get('part_type'),card_edge_native_mm=float(edge),core_bbox_mm=[xb0,yb0,2.3+z0,xb1,yb1,2.3+z1])
        checks.append(dict(ref=part['ref'],value=part['value'],footprint=part['footprint'],height_envelope_mm=h,body_xy_mm=part['body_xy_mm'],overlap_in_xy=limiting is not None,minimum_vertical_gap_mm=None if limiting is None else minimum,pass_clearance=minimum>=.3,limiting=limiting))
    report['variants'][variant]=dict(pass_clearance=all(r['pass_clearance'] for r in checks),components=checks,failures=[r for r in checks if not r['pass_clearance']])
(HERE/('clearance-proposed.json' if proposal else 'clearance.json')).write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
for variant,row in report['variants'].items():print(variant,row['pass_clearance'],[(r['ref'],round(r['minimum_vertical_gap_mm'],3),r['limiting']['core_part_type']) for r in row['failures']])
