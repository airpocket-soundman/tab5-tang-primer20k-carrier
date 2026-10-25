"""Write the two drawing-derived footprints used by lite C. Standard Python."""
from pathlib import Path

LIB = Path(__file__).resolve().parents[1] / 'lib/carrier.pretty'

def write_socket():
    lines = ['(footprint "SODIMM_XDAP_4042044_20401" (version 20211014) (generator pcbnew)',
             '(layer "F.Cu")', '(attr smd)',
             '(descr "XDAP-4042044-20401 STD 5.2mm, drawing T-11-0081 sheet2 RevB; 204 contacts, two hold-down lands")',
             '(fp_text reference "J4" (at 0 6.5) (layer "F.SilkS") (effects (font (size 1 1) (thickness .15))))',
             '(fp_text value "SOCKET XDAP-4042044-20401" (at 0 7.8) (layer "F.Fab") (effects (font (size 1 1) (thickness .15))))']
    for n in range(1, 205):
        x = -31.65 + (n - 1) * .3 if n <= 72 else 31.65 - (204 - n) * .3
        y = 4.1 if n % 2 else -4.1
        lines.append(f'(pad "{n}" smd rect (at {x:.3f} {y} 270) (size 2 .35) (layers "F.Cu" "F.Paste" "F.Mask"))')
    for x, d in [(-33.4, 1.6), (33.4, 1.1)]:
        lines.append(f'(pad "" np_thru_hole circle (at {x} 0) (size {d} {d}) (drill {d}) (layers "*.Cu" "*.Mask"))')
    for x in (-32.5, 32.5):
        lines.append(f'(pad "MP" smd rect (at {x} -12.1) (size 4.5 4.6) (layers "F.Cu" "F.Paste" "F.Mask"))')
    # Socket body is U-shaped, not a solid rectangle over the Core card.
    pts = [(-35.55, 5.1), (35.55, 5.1), (35.55, -21.75), (32.5, -21.75), (32.5, -5.1), (-32.5, -5.1), (-32.5, -21.75), (-35.55, -21.75)]
    for a, b in zip(pts, pts[1:]+pts[:1]):
        lines.append(f'(fp_line (start {a[0]} {a[1]}) (end {b[0]} {b[1]}) (layer "F.Fab") (width .12))')
    # Body +0.25mm, with separate shoulders around the hold-down lands.
    pts = [(-35.8,5.35),(35.8,5.35),(35.8,-22),(32.25,-22),
           (32.25,-14.65),(30,-14.65),(30,-9.55),(32.25,-9.55),
           (32.25,-5.35),(-32.25,-5.35),(-32.25,-9.55),(-30,-9.55),
           (-30,-14.65),(-32.25,-14.65),(-32.25,-22),(-35.8,-22)]
    for a,b in zip(pts,pts[1:]+pts[:1]):
        lines.append(f'(fp_line (start {a[0]} {a[1]}) (end {b[0]} {b[1]}) (layer "F.CrtYd") (width .05))')
    lines += ['(fp_text user "1" (at -32.8 4.1) (layer "F.Fab") (effects (font (size .8 .8) (thickness .1))))', ')']
    (LIB / 'SODIMM_XDAP_4042044_20401.kicad_mod').write_text('\n'.join(lines)+'\n', encoding='utf-8')

def write_inductor():
    lines = ['(footprint "L_COILMX_MS1040" (version 20211014) (generator pcbnew)',
             '(layer "F.Cu") (attr smd)',
             '(descr "COILMX MS1040 series recommended PCB pattern: outer 13.6 inner 5.4 height 4.95 mm")',
             '(fp_text reference "L1" (at 0 -5.8) (layer "F.SilkS") (effects (font (size 1 1) (thickness .15))))',
             '(fp_text value "15uH MS1040" (at 0 5.8) (layer "F.Fab") (effects (font (size 1 1) (thickness .15))))',
             '(pad "1" smd rect (at -4.75 0) (size 4.1 4.95) (layers "F.Cu" "F.Paste" "F.Mask"))',
             '(pad "2" smd rect (at 4.75 0) (size 4.1 4.95) (layers "F.Cu" "F.Paste" "F.Mask"))']
    for layer, x, y in [('F.Fab', 5.75, 5.15)]:
        pts = [(-x,-y),(x,-y),(x,y),(-x,y)]
        for a,b in zip(pts,pts[1:]+pts[:1]):
            lines.append(f'(fp_line (start {a[0]} {a[1]}) (end {b[0]} {b[1]}) (layer "{layer}") (width .05))')
    # Follow the union of maximum body (11.5 x 10.3) and the two lands,
    # with 0.25 mm assembly allowance; the empty corners are not body.
    pts=[(-6,-5.4),(6,-5.4),(6,-2.725),(7.05,-2.725),(7.05,2.725),(6,2.725),
         (6,5.4),(-6,5.4),(-6,2.725),(-7.05,2.725),(-7.05,-2.725),(-6,-2.725)]
    for a,b in zip(pts,pts[1:]+pts[:1]):
        lines.append(f'(fp_line (start {a[0]} {a[1]}) (end {b[0]} {b[1]}) (layer "F.CrtYd") (width .05))')
    lines.append(')')
    (LIB/'L_COILMX_MS1040.kicad_mod').write_text('\n'.join(lines)+'\n', encoding='utf-8')

if __name__ == '__main__':
    write_socket()
    write_inductor()
    print('Wrote lite C socket and inductor drawing-derived land patterns')
