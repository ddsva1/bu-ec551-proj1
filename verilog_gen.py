"""Structural Verilog generation

For a design <name> these files are written to the output folder:
    <name>_sop.v    module circuit_sop: AND-OR circuit of the minimized SOP
    <name>_pos.v    module circuit_pos: OR-AND circuit of the minimized POS
"""

import os
import re

from logic import minimal_cover, pos_string, sop_string

NUM_INPUTS = 16       # width of the fixed "in" port
NUM_OUTPUTS = 8       # width of the fixed "out" port


def verilog_name(name):
    """Legal Verilog identifier"""
    name = re.sub(r"\W", "_", name)
    if name[0].isdigit():
        name = "_" + name
    if name in ("in", "out"):
        name = name + "_sig"
    return name


def write_two_level_module(path, module_name, variables, outputs, style, comments):
    """Write one structural two-level module with the fixed in/out interface.

    outputs: {output name: list of cubes}
    style "sop": each cube is an AND term, and the terms are ORed together.
    style "pos": each cube is an OFF-set cube whose clause is an OR gate
                 (De Morgan: "1-0" -> (~A + C)), and the clauses are ANDed.
    """
    if style == "sop":
        term_gate, final_gate = "and", "or"
        plain_bit = "1"           # cube bit meaning "uncomplemented variable"
        empty_term = "1'b1"       # a term with no literals is constant 1
        pad = "1'b0"              # OR with 0 does not change the result
    else:
        term_gate, final_gate = "or", "and"
        plain_bit = "0"
        empty_term = "1'b0"       # a clause with no literals is constant 0
        pad = "1'b1"              # AND with 1 does not change the result

    def literal(bit, var):
        return var if bit == plain_bit else var + "_n"

    # which bit of "in" each variable comes from (the last variable is in[0])
    n = len(variables)
    input_bits = []
    for i in range(n):
        bit = n - 1 - i
        input_bits.append(f"in[{bit}]" if bit < NUM_INPUTS else "1'b0")
    out_names = list(outputs)

    # variables that appear complemented somewhere need a not gate
    inverted = [var for i, var in enumerate(variables)
                if any(cube[i] not in (plain_bit, "-")
                       for cubes in outputs.values() for cube in cubes)]

    term_wires = []       # internal wires: and0, and1, ... (or or0, or1, ...)
    term_gates = []       # (wire, input signals) for each term gate
    final_gates = []      # (output, input signals) for each output
    for out, cubes in outputs.items():
        final_inputs = []
        for cube in cubes:
            literals = [literal(bit, var) for bit, var in zip(cube, variables) if bit != "-"]
            if len(literals) == 0:
                final_inputs.append(empty_term)
            elif len(literals) == 1:
                final_inputs.append(literals[0])      # one literal needs no gate
            else:
                wire = term_gate + str(len(term_wires))
                term_wires.append(wire)
                term_gates.append((wire, literals))
                final_inputs.append(wire)
        while len(final_inputs) < 2:                   # gates get at least two inputs
            final_inputs.append(pad)
        final_gates.append((out, final_inputs))

    f = open(path, "w")
    for comment in comments:
        f.write("// " + comment + "\n")
    f.write("// inputs:  " + ", ".join(f"{var} = {src}" for var, src in zip(variables, input_bits)) + "\n")
    f.write("// outputs: " + ", ".join(f"{out} = out[{j}]" for j, out in enumerate(out_names)
                                        if j < NUM_OUTPUTS) + "\n")
    # module setup and i/o wires
    f.write("module " + module_name + "(\n")
    f.write(f"   input [{NUM_INPUTS - 1}:0] in,\n")
    f.write(f"   output [{NUM_OUTPUTS - 1}:0] out\n")
    f.write(");\n")
    # give the input and output bits their names
    f.write("   wire " + ", ".join(variables) + ";\n")
    f.write("   wire " + ", ".join(out_names) + ";\n")
    for var, src in zip(variables, input_bits):
        f.write("   buf(" + var + ", " + src + ");\n")
    for j, out in enumerate(out_names[:NUM_OUTPUTS]):
        f.write("   buf(out[" + str(j) + "], " + out + ");\n")
    if len(out_names) < NUM_OUTPUTS:
        f.write(f"   assign out[{NUM_OUTPUTS - 1}:{len(out_names)}] = 0;   // unused outputs off\n")
    # internal wires setup
    if inverted:
        f.write("   wire " + ", ".join(var + "_n" for var in inverted) + ";\n")
    if term_wires:
        f.write("   wire " + ", ".join(term_wires) + ";\n")
    # inverters
    for var in inverted:
        f.write("   not(" + var + "_n, " + var + ");\n")
    # one gate per term
    for wire, inputs in term_gates:
        f.write("   " + term_gate + "(" + wire + ", " + ", ".join(inputs) + ");\n")
    # final gate for each output
    for out, inputs in final_gates:
        f.write("   " + final_gate + "(" + out + ", " + ", ".join(inputs) + ");\n")
    # ending module
    f.write("endmodule\n")
    f.close()


def write_verilog(functions, design_name, source_path, out_dir):
    """Generate <name>_sop.v (circuit_sop) and <name>_pos.v (circuit_pos)."""
    os.makedirs(out_dir, exist_ok=True)
    variables = functions[0].variables
    n = len(variables)
    base = verilog_name(design_name)
    in_ports = [verilog_name(v) for v in variables]
    out_ports = [verilog_name(f.name) for f in functions]

    if n > NUM_INPUTS:
        print(f"Warning: only {NUM_INPUTS} inputs fit the in port; the first "
              f"{n - NUM_INPUTS} variable(s) are tied to 0")
    if len(out_ports) > NUM_OUTPUTS:
        print(f"Warning: only the first {NUM_OUTPUTS} outputs are connected to the out port")

    sop, pos = {}, {}
    sop_comments = [f"Generated by the EC551 Logic Synthesis Engine from {source_path}"]
    pos_comments = list(sop_comments)
    for f, port in zip(functions, out_ports):
        sop[port] = minimal_cover(f.on_set, n)
        pos[port] = minimal_cover(f.off_set, n)
        sop_comments.append(f"minimized SOP: {f.name} = {sop_string(sop[port], variables)}")
        pos_comments.append(f"minimized POS: {f.name} = {pos_string(pos[port], variables)}")

    sop_path = os.path.join(out_dir, f"{base}_sop.v")
    pos_path = os.path.join(out_dir, f"{base}_pos.v")
    write_two_level_module(sop_path, "circuit_sop", in_ports, sop, "sop", sop_comments)
    write_two_level_module(pos_path, "circuit_pos", in_ports, pos, "pos", pos_comments)
    print("Wrote", sop_path)
    print("Wrote", pos_path)
    print("Board wrappers: fpga/top_nexys4ddr.v (sw[15:0], led[7:0] SOP / led[15:8] POS)")
    print("                fpga/top_arty_z7.v   (sw[1:0] + btn[3:0], led[1:0] SOP / led[3:2] POS)")
