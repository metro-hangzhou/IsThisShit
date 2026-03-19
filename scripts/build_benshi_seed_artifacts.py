from __future__ import annotations

import argparse
from pathlib import Path

from qq_data_analysis.benshi_seed_artifacts import write_seed_artifacts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset-dir",
        default="dev/testdata/local/shi_group_751365230",
        help="Path to the local benshi dataset directory.",
    )
    args = parser.parse_args()

    dataset_dir = Path(args.dataset_dir).expanduser().resolve()
    bundle = write_seed_artifacts(dataset_dir)

    print(
        "example_groups="
        + ", ".join(
            f"{name}:{len(rows)}"
            for name, rows in bundle.example_bank_groups.items()
        )
    )
    print(
        f"distribution_artifact={bundle.distribution_baseline.get('artifact')}"
    )
    print(f"dataset_dir={dataset_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
