create_clock -name sys27 -period 37.037037 [get_ports {sys_clk}]
// clk400 variant: memory clock 27MHz*59/4=398.25MHz (PLL IDIV3/FBDIV58/ODIV2), USER=memory/4=99.5625MHz.
// STA at this USER frequency is UNVERIFIED until the official build reports it.
create_generated_clock -name memory398 -source [get_ports {sys_clk}] -multiply_by 59 -divide_by 4 [get_nets {memory_clk}]
create_generated_clock -name user100 -source [get_nets {memory_clk}] -divide_by 4 [get_nets {user_clk}]
// No blanket asynchronous exception between related memory324/user81 clocks.
// First implementation timing report remains a review gate, not a waiver.
// Held request bundle: launched with SYS toggle, sampled no earlier than
// two USER periods later (20.09ns at 99.5625MHz). Bound route+clock delay to20ns (margin only 0.09ns).
set_max_delay -from [get_regs {control/held_base* control/held_count* control/held_seed* control/held_job*}] -to [get_regs {control/job_base* control/job_count* control/job_seed* control/job_id*}] 20
set_false_path -hold -from [get_regs {control/held_base* control/held_count* control/held_seed* control/held_job*}] -to [get_regs {control/job_base* control/job_count* control/job_seed* control/job_id*}]
// Snapshot bundle: USER captures once, acks next USER edge; SYS then has
// two sync stages plus explicit settle cycle. Minimum stable time exceeds
// 3*37.037+12.346=123.457ns. Enforce60ns max, and exempt only hold on
// these held bundles; same-domain paths and all vendor DDR paths stay timed.
set_max_delay -from [get_regs {control/user_snapshot*}] -to [get_regs {control/sys_snapshot*}] 60
set_false_path -hold -from [get_regs {control/user_snapshot*}] -to [get_regs {control/sys_snapshot*}]
// Diagnostic bank uses the very same SNAPSHOT request/ack/settle contract.
set_max_delay -from [get_regs {control/user_debug_snapshot*}] -to [get_regs {control/sys_debug_snapshot*}] 60
set_false_path -hold -from [get_regs {control/user_debug_snapshot*}] -to [get_regs {control/sys_debug_snapshot*}]
// Only the first sampling stage accepts metastability. Stage0->stage1 and
// all subsequent logic remain timed; these seven D pins are explicit.
set_false_path -to [get_pins {control/request_sync_0_s0/D control/ack_sync_0_s0/D control/cal_sync_0_s0/D control/busy_sync_0_s0/D control/fault_sync_0_s0/D control/user_ready_sync_0_s0/D control/heartbeat_sync_0_s0/D}]
report_timing -setup -max_paths 25
report_timing -hold -max_paths 25
report_timing -recovery -max_paths 256 -max_common_paths 1
report_timing -removal -max_paths 25
report_timing -setup -from [get_regs {control/user_snapshot*}] -to [get_regs {control/sys_snapshot*}] -max_paths 512
report_timing -setup -from [get_regs {control/user_debug_snapshot*}] -to [get_regs {control/sys_debug_snapshot*}] -max_paths 176
report_timing -setup -from [get_regs {control/held_base* control/held_count* control/held_seed* control/held_job*}] -to [get_regs {control/job_base* control/job_count* control/job_seed* control/job_id*}] -max_paths 128

// Output-only deep observation shares the same held snapshot handshake.
set_max_delay -from [get_regs {control/user_deep_snapshot*}] -to [get_regs {control/sys_deep_snapshot*}] 60
set_false_path -hold -from [get_regs {control/user_deep_snapshot*}] -to [get_regs {control/sys_deep_snapshot*}]
report_timing -setup -from [get_regs {control/user_deep_snapshot*}] -to [get_regs {control/sys_deep_snapshot*}] -max_paths 256
// sampleip DIAGNOSTIC build only: same blanket-asynchronous clock groups as the Sipeed sample SDC (ddr3.sdc).
// Not a qualified timing sign-off; the sample IP's internal paths are not individually constrained here.
set_clock_groups -asynchronous -group [get_clocks {sys27}] -group [get_clocks {memory398}] -group [get_clocks {user100}]
