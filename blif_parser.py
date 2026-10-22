"""BLIF (Berkeley Logic Interchange Format) parser -- combinational subset.

Standalone: uses only the Python standard library, so this file can be copied
into another project and imported or run on its own.

BLIF is the graph-based circuit input: every .names block is a node (a logic
function of its input nets) and the named nets are the edges.

Supported:
    .model <name>
    .inputs <a> <b> ...          (may repeat)
    .outputs <f> ...             (may repeat)
    .names <in1> ... <out>       followed by single-output cover rows:
        1-0 1                    input pattern (0/1/-) and output value
        1                        (constant node: no inputs)
    .end
    '#' comments and '\\' line continuation.

A .names cover whose rows end in 1 lists the ON-set; rows ending in 0 list the
OFF-set. A .names with no rows is constant 0. Only the first .model is read.
Sequential/hierarchical constructs (.latch, .subckt, ...) are rejected because
only combinational logic is supported.

After parsing, the graph is checked (every net driven exactly once, no
undefined nets, no combinational loops), sorted topologically, and evaluated
row by row over all 2^n input combinations to get each output's truth table.

Two results are available:
  parse_blif_file(path) -> {output: canonical SOP text} in the testdata format
                           (e.g. "~A~BC+~AB~C+A~B~C+ABC"), one entry per output
  read_blif_file(path)  -> BlifCircuit(name, inputs, on_sets): the truth table
                           with the original net names (the engine's load_any()
                           wraps this into a BoolFunction)

SOP text format (same as testdata/sop*.txt): single-letter variables, AND by
juxtaposition, '~' before a complemented variable, '+' between terms, no
spaces and no trailing newline. BLIF inputs that are not all single letters
are renamed A, B, C, ... in declared order (first input = MSB of the minterm
index); see input_letters(). Run  py blif_parser.py <file.blif>  to print the
conversion.
"""

import string
import sys
from collections import deque, namedtuple
from pathlib import Path


class BlifError(ValueError):
    pass


# Parsed and evaluated circuit. on_sets maps each output name to the set of
# minterm numbers where that output is 1 (first input = MSB of the minterm).
BlifCircuit = namedtuple("BlifCircuit", ["name", "inputs", "on_sets"])

_UNSUPPORTED = {".latch", ".mlatch", ".subckt", ".gate", ".search", ".exdc", ".fsm"}


class Cover:
    """One .names node: drives net `name` from `inputs` via single-output cover rows."""

    def __init__(self, name, inputs, lineno):
        self.name = name
        self.inputs = inputs
        self.lineno = lineno
        self.rows = []              # input patterns such as "1-0"
        self.out_value = 1          # rows describe the ON-set (1) or OFF-set (0)


def _logical_lines(text):
    """Yield (line_number, content) with comments stripped and '\\' lines joined."""
    buf, start = "", None
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.split("#", 1)[0].rstrip()
        if start is None:
            start = lineno
        if line.endswith("\\"):
            buf += line[:-1] + " "
            continue
        buf += line
        if buf.strip():
            yield start, buf.strip()
        buf, start = "", None
    if buf.strip():
        yield start, buf.strip()


def read_blif_text(text, default_name="circuit"):
    """Parse BLIF text and evaluate it; returns a BlifCircuit (original names)."""
    name = default_name
    inputs, outputs = [], []
    covers = []
    current = None
    for lineno, line in _logical_lines(text):
        tokens = line.split()
        head = tokens[0]
        if head.startswith("."):
            current = None
            directive = head.lower()
            if directive == ".model":
                name = tokens[1] if len(tokens) > 1 else name
            elif directive == ".inputs":
                inputs += tokens[1:]
            elif directive == ".outputs":
                outputs += tokens[1:]
            elif directive == ".names":
                if len(tokens) < 2:
                    raise BlifError(f"BLIF line {lineno}: .names needs at least an output net")
                current = Cover(tokens[-1], tokens[1:-1], lineno)
                covers.append(current)
            elif directive == ".end":
                break
            elif directive in _UNSUPPORTED:
                raise BlifError(f"BLIF line {lineno}: {directive} is not supported "
                                "(combinational single-model BLIF only)")
            # other directives (.default_input_arrival, ...) carry timing info only; ignored
            continue

        if current is None:
            raise BlifError(f"BLIF line {lineno}: cover row outside a .names block: {line!r}")
        n_in = len(current.inputs)
        if n_in == 0:
            pattern, outv = "", tokens[0]
            if len(tokens) != 1:
                raise BlifError(f"BLIF line {lineno}: constant node row must be '0' or '1'")
        else:
            if len(tokens) != 2:
                raise BlifError(f"BLIF line {lineno}: expected '<pattern> <value>', got {line!r}")
            pattern, outv = tokens
            if len(pattern) != n_in or set(pattern) - set("01-"):
                raise BlifError(f"BLIF line {lineno}: pattern {pattern!r} must be "
                                f"{n_in} characters of 0/1/-")
        if outv not in ("0", "1"):
            raise BlifError(f"BLIF line {lineno}: output value must be 0 or 1, got {outv!r}")
        if current.rows and int(outv) != current.out_value:
            raise BlifError(f"BLIF line {lineno}: a cover may not mix ON (1) and OFF (0) rows")
        current.rows.append(pattern)
        current.out_value = int(outv)

    if not outputs:
        raise BlifError("BLIF: no .outputs declared")

    nodes = _check_graph(inputs, outputs, covers)
    order = _topological_order(nodes)
    return BlifCircuit(name, inputs, _evaluate(inputs, outputs, order))


def read_blif_file(path):
    """BLIF file -> BlifCircuit with the original net names."""
    path = Path(path)
    return read_blif_text(path.read_text(encoding="utf-8-sig"), default_name=path.stem)


def _check_graph(inputs, outputs, covers):
    """Check that every net is driven exactly once; return {net: Cover}."""
    if len(set(inputs)) != len(inputs):
        raise BlifError("BLIF: duplicate primary input name")
    nodes = {}
    for node in covers:
        if node.name in inputs:
            raise BlifError(f"BLIF line {node.lineno}: net {node.name!r} is a primary input "
                            "and cannot be driven by a .names")
        if node.name in nodes:
            raise BlifError(f"BLIF line {node.lineno}: net {node.name!r} is already driven "
                            f"by the .names on line {nodes[node.name].lineno}")
        nodes[node.name] = node
    known = set(inputs) | set(nodes)
    for node in covers:
        for net in node.inputs:
            if net not in known:
                raise BlifError(f"BLIF line {node.lineno}: .names {node.name!r} "
                                f"uses undefined net {net!r}")
    for out in outputs:
        if out not in known:
            raise BlifError(f"BLIF: output {out!r} is not driven by any .names or input")
    return nodes


def _topological_order(nodes):
    """Kahn's algorithm: nodes ordered so every node follows its fan-in."""
    indeg = {name: sum(1 for net in node.inputs if net in nodes)
             for name, node in nodes.items()}
    fanout = {name: [] for name in nodes}
    for name, node in nodes.items():
        for net in node.inputs:
            if net in nodes:
                fanout[net].append(name)
    ready = deque(name for name, d in indeg.items() if d == 0)
    order = []
    while ready:
        name = ready.popleft()
        order.append(nodes[name])
        for nxt in fanout[name]:
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                ready.append(nxt)
    if len(order) != len(nodes):
        # leftovers include nodes merely downstream of a loop; peel those off
        stuck = {name for name, d in indeg.items() if d > 0}
        while True:
            sinks = {s for s in stuck if not any(f in stuck for f in fanout[s])}
            if not sinks:
                break
            stuck -= sinks
        raise BlifError("BLIF: combinational loop detected involving: " + ", ".join(sorted(stuck)))
    return order


def _evaluate(inputs, outputs, order):
    """Fill in the truth table one row at a time; return {output: set of ON minterms}."""
    n = len(inputs)
    on_sets = {out: set() for out in outputs}
    for m in range(2 ** n):
        # input values for minterm m, first input = most significant bit
        values = {net: (m >> (n - 1 - i)) & 1 for i, net in enumerate(inputs)}
        for node in order:                       # fan-in is always evaluated first
            values[node.name] = _eval_cover(node, values)
        for out in outputs:
            if values[out] == 1:
                on_sets[out].add(m)
    return on_sets


def _eval_cover(node, values):
    """Value (0/1) of a .names node: 1 if any row matches (flipped for OFF-set rows)."""
    def row_matches(row):
        return all(ch == "-" or int(ch) == values[net] for ch, net in zip(row, node.inputs))

    hit = any(row_matches(row) for row in node.rows)
    return int(hit) if node.out_value == 1 else int(not hit)


# ---------------------------------------------------------------------------
# SOP text in the testdata format
# ---------------------------------------------------------------------------

def input_letters(inputs):
    """Single-letter name for each input, in order.

    Inputs that are already distinct single letters keep their names;
    otherwise they are renamed A, B, C, ... in declared order.
    """
    if all(len(v) == 1 and v.isalpha() for v in inputs) and len(set(inputs)) == len(inputs):
        return list(inputs)
    if len(inputs) > len(string.ascii_uppercase):
        raise BlifError(f"BLIF: {len(inputs)} inputs cannot be renamed to single letters (max 26)")
    return list(string.ascii_uppercase[:len(inputs)])


def canonical_sop_text(letters, on_set):
    """Sum of minterms such as ~A~BC+AB~C (first letter = MSB of the minterm index)."""
    if not letters:
        raise BlifError("BLIF: a function with no inputs cannot be written as SOP text")
    if not on_set:
        return f"{letters[0]}~{letters[0]}"          # constant 0, written as A AND NOT A
    n = len(letters)
    terms = []
    for m in sorted(on_set):
        term = ""
        for i, letter in enumerate(letters):
            bit = (m >> (n - 1 - i)) & 1
            term += letter if bit else "~" + letter
        terms.append(term)
    return "+".join(terms)


def sop_texts(circuit):
    """{output: canonical SOP text} for every output of a BlifCircuit."""
    letters = input_letters(circuit.inputs)
    return {out: canonical_sop_text(letters, on) for out, on in circuit.on_sets.items()}


def parse_blif_text(text, default_name="circuit"):
    """BLIF text -> {output: canonical SOP text} in the testdata format."""
    return sop_texts(read_blif_text(text, default_name))


def parse_blif_file(path):
    """BLIF file -> {output: canonical SOP text} in the testdata format.

    Example (testdata/full_adder.blif, inputs A B Cin -> A B C):
        {"S": "~A~BC+~AB~C+A~B~C+ABC", "Cout": "~ABC+A~BC+AB~C+ABC"}
    """
    return sop_texts(read_blif_file(path))


if __name__ == "__main__":
    # py blif_parser.py <file.blif>: show the letter mapping and SOP text
    if len(sys.argv) != 2:
        print("usage: py blif_parser.py <file.blif>")
        sys.exit(1)
    circuit = read_blif_file(sys.argv[1])
    for original, letter in zip(circuit.inputs, input_letters(circuit.inputs)):
        print(f"{letter} = {original}")
    for out, sop in sop_texts(circuit).items():
        print(f"{out}: {sop}")
