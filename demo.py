"""Offline portfolio demonstration; no network, model calls, or email sending."""

import argparse
import json
from pathlib import Path

from src.research_rules import evaluate_batch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input", type=Path,
        default=Path(__file__).parent / "examples" / "synthetic_batch.json",
    )
    args = parser.parse_args()
    try:
        records = json.loads(args.input.read_text(encoding="utf-8-sig"))
        result = evaluate_batch(records)
    except (OSError, ValueError, TypeError) as exc:
        print(json.dumps({"passed": False, "error": str(exc)}, ensure_ascii=True))
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
