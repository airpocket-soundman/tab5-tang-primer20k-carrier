# No timing allow-fail. Conditioned rises are >=5samples (<=43.2MHz).
# Conservative54MHz derivedclock target rather than pretending it is SYS54.
create_clock -name osc27 -period 37.037037 [get_ports {sys_clk}]
create_clock -name core54 -period 18.518519 [get_nets {core_clk}]
create_clock -name sampler216 -period 4.629630 [get_nets {filter_clk}]
create_clock -name conditioned_reply54 -period 18.518519 [get_nets {core.clean_reply_clk}]
