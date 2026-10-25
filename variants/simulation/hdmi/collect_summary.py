import json
from pathlib import Path
p=Path('variants/simulation/hdmi')
a={'formal_S_parameters':False,'apply_3d_correction_to_eye':False,'status':'uncertain','reason':'MSL port modal diagnostics have nonzero output incident wave; branch energy/mesh convergence was not achieved within bounded runtime. No socket/Core 3D calibration claimed.','cases':{}}
for d in (p/'local3d').iterdir():
 if not d.is_dir():continue
 r=json.loads((d/'result.json').read_text()); n=d.name
 a['cases'][n]={'termination':'normal' if n.startswith('reference') else 'operator_ABORT','use':'uniform-line impedance cross-check only' if n.startswith('reference') else 'excluded from quantitative eye correction','modal_Zdiff_ohm':r['modal_Zdiff_mean_0p5_to1p5GHz'],'output_backwave_ratio':r['output_backwave_over_incident_max_0p5_to1p5GHz'],'reason':'Uniform reference completed' if n.startswith('reference') else ('Energy stalled around -23 dB; mesh convergence not shown' if n.endswith('025') else 'Pulse incomplete; even diagnostic transmission invalid')}
a['uniform_crosscheck']={'fine_3d_ohm':95.89121,'prior_fine_3d_ohm':96.53623,'two_dimensional_cache_ohm':103.41557,'interpretation':'Independent 3D crosscheck agrees with earlier finite-thickness 3D within 0.67%; 2D differs by about 7.3%. Neither establishes absolute measured impedance. Eye sensitivity scales carrier impedances +/-10%.'}
(p/'local3d/assessment.json').write_text(json.dumps(a,indent=2)+'\n')
summary={'status':'provisional_until_final_CAD_reextraction','hash_kind':'raw-file SHA256, distinct from parent LF-normalized SHA256','variants':{}}
for v in ('lite-a-dual','lite-b-barrel'):
 r=json.loads((p/f'results/{v}/eye_results.json').read_text()); modes={}
 for mode in ('480p','720p'):
  rows=[x for x in r['results'] if x['mode']==mode]
  modes[mode]={'status':'conditional_pass' if all(x['pass_internal'] for x in rows) else 'fail','rows':len(rows),'minimum_signed_center_V':min(x['signed_center_min_V'] for x in rows),'minimum_width_UI':min(x['width_over_100mV_UI'] for x in rows),'maximum_abs_data_clock_delay_ps':max(abs(x['data_minus_clock_delay_ps']) for x in rows)}
 summary['variants'][v]={'source_pcb_sha256':r['source_pcb_sha256'],'HDMI':modes,'limits':r['limits']}
summary['variants']['lite-c-dnp']={'HDMI':'not_used_DNP','retained_copper':'A/B analysis is reference only; no active HDMI claim'}
summary['DDR3']='Incremental NC contact/pad loading only; full controller/physical DDR3 operation remains hardware bring-up gate'
summary['HPD']='Conditional pass with 100nF filter, active-low input and >=10ms debounce; generic transistor model, not vendor corner certification'
(p/'final-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=1))


import json,hashlib
from pathlib import Path
p=Path('variants/simulation/hdmi');f=p/'final-summary.json';r=json.loads(f.read_text());r['status']='complete_for_adopted_CAD_conditional_PoC_scope'
for v in ('lite-a-dual','lite-b-barrel','lite-c-dnp'):
 sha=hashlib.sha256((Path('variants')/v/'kicad/tab5-fpga-carrier.kicad_pcb').read_bytes()).hexdigest()
 if v!='lite-c-dnp':assert sha==r['variants'][v]['source_pcb_sha256']
 r['variants'][v]['source_pcb_sha256']=sha;r['variants'][v]['cad_crosscheck']=json.loads((p/'models'/v/'cad-crosscheck.json').read_text())['ok']
r['HPD']={'powered_DC':'conditional_pass_40cases_with10k_R52_minHigh2.656V_maxLow0.15043V','core_local_both_off':'max18mV applies to bothrails0 only','independent_Core_off':'uncertain permissible injection;10k limits generic model peak0.299mA/DC53.6uA','firmware':'active-low/input-only/debounce>=10ms','details':'hpd/series10k_powered.json and offrail_sensitivity.json'}
r['three_dimensional']={'uniform_crosscheck':'completed','branch_calibration':'uncertain_not_converged_excluded','formal_Sparameters':False,'full_Core_socket':'not_calibrated','details':'local3d/assessment.json'}
r['reproducibility']='HANDOFF.json and scripts; exact reviewed pre-HDMI PCB gzip snapshot retained'
f.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=1))
