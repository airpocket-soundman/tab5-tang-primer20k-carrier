# Nets routed in this order; widths: power 0.5, signal 0.25.
do('OVP_Z',0.25,[Tp('R93',1),Tp('D12',2)])
do('OVP_B',0.25,[Tp('Q11',1),Tp('R93',2),Tp('R94',1)])
do('OVP_NG',0.25,[Tp('Q10',1),Tp('Q11',3),Tp('R92',2)])
do('OVP_G',0.25,[Tp('Q9',1),Tp('Q10',3),Tp('R91',2)])
# upstream VBUS_PD: tap the existing via (34.16,25.31) and feed the four pads of the block
do('VBUS_PD',0.5,[(34.16,25.31,None),Tp('Q9',2),Tp('R91',1),Tp('D12',1),Tp('R92',1)])
# downstream VBUS_PD (to D2 / VIN OR-diode) was cut with the old junction: reconnect on In2
do('VBUS_PD',0.5,[(34.16,26.24,I2),(35.52,34.56,I2)])
do('VBUS_PGM',0.5,[Tp('Q9',3),(39.0,31.08,None)])
# GND: short stub + via to the inner ground planes
for ref,num in (('Q10',2),('Q11',2),('R94',2)):
    x,y=pad(ref,num);ok=False
    for rad in (1.2,1.5,1.8,2.2):
        for dx,dy in ((0,-rad),(0,rad),(-rad,0),(rad,0),(rad,rad),(-rad,-rad),(rad,-rad),(-rad,rad)):
            r=R.route('GND',0.25,[(x,y,F),(x+dx,y+dy,F)],[F])
            if r is None:continue
            vx,vy=x+dx,y+dy
            ci=int(round((vx-R.x0)/R.res));cj=int(round((vy-R.y0)/R.res))
            # a through via must be free (clearance 0.2 + via radius) on EVERY layer, including F.Cu pads
            if any(R._blocked(l,'GND',0.2+0.3)[cj*R.nx+ci] for l in R.layers):continue
            for layer,pts,ww in r[0]:
                add_track(layer,pts,'GND',ww);R.add_track(layer,pts,'GND',ww)
            add_via(vx,vy,'GND');R.add_via(vx,vy,'GND');ok=True;break
        if ok:break
    print('GND stub',ref,num,'ok' if ok else 'FAILED')
    if not ok:failed.append('GND '+ref)
