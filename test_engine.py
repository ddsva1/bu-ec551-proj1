"""Sanity checks for the engine.  Run with:  py -m unittest test_engine.py"""

import glob
import os
import unittest

from custom_commands import find_static_hazards
from logic import (cover_minterms, essential_prime_implicants, input_values,
                   minimal_cover, pos_string, prime_implicants, sop_string)
from parsers import read_blif, read_txt

TESTDATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "testdata")


def load(name):
    path = os.path.join(TESTDATA, name)
    return read_blif(path) if name.endswith(".blif") else read_txt(path)


class TestEngine(unittest.TestCase):

    def test_minimized_forms_match_truth_table(self):
        # every minimized SOP must cover exactly the ON-set, every minimized POS the OFF-set
        for path in glob.glob(os.path.join(TESTDATA, "*")):
            for f in load(os.path.basename(path)):
                with self.subTest(file=os.path.basename(path), output=f.name):
                    n = f.num_vars
                    self.assertEqual(cover_minterms(minimal_cover(f.on_set, n), n), f.on_set)
                    self.assertEqual(cover_minterms(minimal_cover(f.off_set, n), n), f.off_set)

    def test_sop_parse_and_minimize(self):
        f = load("sop7.txt")[0]
        self.assertEqual(f.variables, ["A", "B", "C", "D"])
        self.assertEqual(f.on_set, {0, 1, 2, 3, 4, 5, 6, 7, 9, 12, 13})
        self.assertEqual(sop_string(minimal_cover(f.on_set, 4), f.variables), "~A + B~C + ~CD")
        self.assertEqual(pos_string(minimal_cover(f.off_set, 4), f.variables), "(~A + B + D)(~A + ~C)")

    def test_pos_parse(self):
        f = load("pos1.txt")[0]                  # (A+B)(~A+C)
        self.assertEqual(f.on_set, {2, 3, 5, 7})

    def test_full_adder_blif(self):
        s, cout = load("full_adder.blif")
        self.assertEqual(s.on_set, {1, 2, 4, 7})
        self.assertEqual(cout.on_set, {3, 5, 6, 7})
        self.assertEqual(len(prime_implicants(cout.on_set, 3)), 3)

    def test_multi_level_blif(self):
        f, g = load("gates.blif")                # F = AB + ~CD, G = F xor A
        expected_f, expected_g = set(), set()
        for m in range(16):
            v = input_values(m, ["A", "B", "C", "D"])
            f_value = (v["A"] and v["B"]) or (not v["C"] and v["D"])
            if f_value:
                expected_f.add(m)
            if bool(f_value) != bool(v["A"]):
                expected_g.add(m)
        self.assertEqual(f.on_set, expected_f)
        self.assertEqual(g.on_set, expected_g)

    def test_cyclic_has_no_essentials(self):
        f = load("cyclic.txt")[0]
        primes = prime_implicants(f.on_set, 3)
        self.assertEqual(len(primes), 6)
        self.assertEqual(essential_prime_implicants(primes, f.on_set), [])
        # the greedy cover is valid, but uses 4 terms here while the true
        # minimum is 3 (~A~B + AC + B~C) -- see minimal_cover in logic.py
        cover = minimal_cover(f.on_set, 3)
        self.assertEqual(cover_minterms(cover, 3), f.on_set)
        self.assertEqual(len(cover), 4)

    def test_hazards(self):
        f = load("hazard.txt")[0]                # AB + ~AC
        hazards, fixes = find_static_hazards(f.on_set, minimal_cover(f.on_set, 3), 3)
        self.assertEqual(len(hazards), 1)
        self.assertEqual(fixes, ["-11"])         # add BC
        hazards, fixes = find_static_hazards(f.off_set, minimal_cover(f.off_set, 3), 3)
        self.assertEqual(len(hazards), 1)
        self.assertEqual(fixes, ["-00"])         # add (B + C)


if __name__ == "__main__":
    unittest.main()
