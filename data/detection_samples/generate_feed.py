"""Post a synthetic (mock) sensor feed to a running TMS server (Likhita).

The sensors and cameras do not exist in this project, so this script plays their part. A fixed
``--seed`` always produces the same vehicles, which keeps demos and tests repeatable.

Examples:
    python data/detection_samples/generate_feed.py --url http://localhost:8000 --minutes 5
    python data/detection_samples/generate_feed.py --rate-ns 20 --rate-ew 4      # heavy north-south traffic
    python data/detection_samples/generate_feed.py --pedestrian-every 2          # crosswalk requests
    python data/detection_samples/generate_feed.py --write feed.json             # save instead of sending
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import httpx  # noqa: E402

from tms.detection.synthetic import generate_events  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", default="http://localhost:8000", help="server address")
    parser.add_argument("--intersection", default="INT-001")
    parser.add_argument("--minutes", type=int, default=5, help="minutes of traffic ending now")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--rate-ns", type=int, default=6, help="vehicles per minute on each of N and S")
    parser.add_argument("--rate-ew", type=int, default=6, help="vehicles per minute on each of E and W")
    parser.add_argument("--pedestrian-every", type=int, default=0, help="a crosswalk request every N minutes (0 = none)")
    parser.add_argument("--api-key", default="sensor-demo-key", help="sensor key (TMS_SENSOR_API_KEY)")
    parser.add_argument("--write", metavar="FILE", help="write the events to FILE instead of sending them")
    args = parser.parse_args()

    start = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0) - timedelta(minutes=args.minutes)
    events = generate_events(
        intersection_id=args.intersection, seed=args.seed, minutes=args.minutes, start=start,
        vehicles_per_minute={"N": args.rate_ns, "S": args.rate_ns, "E": args.rate_ew, "W": args.rate_ew},
        pedestrian_every_minutes=args.pedestrian_every,
    )
    if args.write:
        Path(args.write).write_text(json.dumps(events, indent=2))
        print(f"Wrote {len(events)} events to {args.write}")
        return 0

    sent = failed = 0
    with httpx.Client(base_url=args.url, headers={"X-API-Key": args.api_key}, timeout=10) as client:
        for event in events:
            response = client.post("/api/v1/detections", json=event)
            if response.status_code == 201:
                sent += 1
            else:
                failed += 1
                if failed <= 3:
                    print(f"Rejected ({response.status_code}): {response.text}")
    print(f"Sent {sent} detections, {failed} rejected")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
