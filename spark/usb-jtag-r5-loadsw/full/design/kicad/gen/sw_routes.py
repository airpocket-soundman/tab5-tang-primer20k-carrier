# Nets routed in this order; widths: power 0.5, configuration signals 0.25.
# In2.Cu carries the inner GND plane island around SW4 pad 8: keep new routes on F.Cu / B.Cu.
FB=[F,B]
do('BUCK_5V',0.5,[Tp('1'),(38.15,26.85,F)],FB)
do('+5V',0.5,[Tp('4'),(39.0,28.54,None)],FB)
do('VBUS_PD',0.5,[Tp('3'),(39.0,31.08,I2)])
do('PD_CFG1',0.25,[Tp('5'),(47.0,28.54,None)],FB)
do('PD_VDD',0.25,[Tp('6'),(47.0,31.08,None)],FB)
