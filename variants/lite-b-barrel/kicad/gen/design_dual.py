"""A: 99x78, dual 12V input, HDMI, cheaper qualified part candidates."""
from pathlib import Path
import json
import design_base as base
from design_base import *

BOARD=(28.,1.,127.,79.)
VARIANT='lite-a-dual'
PROJECT='tab5-fpga-carrier'
_POSE=json.loads((Path(__file__).parent/'placement.json').read_text())
POWER_FIXED={k:(tuple(v[0]),v[1]) for k,v in _POSE.items()}

def build():
    cs=base.build()
    cs[:]=[c for c in cs if c.ref not in ('H1','H2')]
    lookup={c.ref:c for c in cs}
    for c in cs:
        if c.ref in _POSE:c.pos,c.rot=tuple(_POSE[c.ref][0]),_POSE[c.ref][1]
    lookup['J4'].fp='carrier:DDR3_XDAP_4042044_20401'
    lookup['J4'].value='SOCKET XDAP-4042044-20401'
    lookup['J4'].lcsc='C22471982'
    lookup['J4'].comment='PCBA required; socket only, user supplies Tang Primer 20K Core module'
    lookup['L1'].fp='carrier:L_COILMX_MS1040'
    lookup['L1'].value='15u MS1040-150M'
    lookup['L1'].lcsc='C380054'
    lookup['U3'].sym='Regulator_Linear:XC6206PxxxMR'
    lookup['U3'].fp='Package_TO_SOT_SMD:SOT-23'
    lookup['U3'].value='XC6206P332MR-G'
    lookup['U3'].lcsc='C5446'
    lookup['U3'].comment='3.3V local logic only; no external 3V3 loads; design limit 50mA'
    lookup['R7'].value='3.3k';lookup['R7'].lcsc='C22978'
    lookup['R7'].comment='3.3k parallel (100k+100k): Req 3246.433 ohm, nominal buck 4.982V'
    for ref,a,b in [('R49','BUCK_FB','FB_TRIM'),('R50','FB_TRIM','GND')]:
        p,r=POWER_FIXED[ref]
        cs.append(base.Comp(ref,'Device:R',R0603,'100k',{'1':a,'2':b},'buck',pos=p,rot=r,lcsc='C25803'))
    # Qualified single Basic 510-ohm substitution preserves reviewed branch
    # geometry and avoids extra components and closely spaced new branches.
    for i in range(8):
        c=lookup['R'+str(28+i)]
        c.value='510R'; c.lcsc='C25123' if i in (2,3) else 'C23193'
        c.comment='Basic 510 ohm; +2.2% vs 499; unchanged HDMI branch geometry'
    return cs
