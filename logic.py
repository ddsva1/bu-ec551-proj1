from dataclasses import dataclass
from itertools import combinations


@dataclass
class BoolFunction:
    """One single-output Boolean function, stored as on-set minterm numbers."""
    name: str            # output name
    variables: list      # input names
    on_set: set          # minterm numbers where the function is 1

    @property
    def num_vars(self):
        return len(self.variables)

    @property
    def off_set(self):
        """Minterm numbers where the function is 0."""
        return set(range(2 ** self.num_vars)) - self.on_set


def to_cube(m, n):
    """Minterm number -> full cube of n bits, ex: to_cube(5, 3) = "101"."""
    return format(m, f"0{n}b")


def minterm_cubes(minterms, n):
    """Full cubes for a set of minterms, in increasing minterm order."""
    return [to_cube(m, n) for m in sorted(minterms)]


def input_values(m, variables):
    """Minterm m -> {variable: 0 or 1}, ex: 5 with [A, B, C] -> {A: 1, B: 0, C: 1}."""
    return {var: int(bit) for var, bit in zip(variables, to_cube(m, len(variables)))}


def covers(cube, m):
    """True if minterm m is covered by the cube."""
    bits = to_cube(m, len(cube))
    return all(c == "-" or c == b for c, b in zip(cube, bits))


def cover_minterms(cubes, n):
    """Set of all minterms covered by at least one cube in the list."""
    return {m for m in range(2 ** n) if any(covers(cube, m) for cube in cubes)}


def literal_count(cubes):
    """Total number of literals in a list of cubes (every non-'-' character)."""
    return sum(len(cube) - cube.count("-") for cube in cubes)


def cube_sort_key(cube):
    """Sort cubes like minterms: earlier variables first, ~X before X."""
    return cube.replace("-", "2")


def _join_product(literals, variables):
    """Single-letter variables not separated (A~BC); Multi-letter variables space-separated (A ~B Cin)."""
    if all(len(var) == 1 for var in variables):
        return "".join(literals)
    return " ".join(literals)


def on_string(cube, variables):
    """SOP product term, ex: "1-0" -> "A~C"."""
    literals = []
    for bit, var in zip(cube, variables):
        if bit == "1":
            literals.append(var)
        elif bit == "0":
            literals.append("~" + var)
    if not literals:
        return "1"
    return _join_product(literals, variables)


def off_string(cube, variables):
    """POS sum term from an OFF-set cube, ex: "1-0" -> "(~A + C)"."""
    literals = []
    for bit, var in zip(cube, variables):
        if bit == "1":
            literals.append("~" + var)
        elif bit == "0":
            literals.append(var)
    if not literals:
        return "0"
    return "(" + " + ".join(literals) + ")"


def sop_string(cubes, variables):
    """Sum of products, ex: ["0---", "-10-"] -> "~A + B~C"."""
    if not cubes:
        return "0"
    return " + ".join(on_string(cube, variables) for cube in cubes)


def pos_string(cubes, variables):
    """Product of sums from OFF-set cubes, ex: ["1-0"] -> "(~A + C)"."""
    if not cubes:
        return "1"
    return "".join(off_string(cube, variables) for cube in cubes)


def combine(a, b):
    """Merge two cubes that differ in exactly one position for QM, ex: combine("101", "100") = "10-" """  
    diff = [i for i in range(len(a)) if a[i] != b[i]]
    if len(diff) != 1:
        return None
    i = diff[0]
    if a[i] == "-" or b[i] == "-":
        return None
    return a[:i] + "-" + a[i + 1:]


def prime_implicants(minterms, n):
    """All prime implicants of the function whose ON-set is `minterms`.

    Start with one cube per minterm. Repeatedly merge every pair of cubes
    that differ in one variable. A cube that never merges with anything is
    a prime implicant.
    """
    current = {to_cube(m, n) for m in minterms}
    primes = set()
    while current:
        merged = set()
        used = set()
        for a, b in combinations(sorted(current), 2):
            c = combine(a, b)
            if c is not None:
                merged.add(c)
                used.add(a)
                used.add(b)
        primes |= current - used
        current = merged
    return sorted(primes, key=cube_sort_key)


def essential_prime_implicants(primes, minterms):
    """Primes that are the only prime covering some minterm."""
    essentials = []
    for m in sorted(minterms):
        covering = [p for p in primes if covers(p, m)]
        if len(covering) == 1 and covering[0] not in essentials:
            essentials.append(covering[0])
    return sorted(essentials, key=cube_sort_key)


def count_covered(cube, minterms):
    """How many of the minterms lie inside the cube."""
    return sum(1 for m in minterms if covers(cube, m))


def minimal_cover(minterms, n):
    """
    1. Find essential prime implicants.
    2. If some minterms are still not covered, add the PI that covers
       the most of them.
    """
    primes = prime_implicants(minterms, n)
    cover = essential_prime_implicants(primes, minterms)
    uncovered = {m for m in minterms if not any(covers(p, m) for p in cover)}

    while uncovered:
        best = max(primes, key=lambda p: (count_covered(p, uncovered), p.count("-")))
        cover.append(best)
        uncovered = {m for m in uncovered if not covers(best, m)}
    return sorted(cover, key=cube_sort_key)
