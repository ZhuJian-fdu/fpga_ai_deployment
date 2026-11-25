# Run prepare_ddr_test.py first. Rebuilds locally; never connects to hardware.
set root [file normalize [file join [file dirname [info script]] ..]]
set sources [file join $root build ddr_sources]
set out [file join $root build ddr_test]
if {![file exists [file join $sources mig_35t.prj]]} { error "Run prepare_ddr_test.py first" }
create_project -force ddr_test $out -part xc7a35tfgg484-2
create_ip -name mig_7series -vendor xilinx.com -library ip -version 4.2 -module_name mig_7series_0
set_property CONFIG.XML_INPUT_FILE [file join $sources mig_35t.prj] [get_ips mig_7series_0]
generate_target all [get_ips mig_7series_0]
create_ip -name clk_wiz -vendor xilinx.com -library ip -version 6.0 -module_name clk_wiz_0
set_property -dict [list CONFIG.PRIM_IN_FREQ {50.000} CONFIG.CLKOUT1_REQUESTED_OUT_FREQ {200.000} \
    CONFIG.RESET_TYPE {ACTIVE_LOW} CONFIG.USE_RESET {true} CONFIG.USE_LOCKED {true}] [get_ips clk_wiz_0]
generate_target all [get_ips clk_wiz_0]
add_files [glob [file join $sources *.v]]
add_files [file join $root board acx720_v3_ddr_test_top.v]
add_files -fileset constrs_1 [file join $root board acx720_v3_ddr_test.xdc]
set_property top acx720_v3_ddr_test_top [get_filesets sources_1]
update_compile_order -fileset sources_1
launch_runs synth_1 -jobs 2
wait_on_run synth_1
if {[get_property PROGRESS [get_runs synth_1]] ne "100%"} { error "Synthesis failed" }
launch_runs impl_1 -to_step route_design -jobs 2
wait_on_run impl_1
if {[get_property PROGRESS [get_runs impl_1]] ne "100%"} { error "Implementation failed" }
open_run impl_1
report_timing_summary -file [file join $out timing_summary.rpt]
report_utilization -file [file join $out utilization.rpt]
report_drc -file [file join $out drc.rpt]
report_cdc -file [file join $out cdc.rpt]
foreach path [concat [get_timing_paths -delay_type max -max_paths 1] [get_timing_paths -delay_type min -max_paths 1]] {
    if {[get_property SLACK $path]<0} { error "Timing failed" }
}
set violations [get_drc_violations -quiet -filter {SEVERITY == Error || SEVERITY == {Critical Warning}}]
if {[llength $violations]} { error "Blocking DRC violations: $violations" }
write_bitstream -force [file join $out acx720_v3_ddr_test.bit]
puts "PASS: DDR test bitstream built; physical calibration/traffic checks pending."
close_project
