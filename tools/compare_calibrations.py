#!/usr/bin/env python3
"""Pair the 3D maps of two calibrations by their axes, and compare the data.

    python tools/compare_calibrations.py A.bin A_3d.csv B.bin B_3d.csv [--tags A.dproj]

Two maps are paired when they have the same dimensions and bit-identical axes.
For each map of B the report says: identical data, same axes but different
data (with how many cells differ), or no counterpart in A. Data is compared
in physical units through the descriptors when both rows have a Struct_Addr,
and as raw 16-bit words otherwise (both sides the same way).

--tags carries A's tags over to the paired map of B. A tag moved this way is a
lead to check, not a name: tags made by hand, or with a third-party tool, can
be wrong on either calibration.
"""
import csv
import json
import pathlib
import struct
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from viewer.core import descriptor, formats  # noqa: E402

KEY_COLUMNS = ("Data_Addr", "Map_Z_Addr", "Struct_Addr", "Call_Site_Addr", "Wrapper_Addr")


def rows(path):
    with open(path, newline="") as handle:
        for row in csv.DictReader(handle):
            data = row.get("Data_Addr") or row.get("Map_Z_Addr")
            yield {
                "nx": int(row["Size_X"]), "ny": int(row["Size_Y"]),
                "ax": int(row["Axis_X_Addr"], 16), "ay": int(row["Axis_Y_Addr"], 16),
                "data": int(data, 16),
                "struct": int(row["Struct_Addr"], 16) if row.get("Struct_Addr") else None,
                "keys": {row.get(k, "").upper() for k in KEY_COLUMNS} - {""},
            }


def key(image, r):
    fx = struct.unpack(f">{r['nx']}f", image[r["ax"]:r["ax"] + 4 * r["nx"]])
    fy = struct.unpack(f">{r['ny']}f", image[r["ay"]:r["ay"] + 4 * r["ny"]])
    return r["nx"], r["ny"], fx, fy


def values(image, r, physical):
    n = r["nx"] * r["ny"]
    if physical:
        try:
            d = descriptor.read_3d(image, r["struct"])
            raw = formats.unpack_array(image, d.z_format, n, d.data)
            return [v if d.is_float else d.offset + v * d.factor for v in raw]
        except (descriptor.DescriptorError, ValueError):
            pass
    return list(struct.unpack(f">{n}H", image[r["data"]:r["data"] + 2 * n]))


def differing(image_a, a, image_b, b):
    physical = a["struct"] is not None and b["struct"] is not None
    va, vb = values(image_a, a, physical), values(image_b, b, physical)
    return sum(x != y for x, y in zip(va, vb, strict=True))


def main(argv):
    if len(argv) < 5:
        sys.exit(__doc__)
    image_a, image_b = pathlib.Path(argv[1]).read_bytes(), pathlib.Path(argv[3]).read_bytes()
    maps_a, maps_b = list(rows(argv[2])), list(rows(argv[4]))
    tags = {}
    if "--tags" in argv:
        project = json.loads(pathlib.Path(argv[argv.index("--tags") + 1]).read_text(encoding="utf-8"))
        tags = {k.upper(): v.get("tags", v) for k, v in project.get("tags", {}).items()}

    by_key = {}
    for r in maps_a:
        by_key.setdefault(key(image_a, r), []).append(r)

    identical = different = unmatched = 0
    lines = []
    for b in maps_b:
        candidates = by_key.get(key(image_b, b))
        if not candidates:
            unmatched += 1
            continue
        scored = [(differing(image_a, a, image_b, b), a) for a in candidates]
        cells, best = min(scored, key=lambda t: t[0])
        if cells == 0:
            identical += 1
        else:
            different += 1
        found = [t for k in best["keys"] if k in tags for t in tags[k]]
        if cells or found:
            lead = ("   lead from A: " + "; ".join(found)) if found else ""
            size = b["nx"] * b["ny"]
            lines.append(f"B data {b['data']:06X}  A data {best['data']:06X}  "
                         f"{b['nx']:2d}x{b['ny']:<2d}  {cells:4d}/{size:<4d} cells differ{lead}")
    print(f"B: {len(maps_b)} maps. Identical to A: {identical}. Same axes, different data: "
          f"{different}. No counterpart: {unmatched}.")
    for line in lines:
        print(line)


if __name__ == "__main__":
    main(sys.argv)
