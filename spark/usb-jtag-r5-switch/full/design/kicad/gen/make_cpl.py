"""JLCPCB CPL generator for r5s: fit KiCad footprints to LCSC/EasyEDA official footprints.

For every part the KiCad numbered pads (centroid per pad number) and the EasyEDA numbered
pads are superposed by a quarter-turn rotation + translation (least squares).
CPL Rotation = theta, Mid X/Y = where the LCSC footprint origin falls in board
(Gerber-plot) coordinates.  Same method as spark/single-sided-r4
(assembly-placement-corrections.json); the r4 reproduction is part of the report.

Two refinements over a plain number fit (both are reported, neither touches copper):
  * pad numbers whose pad count differs between KiCad and EasyEDA (SOT-223 tab: KiCad
    pad "2" twice, EasyEDA pad "4") are left out of the fit and checked separately;
  * for polarised parts the EasyEDA *symbol* pin names are compared with the KiCad
    netlist pin functions.  If the numbers are electrically swapped (EasyEDA LED/diode:
    1=A,2=K; KiCad: 1=K,2=A) the fit uses the function-matched pad pairs, otherwise the
    anode would land on the cathode net.

Usage (KiCad python needed for pcbnew; EasyEDA JSON cache avoids network):
  "C:/Program Files/KiCad/10.0/bin/python.exe" make_cpl.py [--fetch] [--cache DIR]
Outputs: order/jlc-cpl.csv, order/placement-corrections.json, order/cpl-fit-report.md
EasyEDA data is third-party and is only cached outside the repository.
"""
import argparse, csv, hashlib, json, math, re, subprocess, time
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
R5S = HERE.parents[3]                     # .../usb-jtag-r5-switch
SPARK = R5S.parent
ORDER = R5S / 'order'
BOM = HERE.parent / 'bom-r5s.csv'
PCB = HERE.parent / 'tab5-fpga-carrier-r5s.kicad_pcb'
NETLIST = HERE.parent / 'sim/netlist.xml'
POS = ORDER / 'kicad-position.csv'
R4_JSON = SPARK / 'single-sided-r4/assembly-placement-corrections.json'
R4_PCB = SPARK / 'single-sided-r4/full/design/kicad/tab5-fpga-carrier.kicad_pcb'
R4_NETLIST = SPARK / 'single-sided-r4/full/design/kicad/sim/netlist.xml'
DEFAULT_CACHE = Path('C:/Users/YAMASH~1/AppData/Local/Temp/claude/f3adf9757f9941cf/'
                     'd5a7e40e-a1b0-4fd4-ae9a-f4ffa17fd89b/scratchpad/ee_cache')
EXCLUDE = {'J3', 'H1', 'H2', 'H3', 'H4', 'H5', 'H6'}
UNIT = 0.254  # mm per EasyEDA unit (10 mil)
OX, OY = 2.0, 79.0   # board (Gerber) origin in KiCad coordinates: X = x - 2, Y = 79 - y
POLAR_PREFIX = ('U', 'D', 'Q', 'J', 'SW')
POLAR_REFS = {'C1', 'C7'}
RESID_WARN = 0.3
# KiCad symbols with role-less pin names (generic TVS/ESD symbol A1/A2): the role of each
# footprint pad follows the KiCad footprint convention (D_SMB pad 1 = cathode) and the net
# (D3: pad 1 = VIN = + rail, unidirectional TVS cathode to the positive rail).
ROLE_OVERRIDE = {'D3': {'1': 'K', '2': 'A'}}
R4_POS_TOL = 0.05


# ---------------------------------------------------------------- inputs
def targets(path):
    out = {}
    with open(path, encoding='utf8', newline='') as f:
        for r in csv.DictReader(f):
            if r['DNP'].strip().lower() == 'true' or not r['LCSC'].strip():
                continue
            if r['Reference'] in EXCLUDE:
                continue
            out[r['Reference']] = r['LCSC'].strip()
    return out


def fetch(lcsc, cache):
    f = cache / f'{lcsc}.json'
    if f.exists():
        return
    cache.mkdir(parents=True, exist_ok=True)
    for attempt in range(8):
        url = f'https://easyeda.com/api/products/{lcsc}/components?version=6.4.19.5'
        subprocess.run(['curl', '-sS', url, '-o', str(f)], check=True)
        try:
            if json.loads(f.read_text(encoding='utf8')).get('success'):
                break
        except Exception:
            pass
        f.unlink(missing_ok=True)
        time.sleep(10 * (attempt + 1))
    time.sleep(2)


def norm_name(s):
    s = s.strip().upper()
    s = re.sub(r'_\d+$', '', s)          # KiCad "K_1" -> "K"
    return s


def ee_load(lcsc, cache):
    """-> dict(pads={num:[(x,y,w,h,shape,layer,hole,rot)]}, sym={num:name}, title, package)."""
    d = json.loads((cache / f'{lcsc}.json').read_text(encoding='utf8'))
    res = d['result']
    ds = res['packageDetail']['dataStr']
    hx, hy = float(ds['head']['x']), float(ds['head']['y'])
    pads = {}
    for s in ds['shape']:
        if not s.startswith('PAD~'):
            continue
        f = s.split('~')
        shape, x, y, w, h, layer, num = f[1], float(f[2]), float(f[3]), float(f[4]), float(f[5]), f[6], f[8]
        hole_r = float(f[9]) if f[9] else 0.0
        rot = float(f[11]) if len(f) > 11 and f[11] else 0.0
        pads.setdefault(num, []).append(((x - hx) * UNIT, -(y - hy) * UNIT, w * UNIT, h * UNIT,
                                         shape, layer, hole_r * UNIT, rot))
    sym = {}
    for s in res['dataStr'].get('shape', []):
        if s.startswith('P~'):
            secs = s.split('^^')
            hdr = secs[0].split('~')
            try:
                sym[hdr[3]] = secs[3].split('~')[4]
            except IndexError:
                pass
    return {'pads': pads, 'sym': sym, 'title': res.get('title', ''),
            'package': ds['head'].get('c_para', {}).get('package', '')}


def netlist_funcs(path):
    funcs = {}
    for net in ET.parse(path).getroot().iter('net'):
        for n in net.iter('node'):
            funcs[(n.get('ref'), n.get('pin'))] = n.get('pinfunction', '')
    return funcs


def kicad_load(board_path, refs):
    import pcbnew
    b = pcbnew.LoadBoard(str(board_path))
    res = {}
    for fp in b.GetFootprints():
        ref = fp.GetReference()
        if ref not in refs:
            continue
        pads = {}
        for p in fp.Pads():
            n = p.GetNumber()
            if n == '':
                continue
            pos = p.GetPosition()
            bb = p.GetBoundingBox()
            pads.setdefault(n, []).append((pcbnew.ToMM(pos.x) - OX, OY - pcbnew.ToMM(pos.y),
                                           pcbnew.ToMM(bb.GetWidth()), pcbnew.ToMM(bb.GetHeight())))
        o = fp.GetPosition()
        res[ref] = {'pads': pads, 'origin': (pcbnew.ToMM(o.x) - OX, OY - pcbnew.ToMM(o.y)),
                    'rot': fp.GetOrientationDegrees(), 'side': 'bottom' if fp.IsFlipped() else 'top',
                    'fpid': str(fp.GetFPID().GetLibItemName()), 'value': fp.GetValue()}
    return res


def read_pos_csv(path):
    out = {}
    with open(path, encoding='utf8', newline='') as f:
        for r in csv.DictReader(f):
            out[r['Ref']] = (float(r['PosX']), float(r['PosY']), float(r['Rot']), r['Side'])
    return out


# ---------------------------------------------------------------- geometry
def centroid(lst):
    return (sum(p[0] for p in lst) / len(lst), sum(p[1] for p in lst) / len(lst))


def rot(p, th):
    c, s = round(math.cos(math.radians(th))), round(math.sin(math.radians(th)))
    return (p[0] * c - p[1] * s, p[0] * s + p[1] * c)


def fit(kc, ec, pairs):
    """pairs: list of (k_nums tuple, e_num).  K position = centroid of all K pads of k_nums.
    Best of theta in 0/90/180/270 (CCW, y up); ties keep the smallest theta."""
    kpos = [centroid([q for n in ks for q in kc[n]]) for ks, _ in pairs]
    epos = [ec[e] for _, e in pairs]
    best, all_ = None, []
    for th in (0, 90, 180, 270):
        r = [rot(p, th) for p in epos]
        tx = sum(kpos[i][0] - r[i][0] for i in range(len(pairs))) / len(pairs)
        ty = sum(kpos[i][1] - r[i][1] for i in range(len(pairs))) / len(pairs)
        res = {'/'.join(pairs[i][0]) + '~' + pairs[i][1]: math.hypot(kpos[i][0] - (r[i][0] + tx), kpos[i][1] - (r[i][1] + ty))
               for i in range(len(pairs))}
        cand = {'theta': th, 'tx': tx, 'ty': ty, 'max': max(res.values()), 'res': res, 'pairs': pairs}
        all_.append(cand)
        if best is None or cand['max'] < best['max'] - 1e-9:
            best = cand
    best['ties'] = [c['theta'] for c in all_ if c['max'] < best['max'] + 0.02]
    return best


def geometry_fit(kall, eall):
    """Fallback when pad numbers cannot be paired (duplicate numbers, e.g. tact switch):
    align the centroid of all pads, pick the quarter-turn with the smallest worst
    nearest-pad distance (ties keep the smallest theta)."""
    kcen, ecen = centroid(kall), centroid(eall)
    best, all_ = None, []
    for th in (0, 90, 180, 270):
        r = [rot(p, th) for p in eall]
        c = centroid(r)
        tx, ty = kcen[0] - c[0], kcen[1] - c[1]
        ep = [(x + tx, y + ty) for x, y in r]
        d = max(max(min(math.hypot(a[0] - b[0], a[1] - b[1]) for b in ep) for a in kall),
                max(min(math.hypot(a[0] - b[0], a[1] - b[1]) for a in kall) for b in ep))
        cand = {'theta': th, 'tx': tx, 'ty': ty, 'max': d, 'res': {}, 'pairs': [], 'geometry': True}
        all_.append(cand)
        if best is None or cand['max'] < best['max'] - 1e-9:
            best = cand
    best['ties'] = [c['theta'] for c in all_ if c['max'] < best['max'] + 0.02]
    return best


TOKEN = re.compile(r'[A-Z]+\d+')


def number_pairs(k, e):
    """Pair K and E pads by number.  Numbers whose pad count differs are excluded; EE pads
    named as a merge of several K pads ('A1B12') are paired with all K pads they name."""
    kcnt = {n: len(v) for n, v in k['pads'].items()}
    ecnt = {n: len(v) for n, v in e['pads'].items()}
    common = sorted(set(kcnt) & set(ecnt))
    used = [n for n in common if kcnt[n] == ecnt[n]]
    pairs = [((n,), n) for n in used]
    merged = []
    for en in sorted(set(ecnt) - set(kcnt)):
        toks = TOKEN.findall(en)
        if len(toks) > 1 and all(t in kcnt for t in toks) and ''.join(toks) == en:
            pairs.append((tuple(toks), en))
            merged.append(en)
    return pairs, {'excluded_count_mismatch': sorted(set(common) - set(used)), 'merged': merged}


def leftovers(r, c):
    """Unpaired K pads: distance to the nearest EE pad after the fit (diagnostic only)."""
    usedk = {n for ks, _ in (c['pairs'] or []) for n in ks}
    boxes = []   # EE pad rectangles in board frame: (cx, cy, half w, half h)
    for lst in r['e']['pads'].values():
        for p in lst:
            x, y = rot((p[0], p[1]), c['theta'])
            w, h = eff_size(p, c['theta'])
            boxes.append((x + c['tx'], y + c['ty'], w / 2, h / 2))
    out = {}
    for n, lst in r['k']['pads'].items():
        if n in usedk:
            continue
        out[n] = max(min(math.hypot(max(abs(p[0] - b[0]) - b[2], 0), max(abs(p[1] - b[1]) - b[3], 0))
                         for b in boxes) for p in lst)
    return out


def fit_part(k, e):
    """Number-based fit (r4 method) with geometry fallback.  k/e as returned by the loaders."""
    kcnt = {n: len(v) for n, v in k['pads'].items()}
    ecnt = {n: len(v) for n, v in e['pads'].items()}
    kc = {n: [(p[0], p[1]) for p in v] for n, v in k['pads'].items()}
    ec = {n: centroid(v) for n, v in e['pads'].items()}
    pairs, info = number_pairs(k, e)
    out = {'k_only': sorted(set(kcnt) - set(ecnt)), 'e_only': sorted(set(ecnt) - set(kcnt)),
           'k_count': len(kcnt), 'e_count': len(ecnt), 'kc': kc, 'ec': ec, 'k': k, 'e': e}
    out.update(info)
    if len(pairs) >= 2:
        out['number'] = fit(kc, ec, pairs)
        out['number']['method'] = 'number'
    else:
        kall = [(p[0], p[1]) for v in k['pads'].values() for p in v]
        eall = [(p[0], p[1]) for v in e['pads'].values() for p in v]
        out['number'] = geometry_fit(kall, eall)
        out['number']['method'] = 'geometry'
    out['leftover'] = leftovers(out, out['number']) if out['number']['method'] == 'number' else {}
    return out


def func_map(kfun, esym, knums, enums):
    """K pad number -> E pad number by equal normalised pin name; None if not total/unique."""
    ek = {}
    for n, name in esym.items():
        ek.setdefault(norm_name(name), []).append(n)
    m = {}
    for n in knums:
        nm = norm_name(kfun.get(n, ''))
        if not nm or nm.startswith('PIN') or len(ek.get(nm, [])) != 1 or ek[nm][0] not in enums:
            return None
        m[n] = ek[nm][0]
    if len(set(m.values())) != len(m):
        return None
    return m


def eff_size(p, th):
    w, h, r = p[2], p[3], p[7]
    return (h, w) if int(round((r + th) / 90.0)) % 2 else (w, h)


def land_diff(k, e, mapping, th):
    """max abs size difference over matched pads (first pad of each number, board frame)."""
    worst = 0.0
    for kns, en in mapping:
        kp, ep = k['pads'][kns[0]][0], e['pads'][en][0]
        ew, eh = eff_size(ep, th)
        worst = max(worst, abs(kp[2] - ew), abs(kp[3] - eh))
    return worst


def norm_angle(a):
    return int(round(a)) % 360


def fmt(v):
    return f'{v:.6f}'


# ---------------------------------------------------------------- main computations
def fit_all(refs_lcsc, kpads, cache, kfuncs):
    out = {}
    for ref, lcsc in sorted(refs_lcsc.items()):
        k, e = kpads.get(ref), ee_load(lcsc, cache)
        if k is None:
            continue
        r = fit_part(k, e)
        r.update({'ref': ref, 'lcsc': lcsc, 'ee_title': e['title'], 'ee_package': e['package']})
        # symbol/function comparison (KiCad netlist pin function vs EasyEDA symbol pin name)
        kfun = {n: kfuncs.get((ref, n), '') for n in k['pads']}
        kfun.update(ROLE_OVERRIDE.get(ref, {}))
        r['kfun'] = kfun
        fm = func_map(kfun, e['sym'], list(k['pads']), set(e['pads']))
        r['func_map'] = fm
        r['polar'] = ref.startswith(POLAR_PREFIX) or ref in POLAR_REFS
        r['swapped'] = bool(fm) and any(a != b for a, b in fm.items())
        r['function'] = None
        if r['swapped']:
            pairs = [((a,), b) for a, b in fm.items() if a in r['kc'] and b in r['ec']
                     and len(k['pads'][a]) == len(e['pads'][b])]
            if len(pairs) >= 2:
                r['function'] = fit(r['kc'], r['ec'], pairs)
                r['function']['method'] = 'function'
        out[ref] = r
    return out


def chosen(r):
    return r['function'] if r['function'] else r['number']


def chosen_pairs(r):
    return chosen(r)['pairs']


# ---------------------------------------------------------------- r4 reproduction
def verify_r4(cache, fetch_missing=False):
    r4 = json.loads(R4_JSON.read_text(encoding='utf8'))['variants']['full']['placements']
    if fetch_missing:
        for v in r4.values():
            fetch(v['lcsc'], cache)
    kp = kicad_load(R4_PCB, set(r4))
    rows = {}
    for ref, v in sorted(r4.items()):
        if not (cache / f"{v['lcsc']}.json").exists() or ref not in kp:
            rows[ref] = {'status': 'no-data', 'lcsc': v['lcsc']}
            continue
        e = ee_load(v['lcsc'], cache)
        r = fit_part(kp[ref], e)
        n = r['number']
        d = math.hypot(n['tx'] - v['x_mm'], n['ty'] - v['y_mm'])
        rows[ref] = {'status': 'ok', 'lcsc': v['lcsc'], 'r4': (v['x_mm'], v['y_mm'], norm_angle(v['angle_deg'])),
                     'mine': (n['tx'], n['ty'], n['theta']), 'dist': d,
                     'angle_ok': n['theta'] == norm_angle(v['angle_deg']), 'pos_ok': d <= R4_POS_TOL,
                     'ties': n['ties'], 'excluded': r['excluded_count_mismatch'],
                     'prev': (v['previous']['x_mm'], v['previous']['y_mm'], v['previous']['angle_deg'])}
    return rows


def natural(ref):
    m = re.match(r'([A-Za-z]+)(\d+)', ref)
    return (m.group(1), int(m.group(2)))


def sha_lf(path):
    return hashlib.sha256(path.read_bytes().replace(b'\r\n', b'\n')).hexdigest()


def pin1_check(r, c, pairs):
    """Distance between K pad '1' (or first pad) and the corrected position of its matched EE pad."""
    mp = {ks[0]: (ks, e1) for ks, e1 in pairs}
    k1 = '1' if '1' in mp else (sorted(mp, key=lambda s: (len(s), s))[0] if mp else None)
    if k1 is None:
        return None
    ks, e1 = mp[k1]
    x, y = rot(r['ec'][e1], c['theta'])
    x, y = x + c['tx'], y + c['ty']
    kx, ky = centroid([q for n in ks for q in r['kc'][n]])
    return {'k_pad': k1, 'e_pad': e1, 'dist': math.hypot(kx - x, ky - y),
            'k_name': r['kfun'].get(k1, ''), 'e_name': r['e']['sym'].get(e1, '')}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--fetch', action='store_true', help='download missing EasyEDA JSON into the cache')
    ap.add_argument('--cache', default=str(DEFAULT_CACHE))
    a = ap.parse_args()
    cache = Path(a.cache)
    tg = targets(BOM)
    if a.fetch:
        for l in sorted(set(tg.values())):
            fetch(l, cache)
    kp = kicad_load(PCB, set(tg) | {'J3'})
    pos = read_pos_csv(POS)
    kfun = netlist_funcs(NETLIST)

    problems = []   # pcbnew pad frame vs supplied position CSV
    for ref in tg:
        k = kp[ref]
        px, py, pr, side = pos[ref]
        if k['side'] != 'top' or side != 'top':
            problems.append(f'{ref}: side {k["side"]}/{side}')
        if math.hypot(k['origin'][0] - px, k['origin'][1] - py) > 0.001:
            problems.append(f'{ref}: origin {k["origin"]} vs csv {px},{py}')
        if ((k['rot'] - pr + 180) % 360) - 180 > 0.01 or ((k['rot'] - pr + 180) % 360) - 180 < -0.01:
            problems.append(f'{ref}: rot {k["rot"]} vs csv {pr}')
    fits = fit_all(tg, kp, cache, kfun)
    r4rows = verify_r4(cache, fetch_missing=a.fetch)
    r4 = json.loads(R4_JSON.read_text(encoding='utf8'))['variants']['full']['placements']

    placements, cpl = {}, []
    for ref in sorted(fits, key=natural):
        r = fits[ref]
        c = chosen(r)
        px, py, pr, _ = pos[ref]
        pairs = chosen_pairs(r)
        r['pairs'] = pairs
        r['pin1'] = pin1_check(r, c, pairs)
        r['land_diff'] = land_diff(r['k'], r['e'], pairs, c['theta'])
        placements[ref] = {
            'x_mm': round(c['tx'], 6), 'y_mm': round(c['ty'], 6), 'angle_deg': c['theta'], 'lcsc': r['lcsc'],
            'previous': {'x_mm': px, 'y_mm': py, 'angle_deg': pr},
            'max_pad_center_residual_mm': round(c['max'], 4),
            'max_land_size_difference_mm': round(r['land_diff'], 3),
            'pad_matching': c['method'],
            'pads_fitted': len(pairs),
        }
        if r['function']:
            n = r['number']
            placements[ref]['number_match_alternative'] = {
                'x_mm': round(n['tx'], 6), 'y_mm': round(n['ty'], 6), 'angle_deg': n['theta'],
                'max_pad_center_residual_mm': round(n['max'], 4)}
        if r['excluded_count_mismatch']:
            placements[ref]['pads_excluded_count_mismatch'] = r['excluded_count_mismatch']
        cpl.append((ref, c['tx'], c['ty'], c['theta']))

    ORDER.mkdir(exist_ok=True)
    with (ORDER / 'jlc-cpl.csv').open('w', encoding='utf8', newline='') as f:
        w = csv.writer(f, lineterminator='\n')
        w.writerow(['Designator', 'Mid X', 'Mid Y', 'Layer', 'Rotation'])
        for ref, x, y, th in cpl:
            w.writerow([ref, fmt(x), fmt(y), 'top', th])
    ok = [x for x in r4rows.values() if x['status'] == 'ok']
    doc = {
        'date': date.today().isoformat(),
        'method': ('Official LCSC EasyEDA footprint fitted to the KiCad footprint by numbered pad centroids: '
                   'quarter-turn rotation (CCW, y up) + least-squares translation; CPL Mid X/Y is the LCSC footprint '
                   'origin in Gerber-plot coordinates (X=x_kicad-2, Y=79-y_kicad). Pad numbers whose pad count differs '
                   'between the two footprints are left out of the fit (SOT-223 tab). For polarised parts whose EasyEDA '
                   'symbol pin names show the pad numbers are electrically swapped against the KiCad netlist, the fit uses '
                   'the function-matched pads (pad_matching=function; number_match_alternative keeps the r4-style result). '
                   'Physical PCB unchanged. Supplier preview remains the final check.'),
        'board_sha256': sha_lf(PCB),
        'r4_reproduction': {'compared': len(ok),
                            'position_and_angle_ok': sum(1 for x in ok if x['pos_ok'] and x['angle_ok']),
                            'tolerance_mm': R4_POS_TOL},
        'placements': placements,
    }
    (ORDER / 'placement-corrections.json').write_text(json.dumps(doc, indent=2, ensure_ascii=False) + '\n', encoding='utf8')
    write_report(tg, fits, kp, pos, r4, r4rows, problems, doc)
    print('parts', len(cpl), 'problems', problems)


def pad_table(r, c):
    """Per-pad rows: K pad, E pad, K pos, fitted EE pos, residual, sizes."""
    rows = []
    for ks, en in c['pairs']:
        kx, ky = centroid([q for n in ks for q in r['kc'][n]])
        ex, ey = rot(r['ec'][en], c['theta'])
        kp, ep = r['k']['pads'][ks[0]][0], r['e']['pads'][en][0]
        ew, eh = eff_size(ep, c['theta'])
        d = math.hypot(kx - (ex + c['tx']), ky - (ey + c['ty']))
        rows.append((','.join(ks), en, kx, ky, ex + c['tx'], ey + c['ty'], d, kp[2], kp[3], ew, eh))
    return rows


NOTES = {
    'SW1': 'パッド番号が重複(KiCad 1,2 が各2枚)し番号照合不能。幾何(全パッド重心+最近傍距離)で補正。KiCad側ランド中心間隔9.4mm、LCSC側8.0mm。実装可否はプレビューで確認。',
    'SW2': 'SW1と同じ。',
    'Y1': 'KiCad側 FA238 4pin 3.2x2.5 と LCSC側 X322512MSB4SI のランド互換を下記で評価。',
    'U1': 'r4と同じ値(残差0.36)。EP(パッド11)ランド寸法差が主因。',
    'L1': 'r4と同じ値(残差0.84)。ランド長さが異なる(中心がずれる)。',
    'D1': '極性: 番号照合とピン名照合で向きが180度異なる(下記)。',
    'U10': 'r4は本体原点保持で66.0。最小二乗では+0.068mm。',
}


def write_report(tg, fits, kp, pos, r4, r4rows, problems, doc):
    L = []
    P = L.append
    ok = [(k, v) for k, v in r4rows.items() if v['status'] == 'ok']
    good = [k for k, v in ok if v['pos_ok'] and v['angle_ok']]
    bad = [(k, v) for k, v in ok if not (v['pos_ok'] and v['angle_ok'])]
    # r4 refs identical to r5s (ref, LCSC, position, orientation)
    same = []
    for ref, v in r4rows.items():
        if ref in fits and v['status'] == 'ok' and fits[ref]['lcsc'] == v['lcsc']:
            px, py, pr, _ = pos[ref]
            ppx, ppy, ppr = v['prev']
            if math.hypot(px - ppx, py - ppy) < 0.001 and (pr - ppr) % 360 < 0.01 or (pr - ppr) % 360 > 359.99 and math.hypot(px - ppx, py - ppy) < 0.001:
                same.append(ref)
    same_ok = []
    for ref in same:
        n = fits[ref]['number']
        v = r4rows[ref]
        if n['theta'] == v['r4'][2] and math.hypot(n['tx'] - v['r4'][0], n['ty'] - v['r4'][1]) <= R4_POS_TOL:
            same_ok.append(ref)
    P('# r5s CPL 補正レポート (JLCPCB 部品配置 / LCSC 公式フットプリント座標)')
    P('')
    P(f'- 作成日: {doc["date"]}  /  基板SHA256(LF正規化): `{doc["board_sha256"]}`')
    P(f'- 生成: `spark/usb-jtag-r5-switch/full/design/kicad/gen/make_cpl.py`(EasyEDA取得物は第三者データのためリポジトリ外のキャッシュ。キャッシュがあればネットワーク不要)')
    P(f'- 対象: {len(fits)} 部品(DNP・LCSC空欄・J3・H1-H6を除外)。すべて上面。裏面の実装対象部品なし(裏面はJ3のみで対象外)。')
    P('')
    P('> **限界**: これは公式ライブラリ座標への補正であり、業者の最終的な部品向きの確認ではない。注文時のプレビューで必ず確認する。')
    P('')
    P('## 1. 重要な所見(先に読むこと)')
    P('')
    sw = sorted([k for k, r in fits.items() if r['function']], key=natural)
    P(f'1. **極性の取り違えの可能性(r4にも波及)**: LCSC公式シンボルのピン名(A/K)とKiCadネットリストのピン機能を照合すると、{", ".join(sw)} は '
      '**パッド番号が電気的に入れ替わっている**(LCSC: 1=A,2=K、KiCad: 1=K,2=A。D3はKiCad側の役割をネット(パッド1=VIN=正側)から K と判断)。'
      '番号だけで重ねると、LCSCのカソードがKiCadのアノード側に載る(CPLの向きが180度逆)。'
      'ピン名で照合すると回転がKiCad向きと一致する(θ = KiCad回転)ため、こちらを `jlc-cpl.csv` に採用した。番号照合の結果は `placement-corrections.json` の `number_match_alternative` と下の表に残してある。'
      'SS54(C22452)のLCSCフットプリントはシルクのカソード棒がパッド2側にあり、シンボルのK=2と整合している。'
      '**r4のCPLは同じ参照名(D1-D8)で番号照合の値(逆向き側)になっているため、r4でも同じ問題がある可能性が高い。要確認。**')
    P('2. **SW1/SW2(C480272)**: KiCad側のパッド番号が重複していて番号照合できない。r4は角度270(残差1.75mm)だったが、パッド配置の幾何では 0 度(または180度、対称)が適合し、270度は合わない。r4の270度は誤りの可能性がある。r5sは 0 度とした。')
    P('3. 極性が機械的に確認できない部品: C1, C7(電解/タンタル。LCSCシンボルのピン名が「1」「2」のみ), D10, D11(同、ピン名なし)。番号照合(θ=KiCad回転)で配置したが、LCSC側のどちらが+/カソードかはデータから確認できない。プレビューで極性マークを確認すること。')
    P('')
    P('## 2. 方法')
    P('')
    P('1. KiCad側: `pcbnew.LoadBoard` の各フットプリントのパッドを番号ごとに重心化。座標は kicad-position.csv と同じ Gerber 座標(X = x_kicad - 2, Y = 79 - y_kicad)。')
    P('2. LCSC側: EasyEDA API の `packageDetail.dataStr` の `PAD~` を、部品原点(head.x, head.y)基準、0.254mm/unit、y を反転(y上向き)。番号ごとの重心。')
    P('3. 共通番号のパッド対を、LCSC座標を θ∈{0,90,180,270}度(反時計回り、y上向き)回して、最小二乗の平行移動 t を求めて KiCad へ合わせる。最大パッド中心残差が最小の θ を採用(同率は小さい θ)。CPL の Rotation = θ、Mid X/Y = t(LCSC原点が来るGerber座標)。')
    P('4. r4との差分(r4の手法の再現に必要だった取り扱い): (a) 両側でパッド数が異なる番号(SOT-223のタブ、PowerPAD、サーマルビア)は当てはめから外す。(b) LCSC側が複数のKiCadパッドを統合した名前(USB-Cの `A1B12` など)は、名前に含まれるKiCadパッド全部の重心と対応させる。(c) 番号が重複して照合できない部品(SW)は、全パッド重心の一致+最近傍距離で θ を選ぶ幾何照合に切り替える。(d) 上記の極性入れ替わりはピン名で対応を取る。')
    P('')
    P('座標原点と pcbnew のパッド座標が kicad-position.csv の位置・向きと一致することを全対象部品で確認済み' + ('。' if not problems else f'(不一致 {len(problems)} 件: {problems})。'))
    P('')
    P('## 3. r4 での再現検証(必須)')
    P('')
    P(f'- r4の `assembly-placement-corrections.json`(full)の {len(r4rows)} 部品に、同じ手法(番号照合のみ。極性のピン名補正は含めない)を r4 基板へ適用: **{len(good)}/{len(ok)} 件で位置0.05mm以内・角度一致({100*len(good)/len(ok):.1f}%)**。')
    P(f'- r5sと「同じ参照名・同じLCSC・同じ位置・同じ向き」の部品: {len(same)} 件、うちr4値を再現: **{len(same_ok)}/{len(same)} 件**。')
    P('')
    P('不一致:')
    P('')
    P('| 参照 | LCSC | r4 (x, y, 角度) | 本手法 | 位置差 mm | 理由 |')
    P('|---|---|---|---|---|---|')
    why = {'SW1': 'KiCadのパッド番号が重複(各2枚)。r4は番号重心で当てはめ残差1.75mmのまま270度を採用。本手法は幾何照合で0度(対称で0/180が同率)。r4側が疑わしい。',
           'SW2': 'SW1と同じ。',
           'U10': 'r4は「本体原点保持」(ランド長が非対称な部品の最小二乗バイアス回避)で66.0。最小二乗では66.068。角度は一致。位置差0.068mmで許容0.05mmをわずかに超過。'}
    for k, v in bad:
        P(f'| {k} | {v["lcsc"]} | ({v["r4"][0]:.3f}, {v["r4"][1]:.3f}, {v["r4"][2]}) | ({v["mine"][0]:.3f}, {v["mine"][1]:.3f}, {v["mine"][2]}) | {v["dist"]:.3f} | {why.get(k, "")} |')
    P('')
    P('一致した部品の中でも、r4が「本体原点保持」としていた非対称ランド部品(D1,D2,D4,L1,U1,C7 等)は、最小二乗でもr4と同じ座標になった(KiCad原点とLCSC原点が同じ位置のため)。J1 は r4が製造元図面の枠で x=12.0 としたのに対し本手法は 12.033(差0.033mm)、Q1-Q5,Q7,Q8,U9 は +0.021mm で、いずれも許容内。符号・原点・y反転・複数パッドの扱いは r4 と同じで矛盾なし。')
    P('')
    P('## 4. 要確認一覧')
    P('')
    P('残差が0.3mmを超える、パッド番号が合わない、極性が確認できない部品:')
    P('')
    P('| 参照 | LCSC | 区分 | 内容 |')
    P('|---|---|---|---|')
    for ref in sorted(fits, key=natural):
        r = fits[ref]; c = chosen(r)
        items = []
        if c['max'] > RESID_WARN:
            items.append(('残差', f'最大残差 {c["max"]:.3f}mm > {RESID_WARN}mm(ランド寸法差 {r["land_diff"]:.2f}mm)'))
        if c['method'] == 'geometry':
            items.append(('番号照合不能', NOTES.get(ref, '')))
        if r['k_only'] or r['e_only'] or r['excluded_count_mismatch']:
            lo = max(r['leftover'].values()) if r['leftover'] else 0
            items.append(('パッド番号', f'KiCadのみ {r["k_only"] or "-"} / LCSCのみ {r["e_only"] or "-"} / 個数不一致で除外 {r["excluded_count_mismatch"] or "-"}。未対応KiCadパッドとLCSCランドの最大距離 {lo:.2f}mm'
                          + ('(許容内)' if lo <= RESID_WARN else '(大きい)')))
        if r['function']:
            n = r['number']
            items.append(('極性', f'ピン名照合を採用(θ={c["theta"]})。番号照合なら θ={n["theta"]}(アノード/カソード逆)'))
        if ref in ('C1', 'C7', 'D10', 'D11'):
            items.append(('極性', 'LCSCシンボルにピン名がなく極性をデータで確認できない。番号照合(θ=KiCad回転)で配置。プレビューで確認'))
        if ref == 'Y1':
            items.append(('ランド互換', '下記 5.3 を参照'))
        for kind, txt in items:
            P(f'| {ref} | {r["lcsc"]} | {kind} | {txt} |')
    P('')
    P('## 5. 新規・再配置部品の詳細')
    P('')
    focus = ['U17', 'U19', 'Y1', 'D10', 'D11', 'J2', 'SW4', 'Q7', 'Q8']
    P('### 5.1 サマリ')
    P('')
    P('| 参照 | LCSC | KiCad FP | LCSC FP | パッド数 K/E/使用 | 最大残差 mm | ランド寸法差(最大) mm |')
    P('|---|---|---|---|---|---|---|')
    for ref in focus + ['R81', 'C85']:
        if ref not in fits:
            continue
        r = fits[ref]; c = chosen(r)
        P(f'| {ref} | {r["lcsc"]} | {r["k"]["fpid"]} | {r["ee_package"]} | {r["k_count"]}/{r["e_count"]}/{len(c["pairs"])} | {c["max"]:.3f} | {r["land_diff"]:.3f} |')
    P('')
    P('### 5.2 パッド別(小さい部品と J2)')
    for ref in ['Y1', 'D10', 'SW4', 'Q7', 'J2']:
        r = fits[ref]; c = chosen(r)
        P('')
        P(f'**{ref}** ({r["lcsc"]}, θ={c["theta"]}, Mid=({c["tx"]:.4f}, {c["ty"]:.4f}))')
        P('')
        P('| KiCad | LCSC | KiCad位置 | 補正後LCSC位置 | 残差 | KiCadランド w×h | LCSCランド w×h |')
        P('|---|---|---|---|---|---|---|')
        for t in pad_table(r, c):
            P(f'| {t[0]} | {t[1]} | ({t[2]:.3f}, {t[3]:.3f}) | ({t[4]:.3f}, {t[5]:.3f}) | {t[6]:.3f} | {t[7]:.2f}×{t[8]:.2f} | {t[9]:.2f}×{t[10]:.2f} |')
    for ref in ['U17', 'U19']:
        r = fits[ref]; c = chosen(r)
        rows = pad_table(r, c)
        w = max(rows, key=lambda t: t[6]); s = max(rows, key=lambda t: max(abs(t[7] - t[9]), abs(t[8] - t[10])))
        P('')
        P(f'**{ref}** ({r["lcsc"]}): {len(rows)} パッドすべて番号が対応。最大残差 {w[6]:.3f}mm(KiCadパッド{w[0]})、ランド寸法差の最大はパッド{s[0]}で KiCad {s[7]:.2f}×{s[8]:.2f} / LCSC {s[9]:.2f}×{s[10]:.2f}。')
    P('')
    P('### 5.3 Y1(水晶)のランド互換評価')
    r = fits['Y1']; c = chosen(r); rows = pad_table(r, c)
    kw = sorted({(round(t[7], 2), round(t[8], 2)) for t in rows}); ew = sorted({(round(t[9], 2), round(t[10], 2)) for t in rows})
    P('')
    P(f'- パッド4個とも番号が対応。回転 θ={c["theta"]}、最大パッド中心残差 {c["max"]:.3f}mm、ランド寸法差の最大 {r["land_diff"]:.3f}mm。KiCad側ランド {kw}、LCSC側ランド {ew}(mm、補正後の盤面向き)。')
    P('- 中心残差が小さく、はんだ付けはKiCadのランドに対しLCSCの推奨ランドが内包または大差なく重なる範囲。パッド番号1-4の対応(1,3が対角のはんだ端子、2,4がGND/NC)は番号一致で整合。')
    P('- ただし「機能(端子名)の一致」はLCSC側シンボルのピン名で確認していない。水晶の向きは端子1の位置で決まるので、プレビューで 1番ピンマーク位置を確認すること。')
    P('')
    P('## 6. 極性・ピン1の確認')
    P('')
    P('KiCad側ピン1パッドの位置と、補正後のLCSC側の対応パッドの位置の距離(`距離`)と、ピン名の対照。`θ-KiCad回転` が0なら、LCSCフットプリントがKiCadと同じ向きで載っている。')
    P('')
    P('| 参照 | 採用 | KiCad pad | LCSC pad | 距離 mm | KiCadピン名 | LCSCシンボルのピン名 | θ | KiCad回転 | θ-回転 | 判定 |')
    P('|---|---|---|---|---|---|---|---|---|---|---|')
    pol = [x for x in sorted(fits, key=natural) if fits[x]['polar'] or x.startswith(('LED', 'C1', 'C7'))]
    for ref in pol:
        r = fits[ref]; c = chosen(r); p1 = r['pin1']
        if p1 is None:
            P(f'| {ref} | {c["method"]} | - | - | - | - | - | {c["theta"]} | {kp[ref]["rot"]:.0f} | - | 番号照合不能(幾何照合)。ピン1の確認対象外(対称) |')
            continue
        d = (c['theta'] - kp[ref]['rot']) % 360
        res = '一致' if p1['dist'] <= RESID_WARN else '不一致(要確認)'
        if ref in ('C1', 'C7', 'D10', 'D11'):
            res += ' / 極性名なし(要プレビュー確認)'
        P(f'| {ref} | {c["method"]} | {p1["k_pad"]} | {p1["e_pad"]} | {p1["dist"]:.3f} | {p1["k_name"]} | {p1["e_name"]} | {c["theta"]} | {kp[ref]["rot"]:.0f} | {d:.0f} | {res} |')
    P('')
    P('「距離」は番号またはピン名で対応づけたペアの位置が一致するかの検査であり、対応付けが電気的に正しいか(極性)は「ピン名」列で見る。IC・コネクタは番号照合でピン1が一致。ピン名が入れ替わっていた部品は、本表では採用したピン名照合の結果。')
    P('')
    P('## 7. 全部品の残差表')
    P('')
    P('| 参照 | LCSC | 照合 | θ | Mid X | Mid Y | 最大残差 mm | ランド差 mm | パッド K/E/使用 | 備考 |')
    P('|---|---|---|---|---|---|---|---|---|---|')
    for ref in sorted(fits, key=natural):
        r = fits[ref]; c = chosen(r)
        note = []
        if r['function']:
            n = r['number']
            note.append(f'番号照合なら θ={n["theta"]},({n["tx"]:.3f},{n["ty"]:.3f})')
        if c['max'] > RESID_WARN:
            note.append('要確認')
        if ref in NOTES and ref not in ('D1',):
            note.append(NOTES[ref][:40])
        P(f'| {ref} | {r["lcsc"]} | {c["method"]} | {c["theta"]} | {c["tx"]:.4f} | {c["ty"]:.4f} | {c["max"]:.3f} | {r["land_diff"]:.2f} | {r["k_count"]}/{r["e_count"]}/{len(c["pairs"])} | {"; ".join(note)} |')
    P('')
    mx = max(fits.values(), key=lambda r: chosen(r)['max'])
    P(f'全体の最大パッド中心残差: {mx["ref"]} の {chosen(mx)["max"]:.3f}mm。')
    P('')
    P('## 8. 限界')
    P('')
    P('- これは公式ライブラリ座標への補正であり、業者の最終的な部品向きの確認ではない。注文時のプレビューで必ず確認する。')
    P('- 極性はLCSCシンボルのピン名とKiCadネットリストの機能名で照合した。LCSCフットプリントのシルク/3Dと実部品の向きの一致は確認していない。')
    P('- THT部品(J1, J2のスタッド, JP1, JP3, SW4)や大型コネクタも同じ方法でCPLに載せたが、業者が実装できるかは別問題。')
    P('- 座標は基板ファイルのパッド位置から算出。基板の部品位置は変更していない。')
    (ORDER / 'cpl-fit-report.md').write_text('\n'.join(L) + '\n', encoding='utf8')


if __name__ == '__main__':
    main()
