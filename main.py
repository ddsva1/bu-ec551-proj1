

import os
import sys
from collections import namedtuple


from custom_commands import export_truth_table, report_hazards
from logic import (TooLargeError, essential_prime_implicants, literal_count, minimal_cover,
                   minterm_cubes, pos_string, prime_implicants, sop_string, on_string)
from parsers import read_blif, read_txt
from verilog_gen import write_verilog

OUTPUT_DIR = "output"

Design = namedtuple("Design", ["name", "path", "functions"])


def load_design(path):
    if path.lower().endswith(".blif"):
        functions = read_blif(path)
    else:
        functions = read_txt(path)
    name = os.path.splitext(os.path.basename(path))[0]
    variables = functions[0].variables
    print(f"Loaded {path}: inputs {', '.join(variables)}; "
          f"output(s) {', '.join(f.name for f in functions)}")
    return Design(name, path, functions)


def numbers(minterms):
    """Comma-separated sorted minterm numbers, e.g. "0, 3, 5"."""
    return ", ".join(str(m) for m in sorted(minterms))



def canonical_sop(design):
    for f in design.functions:
        print(f"{f.name} = {sop_string(minterm_cubes(f.on_set, f.num_vars), f.variables)}")
        print(f"{f.name} = Σm({numbers(f.on_set)})")


def canonical_pos(design):
    for f in design.functions:
        print(f"{f.name} = {pos_string(minterm_cubes(f.off_set, f.num_vars), f.variables)}")
        print(f"{f.name} = ΠM({numbers(f.off_set)})")


def inverse_canonical_sop(design):
    # the inverse is 1 exactly where F is 0, so its minterms are F's OFF-set
    for f in design.functions:
        print(f"~{f.name} = {sop_string(minterm_cubes(f.off_set, f.num_vars), f.variables)}")
        print(f"~{f.name} = Σm({numbers(f.off_set)})")


def inverse_canonical_pos(design):
    # the inverse is 0 exactly where F is 1, so its maxterms are F's ON-set
    for f in design.functions:
        print(f"~{f.name} = {pos_string(minterm_cubes(f.on_set, f.num_vars), f.variables)}")
        print(f"~{f.name} = ΠM({numbers(f.on_set)})")


def minimized_sop(design):
    for f in design.functions:
        cover = minimal_cover(f.on_set, f.num_vars)
        canonical = len(f.on_set) * f.num_vars
        minimized = literal_count(cover)
        print(f"{f.name} = {sop_string(cover, f.variables)}")
        print(f"  literals: canonical SOP {canonical} -> minimized {minimized} "
              f"(saved {canonical - minimized})")


def minimized_pos(design):
    # minimize the OFF-set, then write each cube as a clause (De Morgan)
    for f in design.functions:
        cover = minimal_cover(f.off_set, f.num_vars)
        canonical = len(f.off_set) * f.num_vars
        minimized = literal_count(cover)
        print(f"{f.name} = {pos_string(cover, f.variables)}")
        print(f"  literals: canonical POS {canonical} -> minimized {minimized} "
              f"(saved {canonical - minimized})")


def prime_implicant_count(design):
    for f in design.functions:
        primes = prime_implicants(f.on_set, f.num_vars)
        print(f"{f.name}: {len(primes)} prime implicant(s)")
        for p in primes:
            print(f"  {on_string(p, f.variables):<12} cube {p}")


def essential_prime_implicant_count(design):
    for f in design.functions:
        primes = prime_implicants(f.on_set, f.num_vars)
        essentials = essential_prime_implicants(primes, f.on_set)
        print(f"{f.name}: {len(essentials)} essential prime implicant(s)")
        for p in essentials:
            print(f"  {on_string(p, f.variables):<12} cube {p}")


def on_set_minterms(design):
    for f in design.functions:
        print(f"{f.name}: {len(f.on_set)} ON-set minterm(s)  Σm({numbers(f.on_set)})")


def off_set_maxterms(design):
    for f in design.functions:
        print(f"{f.name}: {len(f.off_set)} OFF-set maxterm(s)  ΠM({numbers(f.off_set)})")


def hazard_detection(design):
    for f in design.functions:
        report_hazards(f)


def truth_table(design):
    export_truth_table(design.functions, design.name, OUTPUT_DIR)


def verilog(design):
    write_verilog(design.functions, design.name, design.path, OUTPUT_DIR)


def run_all(design):
    for key in [str(i) for i in range(1, 13)]:
        run_command(key, design)


COMMANDS = {
    "1": ("Canonical SOP", canonical_sop),
    "2": ("Canonical POS", canonical_pos),
    "3": ("Inverse canonical SOP", inverse_canonical_sop),
    "4": ("Inverse canonical POS", inverse_canonical_pos),
    "5": ("Minimized SOP", minimized_sop),
    "6": ("Minimized POS", minimized_pos),
    "7": ("Number of prime implicants", prime_implicant_count),
    "8": ("Number of essential prime implicants", essential_prime_implicant_count),
    "9": ("ON-set minterms (Σm)", on_set_minterms),
    "10": ("OFF-set maxterms (ΠM)", off_set_maxterms),
    "11": ("Custom 1: hazard detection (static-1 / static-0)", hazard_detection),
    "12": ("Custom 2: truth table export (screen + CSV)", truth_table),
    "v": ("Generate structural Verilog (SOP + POS)", verilog),
    "a": ("Run all commands 1-12", run_all),
}


def run_command(key, design):
    description, function = COMMANDS[key]
    print(f"\n[{key}] {description}")
    try:
        function(design)
    except TooLargeError as error:
        print("Stopped:", error)


def help():
    print("Structure of command line input:")
    print("  py main.py <file>              load the file and open the command menu")
    print("  py main.py <command> <file>    run one command, e.g. py main.py 5 testdata/sop7.txt")
    print("--------------------------------------------------")
    print("Available input file types:")
    print("  .txt   SOP like ~A+B~C+~CD  or  POS like (A+B)(~A+C)")
    print("  .blif  combinational BLIF circuit (multiple outputs allowed)")
    print("--------------------------------------------------")
    print("Available commands:")
    for key, (description, _) in COMMANDS.items():
        print(f"  {key:>2}: {description}")
    print("==================================================")


def menu_loop(design):
    help()
    print("In the menu you can also type:  l <file> = load another file,  h = help,  q = quit")
    while True:
        try:
            choice = input("\ncommand> ").strip()
        except EOFError:
            break
        if choice in ("q", "quit", "exit"):
            break
        elif choice == "h":
            help()
        elif choice.startswith("l "):
            try:
                design = load_design(choice[2:].strip())
            except (OSError, ValueError) as error:
                print("Error:", error)
        elif choice in COMMANDS:
            run_command(choice, design)
        elif choice:
            print("Unknown command; type h for help.")


def main():
    sys.stdout.reconfigure(encoding="utf-8")       # so Σ and Π print on Windows
    args = sys.argv[1:]
    if len(args) == 1:
        command, path = None, args[0]
    elif len(args) == 2:
        command, path = args
    else:
        help()
        return

    if command is not None and command not in COMMANDS:
        print(f"Unknown command {command!r}.")
        help()
        sys.exit(1)
    try:
        design = load_design(path)
    except (OSError, ValueError) as error:
        print("Error:", error)
        sys.exit(1)

    if command is None:
        menu_loop(design)
    else:
        run_command(command, design)


if __name__ == "__main__":
    main()
