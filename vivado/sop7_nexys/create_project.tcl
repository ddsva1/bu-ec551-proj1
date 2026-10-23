# Creates and opens the Vivado project for sop7 on the nexys board.
# Works in any recent Vivado version:
#   Tools -> Run Tcl Script... -> select this file
#   (or in the Tcl Console:  source <path to this file>)
# Then: Generate Bitstream -> Open Hardware Manager -> Program Device.

set here [file dirname [file normalize [info script]]]
create_project sop7_nexys $here/project -part xc7a100tcsg324-1 -force
# [list ...] keeps paths with spaces (e.g. "EC 551") in one piece
add_files -norecurse [list $here/sop7_sop.v $here/sop7_pos.v $here/top_nexys4ddr.v]
add_files -fileset constrs_1 -norecurse [list $here/Nexys4DDR_Master.xdc]
set_property top top [current_fileset]
update_compile_order -fileset sources_1
