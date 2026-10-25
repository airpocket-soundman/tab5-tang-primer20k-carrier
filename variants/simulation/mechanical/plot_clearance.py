"""Plot real body envelopes and official Core underside bounds, no fake socket solid."""
from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

H=Path(__file__).resolve().parent
geometry=json.loads((H/'carrier_geometry.json').read_text(encoding='utf-8'))
report=json.loads((H/'clearance.json').read_text(encoding='utf-8'))
core=json.loads((H/'core_components.json').read_text(encoding='utf-8'))
for variant,parts in geometry.items():
    fig,(ax,side)=plt.subplots(1,2,figsize=(12,6),gridspec_kw={'width_ratios':[1.4,1]})
    socket=next(p for p in parts if p['ref']=='J4');cx,cy=socket['origin_mm']
    # Old preview offset15.5mm is one reference pose, not a mounting guarantee.
    for p in core['parts']:
        if p['depth']!=1:continue
        x0,y0,z0,x1,y1,z1=p['bounds_mm']
        if z0>=0:continue
        ax.add_patch(Rectangle((cx+y0+15.5,cy+x0),y1-y0,x1-x0,facecolor='#869db1',edgecolor='#566e85',alpha=.35,lw=.4))
    for p in parts:
        if p['dnp'] or p['back'] or p['ref']=='J4' or p['ref'].startswith('H'):continue
        x0,y0,x1,y1=p['body_xy_mm']
        ax.add_patch(Rectangle((x0,y0),x1-x0,y1-y0,facecolor='#69a67b',edgecolor='#245f38',alpha=.65,lw=.4))
        if p['ref'] in ('U6','U4','U5','L1','C7','J1','J5','Q5','C24'):
            ax.text((x0+x1)/2,(y0+y1)/2,p['ref'],fontsize=7,ha='center')
    ax.add_patch(Rectangle((cx-.5,cy-33.8),30,67.6,fill=False,edgecolor='#173d63',lw=1.5,ls='--'))
    ax.set(xlim=(28 if variant!='lite-c-dnp' else 2,129),ylim=(80,0),xlabel='Carrier X (mm)',ylabel='Carrier Y (mm)',title='Green: fitted carrier / blue: Core underside')
    ax.set_aspect('equal');ax.grid(alpha=.15)
    rows=[p for p in report['variants'][variant]['components'] if p['overlap_in_xy']]
    rows=sorted(rows,key=lambda p:p['minimum_vertical_gap_mm'])[:12]
    side.barh([p['ref'] for p in rows],[p['minimum_vertical_gap_mm'] for p in rows],color=['#4b9465' if p['pass_clearance'] else '#c65249' for p in rows])
    side.axvline(.3,color='#b77b13',ls='--',label='0.30mm target');side.invert_yaxis();side.set(xlabel='Minimum vertical gap (mm)',title='Assumed lowest card bottom: 2.30mm');side.legend(fontsize=8)
    fig.suptitle(variant+' — official STEP / conservative AABB envelopes',fontsize=13)
    fig.text(.5,.015,'Pose sweep: edge -0.5..4.5mm; relative XY +/-0.25mm; solder +0.05mm. Mounted height remains an assumption.',ha='center',fontsize=8)
    fig.tight_layout(rect=[0,.04,1,.95]);fig.savefig(H/(variant+'-clearance.png'),dpi=150);plt.close(fig)
