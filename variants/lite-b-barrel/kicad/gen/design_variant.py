"""B: common verified 99x78 layout, HDMI fitted, barrel 12V only."""
import design_dual as dual
from design_dual import *
VARIANT='lite-b-barrel'
REMOVED={'J2','U1','C2','R1','R2','R3','R4','R5','D2'}
EDGE_CONNECTORS=('J1','J4','J5')
def build():
    cs=dual.build()
    cs[:]=[c for c in cs if c.ref not in REMOVED]
    return cs
