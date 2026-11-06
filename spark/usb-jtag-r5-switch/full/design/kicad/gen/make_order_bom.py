"""r5s: JLCPCB PCBA BOM and the separate LCSC purchase list (normal python).

Reads bom-r5s.csv, writes into spark/usb-jtag-r5-switch/order/:
  jlc-bom.csv            parts for the JLCPCB PCBA order (SMT + through-hole candidates)
  lcsc-separate-order.csv parts to buy from LCSC separately (NOT in the PCBA order)
  manual-assembly.csv    refs that are never in the PCBA order
  dnp.csv                refs that are not fitted
Part numbers were checked on the JLCPCB part pages (MPN/package/class); stock was NOT checked.
"""
import csv, re
from pathlib import Path
K = Path(__file__).resolve().parents[1]
OUT = K.parents[2] / 'order'
OUT.mkdir(exist_ok=True)

def nat(ref):
    return [int(t) if t.isdigit() else t for t in re.split(r'(\d+)', ref)]

rows = list(csv.DictReader((K / 'bom-r5s.csv').open(encoding='utf8')))
MANUAL = {'J3'}                              # bottom-side 2x15 header for the Tab5: hand soldered
HOLES = {r['Reference'] for r in rows if r['Reference'].startswith('H')}
THT_CANDIDATES = {'J1', 'JP1', 'JP3', 'SW4'}   # through-hole / wave-solder class: supplier option or hand solder

pcba, dnp, manual = [], [], []
for r in rows:
    ref = r['Reference']
    if r['DNP'] == 'True':
        dnp.append(r); continue
    if ref in MANUAL or ref in HOLES:
        manual.append(r); continue
    assert r['LCSC'], ('no LCSC number for a PCBA part', ref)
    pcba.append(r)

groups = {}
for r in pcba:
    groups.setdefault((r['Value'], r['Footprint'], r['LCSC']), []).append(r['Reference'])
with (OUT / 'jlc-bom.csv').open('w', encoding='utf8', newline='') as f:
    w = csv.writer(f)
    w.writerow(['Comment', 'Designator', 'Footprint', 'LCSC Part #'])
    for (val, fp, lc), refs in sorted(groups.items(), key=lambda kv: nat(sorted(kv[1], key=nat)[0])):
        w.writerow([val, ','.join(sorted(refs, key=nat)), fp, lc])

def grp(rows_, action):
    g = {}
    for r in rows_:
        g.setdefault((r['Value'], r['Footprint']), []).append(r['Reference'])
    return [[','.join(sorted(v, key=nat)), k[0], k[1], action] for k, v in sorted(g.items(), key=lambda kv: nat(sorted(kv[1], key=nat)[0]))]

with (OUT / 'manual-assembly.csv').open('w', encoding='utf8', newline='') as f:
    w = csv.writer(f); w.writerow(['Refs', 'Value', 'Footprint', 'Action'])
    w.writerows(grp([r for r in manual if r['Reference'] in MANUAL], 'manual / not in PCBA (bought from LCSC separately)'))
    w.writerows(grp([r for r in manual if r['Reference'] in HOLES], 'mounting hole / no part in PCBA'))
with (OUT / 'dnp.csv').open('w', encoding='utf8', newline='') as f:
    w = csv.writer(f); w.writerow(['Refs', 'Value', 'Footprint'])
    for row in grp(dnp, ''): w.writerow(row[:3])

# ---- separate LCSC purchase list (per board; the order-quantity columns assume 2 and 5 boards)
lc = {r['Reference']: r for r in rows}
def need(ref): return lc[ref]
purchase = [
  # group, refs, qty/board, LCSC, value, footprint, note
  ('A 必須: PCBAに含めない', 'J3', 1, need('J3')['LCSC'], '2.54-2*15P (2x15 pin header)', 'carrier:PinHeader_2x15_Tab5_Bottom',
   'Tab5 M5-Bus用。基板の裏面。手はんだ。JLCPCB分類はextended・THT(r4と同じ扱い)'),
  ('A 必須: PCBAに含めない', 'JP1, JP3 用のショートプラグ', 2, 'C5305', '2.54mm 1x2 shunt (open top)', '(ヘッダに挿す部品)',
   'JP1=バスARM(1-2に挿すとTab5側の電源が正常な時にバス接続を許可、2-3は保管位置)、JP3=Tab5給電の選択(1-2=給電、2-3=保管=停止)。JLCPCB分類 extended / Wave Soldering'),
  ('B 条件付き: 業者がTHT実装できない場合に別途購入', 'SW4', 1, need('SW4')['LCSC'], 'SS-23D03-G080 (DP3T slide switch)', need('SW4')['Footprint'],
   'JLCPCB分類 extended / Wave Soldering。PCBA BOMには載せてある。実物のピン対応の導通確認が必要'),
  ('B 条件付き: 業者がTHT実装できない場合に別途購入', 'JP3', 1, need('JP3')['LCSC'], '2.54-1*3P pin header', need('JP3')['Footprint'],
   'JLCPCB分類 extended / Wave Soldering。PCBA BOMには載せてある'),
  ('B 条件付き: 業者がTHT実装できない場合に別途購入', 'J1', 1, need('J1')['LCSC'], 'DC-005-5A-2.0 (barrel jack)', need('J1')['Footprint'],
   'r4と同じ候補。JLCPCB分類 extended。PCBA BOMには載せてある'),
  ('B 条件付き: 業者がTHT実装できない場合に別途購入', 'JP1', 1, need('JP1')['LCSC'], '2.54-1*3P pin header (BUS ARM, 1x3)', need('JP1')['Footprint'],
   'JP3と同じ部品。3番ピンは未接続(ショートプラグの保管位置)。JLCPCB分類 extended / Wave Soldering。PCBA BOMには載せてある'),
  ('C 未選定: 基板に実装しない(DNP)', 'J6, J7', 2, '', 'PMOD 2x6 pin header', 'Connector_PinHeader_2.54mm:PinHeader_2x06_P2.54mm_Vertical',
   'LCSC番号は未選定。必要になったら選ぶ'),
  ('C 未選定: 基板に実装しない(DNP)', 'J8', 1, '', 'GPIO pads 1x9 pin header', 'Connector_PinHeader_2.54mm:PinHeader_1x09_P2.54mm_Vertical',
   'LCSC番号は未選定。必要になったら選ぶ'),
  ('D LCSC以外(ユーザー支給)', 'Tab5', 1, '', 'M5Stack Tab5', '-', 'ユーザー購入'),
  ('D LCSC以外(ユーザー支給)', 'Tang Primer 20K Core', 1, '', 'Sipeed Tang Primer 20K Core', '-', 'ユーザー購入。SODIMMソケット(J4)に挿す'),
  ('D LCSC以外(ユーザー支給)', 'H1-H6', 6, '', 'M3 mounting hardware', 'MountingHole_3.2mm_M3', 'M3ねじ・スペーサ。LCSC部品ではない'),
]
with (OUT / 'lcsc-separate-order.csv').open('w', encoding='utf8', newline='') as f:
    w = csv.writer(f)
    w.writerow(['Group', 'Refs', 'Qty per board', 'Qty x2 boards', 'Qty x5 boards', 'LCSC Part #', 'Value', 'Footprint', 'Note'])
    for g, refs, q, lcn, val, fp, note in purchase:
        w.writerow([g, refs, q, q * 2, q * 5, lcn, val, fp, note])

print('PCBA BOM rows', len(groups), 'designators', len(pcba), 'manual', len(manual), 'dnp', len(dnp), 'purchase rows', len(purchase))
