# Runtime UART integer head. Does not connect to the board or program Flash.
set root [file normalize [file join [file dirname [info script]] ..]]
set vectors [file join $root build integer_head]
set out [file join $root build integer_uart_hw]
foreach name {weights biases multipliers shifts} {
    if {![file exists [file join $vectors ${name}.mem]]} {error "Run prepare_integer_head.py first"}
}
create_project -force integer_uart $out -part xc7a35tfgg484-2
add_files [file join $root rtl int16_dot_requant.v]
add_files [file join $root rtl integer_head_engine.v]
add_files [file join $root rtl integer_head_uart.v]
foreach name {uart_rx uart_tx} {add_files [file join $root .. 01_digits_linear rtl ${name}.v]}
add_files [file join $root board acx720_v3_integer_uart_top.v]
foreach name {weights biases multipliers shifts} {add_files [file join $vectors ${name}.mem]}
add_files -fileset constrs_1 [file join $root board acx720_v3_integer_uart.xdc]
set_property top acx720_v3_integer_uart_top [get_filesets sources_1]
update_compile_order -fileset sources_1
launch_runs synth_1 -jobs 2
wait_on_run synth_1
if {[get_property PROGRESS [get_runs synth_1]] ne "100%"} {error "Synthesis failed"}
set log_handle [open [file join [get_property DIRECTORY [get_runs synth_1]] runme.log] r]
set synthesis_log [read $log_handle]
close $log_handle
foreach name {weights biases multipliers shifts} {
    if {[string first "data file '${name}.mem' is read successfully" $synthesis_log]<0} {
        error "ROM initialization not confirmed: ${name}.mem"
    }
}
if {[regexp {Synth 8-2898|Synth 8-3848} $synthesis_log]} {error "Malformed ROM or undriven signal"}
launch_runs impl_1 -to_step route_design -jobs 2
wait_on_run impl_1
if {[get_property PROGRESS [get_runs impl_1]] ne "100%"} {error "Implementation failed"}
open_run impl_1
report_timing_summary -file [file join $out timing_summary.rpt]
report_utilization -file [file join $out utilization.rpt]
report_drc -file [file join $out drc.rpt]
report_cdc -file [file join $out cdc.rpt]
report_methodology -file [file join $out methodology.rpt]
check_timing -verbose -file [file join $out check_timing.rpt]
foreach delay {max min} {
    set paths [get_timing_paths -delay_type $delay -max_paths 1]
    if {![llength $paths]} {error "No timing paths"}
    if {[get_property SLACK $paths]<0} {error "Timing failed"}
}
set violations [get_drc_violations -quiet -filter {SEVERITY == Error || SEVERITY == {Critical Warning}}]
if {[llength $violations]} {error "Blocking DRC: $violations"}
write_bitstream -force [file join $out acx720_v3_integer_uart.bit]
puts "PASS: integer UART bitstream built; physical readback pending."
close_project
