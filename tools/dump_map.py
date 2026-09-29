#!/usr/bin/env python3
"""Print maps in physical units, straight from their descriptors.

    python tools/dump_map.py IMAGE.bin STRUCT_HEX [STRUCT_HEX ...]
    python tools/dump_map.py IMAGE.bin --2d STRUCT_HEX      # a 2D curve

STRUCT_HEX is the descriptor address (``Struct_Addr`` in the catalogue CSVs).
Format, factor and offset come from the descriptor: see viewer/core/descriptor.py.
"""
import pathlib
import struct
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from viewer.core import descriptor, formats  # noqa: E402


def values(image, d):
    raw = formats.unpack_array(image, d.z_format, d.size_x * d.size_y, d.data)
    if d.is_float:
        return list(raw)
    return [d.offset + r * d.factor for r in raw]


def axis(image, address, count):
    return struct.unpack(f">{count}f", image[address:address + 4 * count])


def dump(image, address, is_3d):
    d = descriptor.read(image, address, is_3d)
    z = values(image, d)
    x = axis(image, d.axis_x, d.size_x)
    scaling = "" if d.is_float else f" x {d.factor:g} + {d.offset:g}"
    if not is_3d:
        print(f"2D {address:06X}  {d.size_x} points  data {d.data:06X}  {d.z_format}{scaling}")
        print("  X: " + " ".join(f"{v:g}" for v in x))
        print("  Z: " + " ".join(f"{v:.4g}" for v in z))
        print()
        return
    y = axis(image, d.axis_y, d.size_y)
    print(f"3D {address:06X}  {d.size_x}x{d.size_y}  data {d.data:06X}  {d.z_format}{scaling}")
    header = " ".join(f"{v:8g}" for v in x)
    print(f"{'Y / X':>9} | {header}")
    for j in range(d.size_y):
        row = " ".join(f"{z[j * d.size_x + i]:8.3f}" for i in range(d.size_x))
        print(f"{y[j]:9g} | {row}")
    print()


def main(argv):
    if len(argv) < 3:
        sys.exit(__doc__)
    image = pathlib.Path(argv[1]).read_bytes()
    is_3d = True
    for arg in argv[2:]:
        if arg == "--2d":
            is_3d = False
            continue
        dump(image, int(arg, 16), is_3d)
        is_3d = True


if __name__ == "__main__":
    main(sys.argv)
