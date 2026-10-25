"""Documented analytical margins; no claim of measured transient or temperature."""
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
dc=json.loads((HERE/'power_dc_check.json').read_text())
# TI SN74CB3Q3245 SCDS124C, ICC 2mA max per switch; nOE is static in use.
switch_mA=2*2
oe_mA=3.3*1.02/(22000*.99)*1000
control_margin_mA=2*.030
leakage_margin_mA=64*.001
internal_mA=switch_mA+oe_mA+control_margin_mA+leakage_margin_mA
vmax=dc['regulator_conservative_bound_V'][1]
vin_min=12*.95-.55  # regulated adapter -5%, conservative SS54 allowance
vout_max=vmax
lmin=15e-6*.8
fsw_min=400e3
ripple=(vout_max+.55)/(lmin*fsw_min)  # off-time fraction <=1, conservative catch-diode allowance
check_load_A=2.0  # stress sensitivity only; not a guaranteed board continuous rating
peak=check_load_A+ripple/2
irms=(check_load_A**2+ripple**2/12)**.5
result={
 'ok':internal_mA<50 and vmax<6 and peak<4 and peak<6 and irms<4.5,
 'variant':'lite-c-dnp',
 'bus_LDO':{'device':'TOREX XC6206P332MR-G C5446','operating_VIN_max_V':6,'calculated_input_max_V':vmax,'pinout':{'1':'GND','2':'+3V3','3':'+5V'},'internal_load_bound_mA':internal_mA,'design_budget_mA':50,'external_power_budget_mA':0,'quiescent_max_uA':3,'loss_at_internal_bound_W':(vmax-3.3*.98)*internal_mA/1000+vmax*3e-6,'loss_at_50mA_budget_W':(vmax-3.3*.98)*.05+vmax*3e-6,'SOT23_Pd_25C_W':.25,'input_cap':'C10 retained 10u/16V selection, moved close to U3','output_cap':'C11 retained 22u/10V ceramic selection, moved close to U3','notes':['OE is armed once after power-good; it is not clocked at the bus clock. ICCD is not applied to every data edge.','No PMOD/GPIO external 3.3V supply permitted. Internal FPGA/DDR3 rails are generated on the user-supplied Core.','50mA is a budget, not a declaration of full-temperature capability. Initial PoC at ordinary room ambient, temperature and startup to be measured.']},
 'buck_inductor':{'device':'COILMX MS1040-150M C380054','L_nominal_uH':15,'L_min_uH':12,'DCR_max_ohm':.045,'Irms_40C_rise_A':4.5,'Isat_30pct_Ldrop_A':6,'stress_load_A':check_load_A,'ripple_pp_bound_A':ripple,'peak_bound_A':peak,'rms_bound_A':irms,'DCR_loss_at_stress_W':irms**2*.045,'TPS5430_min_peak_current_limit_A':4,'notes':['Conservative off-time ripple bound (Vout_max+0.55V)/(Lmin*fmin), taking off-time fraction <=1; actual 12V buck ripple is smaller.','400kHz minimum frequency and 12uH minimum inductance; the 0.55V catch-diode allowance is an analytical assumption.','Short-circuit peaks, startup overshoot, thermal rise, core-bitstream peaks and full board continuous load capability require measurement.','The original compensated TPS5430/C7 220uF POSCAP topology is retained; no all-MLCC output substitution.']},
 'bringup':{'input':'regulated 12V, centre-positive, 3A-class source with current limiting','initial_Core_load_A':.5,'initial_Core_low_rail_copper_only_V':dc['regulator_conservative_bound_V'][0]-dc['core_0_5A_max_path_drop_V'],'official_Core_voltage_range_V':[4.5,5.5],'minimum_test':'electronic-load startup, ripple, load step and thermal checks before fitting Core; then low-speed parallel CRC/DDR3 bringup','firmware':'Linux physical PARLIO/DMA and GPU board profile remain unverified; use separate appropriate bitstreams'},
 'sources':['https://product.torexsemi.com/system/files/series/xc6206.pdf','root docs/reference/parts/sn74cb3q3245_datasheet.pdf, electrical table ICC 2mA max','root docs/reference/parts/TPS5430_datasheet.pdf, VFB1.196..1.245 and fSW400kHz min','variants/reference/MS1040-current.pdf, 150M row and recommended pad drawing']}
(HERE/'lite_c_budget.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'ok':result['ok'],'internal_LDO_mA':internal_mA,'stress_inductor_peak_A':peak,'initial_core_copper_only_low_V':result['bringup']['initial_Core_low_rail_copper_only_V']}))
assert result['ok']
