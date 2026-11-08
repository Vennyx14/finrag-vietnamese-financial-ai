"""Wilson 95% score interval helpers for FinRAG reports.

Usage:
    python wilson.py <successes> <total>            # interval for a proportion
    python wilson.py --min-n <wrong> [--max-upper 0.05]
        # smallest number of answered questions for which <wrong> errors keeps
        # the upper bound of the wrong rate at or below --max-upper (M4 gate)
"""

from __future__ import annotations

import argparse
import math

Z = 1.959963984540054


def wilson(successes: int, total: int, z: float = Z) -> tuple[float, float]:
    if total <= 0:
        raise ValueError("total must be positive")
    p = successes / total
    denom = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denom
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def min_n(wrong: int, max_upper: float) -> int:
    n = max(wrong, 1)
    while wilson(wrong, n)[1] > max_upper:
        n += 1
    return n


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("values", nargs="*", type=int)
    parser.add_argument("--min-n", type=int, dest="wrong")
    parser.add_argument("--max-upper", type=float, default=0.05)
    args = parser.parse_args()
    if args.wrong is not None:
        n = min_n(args.wrong, args.max_upper)
        print(f"{args.wrong} wrong: need at least {n} answered questions for upper bound <= {args.max_upper:.1%}")
        return
    if len(args.values) != 2:
        parser.error("give <successes> <total>, or --min-n <wrong>")
    k, n = args.values
    lo, hi = wilson(k, n)
    print(f"{k}/{n} = {k / n:.1%}, Wilson 95% [{lo:.1%}, {hi:.1%}]")


if __name__ == "__main__":
    main()
