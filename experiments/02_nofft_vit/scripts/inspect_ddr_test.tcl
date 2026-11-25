# Read-only post-build inspection; no board access or bitstream changes.
set root [file normalize [file join [file dirname [info script]] ..]]
set out [file join $root build ddr_test]
open_project [file join $out ddr_test.xpr]
report_ip_status -file [file join $out ip_status.rpt]
open_run impl_1
report_io -file [file join $out io.rpt]
check_timing -verbose -file [file join $out check_timing_verbose.rpt]
report_methodology -file [file join $out methodology.rpt]
foreach cell [get_cells -hier -filter {REF_NAME == PLLE2_ADV}] {
    foreach pin [get_pins -of_objects $cell -filter {REF_PIN_NAME =~ CLKOUT*}] {
        set nets [get_nets -quiet -of_objects $pin]
        set loads [get_pins -quiet -leaf -of_objects $nets -filter {DIRECTION == IN}]
        puts "PLL_OUTPUT $pin -> $loads"
    }
}
close_project
