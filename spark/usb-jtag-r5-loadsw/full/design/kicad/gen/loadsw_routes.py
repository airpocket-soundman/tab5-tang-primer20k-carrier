# Executed by add_loadsw.py (uses do, T, pad, FB, F, B, b, tomm). Power 0.5 mm, gates/signals 0.25 mm.
BUCK_TAP = (38.15, 26.85, F)       # end of the BUCK_5V trunk (F.Cu) that used to run to SW4 pad1
P5V_TAP = (39.0, 28.54, None)      # +5V trunk via
VBUS_TAP = (39.0, 31.08, None)     # VBUS_PD trunk via (In2 trunk)
# nearest existing GND copper for D12 pad 2 (a through-hole pad or a via on net GND)
def nearest_gnd(x, y):
    best = None
    for f in b.GetFootprints():
        if f.GetReference() in ('Q11', 'Q12', 'Q13', 'Q14', 'Q15', 'D12', 'R91', 'R92', 'R93', 'R94', 'R95'): continue
        for p in f.Pads():
            if p.GetNetname() == 'GND' and (p.IsOnLayer(F)):
                px, py = tomm(p.GetX()), tomm(p.GetY()); d = math.hypot(px - x, py - y)
                if best is None or d < best[0]: best = (d, px, py, None)
    for t in b.GetTracks():
        if t.GetClass() == 'PCB_VIA' and t.GetNetname() == 'GND':
            px, py = tomm(t.GetX()), tomm(t.GetY()); d = math.hypot(px - x, py - y)
            if best is None or d < best[0]: best = (d, px, py, None)
    return best
# 1) power
do('LS_SCR', 0.5, [T('Q11', 2), T('Q12', 2), T('R91', 1)], FB)
do('LS_SCP', 0.5, [T('Q13', 2), T('Q14', 2), T('Q15', 2), T('R93', 1), T('R95', 1)], FB)
do('BUCK_5V', 0.5, [T('Q11', 3), BUCK_TAP], FB)
do('+5V', 0.5, [T('Q12', 3), T('Q14', 3), P5V_TAP], FB)
do('VBUS_PD', 0.5, [T('Q13', 3), VBUS_TAP], [F, I2, B])
# 2) gates and guard
do('RUN_G', 0.25, [T('Q11', 1), T('Q12', 1), T('R91', 2), T('R92', 1)], FB)
do('PGM_G', 0.25, [T('Q13', 1), T('Q14', 1), T('Q15', 3), T('R93', 2), T('R94', 1)], FB)
do('LS_KG', 0.25, [T('Q15', 1), T('R95', 2), T('D12', 1)], FB)
# 3) SW4 signals
do('SW_RUN', 0.25, [T('R92', 2), (*pad('SW4', 1), None)], FB)
do('SW_PGM', 0.25, [T('R94', 2), (*pad('SW4', 3), None)], FB)
# 4) grounds: D12 anode to the nearest GND copper, SW4 pad4 (common) to SW4 pad 10 (GND)
x, y = pad('D12', 2)
g = nearest_gnd(x, y)
print('D12 GND target', g)
do('GND', 0.3, [T('D12', 2), (g[1], g[2], g[3])], FB)
do('GND', 0.3, [(*pad('SW4', 4), None), (*pad('SW4', 10, 1), None)], FB)
