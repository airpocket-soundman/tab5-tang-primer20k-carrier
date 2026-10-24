"""Exact interval coverage of TMDS centre lines, widths, roles and via geometry.
Run with KiCad Python. CHECK_PCB / CHECK_ROLES / CHECK_JSON support isolated
regressions. Position tolerance is 0.003mm; width tolerance is 0.001mm.
Vias are checked against a reviewed physical policy, not an EM parasitic model.
"""
import json
import math
import os
import sys
from pathlib import Path
import pcbnew

HERE = Path(__file__).resolve().parent
mm = pcbnew.ToMM
POS_TOL, WIDTH_TOL = .003, .001
LAYERS = ['F.Cu', 'In2.Cu', 'B.Cu']
ROLES = ('main', 'stub', 'strap', 'branch')

def segments(net, role_data):
    out = []
    for role, polylines in role_data.get(net, {}).items():
        if role not in ROLES:
            raise ValueError('Unknown role: '+role)
        for layer, points, width in polylines:
            layer = LAYERS[layer] if isinstance(layer, int) else layer
            for a, b in zip(points[:-1], points[1:]):
                out.append(dict(role=role, layer=layer, a=a, b=b, width=width))
    return out

def overlap(source, candidate):
    """Collinear overlap as a distance interval on source; point contacts do not count."""
    if source['layer'] != candidate['layer']:
        return None
    x, y = source['a']; dx=source['b'][0]-x; dy=source['b'][1]-y
    length=math.hypot(dx,dy)
    if length <= POS_TOL:
        return None
    ux,uy=dx/length,dy/length
    projected=[]
    for px,py in (candidate['a'],candidate['b']):
        if abs((px-x)*uy-(py-y)*ux) > POS_TOL:
            return None
        projected.append((px-x)*ux+(py-y)*uy)
    lo,hi=max(0,min(projected)),min(length,max(projected))
    return (lo,hi) if hi-lo > POS_TOL else None

def coverage(source, candidates):
    """Partition at every collinear endpoint; no midpoint-only/stale sampling shortcut."""
    length=math.dist(source['a'],source['b'])
    if length <= POS_TOL:
        return False, [], [], []
    intervals=[]; widths=[]
    for index,candidate in enumerate(candidates):
        span=overlap(source,candidate)
        if span is None:
            continue
        if abs(source['width']-candidate['width']) > WIDTH_TOL:
            widths.append(dict(span_mm=span, actual=source['width'], other=candidate['width']))
        else:
            intervals.append((span,index))
    cuts=sorted({0.,length}|{v for span,_ in intervals for v in span})
    gaps=[]; duplicates=[]
    for lo,hi in zip(cuts[:-1],cuts[1:]):
        if hi-lo <= POS_TOL:
            continue
        mid=(lo+hi)/2
        hits=[i for (a,b),i in intervals if a <= mid <= b]
        if not hits:
            gaps.append([lo,hi])
        elif len(hits)>1:
            duplicates.append(dict(span_mm=[lo,hi], candidates=hits))
    return not gaps and not widths, gaps, duplicates, widths

def via_record(board, via):
    p=via.GetPosition()
    return dict(net=via.GetNetname(), x=mm(p.x), y=mm(p.y), diameter_mm=mm(via.GetWidth(via.TopLayer())),
                drill_mm=mm(via.GetDrillValue()), type=int(via.GetViaType()),
                layers=[board.GetLayerName(via.TopLayer()),board.GetLayerName(via.BottomLayer())])

def audit(board, roles, policy):
    report=dict(nets={},unclassified=[],stale_roles=[],overlapping_roles=[],width_mismatches=[],via_errors=[],vias=[])
    counts={r:0 for r in ROLES}; counts['via_main']=0
    tracks=list(board.GetTracks())
    nets=sorted({t.GetNetname() for t in tracks if t.GetNetname().startswith(('HDMI_D','HDMI_CK'))}|set(roles))
    seen_vias=set()
    for net in nets:
        rs=segments(net,roles); copper=[]; vias=[]
        for track in tracks:
            if track.GetNetname()!=net: continue
            if isinstance(track,pcbnew.PCB_VIA):
                vias.append(track)
            else:
                a,b=track.GetStart(),track.GetEnd()
                copper.append(dict(layer=board.GetLayerName(track.GetLayer()),a=[mm(a.x),mm(a.y)],
                                   b=[mm(b.x),mm(b.y)],width=mm(track.GetWidth())))
        cls={r:0 for r in ROLES};cls.update(via_main=0,pcb_segments=len(copper),pcb_vias=len(vias))
        for segment in copper:
            ok,gaps,duplicates,widths=coverage(segment,rs)
            detail=dict(net=net,segment=segment)
            if gaps:report['unclassified'].append(dict(**detail,gaps_mm=gaps))
            if not ok and not gaps and not widths:
                report['unclassified'].append(dict(**detail,error='Degenerate segment at/below position tolerance'))
            if widths:report['width_mismatches'].append(dict(**detail,mismatches=widths))
            if duplicates:report['overlapping_roles'].append(dict(**detail,overlaps=duplicates))
            if ok and not duplicates:
                # Count once; a straight copper segment may cross several role boundaries.
                candidates=[r for r in rs if overlap(segment,r) is not None]
                role=max(candidates,key=lambda r: overlap(segment,r)[1]-overlap(segment,r)[0])['role']
                cls[role]+=1;counts[role]+=1
        for role in rs:
            ok,gaps,_duplicates,widths=coverage(role,copper)
            if not ok:report['stale_roles'].append(dict(net=net,role=role,gaps_mm=gaps,width_mismatch=bool(widths)))
        for via in vias:
            actual=via_record(board,via); report['vias'].append(actual)
            matches=[(i,v) for i,v in enumerate(policy['vias']) if v['net']==net and math.hypot(v['x']-actual['x'],v['y']-actual['y'])<=POS_TOL]
            geometry_ok=False
            if len(matches)==1:
                i,v=matches[0];seen_vias.add(i)
                geometry_ok=(abs(v['diameter_mm']-actual['diameter_mm'])<=WIDTH_TOL
                             and abs(v['drill_mm']-actual['drill_mm'])<=WIDTH_TOL
                             and v['layers']==actual['layers'] and v['type']==actual['type'])
            contact=any(math.dist([actual['x'],actual['y']],r[end])<=POS_TOL for r in rs for end in ('a','b'))
            if geometry_ok and contact:
                cls['via_main']+=1;counts['via_main']+=1
            else:
                report['via_errors'].append(dict(actual=actual,policy_matches=len(matches),geometry_ok=geometry_ok,role_contact=contact))
        report['nets'][net]=cls
    for i,via in enumerate(policy['vias']):
        if i not in seen_vias:report['via_errors'].append(dict(missing_expected_via=via))
    report.update(counts=counts,position_tolerance_mm=POS_TOL,width_tolerance_mm=WIDTH_TOL,
                  via_model=policy['model'], exclusions='Socket/connector in-pad lengths are reported by tmds_sparam.py; pad EM transitions and via parasitics are not modelled.')
    report['ok']=not any(report[k] for k in ('unclassified','stale_roles','overlapping_roles','width_mismatches','via_errors'))
    return report

def main():
    board=pcbnew.LoadBoard(os.environ.get('CHECK_PCB') or str(HERE.parent/'tab5-fpga-carrier.kicad_pcb'))
    roles=json.loads(Path(os.environ.get('CHECK_ROLES') or HERE/'tmds_roles.json').read_text())
    policy=json.loads((HERE/'tmds_via_policy.json').read_text())
    report=audit(board,roles,policy)
    output=os.environ.get('CHECK_JSON') or (str(HERE/'classification_report.json') if not os.environ.get('CHECK_PCB') and not os.environ.get('CHECK_ROLES') else None)
    if output:Path(output).write_text(json.dumps(report,indent=1)+'\n')
    print('TMDS classification:', 'OK' if report['ok'] else 'FAILED',report['counts'])
    print({k:len(report[k]) for k in ('unclassified','stale_roles','overlapping_roles','width_mismatches','via_errors')})
    sys.exit(0 if report['ok'] else 1)

if __name__=='__main__':main()
