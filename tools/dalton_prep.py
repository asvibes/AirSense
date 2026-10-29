import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.sources.dalton_replay import load_dalton_csv


def main() -> int:
    parser = argparse.ArgumentParser(description="Preview or replay a DALTON CSV as AirSense readings.")
    parser.add_argument("--csv", required=True, help="Path to a DALTON processed CSV file.")
    parser.add_argument("--room", default=None, help="Optional room name to attach to all rows.")
    parser.add_argument("--limit", type=int, default=10, help="Maximum number of valid CO₂ records to return.")
    parser.add_argument(
        "--include-invalid",
        action="store_true",
        help="Include rows where Valid_CO2 is 0 or null.",
    )
    args = parser.parse_args()

    rows = load_dalton_csv(
        args.csv,
        room_name=args.room,
        limit=args.limit,
        valid_co2_only=not args.include_invalid,
    )
    print(json.dumps(rows, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
