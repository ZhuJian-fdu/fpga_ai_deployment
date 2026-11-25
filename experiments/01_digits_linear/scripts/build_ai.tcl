# Local build only: never programs a board or configuration Flash.
source [file join [file dirname [info script]] create_ai_project.tcl]
set out [file join $root build ai]
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
foreach path [concat [get_timing_paths -delay_type max -max_paths 1] [get_timing_paths -delay_type min -max_paths 1]] {
    if {[get_property SLACK $path]<0} { error "Timing failed" }
}
set violations [get_drc_violations -quiet -filter {SEVERITY == Error || SEVERITY == {Critical Warning}}]
if {[llength $violations]} { error "Blocking DRC violations: $violations" }
write_bitstream -force [file join $out acx720_v3_ai.bit]
puts "PASS: AI bitstream built; physical image inference validation is pending."
close_project
