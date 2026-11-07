create_clock -name sys27 -period 37.037037 [get_ports {sys_clk}]
create_generated_clock -name memory398 -source [get_ports {sys_clk}] -multiply_by 59 -divide_by 4 [get_nets {memory_clk}]
create_generated_clock -name user99 -source [get_nets {memory_clk}] -divide_by 4 [get_nets {user_clk}]
// Initial unwaived diagnostic. No mailbox exceptions, asynchronous clock groups or blanket false paths.
report_timing -setup -max_paths 100 -max_common_paths 1
report_timing -hold -max_paths 100 -max_common_paths 1
report_timing -recovery -max_paths 100 -max_common_paths 1
report_timing -removal -max_paths 100 -max_common_paths 1
