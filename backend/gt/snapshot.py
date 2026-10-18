"""Record each stored hack's trace into data/replays/snapshots/<name>.json.gz, shipped with the repo.

A fresh server (Render's free disk is wiped on every restart) then loads the real hacks in seconds, with no Etherscan
calls. Re-run after changing a replay file or the trace logic:  py -3.11 -m gt.snapshot [name ...]   (from backend/)"""
import dataclasses
import gzip
import json
import sys

from gt.api import trace_case
from gt.config import DATA_DIR


def main(names: list[str]) -> None:
    for path in sorted((DATA_DIR / "replays").glob("*.json")):
        if names and path.stem not in names:
            continue
        transfers, codes, complete, hubs = trace_case(json.loads(path.read_text()))
        out = DATA_DIR / "replays" / "snapshots" / f"{path.stem}.json.gz"
        out.parent.mkdir(exist_ok=True)
        body = {"transfers": [dataclasses.asdict(t) for t in transfers], "codes": codes,
                "complete": sorted(complete), "hubs": hubs}
        out.write_bytes(gzip.compress(json.dumps(body, separators=(",", ":")).encode(), mtime=0))
        print(f"{path.stem}: {len(transfers)} transfers, {len(hubs)} third-party contracts, {out.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main(sys.argv[1:])
