create_clock -name osc27 -period 37.037037 [get_ports {sys_clk}]
create_generated_clock -name core54 -source [get_ports {sys_clk}] -multiply_by 2 [get_nets {core_clk}]
create_generated_clock -name sampler216 -source [get_ports {sys_clk}] -multiply_by 8 [get_nets {filter_clk}]
// Aperiodic conditioned clock has >=5sample spacing and2sample HIGH.
// Independent conservative54MHz/50percent clock bounds both minimum pulse widths.
// Do not invent a fixed divide ratio/phase for this conditional clock.
create_clock -name conditioned_reply54 -period 18.518519 [get_nets {core/clean_reply_clk}]
// Initial unwaived run: no false paths, multicycle or asynchronous groups.
report_timing -setup -max_paths 50
report_timing -hold -max_paths 50
report_timing -recovery -max_paths 50
report_timing -removal -max_paths 50
report_timing -setup -from [get_regs {core/clock_conditioner/*}] -to [get_regs {core/clock_conditioner/*}] -max_paths 100
report_timing -hold -from [get_regs {core/clock_conditioner/*}] -to [get_regs {core/clock_conditioner/*}] -max_paths 100
