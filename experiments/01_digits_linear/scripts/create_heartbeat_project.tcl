# Source in Vivado Tcl Console, or run with -mode batch -source.
set root [file normalize [file join [file dirname [info script]] ..]]
set project_dir [file join $root build heartbeat]
set project_file [file join $project_dir acx720_v3_heartbeat.xpr]
if {[file exists $project_file]} {
    open_project $project_file
} else {
    create_project acx720_v3_heartbeat $project_dir -part xc7a35tfgg484-2
    add_files [list [file join $root rtl heartbeat.v] [file join $root board acx720_v3_heartbeat_top.v]]
    add_files -fileset constrs_1 [file join $root board acx720_v3_heartbeat.xdc]
    add_files -fileset sim_1 [file join $root sim tb_acx720_v3_heartbeat.sv]
    set_property top acx720_v3_heartbeat_top [get_filesets sources_1]
    set_property top tb_acx720_v3_heartbeat [get_filesets sim_1]
    update_compile_order -fileset sources_1
    update_compile_order -fileset sim_1
}
puts "Project ready: $project_file"
