# Gowin Education1.9.11.03 / SUG100-4.4.2E documented IPFlow.
# Configuration based on Core schematic, NOT physical-part identification.
set fpga_root [file normalize [file join [file dirname [info script]] ../..]]
# MEM_IP_TAG (e.g. clk400) selects a separate output dir; MEM_CLK overrides Memory_Clock (default 324).
set tag ""
set mem_clk 324
if {[info exists env(MEM_IP_TAG)] && $env(MEM_IP_TAG) ne ""} {set tag -$env(MEM_IP_TAG)}
if {[info exists env(MEM_CLK)] && $env(MEM_CLK) ne ""} {set mem_clk $env(MEM_CLK)}
set output [file normalize [file join $fpga_root build mem-bist-ip$tag]]
create_project -name memconfig -dir $output -pn GW2A-LV18PG256C8/I7 -device_version C -force
create_ipc -name ddr3 -module_name MemDDR3 -dir [file join $output generated] -force
set_property -dict [subst {
 CONFIG.Memory_Clock $mem_clk CONFIG.CLK_Ratio {1:4}
 CONFIG.Dq_Width 16 CONFIG.Dram_Width 16
 CONFIG.Rank_Address 1 CONFIG.Bank_Address 3 CONFIG.Row_Address 13 CONFIG.Column_Address 10
 CONFIG.Burst_Mode 8 CONFIG.Burst_Type SEQ CONFIG.CAS_Latency 6 CONFIG.CW_Latency 5
 CONFIG.Additive_Latency 0 CONFIG.Wrire_Recovery 8
 CONFIG.Rtt_Nom 40 CONFIG.Rtt_Wr OFF CONFIG.Addr_Cmd_Mode 1T
 CONFIG.User_Refresh false CONFIG.tRTP_Period 15000 CONFIG.tRP_Period 20000
 CONFIG.tWTR_Period 15000 CONFIG.tRC_Period 75000 CONFIG.tRAS_Period 50000
 CONFIG.tRCD_Period 20000 CONFIG.tFAW_Period 60000 CONFIG.tRRD_Period 15000
 CONFIG.tCKE_Period 75000 CONFIG.tREFI_Period 3500000 CONFIG.tRFC_Period 260000 CONFIG.tDLLK 512
}] [get_ips MemDDR3]
report_property [get_ips MemDDR3]
generate_target [get_ips MemDDR3]
puts {MEM_DOCUMENT_CONFIGURATION_GENERATED_NO_HARDWARE}
exit
