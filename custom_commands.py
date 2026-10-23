"""Custom commands.

Command 11 - Hazard detection
    Finds static-1 hazards in the minimized SOP and static-0 hazards in the
    minimized POS, says which extra term or clause removes each one, and
    prints the hazard-free form.

Command 12 - Truth table export
    Prints the truth table of every output and saves it as a CSV file.
"""

import csv
import os

from logic import (covers, input_values, minimal_cover, prime_implicants,
                   pos_string, sop_string, on_string, off_string, to_cube)


# ---------------------------------------------------------------------------
# Command 11: hazard detection
# ---------------------------------------------------------------------------

def find_static_hazards(minterms, cover, n):
    """Static hazards of a two-level cover.

    Two minterms of the set that differ in one variable are "adjacent". If no
    single cube of the cover contains both, then while that variable changes
    one gate turns off as another turns on, and the output can glitch. That
    is a static hazard. The fix is to add a prime implicant that contains
    both minterms (one always exists).

    Call with the ON-set and the minimized SOP cover for static-1 hazards,
    or with the OFF-set and the minimized POS cover for static-0 hazards.

    Returns (hazards, fixes). Each hazard is (m1, m2, var_index, fix_cube),
    and fixes is the list of cubes to add to the cover.
    """
    primes = prime_implicants(minterms, n)
    hazards = []
    fixes = []
    for m1 in sorted(minterms):
        for i in range(n):
            m2 = m1 ^ (1 << (n - 1 - i))           # flip variable i (variable 0 = MSB)
            if m2 < m1 or m2 not in minterms:
                continue                            # visit each adjacent pair once
            if any(covers(c, m1) and covers(c, m2) for c in cover):
                continue                            # one term holds the output steady
            # reuse a fix that was already added if it covers this pair too
            fix = next(c for c in fixes + primes if covers(c, m1) and covers(c, m2))
            if fix not in fixes:
                fixes.append(fix)
            hazards.append((m1, m2, i, fix))
    return hazards, fixes


def describe_transition(m1, var_index, variables):
    """Text such as "A changes while B=1, C=1"."""
    values = input_values(m1, variables)
    others = [f"{var}={values[var]}" for j, var in enumerate(variables) if j != var_index]
    return f"{variables[var_index]} changes while {', '.join(others) or 'no other inputs'}"


def report_hazards(f):
    """Print the static-1 (SOP) and static-0 (POS) hazards of one function."""
    n, variables = f.num_vars, f.variables

    # static-1: output should stay 1, minimized SOP
    sop_cover = minimal_cover(f.on_set, n)
    hazards, fixes = find_static_hazards(f.on_set, sop_cover, n)
    print(f"{f.name} minimized SOP = {sop_string(sop_cover, variables)}")
    if not hazards:
        print("  no static-1 hazards")
    for m1, m2, i, fix in hazards:
        print(f"  static-1 hazard: {describe_transition(m1, i, variables)} "
              f"(minterms {m1} <-> {m2}); fix: add {on_string(fix, variables)}")
    if hazards:
        print(f"  hazard-free SOP: {f.name} = {sop_string(sop_cover + fixes, variables)}")

    # static-0: output should stay 0, minimized POS
    pos_cover = minimal_cover(f.off_set, n)
    hazards, fixes = find_static_hazards(f.off_set, pos_cover, n)
    print(f"{f.name} minimized POS = {pos_string(pos_cover, variables)}")
    if not hazards:
        print("  no static-0 hazards")
    for m1, m2, i, fix in hazards:
        print(f"  static-0 hazard: {describe_transition(m1, i, variables)} "
              f"(maxterms {m1} <-> {m2}); fix: add {off_string(fix, variables)}")
    if hazards:
        print(f"  hazard-free POS: {f.name} = {pos_string(pos_cover + fixes, variables)}")


# ---------------------------------------------------------------------------
# Command 12: truth table export
# ---------------------------------------------------------------------------

MAX_PRINTED_ROWS = 64


def truth_table_rows(functions):
    """Header and rows: minterm number, input bits, then one column per output."""
    variables = functions[0].variables
    n = len(variables)
    header = ["m"] + variables + [f.name for f in functions]
    rows = []
    for m in range(2 ** n):
        bits = [int(b) for b in to_cube(m, n)]
        outputs = [1 if m in f.on_set else 0 for f in functions]
        rows.append([m] + bits + outputs)
    return header, rows


def print_truth_table(header, rows, num_inputs):
    """Aligned table: m | inputs | outputs."""
    widths = [max(len(str(row[i])) for row in [header] + rows) for i in range(len(header))]

    def line(values):
        cells = [str(v).rjust(w) for v, w in zip(values, widths)]
        return (cells[0] + " | " + " ".join(cells[1:1 + num_inputs])
                + " | " + " ".join(cells[1 + num_inputs:]))

    print(line(header))
    print("-" * len(line(header)))
    for row in rows[:MAX_PRINTED_ROWS]:
        print(line(row))
    if len(rows) > MAX_PRINTED_ROWS:
        print(f"... {len(rows) - MAX_PRINTED_ROWS} more rows (see the CSV file)")


def export_truth_table(functions, design_name, out_dir):
    """Print the truth table and save it to <out_dir>/<design>_truth_table.csv."""
    header, rows = truth_table_rows(functions)
    print_truth_table(header, rows, len(functions[0].variables))

    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{design_name}_truth_table.csv")
    with open(path, "w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(header)
        writer.writerows(rows)
    print(f"Saved {path}")
