set root [file normalize [file join [file dirname [info script]] ..]]
set project_dir [file join $root build ai]
set project_file [file join $project_dir acx720_v3_ai.xpr]
foreach name {weights.mem biases.mem} {
    if {![file exists [file join $root build model $name]]} { error "Run train_export.py first: missing $name" }
}
if {[file exists $project_file]} {
    open_project $project_file
} else {
    create_project acx720_v3_ai $project_dir -part xc7a35tfgg484-2
    foreach source {heartbeat.v uart_rx.v uart_tx.v digit_classifier.sv digit_protocol.sv digit_uart.sv} {
        add_files [file join $root rtl $source]
    }
    # Vivado copies these sources to its synthesis working directory for readmemh.
    add_files [list [file join $root build model weights.mem] [file join $root build model biases.mem]]
    add_files [file join $root board acx720_v3_ai_top.v]
    add_files -fileset constrs_1 [file join $root board acx720_v3_ai.xdc]
    set_property top acx720_v3_ai_top [get_filesets sources_1]
    update_compile_order -fileset sources_1
}
puts "Project ready: $project_file"
