#!/usr/bin/env python3
"""Make Ghidra's decompiled C readable: resolve literal-pool symbols.

    python tools/annotate_decompiled.py IMAGE.bin 3D.csv 2D.csv [--name HEX=name ...] FILE.c ...

``PTR_FUN_…``, ``PTR_DAT_…``, ``DAT_…`` and friends are literal-pool slots; the u32
stored there is a RAM global, a function or a map descriptor. Each one is replaced by:

    v_FFFFxxxx          RAM (>= 0xFFFE0000)
    MAP3D_xxxxxx[nx×ny] a descriptor in the 3D catalogue (Struct_Addr)
    MAP2D_xxxxxx[n]     a descriptor in the 2D catalogue
    <name>              an address given with --name, e.g. --name 7128=interp3d
    rom_xxxxxx          anything else inside the image

The catalogues must have a Struct_Addr column (current AnalyzeDensoMaps.py output).
"""
import csv
import pathlib
import re
import struct
import sys

SLOT = re.compile(r"\b(PTR_FUN_|PTR_PTR_|PTR_LAB_|PTR_DAT_|DAT_)([0-9a-fA-F]{8})\b")
CALL = re.compile(r"\(\*\(code \*\)(PTR_FUN_[0-9a-fA-F]{8})\)")


def catalogue(path, label):
    names = {}
    with open(path, newline="") as handle:
        for row in csv.DictReader(handle):
            if not row.get("Struct_Addr"):
                continue
            address = int(row["Struct_Addr"], 16)
            dims = row["Size_X"] + ("x" + row["Size_Y"] if label == "MAP3D" else "")
            names[address] = f"{label}_{address:06X}[{dims}]"
    return names


def main(argv):
    if len(argv) < 5:
        sys.exit(__doc__)
    image = pathlib.Path(argv[1]).read_bytes()
    names = {**catalogue(argv[2], "MAP3D"), **catalogue(argv[3], "MAP2D")}
    files = []
    args = argv[4:]
    while args:
        arg = args.pop(0)
        if arg == "--name":
            key, value = args.pop(0).split("=", 1)
            names[int(key, 16)] = value
        else:
            files.append(arg)

    def resolve(match):
        slot = int(match.group(2), 16)
        if slot + 4 > len(image):
            return match.group(0)
        value = struct.unpack(">I", image[slot:slot + 4])[0]
        if value in names:
            return names[value]
        if value >= 0xFFFE0000:
            return f"v_{value:08X}"
        if value < len(image):
            return f"rom_{value:06X}"
        return f"0x{value:08X}"

    for path in files:
        text = CALL.sub(r"\1", pathlib.Path(path).read_text())
        print(SLOT.sub(resolve, text))


if __name__ == "__main__":
    main(sys.argv)
