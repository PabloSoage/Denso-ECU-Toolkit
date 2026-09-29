# Denso ECU Toolkit

A reverse-engineering toolchain for **Denso SH705x** engine control units: Ghidra
(Jython) scripts that find and extract calibration maps from the binary, and a
standalone PyQt6 viewer for reading, comparing and patching them.

This is not a one-click tuning tool. It is instrumentation — it finds structure
in a firmware image and shows it to you.

---

## Why the map discovery works

Every calibration map in these ECUs is reached through one of **two master
interpolation functions**, called with a single pointer to a small descriptor
structure. Find those two functions, and the cross-reference graph hands you the
entire map catalogue.

A blind structural scan for that descriptor layout works as an independent
route. On the reference image the two agree completely:

| | Rows |
|---|---|
| Blind heuristic scan (`potential_maps.csv`) | 3,876 candidates |
| Confirmed via call-site extraction | 398 3D maps + 327 2D curves |
| **Candidates containing a confirmed map** | **725 / 725 — 100%** |

The scanner found every map the call-site extraction later confirmed. That is
what makes it usable on a calibration whose master functions you have not
located yet.

Details, descriptor layouts and identified maps: [`docs/findings.md`](docs/findings.md).

---

## Reference platform

| | |
|---|---|
| Vehicle | Opel Astra 1.7 CDTI, 125 hp, MY2009 |
| Engine code | A17DTR |
| ECU | DENSO `NCLZQ60R98113172` |
| Hardware / Software | `012BE10671` / `AU15NCLZQ60R` |
| MCU | Renesas SH-2A, big endian, 32-bit |
| Image size | 1,536 KB (`0x00000000`–`0x0017FFFF`) |

The structural heuristics and the interpolation-wrapper pattern are common
across SH705x-based Denso ECUs; the specific addresses are not.

---

## What is in this repository — and what is not

**Here** — everything that is the author's own work, GPL-3.0:

* `Scripts/` — the Ghidra extraction scripts
* `viewer/` — the visualiser
* `*.csv` — the extracted map catalogue for the reference image
* `A17DTR.dproj` — a viewer project with 64 tagged maps
* `docs/` — reverse-engineering findings

**Not here** — the firmware image, its decompiled source and the Ghidra project
database. Those are copyrighted GM/Denso material that cannot be licensed under
the GPL, so they live in a **separate private repository**.

If you have access, clone it into `research/` (it is in `.gitignore`, and the
default paths already point there):

```bash
git clone git@github.com:PabloSoage/Denso-ECU-Toolkit.git
cd Denso-ECU-Toolkit
git clone git@github.com:PabloSoage/denso-a17-research.git research
```

**Without it the viewer still runs.** It says so at launch and lets you load
your own binary from ⚙ Global Settings. The CSVs, tags and the entire UI work
against any image you point it at.

---

## Install

Python 3.10+.

```bash
python -m venv .venv
# Windows:        .\.venv\Scripts\activate
# Linux / macOS:  source .venv/bin/activate

pip install -e .          # or: pip install -r requirements.txt
python -m viewer          # or the installed script: denso-viewer
```

`python viewer/main.py` also still works.

---

## The workflow

### 1. Load the binary into Ghidra

Developed against **Ghidra 12.0.4**. Before running the auto-analyser:

* **Processor:** `SuperH` / `SH-2A` / **big endian** / 32-bit
* **Memory map** (`Window → Memory Map`):

| Block | Start | End | Permissions |
|---|---|---|---|
| ROM | `0x00000000` | `0x0017FFFF` | Read, Execute, **Initialized** |
| RAM | `0xFFFF0000` | `0xFFFFFFFF` | Read, Write, **Volatile** |

`Initialized` on the ROM block is not optional — without it the scripts cannot
read memory and return zero results. Adjust the ROM end address to your image
size.

Then copy `Scripts/` into your `ghidra_scripts` directory.

**Or headless, in one command** — `SetupDensoImage.py` does the memory map and
seeds functions from the SH vector table, and `AnalyzeDensoMaps.py` then finds
the master functions and extracts the catalogue (steps 3 and 4):

```bash
analyzeHeadless <project_dir> <name> -import image.bin     -processor SuperH:BE:32:SH-2A -loader BinaryLoader -loader-baseAddr 0x0     -scriptPath Scripts -preScript SetupDensoImage.py     -postScript AnalyzeDensoMaps.py <out_dir>
```

On the reference image this reproduces the published catalogue: the same two
master functions, and 398 3D maps identical row for row to `3d_maps_review.csv`.

### 2. Heuristic discovery

Run **`AnalyzePotentialDensoMaps.py`** → `potential_maps.csv`.

A few thousand structurally valid candidates. It reports how many it could infer
an element width for, and how many memory reads failed.

### 3. Find the master interpolation functions

They differ between calibrations. `AnalyzeDensoMaps.py` now finds them itself:
it ranks every function called at least 20 times by how many of its call sites
pass a valid descriptor in `R4`, and offers the winners as defaults. On the
reference image that is `000080E4` (423 of 462 calls) and `00008070` (330 of 336).
To check them by hand:

1. Open the viewer, ⚙ **Global Settings** → *Main Application Mode: Potential
   Maps*, and point it at `potential_maps.csv`.
2. Tick **Smart Axis Filter (Hide Noise)**. It keeps only candidates whose axes
   are monotonic — the cheapest way to separate real maps from coincidences.
3. Pick an obviously real map (a clean 16×16, say) and note its **Data address**.
4. In Ghidra press `G`, jump there, and follow the cross-references: data →
   descriptor → the `CALL` that consumes it. That call target is your master
   **3D** function.
5. Repeat from a 2D curve for the master **2D** function.

For the reference image they are `000080E4` (3D) and `00008070` (2D).

### 4. Mass extraction

Run **`AnalyzeDensoMaps.py`**. Interactively it asks for both addresses (with
the detected ones as defaults) and where to save; headless it takes an output
directory, and optionally the two addresses, as script arguments. It writes
`3d_maps_review.csv` and `2d_maps_review.csv`.

It resolves each call's argument through `R4` (the SH argument register),
**checks the delay slot** — SH branches are delayed and the argument load is
often placed there — validates every descriptor before emitting it, and prints a
breakdown of what it rejected and why.

### 5. Forward dataflow (optional)

Run **`AnalyzeDTCsAll.py`** on the two CSVs. For each map it finds the RAM
variable the interpolation result is stored into, then the other functions that
read it, with a confidence score.

> This is a **lead**, not proof that a DTC was found. The output and the UI both
> say so. Confirm in Ghidra before patching anything.

### 6. Units from the descriptors

Each descriptor carries the element type, a factor and an offset
([`docs/findings.md`](docs/findings.md) §2). Save a project with the catalogue,
then:

```bash
python tools/apply_descriptor_formats.py project.dproj   # per-map format, factor, offset
python tools/dump_map.py image.bin <Struct_Addr>          # one map, in physical units
```

Rows need a `Struct_Addr`, which the current `AnalyzeDensoMaps.py` writes. Maps
that already have a per-map override keep it unless you pass `--overwrite`.

### 7. Read, compare, patch

In the viewer: ⚙ **Global Settings** → load the CSVs and the binary → *Main
Application Mode: Map Viewer*.

### 8. Following the code (optional)

* **`DecompileAt.py <out> ADDR…`** writes the decompiled C of the functions containing
  those addresses.
* **`RamCrossRefs.py <out> RAMADDR…`** lists the functions that reach a RAM global
  through a literal pool and decompiles them. It does not tell reads from writes.
* **`tools/annotate_decompiled.py`** rewrites that C so each `PTR_…`/`DAT_…` slot shows
  what it holds: `v_FFFFxxxx`, `MAP3D_xxxxxx[nx×ny]`, or a name you pass with
  `--name`.
* **`tools/compare_calibrations.py A.bin A_3d.csv B.bin B_3d.csv [--tags A.dproj]`**
  pairs the maps of two calibrations by identical axes and reports which data
  differ. Tags carried over with `--tags` are leads, not names.

Run the two Ghidra scripts headless on an analysed project with
`-process <image> -noanalysis -postScript …`.

---

## The viewer

**Three modes** — Map Viewer (the catalogue), Hex Dump (the whole ROM with map
overlays), Potential Maps (unconfirmed candidates, read-only).

**Two render engines** — Matplotlib (hover read-out of the value under the
cursor) and PyQtGraph + OpenGL (high frame rate, no hover).

**Views** — Plot, Table, or synchronised Split.

**Formats** — parse as 8/16/32-bit or float, signed or unsigned, either byte
order, globally or per map. Factors and offsets convert raw values to bar, Nm,
mg/stroke, °C.

**Smart Axis Filter** — monotonicity test over the discrete derivative of each
axis; the primary tool for sifting heuristic output.

**Hex dump** — the whole ROM in a lazy table model. 3D maps in blue, 2D curves
in green, custom tags in orange, each outlined with its label. Right-click any
selection to tag it or give it dimensions.

**Comparison** — nine modes: difference against the original, percentage
difference, against a stored reference map, against an external binary, and
side-by-side twin views of each.

**Editing** — type into the table; modified cells turn red, and so do modified
maps in the list. Export writes the patched image.

> ⚠️ **Checksums are not recalculated.** No checksum block has been located in
> this firmware, so the toolkit cannot correct one — and does not pretend to.
> Export shows you exactly which byte ranges changed and makes you confirm.
> Run the file through a checksum tool that knows your ECU before flashing, and
> have a bootloader recovery path.

---

## Project layout

```
Scripts/                    Ghidra Jython scripts (setup, extraction, decompile, RAM xrefs)
tools/                      command-line helpers (descriptor formats, dumps, comparison)
viewer/
  core/                     data model — no Qt imports
    state.py                the enums that define application state
    formats.py              struct format widths and conversions
    descriptor.py           map descriptors: dimensions, element type, factor, offset
    data_manager.py         binary, catalogue, tags, projects
    integrity.py            what changed, and the checksum warning
  ui/
    main_window.py          state owner and orchestration
    components/             reusable Qt widgets (canvas, hex model, sparkline)
    panels/                 application panels wired to the main window
    managers/               list, rendering, mouse
    dialogs/                modal dialogs
docs/findings.md            reverse-engineering results
tests/                      unit tests for viewer.core
research/                   private data (gitignored, see above)
```

## Development

```bash
pip install -e ".[dev]"
pytest
ruff check .
```

The tests cover `viewer.core` and need only numpy and pandas — no display, no
Qt, no firmware image. They run on a synthetic binary built in the fixtures.

---

## Disclaimer

For education, research and reverse engineering. Modifying an ECU binary without
understanding combustion, checksums and the hardware limits can destroy an
engine or produce illegal emissions. The authors accept no responsibility for
any damage.

## License

Copyright (C) 2026 Pablo Soage Rodas

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY
WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
PARTICULAR PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with
this program. If not, see <https://www.gnu.org/licenses/>.

**The license covers this repository's own code and analysis results only.** It
does not and cannot cover any OEM firmware image you use it on.
