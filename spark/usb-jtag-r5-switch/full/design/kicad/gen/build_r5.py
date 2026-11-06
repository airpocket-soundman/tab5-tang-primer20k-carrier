"""Generate r5 KiCad schematic, BOM/net contract and placement-only PCB.

Never outputs manufacturing Gerbers. Land patterns follow archived TI drawings;
independent land-pattern review and high-speed/power routing remain release gates.
"""
from pathlib import Path
import csv, json, copy, sys
import design, make_sch as sch, sexp

HERE=Path(__file__).resolve().parent
K=HERE.parent

def custom_symbol(name, pins):
    # Single-unit symbols avoid losing multi-unit gate power pins during export.
    symbol=copy.deepcopy(sch.get_symbol('Connector_Generic','Conn_02x08_Odd_Even'))
    symbol[1]=sch.S(name)
    for p in sexp.find(symbol,'property'):
        if p[1]=='Reference':p[2]=sch.S('U')
        elif p[1]=='Value':p[2]=sch.S(name)
    for child in sexp.find(symbol,'symbol'):
        child[1]=sch.S(str(child[1]).replace('Conn_02x08_Odd_Even',name))
        for p in list(sexp.find(child,'pin')):
            n=str(sexp.first(p,'number')[1])
            if n not in pins:child.remove(p);continue
            label,kind=pins[n];p[1]=kind
            sexp.first(p,'name')[1]=sch.S(label)
    return symbol

orig_write=sch.write_lib
def write_lib():
    orig_write()
    p=K/'lib/carrier.kicad_sym';lib=sexp.parse(p.read_text(encoding='utf8'))
    ft=copy.deepcopy(sch.get_symbol('Interface_USB','FT232H'))
    ft[1]=sch.S('FT232H_5V')
    for child in sexp.find(ft,'symbol'):
        child[1]=sch.S(str(child[1]).replace('FT232H_','FT232H_5V_',1))
        for pin in sexp.find(child,'pin'):
            n=str(sexp.first(pin,'number')[1])
            if n in ('37','38','39'):pin[1]='power_out'
            if n=='44':pin[1]='output'
    # Datasheet5V mode: VCCD is an OUTPUT; EECLK is always an output.
    lib.append(ft)
    lib.append(custom_symbol('SW_SLIDE_DP3T_SS-23D03',{str(i):(n,'passive') for i,n in [
        (1,'A_RUN'),(2,'A_MID_NC'),(3,'A_PGM'),(4,'A_COM'),(5,'B_COM'),(6,'B_PGM'),(7,'B_MID_NC'),(8,'B_RUN'),(9,'SH'),(10,'SH')]}))
    lib.extend([
      custom_symbol('CH224A',{str(i):(n,t) for i,n,t in [
        (1,'VHV','power_in'),(2,'CFG2/SCL','input'),(3,'CFG3/SDA','input'),(4,'DP','passive'),(5,'DM','passive'),
        (6,'CC2','passive'),(7,'CC1','passive'),(8,'VBUS','input'),(9,'CFG1','input'),(10,'PG','open_collector'),(11,'GND','power_in')]}),
      custom_symbol('TPS259470A',{str(i):(n,t) for i,n,t in [
        (1,'EN/UVLO','input'),(2,'OVLO','input'),(3,'AUXOFF','open_collector'),(4,'~{FLT}','open_collector'),
        (5,'IN','power_in'),(6,'OUT','passive'),(7,'DVDT','passive'),(8,'GND','power_in'),(9,'ILM','passive'),(10,'ITIMER','passive')]}),
      custom_symbol('TPS630701',{str(i):(n,t) for i,n,t in [
        (1,'PS/SYNC','input'),(2,'PG','open_collector'),(3,'VAUX','passive'),(4,'GND','power_in'),(5,'FB','input'),(6,'FB2','passive'),
        (7,'VOUT','power_out'),(8,'VOUT','passive'),(9,'L2','passive'),(10,'PGND','power_in'),(11,'L1','passive'),
        (12,'VIN','power_in'),(13,'VIN','passive'),(14,'EN','input'),(15,'VSEL','input')]}),
      custom_symbol('TPS2553DBV',{str(i):(n,t) for i,n,t in [(1,'IN','power_in'),(2,'GND','power_in'),(3,'EN','input'),(4,'~{FAULT}','open_collector'),(5,'ILIM','passive'),(6,'OUT','power_out')]}),
      custom_symbol('SN74LVC125A',{str(i):(n,t) for i,n,t in [
        (1,'~{OE1}','input'),(2,'A1','input'),(3,'Y1','tri_state'),(4,'~{OE2}','input'),(5,'A2','input'),(6,'Y2','tri_state'),(7,'GND','power_in'),
        (8,'Y3','tri_state'),(9,'A3','input'),(10,'~{OE3}','input'),(11,'Y4','tri_state'),(12,'A4','input'),(13,'~{OE4}','input'),(14,'VCC','power_in')]})])
    p.write_text(sexp.dump(lib)+'\n',encoding='utf8');sch._lib_cache.pop('carrier',None)
sch.write_lib=write_lib

def footprint(name,pads,body):
    lines=[f'(footprint "{name}" (version 20241229) (generator "r5_land_pattern") (layer "F.Cu") (attr smd)',
      ' (property "Reference" "REF**" (at 0 -2.5) (layer "F.SilkS") (effects (font (size 0.8 0.8) (thickness 0.12))))',
      f' (property "Value" "{name}" (at 0 2.5) (layer "F.Fab") (effects (font (size 0.8 0.8) (thickness 0.12))))',
      f' (fp_rect (start {-body[0]/2} {-body[1]/2}) (end {body[0]/2} {body[1]/2}) (stroke (width 0.1) (type default)) (fill none) (layer "F.Fab"))',
      ' (fp_rect (start -1.8 -1.9) (end 1.8 1.9) (stroke (width 0.05) (type default)) (fill none) (layer "F.CrtYd"))',
      ' (fp_circle (center -1.55 -1.6) (end -1.45 -1.6) (stroke (width 0.1) (type default)) (fill solid) (layer "F.SilkS"))']
    # Rectangular regions sharing a pad number form the TI non-rectangular lands.
    # Mask/paste region overlap must be independently reviewed before manufacture.
    for n,x,y,w,h in pads:
        lines.append(f' (pad "{n}" smd rect (at {x} {y}) (size {w} {h}) (layers "F.Cu" "F.Paste" "F.Mask") (solder_mask_margin 0.05))')
    lines.append(')')
    (K/'lib/carrier.pretty'/f'{name}.kicad_mod').write_text('\n'.join(lines)+'\n',encoding='utf8')

def land_patterns():
    # TI RPW0010A land-pattern example4225183/A page73, top view.
    pads=[]
    for n,y in [(1,-.875),(2,-.225),(3,.225),(4,.875)]:pads.append((n,-.9,y,.6,.3))
    for n,y in [(10,-.875),(9,-.225),(8,.225),(7,.875)]:pads.append((n,.9,y,.6,.3))
    pads += [(1,-.725,-.9625,.25,.475),(4,-.725,.9625,.25,.475),
             (10,.725,-.9625,.25,.475),(7,.725,.9625,.25,.475),
             (5,-.2375,0,.3,2.4),(6,.2375,0,.3,2.4)]
    footprint('TI_RPW0010A',pads,(2,2))
    # TI RNM0015A land-pattern example4222000/B page40.
    pads=[(n,-1.15,y,.6,.25) for n,y in [(1,-.75),(2,-.25),(3,.25),(4,.75)]]
    pads += [(15,-.725,-1.4,.25,.6),(14,-.225,-1.4,.25,.6),(5,-.725,1.4,.25,.6),(6,-.225,1.4,.25,.6)]
    pads += [(13,.3,-1.3875,.25,.525),(12,.8,-1.3875,.25,.525),(13,.55,-1.25,.75,.25),
             (7,.3,1.3875,.25,.525),(8,.8,1.3875,.25,.525),(7,.55,1.25,.75,.25),
             (11,.55,-.5,1.35,.25),(10,.3625,0,1.725,.25),(9,.55,.5,1.35,.25)]
    # 12/13 are VIN, 7/8 are VOUT: touching paired lands are intentional.
    footprint('TI_RNM0015A',pads,(2.5,3))

def generate():
    # Manual selector revision reuses the r4 power footprints.
    sch.BLOCK_ORIGIN.update({'r5power':(30,800,700),'usbjtag':(800,800,780)})
    # Captions are deliberately explicit about the new stage.
    src=Path(sch.__file__).read_text(encoding='utf8')
    src=src.replace('"buck": "VIN -> +5V buck (TPS5430)"','"buck": "VIN -> BUCK_5V (r4 TPS5430 retained)"')
    src=src.replace('"core": "Tang Primer 20K Core SODIMM socket (pin names = nets)"',
       '"r5power": "R5S: SW4 slide switch (JP2+JP4 linked) 1=RUN 3=PROGRAM 2=OFF; JP3 still manual; change only UNPOWERED", "usbjtag": "R5 MANUAL: FT232H USB-JTAG, NO EEPROM; direct SODIMM JTAG143/147/149/153", "core": "Tang Primer 20K Core SODIMM socket (pin names = nets)"')
    src=src.replace('["paper", S("A0")]', '["paper", S("User"), "1800", "1250"]')
    src=src.replace('S("2026-10-22")','S("2026-11-03")').replace('S("0.1")','S("r5 engineering candidate")')
    a=src.index('    for i, net in enumerate([')
    z=src.index('):',a)+2
    src=src[:a]+'    for i, net in enumerate(["GND", "+5V", "HDMI_5V", "VIN", "PD_VDD", "DC_RAW", "VBUS_PD", "TAB_3V3"]):'+src[z:]
    # Keep modifications reviewable in the actual local generator.
    Path(sch.__file__).write_text(src,encoding='utf8')
    # Reload after the local generator edit, then restore library extension.
    import importlib
    importlib.reload(sch)
    global orig_write
    orig_write=sch.write_lib;sch.write_lib=write_lib
    sch.BLOCK_ORIGIN.update({'r5power':(30,800,700),'usbjtag':(800,800,780)})
    sch.build_sch();sch.write_project_files()
    cs=design.build()
    with (K/'bom-r5s.csv').open('w',newline='',encoding='utf8') as f:
        w=csv.writer(f);w.writerow(['Reference','Value','Footprint','DNP','LCSC','Comment'])
        for c in cs:w.writerow([c.ref,c.value,c.fp,c.dnp,c.lcsc,c.comment])
    (K/'circuit-contract.json').write_text(json.dumps({c.ref:{'value':c.value,'pins':c.pins,'footprint':c.fp,'dnp':c.dnp} for c in cs},indent=2)+'\n',encoding='utf8')
    print('r5 schematic, BOM, electrical contract generated:',len(cs),'components')

if __name__=='__main__':generate()
