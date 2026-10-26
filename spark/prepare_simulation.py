"""Copy established models into the isolated Spark study and bind actual CAD."""
from pathlib import Path
import shutil
H=Path(__file__).resolve().parent;SOURCE=H.parents[1]/'tab5-tang-primer20k-carrier-audit-pages'
P=H/'simulation/parallel';W=H/'simulation/power'
P.mkdir(parents=True,exist_ok=True);W.mkdir(parents=True,exist_ok=True)
for name in ('extract_paths.py','run_waveforms.py','run_final_selected.py','periodic_link.py','ngspice_shared.py'):
 shutil.copyfile(SOURCE/'variants/simulation/parallel'/name,P/name)
p=P/'extract_paths.py';s=p.read_text(encoding='utf8').replace("VARIANTS=('lite-a-dual','lite-b-barrel','lite-c-dnp')","VARIANTS=('spark-full-pcba',)").replace("path=ROOT/'variants'/variant/'kicad/tab5-fpga-carrier.kicad_pcb'","path=ROOT/'spark/design/kicad/tab5-fpga-carrier.kicad_pcb'");p.write_text(s,encoding='utf8')
p=P/'periodic_link.py';s=p.read_text(encoding='utf8').replace("('lite-a-dual','lite-c-dnp')","('spark-full-pcba',)");p.write_text(s,encoding='utf8')
for name in ('power_models.py','simulate_case.py','ngspice_shared.py'):
 shutil.copyfile(SOURCE/'variants/simulation/power'/name,W/name)
for d in ('models','results','cases'):(W/d).mkdir(exist_ok=True)
shutil.copyfile(SOURCE/'variants/simulation/power/models/TPS5430_TRANS.LIB',W/'models/TPS5430_TRANS.LIB')
p=W/'power_models.py';s=p.read_text(encoding='utf8').replace("str(3300*c.get('rbot_mult',1))","str(3240*c.get('rbot_mult',1))")
s='\n'.join(l for l in s.splitlines() if "'Rtrim1 " not in l and "'Rtrim2 " not in l)+'\n'
p.write_text(s,encoding='utf8')
cache=SOURCE/'kicad/sim/zdiff_cache.json'
if cache.exists():shutil.copyfile(cache,H/'design/kicad/sim/zdiff_cache.json')
print('Isolated models prepared')
