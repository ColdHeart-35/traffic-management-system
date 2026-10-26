"""Rebuild validation_set.csv, the labelled sample the vehicle classifier is checked against.

    python data/detection_samples/make_validation_set.py
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from tms.detection.synthetic import validation_set  # noqa: E402


def main() -> None:
    target = Path(__file__).with_name("validation_set.csv")
    with target.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["length_m", "width_m", "height_m", "has_windows", "label"])
        for features, label in validation_set():
            writer.writerow([features.length_m, features.width_m, features.height_m, int(features.has_windows), label])
    print(f"Wrote {target}")


if __name__ == "__main__":
    main()
