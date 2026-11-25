# Out-of-context synthesis only. No board pins and no bitstream are generated.
set root [file normalize [file join [file dirname [info script]] ..]]
set model [file join $root build model]
set out [file join $root build vivado]
file mkdir $out
foreach name {weights.mem biases.mem} {
    if {![file exists [file join $model $name]]} { error "Run train_export.py first" }
}
cd $model
read_verilog -sv [file join $root rtl digit_classifier.sv]
synth_design -top digit_classifier -part xc7a35tfgg484-2 -mode out_of_context
# 10 ns is an exploratory core target, not the board oscillator frequency.
create_clock -name core_clk -period 10.000 [get_ports clk]
report_utilization -file [file join $out core_utilization.rpt]
report_timing_summary -file [file join $out core_synth_timing.rpt]
write_checkpoint -force [file join $out core_synth.dcp]
puts "PASS: core synthesis completed; board implementation is still required."
exit
