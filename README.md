# bu-ec551-proj1 — Logic Synthesis Engine

EC551 Programming Assignment 1 (Fall 2026). A small Python logic-synthesis tool. It
loads a Boolean function (SOP or POS expression) or a combinational circuit (BLIF),
computes canonical and minimized forms and logic metrics, finds hazards, exports
truth tables, and generates **structural Verilog** that runs on an FPGA (Arty Z7-20
or Nexys 4 DDR).

Plain Python 3 (3.8+), standard library only; nothing else to install.

## Quick start

```bash
py main.py testdata/sop7.txt              # load a file and open the command menu
py main.py 5 testdata/sop7.txt            # run one command (here: minimized SOP) and exit
py main.py a testdata/full_adder.blif     # run all 12 commands
py main.py v testdata/full_adder.blif     # generate Verilog into output/
py -m unittest test_engine.py             # run the tests
```

(`py` is the Windows launcher; use `python3` on macOS/Linux.)

In the menu, type a command number, `v`, `a`, `l <file>` to load another file,
`h` for help, or `q` to quit.

## Input formats

**Boolean expression (`.txt`)**: one expression, single-letter variables, `~` for NOT,
spaces ignored. Variables are ordered alphabetically, and the first one is the most
significant bit of the minterm number. The output is called `F`.

| Form | Example |
|---|---|
| SOP | `~A+B~C+~CD` |
| POS | `(A+B)(~A+C)` |

**BLIF circuit (`.blif`)**: the graph-based input. Each `.names` block is one node
(gate), and the net names are the wires between nodes. Supported: `.model`, `.inputs`,
`.outputs`, `.names` with either ON-set (`... 1`) or OFF-set (`... 0`) rows (not both), `.end`,
`#` comments and `\` line continuation. Multiple outputs are allowed; every command
runs on each one. Example: [testdata/gates.blif](testdata/gates.blif)
```
.model gates
.inputs A B C D
.outputs F G
.names A B n1     # n1 = A AND B
11 1
...
```

## Commands

| # | Command | Output |
|---|---|---|
| 1 | Canonical SOP | sum of minterms, plus Σm(...) |
| 2 | Canonical POS | product of maxterms, plus ΠM(...) |
| 3 | Inverse canonical SOP | SOP of ~F |
| 4 | Inverse canonical POS | POS of ~F |
| 5 | Literal-minimized SOP | minimized SOP + literals saved vs. canonical SOP |
| 6 | Literal-minimized POS | minimized POS + literals saved vs. canonical POS |
| 7 | Prime implicants | count (and the list) |
| 8 | Essential prime implicants | count (and the list) |
| 9 | ON-set minterms | count + Σm list |
| 10 | OFF-set maxterms | count + ΠM list |
| 11 | **Custom Command 1: hazard detection** | static-1 hazards of the minimized SOP and static-0 hazards of the minimized POS, the term/clause that fixes each one, and the hazard-free expression |
| 12 | **Custom Command 2: truth table export** | aligned table on screen + `output/<name>_truth_table.csv` |
| v | Structural Verilog | `output/<name>_sop.v` (module `circuit_sop`) and `output/<name>_pos.v` (module `circuit_pos`) |
| a | Run all of 1–12 | |

Example (`py main.py 11 testdata/hazard.txt`):
```
F minimized SOP = ~AC + AB
  static-1 hazard: A changes while B=1, C=1 (minterms 3 <-> 7); fix: add BC
  hazard-free SOP: F = ~AC + AB + BC
```

## Architecture

```
 .txt / .blif ──► parsers.py ──► list of BoolFunction(name, variables, on_set)
                                          │
              ┌───────────────────────────┼─────────────────────────────┐
              ▼                           ▼                             ▼
          logic.py                custom_commands.py              verilog_gen.py
  canonical forms, formatting,    #11 hazard detection           structural SOP / POS
  Quine-McCluskey, EPIs,          #12 truth table export         modules
  minimal cover
              └───────────────────────────┼─────────────────────────────┘
                                          ▼
                                       main.py
                        menu / one-shot CLI, prints each command
```

**One representation everywhere.** Every input is turned into its truth table: a
`BoolFunction` holds the input names and the set of ON minterms (the OFF-set is
everything else). Every product term or clause is a **cube string** with one character
per variable: `1` = variable, `0` = complemented, `-` = absent. For example, `"1-0"`
is `A~C`.

- Canonical SOP = one full cube per ON minterm. Canonical POS = one full cube per OFF
  minterm, written as a clause by De Morgan (`"1-0"` → `(~A + C)`). The inverse forms
  use the same code with the ON and OFF sets swapped.
- **Minimized SOP** = minimal cover of the ON-set. **Minimized POS** = minimal cover of
  the OFF-set, written as clauses.
- **Quine-McCluskey** (`prime_implicants`): start with one cube per minterm and keep
  merging pairs that differ in one variable (`101` + `100` → `10-`). Cubes that never
  merge are the prime implicants.
- **Essential PIs**: prime implicants that are the only prime implicant covering a minterm.
- **Choosing the cover** (`minimal_cover`): take the essential PIs. Then, while some
  minterms are uncovered, add the prime that covers the most of them (fewest literals
  on a tie). This greedy choice is simple and fast, and usually gives the minimum, but
  not always. On `testdata/cyclic.txt` (no essential PIs) it gives 4 terms where the
  minimum is 3. In a check against brute force on random functions of up to 4
  variables, greedy was not minimal in about 2% of cases.
- **Hazards**: two adjacent minterms of the ON-set (differing in one variable) that no
  single term of the minimized SOP contains form a static-1 hazard. The fix is a prime
  implicant containing both. Static-0 hazards are the same check on the OFF-set
  and the minimized POS.
- **Verilog**: two-level structural circuits using only gate primitives (`not`, `and`,
  `or`). Complemented inputs get one shared `not` gate (`A_n`). Each term with two or
  more literals becomes an `and`/`or` gate on a wire `and0, and1, …`/`or0, or1, …`,
  and the final `or`/`and` gate drives the output. Every generated module has the same
  fixed interface, `circuit_sop` / `circuit_pos (input [15:0] in, output [7:0] out)`.
  The last variable is `in[0]`, the first output is `out[0]`, and `buf` gates at the
  top of the module give each bit its variable name. Because of this, the hand-written
  board wrappers in `fpga/` work for every design.

## Folder structure

```
bu-ec551-proj1/
├── main.py              command-line front end (menu + one-shot), prints the 12 commands
├── parsers.py           .txt expression parser and BLIF parser -> BoolFunction
├── logic.py             BoolFunction, cube helpers, formatting, Quine-McCluskey, minimal cover
├── custom_commands.py   #11 hazard detection, #12 truth table export
├── verilog_gen.py       structural Verilog generation (circuit_sop / circuit_pos)
├── test_engine.py       unit tests (py -m unittest test_engine.py)
├── fpga/                hand-written board files (same for every design)
│   ├── top_arty_z7.v    wrapper module "top", Digilent Arty Z7-20
│   ├── arty_z7_20.xdc   pin constraints, Digilent Arty Z7-20
│   ├── top_nexys4ddr.v  wrapper module "top", Digilent Nexys 4 DDR
│   └── nexys4ddr.xdc    pin constraints, Digilent Nexys 4 DDR
├── testdata/            example inputs (sop*.txt, pos*.txt, hazard.txt, cyclic.txt, *.blif)
├── xtestdata/           example blif inputs with errors, to prove error detection.(xsop*.blif)
└── output/              generated .v and .csv files (created when needed, not committed)
```

## Running on the FPGA

1. Generate the Verilog: `py main.py v testdata/full_adder.blif`
2. In Vivado: **Create Project → RTL Project**, then choose the part:
   - Arty Z7-20: `xc7z020clg400-1`
   - Nexys 4 DDR: `xc7a100tcsg324-1`
3. Add design sources: `output/<name>_sop.v`, `output/<name>_pos.v`, and your board's
   wrapper: `fpga/top_arty_z7.v` or `fpga/top_nexys4ddr.v`.
4. Add the constraints for your board: `fpga/arty_z7_20.xdc` or `fpga/nexys4ddr.xdc`.
5. Generate Bitstream → Open Hardware Manager → Program Device.
   On the Arty Z7, set the programming-mode jumper (JP4) to JTAG.

To try a different design, replace the two `output/` files with the new ones. The
wrapper and constraints stay the same.

**I/O mapping** (also in the comments of each wrapper):

| | Nexys 4 DDR | Arty Z7-20 |
|---|---|---|
| Inputs (`in[0]` = last variable) | `sw[15:0]` | `sw[1:0]`, then `btn[3:0]` (6 inputs) |
| SOP outputs (`out[0]` = first output) | `led[7:0]` | `led[1:0]` |
| POS outputs | `led[15:8]` | `led[3:2]` |

The switches read as the minterm number in binary. The SOP and POS circuits implement
the same function, so their LEDs should always match. Check them against the CSV from
command 12.

## Testing

`py -m unittest test_engine.py` checks that the minimized SOP/POS of every file in
`testdata/` reproduces the original truth table. It also checks the POS and BLIF
parsers, the cyclic function with no essential PIs, and the hazard example.

## Testdata Usage
| Edge Case Tested | Command |
|---|---|
|Minimal Cases|sop[1 to 3].[blif/txt]|
|Linking Minimal Cases|sop[4a/4b//5a/5b/6].[blif/txt]|
|Varying .blif implementation with same result|sop4[a/b].blif, sop5[a/b].blif, sop7[a/b].blif|
|Difference between PI/EPI non-equivalence|sop9.txt|

|Common Errors|Error Detection Proof|
|---|---|
|Missing Primary Input|xsop1.blif|
|Missing .outputs line|xsop2.blif|
|Missing outputs in .outputs line|xsop3.blif|
|Internal wire driven twice|xsop4.blif|
|Primary Input driven by internal gate|xsop5.blif|

|Uncaught Errors|File used|
|---|---|
|Internal gate ordering|xsop6.blif; will provide incorrect verilog code, will not result in correct commands.|
|Missing '.end' line|xsop7.blif; will provide incorrect verilog code, will not result in correct commands|
|Error in gate names|xsop8.blif; will provide incorrect verilog code, will not result in correct commands|


## AI usage

Per the course AI policy: this project was developed with help from Anthropic's Claude
(Claude Code). It was used to restructure our original `main.py` and BLIF parser into
the current modules, and to write the minimization, hazard, truth-table, Verilog and
test code, the FPGA wrappers/constraints, and some of this README. Design decisions (input
formats, interface, minimization method, custom commands, Verilog style, target
boards) were made by the team.
