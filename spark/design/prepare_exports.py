from pathlib import Path
H=Path(__file__).resolve().parent
p=H/'kicad/gen/export_poc_package.py';s=p.read_text(encoding='utf8')
s=s.replace("OUT=ROOT/'manufacturing/poc-2026-10-24'","OUT=ROOT/'manufacturing/spark-full-review-2026-10-26'")
s=s.replace("MANUAL={'J1','J3','J5','SW1','SW2','SW3','JP1'}","MANUAL={'J1','J3','SW3','JP1'}")
s=s.replace('sim/drc_r3.json','sim/drc-final.json')
s=s.replace('Ready for small PoC fabrication; M5-Bus left pin1 confirmed by user, 2026-10-24; manufacturer assembly preview required','Engineering quote/review only. Not fabrication released: Spark eligibility,13 native schematic warnings, mechanical fit and supplier DFM outstanding. Native PCB DRC passed.')
(H/'kicad/gen/export_spark_review.py').write_text(s,encoding='utf8')
