# Reference for a timing tool supporting generated clocks and scoped exceptions.
create_clock -name osc27 -period 37.037037 [get_ports {sys_clk}]
create_generated_clock -name core54 -source [get_ports {sys_clk}] -multiply_by 2 [get_pins {clock_gen/pll/CLKOUT}]
create_clock -name reply_bus40 -period 25.000000 [get_ports {bus_clk}]
# Intentional asynchronous crossings require scoped exceptions in a full STA tool:
# SYS immutable metadata -> first metadata_meta stage (second stage remains timed).
# RAW done/started/progress -> first SYS synchronizer stage (second remains timed).
# SYS offer -> raw clock-enable/state gating, stable before READY+host guard.
# Raw ARM/reset/DIR and offer abort paths are asynchronous output-disable controls.
# Do not blanket-mask RAM/read/write paths or same-domain payload/CRC timing.
# nextpnr generic set_false_path is currently a documented no-op; it is not used.
# Host IO setup/hold and clock/data flight time need separate pad/waveform evidence.
