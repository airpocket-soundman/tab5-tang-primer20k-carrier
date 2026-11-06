# Part placement (mm, board frame). Region used: x 38.6..48.8, y 11.5..23 on F.Cu (free in r5).
# The r5 GND stitching stub at (38.2..37.15, 19.9) and via (47.25, 16.0) are kept; parts stay >= 1 mm away.
SOT=('Package_TO_SOT_SMD','SOT-23');R_=('Resistor_SMD','R_0603_1608Metric');D_=('Diode_SMD','D_SOD-123')
place('Q9' ,*SOT,'AO3401A',42.6,20.5,0,{'1':'OVP_G','2':'VBUS_PD','3':'VBUS_PGM'})
place('Q10',*SOT,'2N7002',40.0,16.5,0,{'1':'OVP_NG','2':'GND','3':'OVP_G'})
place('Q11',*SOT,'MMBT3904',44.5,16.5,0,{'1':'OVP_B','2':'GND','3':'OVP_NG'})
place('D12',*D_,'BZT52C6V2',47.0,19.8,90,{'1':'VBUS_PD','2':'OVP_Z'})
place('R91',*R_,'10k',39.6,21.5,90,{'1':'VBUS_PD','2':'OVP_G'})
place('R92',*R_,'100k',40.5,12.5,0,{'1':'VBUS_PD','2':'OVP_NG'})
place('R93',*R_,'1k',47.5,13.2,0,{'1':'OVP_Z','2':'OVP_B'})
place('R94',*R_,'4.7k',44.5,12.5,0,{'1':'OVP_B','2':'GND'})
# Dense block: reference designators go to F.Fab (assembly drawing / BOM keep them) so the silkscreen
# has no overlap warnings; the r5 board itself has 0 DRC warnings and the variant must keep that.
for _ref in ('Q9','Q10','Q11','D12','R91','R92','R93','R94'):
    _f=next(f for f in b.GetFootprints() if f.GetReference()==_ref)
    _f.Reference().SetLayer(pcbnew.F_Fab)
    _f.Value().SetLayer(pcbnew.F_Fab)
