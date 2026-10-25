from pathlib import Path
HERE=Path(__file__).resolve().parent
G=HERE/'kicad/gen'
p=G/'make_pcb.py';s=p.read_text(encoding='utf-8-sig')
s=s.replace('SetAuxOrigin(V(2.0,79.0))','SetAuxOrigin(V(28.0,79.0))')
p.write_text(s,encoding='utf-8')
# All unchanged parts inherit reviewed physical poses from the preserved PCB.
# New power parts use explicit reviewed coordinates; validation is separate.
p=G/'place_pcb.py';s=p.read_text(encoding='utf-8-sig')
s=s.replace('movable = [c for c in comps if not is_fixed(c)]','movable = []  # A: explicit candidate placement; inspect DRC and placement report')
p.write_text(s,encoding='utf-8')
p=G/'route_pcb.py';s=p.read_text(encoding='utf-8-sig')
start=s.index("    fixed('BUCK_PH',[ph,")
end=s.index("    # The initial routing tree",start)
s=s[:start]+'''    # A candidate: explicit short front-side switching loop, from actual pad coordinates.
    fixed('BUCK_PH',[ph,(43.5,60.295),(43.5,lp[1]),lp],.8)
    fixed('BUCK_PH',[ph,(40.0,58.0),(dk[0],58.0),dk],.8)
    cp=pad('BUCK_PH','C3.2')
    fixed('BUCK_PH',[cp,(dk[0],cp[1]),dk],.4)
    boot=pad('BUCK_BOOT','U2.1'); cb=pad('BUCK_BOOT','C3.1')
    fixed('BUCK_BOOT',[boot,(36.8,61.6),(35.5,cb[1]),cb],.25)
    vin=pad('VIN','U2.7'); ci=pad('VIN','C4.1')
    fixed('VIN',[vin,(44.0,vin[1]),ci],.8)
''' + s[end:]
p.write_text(s,encoding='utf-8')
# Remove original-board absolute-coordinate stitches, retaining generic repair.
p=G/'finish_pcb.py';s=p.read_text(encoding='utf-8-sig')
if '    # Confirmed left-column M5-Bus revision:' in s:
    start=s.index('    # Confirmed left-column M5-Bus revision:')
    end=s.index('    # 1) GND stub',start)
    s=s[:start]+s[end:]
p.write_text(s,encoding='utf-8')
print('A generation pipeline prepared')
