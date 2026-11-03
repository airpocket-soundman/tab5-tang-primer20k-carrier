# Actual nextpnr constraints. No timing-allow-fail and no ineffective false paths.
create_clock -name osc27 -period 37.037037 [get_ports {sys_clk}]
create_clock -name core54 -period 18.518519 [get_nets {core_clk}]
create_clock -name reply_bus40 -period 25.000000 [get_ports {bus_clk}]
