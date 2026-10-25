"""Prepare the independent A candidate; run with KiCad's Python."""
from pathlib import Path
import json
import pcbnew

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
GEN = HERE/'kicad/gen'

def main():
    b=pcbnew.LoadBoard(str(ROOT/'kicad/tab5-fpga-carrier.kicad_pcb'))
    poses={f.GetReference():[[round(pcbnew.ToMM(f.GetPosition().x),5),round(pcbnew.ToMM(f.GetPosition().y),5)],f.GetOrientationDegrees()] for f in b.GetFootprints()}
    poses.update({
      'J1':[[43,15],0], 'J2':[[32,30],270], 'U1':[[43,30.5],180],
      'R3':[[38,27],270], 'R4':[[38,30.5],270], 'R5':[[38,34],270],
      'R2':[[49.5,24],270], 'R1':[[49.5,27.5],270], 'C2':[[49.5,31],270],
      'F1':[[43,24],0], 'D1':[[49,16.5],90], 'D2':[[49,36.5],90],
      'D3':[[32.5,40],90], 'C1':[[41.5,40],0],
      'U2':[[40,63],0], 'L1':[[43,51.5],90], 'D4':[[33.5,57],180],
      'C3':[[33.5,61.3],90], 'C4':[[46.5,62],0], 'C5':[[46.5,66],0],
      'C6':[[46.5,69],0], 'C7':[[33.5,48.5],90], 'C8':[[33,73],0], 'C9':[[40,73],0],
      'R6':[[35,66.5],90], 'R7':[[32.5,65.5],90], 'R8':[[39.5,69],0], 'R9':[[43,69],0],
      'R49':[[31,69],0], 'R50':[[34.5,69],0],
      'SW3':[[33,6.5],0], 'SW1':[[62,7],0], 'SW2':[[71.2,7],0],
      'U3':[[61.5,13],0], 'C10':[[56.5,13],90], 'C11':[[66.5,13.5],90],
      'Q2':[[66.5,19],0], 'R41':[[59.5,41],90],
    })
    for i in range(4):
        poses['R'+str(42+i)]=[[119.2,61+i*2],0]
        poses['D'+str(5+i)]=[[123,61+i*2],0]
    for k in ('H1','H2'):poses.pop(k)
    (GEN/'placement.json').write_text(json.dumps(poses,indent=2)+'\n')
    lib=HERE/'kicad/lib/carrier.pretty'
    def footprint(name,desc,body,pads,holes=()):
        x0,y0,x1,y1=body
        s=[f'(footprint "{name}" (version 20241229) (generator "pcbnew") (layer "F.Cu")',f'(descr "{desc}")','(attr smd)',f'(fp_text reference "REF**" (at 0 {y1+1.5}) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))',f'(fp_text value "{name}" (at 0 {y1+3}) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))',f'(fp_rect (start {x0} {y0}) (end {x1} {y1}) (stroke (width 0.1) (type default)) (fill none) (layer "F.Fab"))']
        for num,x,y,w,h in pads:
            s.append(f'(pad "{num}" smd rect (at {x:.5f} {y:.5f}) (size {w} {h}) (layers "F.Cu" "F.Paste" "F.Mask"))')
        for x,y,d in holes:
            s.append(f'(pad "" np_thru_hole circle (at {x} {y}) (size {d} {d}) (drill {d}) (layers "*.Cu" "*.Mask"))')
        s.append(')')
        (lib/(name+'.kicad_mod')).write_text('\n'.join(s)+'\n')
    pads=[]
    for n in range(1,205):
        x=-31.65+(n-1)*.3 if n<=72 else 31.65-(204-n)*.3
        pads.append((str(n),x,4.1 if n%2 else -4.1,.35,2))
    pads.extend([('MP',-32.5,-12.1,4.5,4.6),('MP',32.5,-12.1,4.5,4.6)])
    footprint('DDR3_XDAP_4042044_20401','XDAP 204-pin STD 5.2mm socket; manufacturer T-11-0081 Rev B page2 recommended PCB',(-35.55,-21.75,35.55,5.1),pads,[(-33.4,0,1.6),(33.4,0,1.1)])
    socket=lib/'DDR3_XDAP_4042044_20401.kicad_mod'
    court=[(-35.8,5.35),(35.8,5.35),(35.8,-22),(32.25,-22),(32.25,-14.7),(30,-14.7),(30,-9.5),(32.25,-9.5),(32.25,-5.35),(-32.25,-5.35),(-32.25,-9.5),(-30,-9.5),(-30,-14.7),(-32.25,-14.7),(-32.25,-22),(-35.8,-22)]
    shapes=[]
    for a,z in zip(court,court[1:]+court[:1]):
        shapes.append(f'(fp_line (start {a[0]} {a[1]}) (end {z[0]} {z[1]}) (stroke (width .05) (type default)) (layer "F.CrtYd"))')
    socket.write_text(socket.read_text().rsplit(')',1)[0]+'\n'.join(shapes)+'\n)\n')
    footprint('L_COILMX_MS1040','COILMX MS1040 manufacturer recommended land pattern: 13.6 outer 5.4 inner 4.95 high',(-5.75,-5,5.75,5),[('1',-4.75,0,4.1,4.95),('2',4.75,0,4.1,4.95)])
    catalog=json.loads((GEN/'order_parts.json').read_text())
    selected={
      'XC6206P332MR-G|Package_TO_SOT_SMD:SOT-23':'C5446',
      '15u MS1040-150M|carrier:L_COILMX_MS1040':'C380054',
      'SOCKET XDAP-4042044-20401|carrier:DDR3_XDAP_4042044_20401':'C22471982',
      '1k|Resistor_SMD:R_0402_1005Metric':'C11702',
      '510R|Resistor_SMD:R_0603_1608Metric':'C23193',
      '510R|Resistor_SMD:R_0402_1005Metric':'C25123',
    }
    for key,pn in selected.items():
        catalog['parts'][key]={'lcsc':pn,'status':'variant candidate; stock/assembly preview required','url':f'https://www.lcsc.com/product-detail/{pn}.html'}
    (GEN/'order_parts.json').write_text(json.dumps(catalog,indent=2)+'\n')
    print('A candidate source prepared:',len(poses),'placement records')

if __name__=='__main__':main()
