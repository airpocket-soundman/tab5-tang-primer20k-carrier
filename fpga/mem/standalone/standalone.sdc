create_clock -name sys27 -period 37.037037 [get_ports {sys_clk}]
create_generated_clock -name memory398 -source [get_ports {sys_clk}] -multiply_by 59 -divide_by 4 [get_nets {memory_clk}]
create_generated_clock -name user100 -source [get_nets {memory_clk}] -divide_by 4 [get_nets {user_clk}]
set_clock_groups -asynchronous -group [get_clocks {sys27}] -group [get_clocks {memory398}] -group [get_clocks {user100}]
report_timing -setup -max_paths 25
report_timing -hold -max_paths 25
