# Carrier board (NOT the Dock bench). DRAFT template: every number below that is not a clock
# period of an existing oscillator is an UNVERIFIED PLACEHOLDER, not a measured or derived value.
# Companion to tab5_carrier_link.cst (generated). See docs/キャリア制約_cst_sdc生成.md.

# Core oscillator (same as the Dock bench).
create_clock -name sys_clk -period 37.037 [get_ports {sys_clk}]

# ---- External source-synchronous receive (future front end; NOT used by the current RTL) ----
# The current tops (platform/dock/*) sample bus_clk as DATA with sys_clk and do not use it as a clock,
# so the constraints below must stay disabled for them. Enable only together with a front end that
# really clocks data[7:0] from bus_clk (ESP32-P4 PARLIO TX, SoC maximum 40 MHz; board/jumper limit
# is NOT established: 20 MHz is the highest jumper rate verified so far).
#
# create_clock -name bus_clk -period 25.000 [get_ports {bus_clk}]       ;# 40 MHz = SoC maximum, not a verified rate
#
# PLACEHOLDER skew window of data[7:0] relative to bus_clk at the FPGA pins (ns).
# TODO: derive from the P4 PARLIO output skew, the carrier trace delays (kicad/ length report) and the
#       Core module net lengths (docs/reference/tang-primer-20k/Core_3690_Net_Length.xlsx).
# set_input_delay -clock bus_clk -max 2.000 [get_ports {data[*]}]       ;# PLACEHOLDER (setup side)
# set_input_delay -clock bus_clk -min 0.500 [get_ports {data[*]}]       ;# PLACEHOLDER (hold side)
#
# Direction / ready are slow control lines (synchronized with sys_clk in the RTL): no I/O delay is set.
# No blanket false paths: review CDC/IO timing reports before hardware release.
