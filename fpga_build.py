"""
Usage:
    py fpga_build.py <board> <input file>
    board: nexys  (Digilent Nexys 4 DDR)
           

Steps:
    1. generate output/<name>_sop.v and output/<name>_pos.v (same as command v)
    2. copy the files Vivado needs into a work folder, and run
       Vivado in batch mode there with fpga/build.tcl: synthesis,
       implementation, bitstream, then program the connected board
    3. copy the bitstream and Vivado's log back to build/
"""

import os
import shutil
import subprocess
import sys
import tempfile

from logic import TooLargeError
from main import load_design
from verilog_gen import verilog_name, write_verilog

VIVADO = r"C:\AMDDesignTools\2025.2\Vivado\bin\vivado.bat"

WORK_DIR = os.path.join(tempfile.gettempdir(), "ec551_fpga_build")

BOARDS = {
    "nexys": {
        "part": "xc7a100tcsg324-1",
        "top": "fpga/top_nexys4ddr.v",
        "xdc": "fpga/Nexys4DDR_Master.xdc",
        "inputs": 16,         # sw[15:0]
        "outputs": 8,         # led[7:0] SOP, led[15:8] POS
    },
}


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in BOARDS:
        print(__doc__)
        sys.exit(1)
    board_name = sys.argv[1]
    board = BOARDS[board_name]
    input_path = os.path.abspath(sys.argv[2])
    if not os.path.exists(VIVADO):
        print(f"Vivado not found at {VIVADO}; edit VIVADO at the top of fpga_build.py")
        sys.exit(1)

    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    design = load_design(input_path)
    try:
        write_verilog(design.functions, design.name, design.path, "output")
    except TooLargeError as error:
        print("Stopped:", error)
        sys.exit(1)
    if len(design.functions[0].variables) > board["inputs"] or len(design.functions) > board["outputs"]:
        print(f"Note: this board shows only the first {board['inputs']} inputs "
              f"and {board['outputs']} outputs")

    shutil.rmtree(WORK_DIR, ignore_errors=True)
    os.makedirs(WORK_DIR, exist_ok=True)
    base = verilog_name(design.name)
    sources = [f"output/{base}_sop.v", f"output/{base}_pos.v", board["top"]]
    for file in sources + [board["xdc"], "fpga/build.tcl"]:
        shutil.copy(file, WORK_DIR)
    bitfile = f"{base}_{board_name}.bit"
    command = [VIVADO, "-mode", "batch", "-nojournal", "-log", "vivado.log",
               "-source", "build.tcl",
               "-tclargs", board["part"], bitfile, os.path.basename(board["xdc"])]
    command += [os.path.basename(file) for file in sources]
    print("Running Vivado (takes a few minutes)...", flush=True)
    result = subprocess.run(command, cwd=WORK_DIR)

    os.makedirs("build", exist_ok=True)
    built = os.path.exists(os.path.join(WORK_DIR, bitfile))
    for file in (bitfile, "vivado.log"):
        if os.path.exists(os.path.join(WORK_DIR, file)):
            shutil.copy(os.path.join(WORK_DIR, file), "build")
    if result.returncode != 0:
        if built:
            print(f"build/{bitfile} was built, but programming the board failed (see the message above)")
        else:
            print("Vivado stopped with an error; see build/vivado.log")
        sys.exit(1)
    print(f"Done: build/{bitfile} is on the {board_name} board")


if __name__ == "__main__":
    main()
