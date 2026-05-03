"""CLI entry-point for running an eval benchmark against the live retriever.

    python -m scripts.run_eval                          # default seed_v1.yaml
    python -m scripts.run_eval app/data/eval/X.yaml     # explicit path
    python -m scripts.run_eval --strategy dense         # override retrieval
"""
from __future__ import annotations

import argparse
import asyncio

from app.services.eval.runner import run


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("benchmark", nargs="?", default="app/data/eval/seed_v1.yaml")
    parser.add_argument("--strategy", default=None, help="dense | hybrid (default: settings)")
    parser.add_argument("--show-failures", action="store_true",
                        help="Print items where hit@5 = 0")
    args = parser.parse_args()

    scorecard = asyncio.run(run(args.benchmark))
    print(scorecard.render())

    if args.show_failures:
        misses = [r for r in scorecard.items if r.hit_at_5 == 0]
        if not misses:
            print("\nNo failures (all items hit@5 ≥ 1).")
        else:
            print(f"\n{'-' * 70}")
            print(f"  Failures (hit@5 = 0): {len(misses)}")
            print(f"{'-' * 70}")
            for r in misses:
                print(f"\n[{r.item.id}]  {r.item.question_en}")
                print(f"  expected: {r.item.expected_verses}")
                print(f"  retrieved (top 5):")
                for rid in r.retrieved_ids[:5]:
                    print(f"    {rid}")


if __name__ == "__main__":
    main()
