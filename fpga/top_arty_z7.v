// Board wrapper for the Digilent Arty Z7-20 (constraints: fpga/arty_z7_20.xdc).
//
// Connects the generated modules circuit_sop and circuit_pos
// (output/<name>_sop.v and output/<name>_pos.v from  py main.py v <file>)
// to the board. Works for any design without editing.
//
// The Arty Z7 has only 2 switches, 4 buttons and 4 LEDs, so:
//   in[1:0]   = sw[1:0]     (the last variable is sw[0])
//   in[5:2]   = btn[3:0]    (hold a button for 1)
//   in[15:6]  = 0
//   led[1:0]  <- circuit_sop outputs out[1:0]
//   led[3:2]  <- circuit_pos outputs out[1:0]
//
// The SOP and POS circuits implement the same function, so led[1:0] and
// led[3:2] should always match.
module top(
   input [1:0] sw,
   input [3:0] btn,
   output [3:0] led
);
   wire [15:0] circuit_in = {10'b0, btn, sw};
   wire [7:0] sop_out, pos_out;

   circuit_sop sop(.in(circuit_in), .out(sop_out));
   circuit_pos pos(.in(circuit_in), .out(pos_out));

   assign led = {pos_out[1:0], sop_out[1:0]};
endmodule
