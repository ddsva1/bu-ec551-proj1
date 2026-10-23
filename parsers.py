"""Input parsers: turn an input file into a list of BoolFunction objects.

Two input formats are supported:

1. Boolean expression (.txt) -- one SOP or POS expression, single-letter
   variables, '~' for NOT, spaces are ignored:
       SOP:  ~A+B~C+~CD
       POS:  (A+B)(~A+C)
   The output is named F. Variables are ordered alphabetically, and the first
   one is the most significant bit of the minterm number.

2. BLIF circuit (.blif):
       .model <name>
       .inputs <a> <b> ...
       .outputs <f> ...
       .names <in1> <in2> ... <out>    one node; the rows below are its truth table
       1-0 1                            
       .end
"""

import string

from logic import BoolFunction, input_values


def parse_literals(text):
    """'~AB~C' -> [("A", False), ("B", True), ("C", False)]"""
    literals = []
    negate = False
    for ch in text:
        if ch == "~":
            negate = not negate
        elif ch.isalpha():
            literals.append((ch, not negate))
            negate = False
        else:
            raise ValueError(f"unexpected character {ch!r} in {text!r}")
    if negate:
        raise ValueError(f"'~' must be followed by a variable in {text!r}")
    return literals


def literal_is_true(literal, values):
    var, positive = literal
    return values[var] == (1 if positive else 0)


def read_txt(path):
    """Read one SOP or POS expression from a text file."""
    with open(path, encoding="utf-8-sig") as file:
        expr = "".join(file.read().split())      # drop all spaces and newlines
    if not expr:
        raise ValueError(f"{path}: file is empty")
    bad = set(expr) - set(string.ascii_letters + "~+()")
    if bad:
        raise ValueError(f"{path}: unexpected characters {''.join(sorted(bad))!r}")

    # same idea as zero() in the original main.py: collect the variables used
    variables = sorted({ch for ch in expr if ch.isalpha()})

    if "(" in expr:
        if not (expr.startswith("(") and expr.endswith(")")):
            raise ValueError(f"{path}: a POS expression must look like (A+B)(~C+D)")
        clauses = []
        for clause_text in expr[1:-1].split(")("):
            clause = []
            for piece in clause_text.split("+"):
                literals = parse_literals(piece)
                if len(literals) != 1:
                    raise ValueError(f"{path}: each POS clause must be literals joined by '+', "
                                     f"got ({clause_text})")
                clause += literals
            clauses.append(clause)

        def is_on(values):
            return all(any(literal_is_true(lit, values) for lit in clause) for clause in clauses)
    else:
        terms = [parse_literals(term_text) for term_text in expr.split("+")]
        if any(len(term) == 0 for term in terms):
            raise ValueError(f"{path}: empty product term (check for '++' or a trailing '+')")

        def is_on(values):
            return any(all(literal_is_true(lit, values) for lit in term) for term in terms)

    on_set = {m for m in range(2 ** len(variables)) if is_on(input_values(m, variables))}
    return [BoolFunction("F", variables, on_set)]



UNSUPPORTED = (".latch", ".mlatch", ".subckt", ".gate", ".search", ".fsm")


class Gate:
    """One .names block: a logic node driving one net."""

    def __init__(self, inputs):
        self.inputs = inputs     # names of the input nets
        self.rows = []           # cover rows such as "1-0"
        self.row_value = 1       # 1: rows list the ON-set, 0: rows list the OFF-set


def blif_lines(text):
    """Lines of a BLIF file with comments removed and '\\' continuations joined."""
    lines = []
    current = ""
    for raw in text.splitlines():
        current += raw.split("#")[0].strip()
        if current.endswith("\\"):
            current = current[:-1] + " "
            continue
        if current.strip():
            lines.append(current.strip())
        current = ""
    return lines


def evaluate_net(net, values, gates):
    """Value (0/1) of a net for one input combination.

    `values` starts with the primary inputs. Each gate's result is stored in
    it, so the recursion walks back through the graph only as far as needed.
    """
    if net in values:
        return values[net]
    if net not in gates:
        raise ValueError(f"net {net!r} is used but never driven")
    gate = gates[net]
    in_values = [evaluate_net(name, values, gates) for name in gate.inputs]
    row_hit = any(all(c == "-" or int(c) == v for c, v in zip(row, in_values))
                  for row in gate.rows)
    values[net] = int(row_hit) if gate.row_value == 1 else int(not row_hit)
    return values[net]


def read_blif(path):
    """Read a combinational BLIF file; one BoolFunction per output."""
    with open(path, encoding="utf-8-sig") as file:
        lines = blif_lines(file.read())

    inputs, outputs = [], []
    gates = {}          # net name -> Gate driving it
    gate = None         # the .names block whose rows are being read
    for line in lines:
        tokens = line.split()
        keyword = tokens[0]
        if keyword == ".inputs":
            inputs += tokens[1:]
        elif keyword == ".outputs":
            outputs += tokens[1:]
        elif keyword == ".names":
            if len(tokens) < 2:
                raise ValueError(f"{path}: '.names' needs at least an output net")
            net = tokens[-1]
            if net in gates or net in inputs:
                raise ValueError(f"{path}: net {net!r} is driven more than once")
            gate = Gate(tokens[1:-1])
            gates[net] = gate
        elif keyword == ".end":
            break
        elif keyword in UNSUPPORTED:
            raise ValueError(f"{path}: {keyword} is not supported (combinational BLIF only)")
        elif keyword.startswith("."):
            gate = None                     # .model and other directives: nothing to do
        else:
            # a cover row of the current .names block
            if gate is None:
                raise ValueError(f"{path}: row {line!r} is not inside a .names block")
            if len(gate.inputs) == 0:
                pattern, value = "", tokens[0]          # constant node: just "1" or "0"
            elif len(tokens) == 2:
                pattern, value = tokens
            else:
                raise ValueError(f"{path}: expected '<pattern> <value>', got {line!r}")
            if len(pattern) != len(gate.inputs) or set(pattern) - set("01-") or value not in ("0", "1"):
                raise ValueError(f"{path}: bad cover row {line!r}")
            gate.rows.append(pattern)
            gate.row_value = int(value)

    if not inputs:
        raise ValueError(f"{path}: no .inputs declared")
    if not outputs:
        raise ValueError(f"{path}: no .outputs declared")

    functions = []
    try:
        for out in outputs:
            on_set = set()
            for m in range(2 ** len(inputs)):
                if evaluate_net(out, input_values(m, inputs), gates) == 1:
                    on_set.add(m)
            functions.append(BoolFunction(out, inputs, on_set))
    except RecursionError:
        raise ValueError(f"{path}: combinational loop detected") from None
    return functions
