# Internal synchronous logic only. bus_clk is sampled as data, not used as a clock.
create_clock -name sys_clk -period 37.037 [get_ports {sys_clk}]
# Asynchronous inputs require settling times stated in the bench protocol.
# No blanket false paths: review CDC/IO timing reports before hardware release.
