# Builds locally; never connects to or programs a device.
source [file join [file dirname [info script]] create_heartbeat_project.tcl]
set out [file join $root build heartbeat]
# Explicit rebuild to pick up changes; only generated Vivado run outputs reset.
reset_run synth_1
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
set setup_path [get_timing_paths -delay_type max -max_paths 1]
set hold_path [get_timing_paths -delay_type min -max_paths 1]
foreach path [concat $setup_path $hold_path] {
    if {[get_property SLACK $path] < 0} { error "Timing failed; no bitstream generated" }
}
set violations [get_drc_violations -quiet -filter {SEVERITY == Error || SEVERITY == {Critical Warning}}]
if {[llength $violations]} { error "Blocking DRC violations: $violations" }
write_bitstream -force [file join $out acx720_v3_heartbeat.bit]
puts "PASS: bitstream built; physical board verification is still required."
close_project
