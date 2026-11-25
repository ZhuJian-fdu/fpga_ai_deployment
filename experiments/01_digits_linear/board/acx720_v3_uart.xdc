# V3 pin table Sheet1 rows 2, 4-6, 27, 29-30; schematic pages 1/2/9/10.
set_property PACKAGE_PIN Y18 [get_ports clk]
set_property PACKAGE_PIN B21 [get_ports reset_n]
set_property PACKAGE_PIN M22 [get_ports led0]
set_property PACKAGE_PIN N22 [get_ports led1]
set_property PACKAGE_PIN L21 [get_ports led2]
set_property PACKAGE_PIN J21 [get_ports uart_rx]
set_property PACKAGE_PIN M15 [get_ports uart_tx]
set_property IOSTANDARD LVCMOS33 [get_ports {clk reset_n led0 led1 led2 uart_rx uart_tx}]
create_clock -name sys_clk -period 20.000 [get_ports clk]
set_false_path -from [get_ports reset_n]
# External asynchronous UART input: ignore ONLY path into first synchronizer FF.
set_false_path -from [get_ports uart_rx] -to [get_pins {u_echo/u_rx/rx_sync_reg[0]/D}]
# UART receiver uses its own clock; LEDs have no synchronous timing relationship.
set_false_path -to [get_ports {uart_tx led0 led1 led2}]
set_property CFGBVS VCCO [current_design]
set_property CONFIG_VOLTAGE 3.3 [current_design]
