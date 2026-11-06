"""Preserve r4 signal routing/connector poses; replace only r5 affected circuitry.

Run with KiCad Python. Output is an engineering PCB, never a fabrication release.
"""
from pathlib import Path
import json, copy, sys, time
import pcbnew
import design, make_pcb, place_pcb, route_pcb as rt

K=Path(__file__).resolve().parents[1]
# kicad -> design -> full -> usb-jtag-r5 -> spark
R4=K.parents[3]/'single-sided-r4/full/design/kicad'
def xy(p):return pcbnew.ToMM(p.x),pcbnew.ToMM(p.y)

def main():
    cs=design.build(); cd={c.ref:c for c in cs}
    b=make_pcb.Builder();b.board=pcbnew.LoadBoard(str(R4/'tab5-fpga-carrier.kicad_pcb'))
    b.nets={n.GetNetname():n for n in b.board.GetNetsByNetcode().values()}
    original={fp.GetReference():fp for fp in b.board.GetFootprints()}
    changes={'J2'}
    newrefs=set(cd)-set(original)
    affected={'VIN','+5V','SYS_RAW','DC_IN','VBUS_PD','CC1','CC2'}
    for c in cs:
        if c.ref in newrefs|changes:affected.update(n for n in c.pins.values() if n)
    for fp in list(b.board.GetFootprints()):
        if fp.GetReference() not in cd or fp.GetReference() in changes:
            b.board.RemoveNative(fp)
    for t in list(b.board.GetTracks()):
        if t.GetNetname() in affected-{'GND'}:
            b.board.RemoveNative(t)
        elif t.GetNetname()=='GND':
            # The new USB receptacle has different NPTH/shell geometry.
            pts=[xy(t.GetPosition())] if isinstance(t,pcbnew.PCB_VIA) else [xy(t.GetStart()),xy(t.GetEnd())]
            if any(2<x<14 and 19<y<34 for x,y in pts):b.board.RemoveNative(t)
    # Rebind retained components, where r5 deliberately renamed supply pins.
    for fp in b.board.GetFootprints():
        c=cd[fp.GetReference()];b.fps[c.ref]=fp
        c.pos=xy(fp.GetPosition());c.rot=fp.GetOrientationDegrees()
        fp.SetDNP(c.dnp);fp.SetValue(c.value)
        for p in fp.Pads():
            net=(c.pads if c.pads is not None else c.pins).get(p.GetNumber())
            if net:p.SetNet(b.net(net))
        design.POWER_FIXED[c.ref]=(c.pos,c.rot)
    for c in cs:
        if c.ref in newrefs|changes:b.create(c)
    place_pcb.run(b,cs)
    # New signal lands must not sit on old GND stitching. KiCad's DSN export
    # otherwise propagates the new pad's net onto those old ground segments.
    newboxes=[b.fps[ref].GetBoundingBox(False) for ref in newrefs|changes]
    for bb in newboxes:bb.Inflate(pcbnew.FromMM(.5))
    for t in list(b.board.GetTracks()):
        if t.GetNetname()!='GND':continue
        if isinstance(t,pcbnew.PCB_VIA):points=[t.GetPosition()]
        else:
            a,z=t.GetStart(),t.GetEnd();n=max(1,int(((a.x-z.x)**2+(a.y-z.y)**2)**.5/pcbnew.FromMM(.1)))
            points=[pcbnew.VECTOR2I(int(a.x+(z.x-a.x)*i/n),int(a.y+(z.y-a.y)*i/n)) for i in range(n+1)]
        if any(bb.Contains(p) for bb in newboxes for p in points):b.board.RemoveNative(t)
    b.board.GetTitleBlock().SetRevision('r5 USB-JTAG ENGINEERING / NOT FOR FABRICATION')
    b.board.GetTitleBlock().SetDate('2026-11-03')
    for fp in b.board.GetFootprints():
        fp.Reference().SetLayer(pcbnew.F_Fab if not fp.IsFlipped() else pcbnew.B_Fab)
        fp.Value().SetLayer(pcbnew.F_Fab if not fp.IsFlipped() else pcbnew.B_Fab)
        fp.Value().SetVisible(False)
    b.save(str(K/(design.PROJECT+'.kicad_pcb')))
    (K/'sim/placement.json').write_text(json.dumps({c.ref:{'xy':c.pos,'rotation':c.rot} for c in cs},indent=2)+'\n')
    if '--place-only' in sys.argv:return
    rt.GRID=.05
    r=rt.Router(b.board,*design.BOARD);r.load(design.BOARD)
    layers={pcbnew.F_Cu:0,pcbnew.In2_Cu:1,pcbnew.B_Cu:2}
    for t in b.board.GetTracks():
        n=r.nid(t.GetNetname())
        if isinstance(t,pcbnew.PCB_VIA):
            for l in range(3):r.stamp_disc(l,*xy(t.GetPosition()),n,pcbnew.ToMM(t.GetWidth(pcbnew.F_Cu))/2+rt.CLR+rt.TW/2)
        elif t.GetLayer() in layers:
            r.stamp_path(layers[t.GetLayer()],[xy(t.GetStart()),xy(t.GetEnd())],n,pcbnew.ToMM(t.GetWidth()))
    r.base=[o.copy() for o in r.occ]
    # Escape fine-pitch IC pins orthogonally before A*. The0.1mm r4 grid
    # could not resolve several0.45/0.5mm r5 pads.
    for ref in ('U2','U11','U12','U17','U21'):
        cx,cy=xy(b.fps[ref].GetPosition())
        def direction(x,y,cx=cx,cy=cy):
            dx,dy=x-cx,y-cy
            return ((1 if dx>0 else -1),0) if abs(dx)>abs(dy) else (0,(1 if dy>0 else -1))
        r.add_escape_stubs({ref+'.':(.55,direction)})
    nets=sorted((affected-{'GND'}) & set(r.pads),key=lambda n:(n not in ('REG_L1','REG_L2'),-rt.ORDER_W.get(n,.127),n))
    failed=[];start=time.time()
    for i,n in enumerate(nets):
        r.max_exp=350000
        print(f'[{i+1}/{len(nets)}] {n} ({len(r.pads[n])} pads) t={time.time()-start:.1f}s',flush=True)
        if not r.route_net(n,rt.ORDER_W.get(n,.127),16):failed.append(n)
    for name,l,pts,w in r.perm+r.tracks:b.track(name,rt.LAYER_NAMES[l],pts,w)
    for name,x,y in r.vias:b.via(name,x,y)
    b.fill();b.save(str(K/(design.PROJECT+'.kicad_pcb')))
    (K/'sim/route-result.json').write_text(json.dumps({'failed_nets':failed,'affected_nets':nets,'seconds':time.time()-start,'preserved_r4_signal_routes':True},indent=2)+'\n')
    print('Saved engineering route; failed:',failed,flush=True)

if __name__=='__main__':main()
