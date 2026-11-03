create_clock -name osc27 -period 37.037037 [get_ports {sys_clk}]
create_generated_clock -name sampler216 -source [get_ports {sys_clk}] -multiply_by 8 [get_nets {filter_clk}]
//No exceptions: sampler-only independent evidence, not full-image qualification.
report_timing -setup -max_paths 100
report_timing -hold -max_paths 100
report_timing -recovery -max_paths 100
report_timing -removal -max_paths 100
