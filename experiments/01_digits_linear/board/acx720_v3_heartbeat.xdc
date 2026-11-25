# Verified against V3 pin table (2024-11-13): Sheet1 rows 2, 4, 27.
# Schematic: ACX720-V3-SCH.pdf pages 1, 2, 3, 10, 12.
# Assumes factory 3.3 V VCCIO / Bank 16 configuration. See board/README.md.
set_property PACKAGE_PIN Y18 [get_ports clk]
set_property PACKAGE_PIN B21 [get_ports reset_n]
set_property PACKAGE_PIN M22 [get_ports led0]
set_property IOSTANDARD LVCMOS33 [get_ports {clk reset_n led0}]
create_clock -name sys_clk -period 20.000 [get_ports clk]

# S4 only drives asynchronous reset on the two-stage synchronizer.
set_false_path -from [get_ports reset_n]
# Human-visible LED has no external synchronous receiver.
set_false_path -to [get_ports led0]

# Configuration bank is 3.3 V (schematic page 3), CFGBVS tied high (page 2).
set_property CFGBVS VCCO [current_design]
set_property CONFIG_VOLTAGE 3.3 [current_design]
