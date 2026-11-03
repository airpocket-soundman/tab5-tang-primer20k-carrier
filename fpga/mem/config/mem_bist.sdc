create_clock -name sys27 -period 37.037037 [get_ports {sys_clk}]
create_generated_clock -name memory324 -source [get_ports {sys_clk}] -multiply_by 12 [get_nets {memory_clk}]
create_generated_clock -name user81 -source [get_nets {memory_clk}] -divide_by 4 [get_nets {user_clk}]
// No blanket asynchronous exception between related memory324/user81 clocks.
// First implementation timing report remains a review gate, not a waiver.
report_timing -setup -max_paths 25
report_timing -hold -max_paths 25
