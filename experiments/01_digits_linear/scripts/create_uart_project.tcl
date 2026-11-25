set root [file normalize [file join [file dirname [info script]] ..]]
set project_dir [file join $root build uart]
set project_file [file join $project_dir acx720_v3_uart.xpr]
if {[file exists $project_file]} {
    open_project $project_file
} else {
    create_project acx720_v3_uart $project_dir -part xc7a35tfgg484-2
    foreach source {heartbeat.v uart_rx.v uart_tx.v uart_echo.v} {
        add_files [file join $root rtl $source]
    }
    add_files [file join $root board acx720_v3_uart_top.v]
    add_files -fileset constrs_1 [file join $root board acx720_v3_uart.xdc]
    add_files -fileset sim_1 [file join $root sim tb_uart_echo.sv]
    set_property top acx720_v3_uart_top [get_filesets sources_1]
    set_property top tb_uart_echo [get_filesets sim_1]
    update_compile_order -fileset sources_1
    update_compile_order -fileset sim_1
}
puts "Project ready: $project_file"
