#!/usr/bin/env python3
"""Store every map's format, factor and offset, read from its descriptor, in a project.

    python tools/apply_descriptor_formats.py PROJECT.dproj [--overwrite]

The project's binary and catalogue CSVs must be reachable. Maps are only updated
when their catalogue row has a Struct_Addr (the CSVs written by the current
AnalyzeDensoMaps.py have it) and the descriptor's data pointer matches the row.
Existing per-map overrides are kept unless --overwrite is given.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from viewer.core.data_manager import DataManager  # noqa: E402


def main(argv):
    if len(argv) < 2:
        sys.exit(__doc__)
    project = argv[1]
    dm = DataManager()
    ok, message = dm.load_project(project)
    if not ok:
        sys.exit(message)
    ok, message = dm.load_csv("all")
    if not ok:
        sys.exit(message)
    applied, kept, failed = dm.apply_descriptor_formats(overwrite="--overwrite" in argv)
    print(f"{applied} maps updated, {kept} kept their existing override, {len(failed)} failed")
    for struct_hex, reason in failed[:20]:
        print(f"  {struct_hex}: {reason}")
    ok, message = dm.save_project(project)
    if not ok:
        sys.exit(message)


if __name__ == "__main__":
    main(sys.argv)
