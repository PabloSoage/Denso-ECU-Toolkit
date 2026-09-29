# Findings — Denso SH705x, Isuzu 1.7 CDTI

Reverse-engineering results for the reference calibration. These are **analysis
results, not firmware**: addresses, structure layouts and interpretations.

Reference image: Opel Astra 1.7 CDTI, ECU `DENSO NCLZQ60R98113172`,
software `AU15NCLZQ60R`, 1,536 KB, Renesas SH-2A, big endian.

> Addresses are specific to this calibration. Everything **structural** — the
> descriptor layout, the single-pointer calling convention, the axis-before-data
> ordering — has held across the SH705x Denso images this has been tried on.
> The addresses themselves have not.

---

## 1. The three functions everything hangs off

| Address | Role | Signature |
|---|---|---|
| `FUN_000080E4` | Master **3D** interpolation | `float f(int descriptor)` |
| `FUN_00008070` | Master **2D** interpolation | `float f(int descriptor)` |
| `FUN_00008490` | min/max clamp | `float f(float v, float min, float max)` |

Every calibration map in the image materialises as a **CALL** to one of the
first two. That is what makes exhaustive extraction possible: find these two
addresses and the cross-reference graph hands you the whole map catalogue.

Three properties of the call sites drive the design of `Scripts/`:

1. **One argument, a pointer to the descriptor, in `R4`.** On SH-2A it is loaded
   from the literal pool with `MOV.L @(disp,PC),Rn`, so the operand of the
   instruction is the *slot*, and the pointer is one dereference away.
2. **The result is stored straight into a RAM global** (`0xFFFFxxxx`) on the
   line following the call. That store is the map's output and the correct
   anchor for any forward dataflow analysis.
3. **One function consumes many maps.** `FUN_00049478` alone calls the master
   functions six times. Any heuristic working at function granularity collapses
   all six into one answer.

---

## 2. Descriptor layout

The master functions read more of the descriptor than its pointers: an element
type and a factor/offset pair. What they return is `offset + raw * factor`, so
every map's physical unit is stored next to its dimensions. Read from the
decompiled master functions of **two calibrations** (this image at
`0x80E4`/`0x8070`, and `NCLSW420AX36` at `0x7128`/`0x70B4`; same layout in both).

### 3D map — 28 bytes

| Offset | Type | Field |
|---|---|---|
| `0x00` | `u16` | `Size_X` (columns) |
| `0x02` | `u16` | `Size_Y` (rows) |
| `0x04` | `u32` | pointer to X axis |
| `0x08` | `u32` | pointer to Y axis |
| `0x0C` | `u32` | pointer to Z data |
| `0x10` | `u8`  | element type (below) |
| `0x14` | `f32` | factor |
| `0x18` | `f32` | offset |

### 2D curve — 20 bytes

| Offset | Type | Field |
|---|---|---|
| `0x00` | `u16` | `Size_X` (points) |
| `0x02` | `u8`  | element type (below) |
| `0x03` | `u8`  | not used by the master function |
| `0x04` | `u32` | pointer to X axis |
| `0x08` | `u32` | pointer to curve data |
| `0x0C` | `f32` | factor |
| `0x10` | `f32` | offset |

### Element type

The type byte is also the offset into the table of element readers. The readers
are byte-identical in both calibrations; each one's load instruction says what
it reads:

| Type | Reader loads | Element | Factor/offset |
|---|---|---|---|
| `0x00` | `fmov.s` | `f32` | not applied |
| `0x04` | `mov.b` + `extu.b` | `u8` | applied |
| `0x08` | `mov.w` + `extu.w` | `u16` | applied |
| `0x0C` | `mov.b` (sign-extended) | `s8` | applied |
| `0x10` | `mov.w` (sign-extended) | `s16` | applied |

Axes are always `f32`.

**Invariant used as a filter:** `data > axis_x` (and `> axis_y` for 3D). Axes
precede their data in the layout throughout the ROM. Combined with a check that
all three pointers land in initialised ROM, this is what keeps the heuristic
scanner's false-positive rate workable.

> **Corrected.** An earlier version of this section said the descriptor does not
> encode the element width and that it has to be inferred from the gap to the
> next data block. It does encode it, in the type byte. The `Inferred_Width`
> column is still written by the extractor, but the descriptor is the authority:
> `viewer/core/descriptor.py` decodes it, and `tools/apply_descriptor_formats.py`
> stores format, factor and offset for every map in a project.

---

## 3. The heuristic scanner is a superset — measured

Cross-checking the blind structural scan against the call-site extraction on
this image:

| | Rows |
|---|---|
| `potential_maps.csv` — blind structural scan | 3,876 |
| `3d_maps_review.csv` — confirmed via X-refs | 398 |
| `2d_maps_review.csv` — confirmed via X-refs | 327 |

| Overlap by **data address** | Result |
|---|---|
| potential ∩ 3D | **398 / 398 (100%)** |
| potential ∩ 2D | **327 / 327 (100%)** |

The blind scan found **every single map** the call-site extraction later
confirmed. That validates the descriptor layout above, and it means the scanner
is usable on a calibration where the master interpolation functions have not
been located yet: run it, enable the Smart Axis Filter, and start reading.

> ⚠️ The same comparison by *descriptor* vs *call site* address gives **0/398
> overlap** — they are different things. See §5.

---

## 4. Identified maps

| Data address | Dimensions | Interpretation | Confidence |
|---|---|---|---|
| `0x000CB584` | 20 × 18 | Rail pressure (high-pressure pump) | High |
| `0x000D37D8` | — | X = rpm, Y = torque(?). Either target boost (mbar) or EGR control (fresh air, mg/stroke) | Medium |
| `0x000B88EC` | — | Empty when read at the wrong width. X axis 0–6000 = rpm, other axis pedal or fuel. Possibly `drivers_wish` | Low |
| `0x000A39C8` | 2D | Unidentified curve | — |
| `0x000449C4` | — | Tagged as both VNT duty cycle **and** EGR duty cycle — contradictory, unresolved | Low |

Other addresses of interest:

* `0x0008733C` — associated with **DTC P0115** (coolant temperature sensor).

---

## 5. `Wrapper_Addr` meant two different things

Worth recording because it silently cost work.

* In `potential_maps.csv`, `Wrapper_Addr` was the **descriptor** address.
* In the review CSVs, `Wrapper_Addr` was the **call site** address.

Same header, disjoint address spaces, **zero** overlapping rows. Tags were
indexed by that column, so a tag applied in Potential Maps mode was invisible in
Map Viewer mode and vice versa, with no error to explain it.

The schema now names them separately:

| Column | Meaning |
|---|---|
| `Data_Addr` | Z data / curve data — the canonical identity |
| `Struct_Addr` | The descriptor structure |
| `Call_Site_Addr` | The instruction that calls the interpolator |

`Wrapper_Addr` is still read from older CSVs and interpreted according to which
file it came from. The viewer resolves tags against *every* identity a row has,
so tags survive whichever mode they were created in.

---

## 6. Why the first DTC analysis was wrong

The original forward-taint script scanned the **containing function** from its
first instruction and took the first reference matching
`isWrite() or isData()`. In Ghidra `RefType.READ.isData()` is also true, so the
condition collapsed to "any data access" — and the first data access in a
compiled function is the prologue copying globals into locals.

The output said as much:

| Symptom on the reference image | Value |
|---|---|
| Rows produced | 587 |
| Distinct RAM variables | **94** |
| Top variable `FFFF4CF8` | **109 rows (19%)** |
| Top two variables combined | 199 rows (34%) |

`FFFF4CF8` is `uStack_4c = DAT_ffff4cf8;` — a prologue **read** in
`FUN_00049478`. One RAM address cannot be the output of 109 different maps.

The current script anchors on the **call site**, scans forward a short window,
and accepts only `RefType.isWrite()`. It also scores how much the consuming
function actually looks like diagnostic code, and the UI states plainly that the
result is a dataflow lead rather than proof of a DTC.

---

## 7. Open questions

* **No inverse interpolation function found.** If the calibration ever needs to
  solve "which X yields this Z", there should be one.
* **`FUN_00008574`** is called in a cascade of rising thresholds
  (`9 <`, `0x27 <`, `0x31 <`, … `99 <`) against `DAT_FFFF7DAE`, incrementing a
  counter that then selects one of 13 `switch` cases. It looks like a stepped
  **operating-mode selector** for the turbo/EGR control. Resolving
  `DAT_FFFF7DAE` would unlock that whole block.
* **`0x000449C4`** — VNT or EGR? If this A17DTR calibration really does contain
  vane control, that is a data point for the variable-vs-fixed geometry question
  across the A17DT* family.
* **The checksum block has not been located** in this image. Until it is, the
  viewer must not and does not claim to produce a flashable image. See
  `viewer/core/integrity.py`.
  On a second calibration (`NCLSW420AX36`) there is a header at `0x13FF50`,
  duplicated at `0x13FF5C`: `u32 start = 0x0C0000`, `u32 end = 0x13FF4F`, `u16 cks`,
  `u16 0xF7A1`. The 16-bit sum of `start..end` plus `cks` is `0x5157` on two
  independent reads of that ECU. This image has no header of that shape, so the
  rule is not generalised and nothing in the toolkit relies on it.
