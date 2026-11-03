create_clock -name osc27 -period 37.037037 [get_ports {sys_clk}]
create_generated_clock -name core54 -source [get_ports {sys_clk}] -multiply_by 2 [get_pins {clock_gen/pll/CLKOUT}]
