"""KiCad post-route: preserve r4 converter loop, connect new3V3 branches, GND vias."""
from pathlib import Path
import json,sys
import pcbnew
import design, route_pcb as rt
K=Path(__file__).resolve().parents[1]
P=K/(design.PROJECT+'.kicad_pcb')
def xy(p):return pcbnew.ToMM(p.x),pcbnew.ToMM(p.y)
def V(x,y):return pcbnew.VECTOR2I(pcbnew.FromMM(x),pcbnew.FromMM(y))

def main():
    b=pcbnew.LoadBoard(str(P));old=pcbnew.LoadBoard(str(K.parents[3]/'single-sided-r4/full/design/kicad/tab5-fpga-carrier.kicad_pcb'))
    canonical={'+3V3','DBG_3V3','JTAG_TCK_PRE','BUCK_PH','BUCK_FB','BUCK_EN','BUCK_BOOT','BUCK_5V','XTAL_IN','XTAL_OUT','FT_REF','FT_RESET_N'}
    oldgndids={t.m_Uuid.AsString() for t in old.GetTracks() if t.GetNetname()=='GND'}
    for t in list(b.GetTracks()):
        if t.GetNetname() in canonical or (t.GetNetname()=='GND' and t.m_Uuid.AsString() not in oldgndids):b.RemoveNative(t)
        elif not isinstance(t,pcbnew.PCB_VIA) and t.GetWidth()<pcbnew.FromMM(.127):t.SetWidth(pcbnew.FromMM(.127))
    for t in old.GetTracks():
        if t.GetNetname() in canonical:
            q=t.Duplicate();q.SetNet(b.FindNet(t.GetNetname()));b.Add(q)
        elif t.GetNetname()=='+5V':
            if isinstance(t,pcbnew.PCB_VIA) and xy(t.GetPosition())==(48.6,61.6):continue  # clipped old Core branch
            if not isinstance(t,pcbnew.PCB_VIA) and (xy(t.GetStart())==(48.6,61.6) or xy(t.GetEnd())==(48.6,61.6)):continue
            pts=[xy(t.GetPosition())] if isinstance(t,pcbnew.PCB_VIA) else [xy(t.GetStart()),xy(t.GetEnd())]
            # Only the local r4 converter output tree. Never bridge its former
            # Core/peripheral branches across the new mode selector.
            if all(19<x<49 and 45<y<77 for x,y in pts):
                q=t.Duplicate();q.SetNet(b.FindNet('BUCK_5V'));b.Add(q)
    fps={f.GetReference():f for f in b.GetFootprints()}
    for ref,newxy in [('C86',(18,28)),('C87',(16,35))]:
        fp=fps[ref];before={p.GetNumber():p.GetPosition() for p in fp.Pads()}
        fp.SetPosition(V(*newxy))
        # Clock nets are rerouted after moving the capacitors.
    rt.GRID=.05
    r=rt.Router(b,*design.BOARD);r.load(design.BOARD)
    layers={pcbnew.F_Cu:0,pcbnew.In2_Cu:1,pcbnew.B_Cu:2}
    for t in b.GetTracks():
        n=r.nid(t.GetNetname())
        if isinstance(t,pcbnew.PCB_VIA):
            for l in range(3):r.stamp_disc(l,*xy(t.GetPosition()),n,pcbnew.ToMM(t.GetWidth(pcbnew.F_Cu))/2+rt.CLR+rt.TW/2)
        elif t.GetLayer() in layers:
            pts=[xy(t.GetStart()),xy(t.GetEnd())];w=pcbnew.ToMM(t.GetWidth())
            r.stamp_path(layers[t.GetLayer()],pts,n,w)
            if t.GetNetname() in ('+3V3','BUCK_5V'):r.perm.append((t.GetNetname(),layers[t.GetLayer()],pts,w))
    r.base=[o.copy() for o in r.occ]
    r.max_exp=500000
    # Escape exact0.5mm FT232H clock pins before quantized maze routing.
    for name,pin,distance in [('XTAL_IN','1',-.7),('XTAL_OUT','2',-.7),('FT_REF','5',1.4),('FT_RESET_N','34',1.0),('DBG_3V3','12',1.3)]:
        lst=r.pads[name]
        for i,(x,y,layers0,label) in enumerate(lst):
            if label!='U17.'+pin:continue
            end=(x+distance,y);pts=[(x,y),end];n=r.nid(name)
            r.perm.append((name,0,pts,.127));r.stamp_path(0,pts,n,.127)
            r._stamp_base(lambda name=name,pts=pts,n=n:r.stamp_path(0,pts,n,.127))
            lst[i]=(end[0],end[1],layers0,label)
        # The seed must belong to the existing stub's connected component.
        # Seeding an isolated capacitor would falsely mark two islands joined.
        lst.sort(key=lambda p:p[3]!='U17.'+pin)
    r.pads['+3V3'].sort(key=lambda p:p[3]!='U3.2')
    r.pads['BUCK_5V'].sort(key=lambda p:p[3]!='L1.2')
    connected=True
    # Ground escapes take precedence over reference/reset signal routing.
    pads={p.GetNumber():p for p in fps['U17'].Pads()}
    ground_escapes=[]
    for pin,target in [('4',(21.7,32.8)),('35',(32.1,29.8)),('36',(32.1,29.8))]:
        x,y=xy(pads[pin].GetPosition());pts=[(x,y),(target[0],y),target]
        ground_escapes.append((pts,target));n=r.nid('GND')
        r.stamp_path(0,pts,n,.127);r._stamp_base(lambda pts=pts,n=n:r.stamp_path(0,pts,n,.127))
        for l in range(3):r.stamp_disc(l,*target,n,.3+rt.CLR+rt.TW/2)
    upads={p.GetNumber():p for p in fps['U19'].Pads()}
    x,y=xy(upads['7'].GetPosition());target=(43,y);pts=[(x,y),target]
    ground_escapes.append((pts,target));n=r.nid('GND')
    r.stamp_path(0,pts,n,.127)
    for l in range(3):r.stamp_disc(l,*target,n,.3+rt.CLR+rt.TW/2)
    # Link the lower FT232H AGND group and REF return onF.Cu before
    # routing the3V3 supply. A via under the IC body reaches the reference plane.
    rp={p.GetNumber():p for p in fps['R81'].Pads()}
    a=xy(rp['2'].GetPosition());target=(24.9,36.25)
    pts=[a,(22,36),(22,36.25),target]
    ground_escapes.append((pts,target));r.stamp_path(0,pts,n,.127)
    for l in range(3):r.stamp_disc(l,*target,n,.3+rt.CLR+rt.TW/2)
    r.base=[o.copy() for o in r.occ]
    for net,width in [('+3V3',.2),('BUCK_5V',.5),('XTAL_IN',.127),('XTAL_OUT',.127),('FT_REF',.127),('FT_RESET_N',.127),('DBG_3V3',.127),('JTAG_TCK_PRE',.127)]:
        ok=r.route_net(net,width,40);print(net,ok,flush=True);connected=connected and ok
    print('new3V3 branches:',connected,flush=True)
    newrefs={c.ref for c in design.build()}-{fp.GetReference() for fp in old.GetFootprints()}
    r.stitch_gnd(lambda name:name.split('.')[0] in newrefs and not name.startswith('JP') and name not in ('U17.4','U17.35','U17.36'),limit=120)
    clockstubs=[t for t in r.perm if t[0] in ('XTAL_IN','XTAL_OUT','FT_REF','FT_RESET_N','DBG_3V3')]
    for name,l,pts,w in clockstubs+r.tracks:
        for a,z in zip(pts,pts[1:]):
            t=pcbnew.PCB_TRACK(b);t.SetStart(V(*a));t.SetEnd(V(*z));t.SetWidth(pcbnew.FromMM(w));t.SetLayer([pcbnew.F_Cu,pcbnew.In2_Cu,pcbnew.B_Cu][l]);t.SetNet(b.FindNet(name));b.Add(t)
    for name,x,y in r.vias:
        t=pcbnew.PCB_VIA(b);t.SetPosition(V(x,y));t.SetWidth(pcbnew.FromMM(.6));t.SetDrill(pcbnew.FromMM(.3));t.SetViaType(pcbnew.VIATYPE_THROUGH);t.SetNet(b.FindNet(name));b.Add(t)
    def ground_path(points):
        for a,z in zip(points,points[1:]):
            if a==z:continue
            t=pcbnew.PCB_TRACK(b);t.SetStart(V(*a));t.SetEnd(V(*z));t.SetWidth(pcbnew.FromMM(.127));t.SetLayer(pcbnew.F_Cu);t.SetNet(b.FindNet('GND'));b.Add(t)
    # Explicit orthogonal escapes for the three FT232H ground pins which the
    # coarse ground stitcher cannot escape between adjacent signal lands.
    for pts,target in ground_escapes:
        ground_path(pts)
        t=pcbnew.PCB_VIA(b);t.SetPosition(V(*target));t.SetWidth(pcbnew.FromMM(.6));t.SetDrill(pcbnew.FromMM(.3));t.SetViaType(pcbnew.VIATYPE_THROUGH);t.SetNet(b.FindNet('GND'));b.Add(t)
    keep=[]
    oldviaxy={xy(t.GetPosition()) for t in old.GetTracks() if isinstance(t,pcbnew.PCB_VIA) and t.GetNetname()=='GND'}
    vias=[t for t in b.GetTracks() if isinstance(t,pcbnew.PCB_VIA) and t.GetNetname()=='GND']
    vias.sort(key=lambda t:xy(t.GetPosition()) not in oldviaxy)
    for v in vias:
        x,y=xy(v.GetPosition())
        near=next((q for q in keep if (x-xy(q.GetPosition())[0])**2+(y-xy(q.GetPosition())[1])**2<.55**2),None)
        if near:
            ground_path([(x,y),xy(near.GetPosition())]);b.RemoveNative(v)
        else:keep.append(v)
    # Mode labels on the user-facing surface; references/long values stay onFab.
    for item in list(b.GetDrawings()):
        if isinstance(item,pcbnew.PCB_TEXT) and item.GetText() in ('RUN 1-2','PROG 2-3','ALL 3 / POWER OFF'):b.RemoveNative(item)
    for text,where in [('RUN 1-2',(39.5,23)),('PROG 2-3',(39.5,34)),('ALL 3 / POWER OFF',(43,36))]:
        t=pcbnew.PCB_TEXT(b);t.SetText(text);t.SetPosition(V(*where));t.SetTextSize(V(.8,.8));t.SetTextThickness(pcbnew.FromMM(.12));t.SetLayer(pcbnew.F_SilkS);b.Add(t)
    b.BuildConnectivity();pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    # Stitch isolated top-side ground polygons directly to the continuous
    # In1 reference plane. All-layer copper masks and hole spacing are checked.
    r.prepare(r.nid('GND'),rt.TW)
    gndvias=[t for t in b.GetTracks() if isinstance(t,pcbnew.PCB_VIA) and t.GetNetname()=='GND']
    throughpads=[p for f in b.GetFootprints() for p in f.Pads() if max(p.GetDrillSize().x,p.GetDrillSize().y)>0]
    island_vias=[]
    for zone in b.Zones():
        if zone.GetLayer() not in (pcbnew.F_Cu,pcbnew.In2_Cu,pcbnew.B_Cu) or zone.GetNetname()!='GND':continue
        polygons=zone.GetFilledPolysList(zone.GetLayer())
        for i in range(polygons.OutlineCount()):
            poly=polygons.COutline(i)
            if any(polygons.Contains(v.GetPosition(),i) for v in gndvias):continue
            if any(p.GetNetname()=='GND' and poly.PointInside(p.GetPosition()) for p in throughpads):continue
            bb=poly.BBox();candidate=None
            x0,y0=xy(bb.GetOrigin());x1,y1=xy(bb.GetEnd())
            for ix in range(int((x1-x0)/.15)+1):
                if candidate:break
                for iy in range(int((y1-y0)/.15)+1):
                    x,y=x0+ix*.15,y0+iy*.15;p=V(x,y)
                    if not polygons.Contains(p,i):continue
                    cx,cy=r.cell(x,y)
                    if not (0<=cx<r.W and 0<=cy<r.H and r._viafree[cy,cx]):continue
                    if any((x-xy(v.GetPosition())[0])**2+(y-xy(v.GetPosition())[1])**2<.6**2 for v in gndvias):continue
                    if any((x-xy(p.GetPosition())[0])**2+(y-xy(p.GetPosition())[1])**2<(pcbnew.ToMM(max(p.GetDrillSize().x,p.GetDrillSize().y))/2+.15+.25)**2 for p in throughpads):continue
                    candidate=(x,y);break
            if candidate:
                v=pcbnew.PCB_VIA(b);v.SetPosition(V(*candidate));v.SetWidth(pcbnew.FromMM(.6));v.SetDrill(pcbnew.FromMM(.3));v.SetViaType(pcbnew.VIATYPE_THROUGH);v.SetNet(b.FindNet('GND'));b.Add(v);gndvias.append(v);island_vias.append(candidate)
    # R4 is permanentlyDNP. Its return polygon lost the r4 USB ground stitch
    # when the connector changed. Use a0.5/0.3 via beside that unused land.
    ground_path([(14.5,22.325),(13.9,22.44)])
    v=pcbnew.PCB_VIA(b);v.SetPosition(V(13.9,22.44));v.SetWidth(pcbnew.FromMM(.5));v.SetDrill(pcbnew.FromMM(.3));v.SetViaType(pcbnew.VIATYPE_THROUGH);v.SetNet(b.FindNet('GND'));b.Add(v)
    # Give the drill its required0.25mm clearance from the two inner-layer
    # control traces. These tiny parallel jogs do not alter any logical net.
    for net,start,end,offset in [('CC1',(15.5886,21.3903),(13.4701,23.5088),.06),('PD_CFG3',(16.3,19.4),(13.2,22.5),-.06)]:
        for t in list(b.GetTracks()):
            if isinstance(t,pcbnew.PCB_VIA) or t.GetNetname()!=net or t.GetLayer()!=pcbnew.In2_Cu:continue
            a,z=xy(t.GetStart()),xy(t.GetEnd())
            if any(abs(a[i]-start[i])>.001 or abs(z[i]-end[i])>.001 for i in (0,1)):continue
            pts=[a,(a[0]+offset,a[1]),(z[0]+offset,z[1]),z];b.RemoveNative(t)
            for u,w in zip(pts,pts[1:]):
                q=pcbnew.PCB_TRACK(b);q.SetStart(V(*u));q.SetEnd(V(*w));q.SetLayer(pcbnew.In2_Cu);q.SetWidth(pcbnew.FromMM(.127));q.SetNet(b.FindNet(net));b.Add(q)
    pcbnew.ZONE_FILLER(b).Fill(b.Zones());pcbnew.SaveBoard(str(P),b)
    (K/'sim/manual-finalize.json').write_text(json.dumps({'converter_loop':'restored fromr4','peripheral3V3_tree':'restored fromr4','new3V3_route':connected,'new_ground_stitch_vias':len(r.vias),'note':'run KiCad DRC after this operation'},indent=2)+'\n')
if __name__=='__main__':main()
