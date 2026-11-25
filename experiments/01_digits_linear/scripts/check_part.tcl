# Run with Vivado -mode batch -source <this_file> from build/vivado.
set target xc7a35tfgg484-2
set matches [get_parts -quiet $target]
if {[llength $matches] != 1} {
    error "Target device not installed: $target. Install Artix-7 device support."
}
puts "PASS: Vivado [version -short] recognizes $target"
exit
