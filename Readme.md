# Denso ECU Reverse Engineering Suite & Map Visualizer

A modular toolchain designed for the extraction, static analysis, and visualization of calibration maps from Denso Engine Control Units (ECUs). This project relies on Ghidra (Jython) scripts for automated structural discovery and cross-reference analysis, paired with a high-performance, standalone Python/PyQt6 visualizer for data manipulation and binary patching.

This suite is not an automated "one-click" tuning solution; it is a reverse-engineering utility designed to accelerate the identification of map interpolation logic and diagnostic routines.

### Tested Target Platform
* **Vehicle:** Opel Astra 1.7 CDTI (A17DTR) Turbo-Diesel 125HP MY2009
* **ECU:** DENSO NCLZQ60R98113172
* **Hardware/Software:** HW: 012BE10671 | SW: AU15NCLZQ60R
* **Firmware Size:** 1.5 MB (1536 KB)

*Note: While developed against this specific firmware, the structural heuristics and interpolation wrapper patterns are common across many SH705x/Renesas-based Denso ECUs.*

---

## Feature Overview

### 1. Ghidra Static Analysis Scripts (`/Scripts`)
Written in Jython, these scripts interact directly with the Ghidra API to parse the binary.
* **`AnalyzePotentialDensoMaps.py` (Struct Hunter):** Performs brute-force heuristic memory scanning to locate valid Denso 2D/3D map wrappers. It strictly checks pointers against the valid initialized ROM memory map to avoid false positives.
* **`Analyze2DMaps.py` & `Analyze3DMaps.py`:** Mass-extracts calibration maps by iterating over all cross-references (X-Refs) to the ECU's master interpolation functions.
* **`AnalyzeDTCsAll.py` (Forward Taint Analysis):** Maps physical sensor curves/maps to Diagnostic Trouble Code (DTC) managers by tracing RAM memory writes (`0xFFFFxxxx`) and resolving their forward read references.

### 2. Standalone UI Visualizer (`viewer/main.py`)
A standalone PyQt6 desktop application decoupled from Ghidra for maximum performance.
* **Visualization Modes:** *Plot View:* Renders maps graphically. Supports Dual Render Engines: **Matplotlib** (slower, detailed hover tooltips) and **PyQtGraph + OpenGL** (high-FPS rendering without hover).
  * *Table View:* Displays decrypted data in a standard grid with integrated *Sparklines* (Bar or Line style).
  * *Split View:* Synchronized side-by-side plot and table viewing.
* **Global & Custom Formats:** Dynamically parse data as 8-bit, 16-bit, 32-bit, or Float, toggle Endianness (LoHi/HiLo), and switch between Signed/Unsigned. Custom math factors and offsets can be applied globally or per-map.
* **Smart Axis Filter:** Uses discrete derivative mathematics (`numpy.diff`) to check axis monotonicity, instantly filtering out noise and false positives from the heuristic scanner.
* **Advanced Hex Dump:** A custom `QAbstractTableModel` implementation capable of mapping the entire ROM instantly. Features color-coded map overlays (3D in blue, 2D in green, custom tags in orange).
* **Tagging & Editing:** Right-click hex selections to define custom map dimensions or tags. Apply arithmetic edits directly to the data table and export the patched `.bin` file.
* **Binary Diffing:** Compare modifications side-by-side with the original binary or an external reference binary map-by-map.

---

## ⚙️ Setup & Installation

### 1. Ghidra Environment Setup
This toolchain was developed and tested on **Ghidra 12.0.4**. When importing your `.bin` file into Ghidra, ensure you configure the Language and Memory Map correctly before running the Auto-Analyzer:
* **Processor:** `SuperH` / `Big Endian` / `32-bit` / `SH-2A`
* **Memory Map Configuration:**
  * Add ROM Block: Start `0x00000000` to `0x0017FFFF` (Set permissions to `Read`, `Execute`, and `Initialized`). *Adjust end address based on your specific bin size.*
  * Add RAM Block: Start `0xFFFF0000` to `0xFFFFFFFF` (Set permissions to `Read`, `Write`, `Volatile`).
* Copy the contents of the `/Scripts` folder into your `ghidra_scripts` directory.

### 2. Python Visualizer Setup
Tested on **Python 3.11.4**. Run the following commands in your terminal to set up the environment and launch the UI:

**For Windows:**
```cmd
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python viewer/main.py
```

**For Linux / macOS:**
```bash
python3 -m venv .venv
source ./.venv/bin/activate
pip install -r requirements.txt
python viewer/main.py
```

---

## Workflow Guide

To properly extract and visualize all maps, follow this standard reverse-engineering workflow:

### Step 1: Heuristic Discovery
1. Load your `.bin` into Ghidra, apply the correct memory map, and run the Auto-Analyze tool.
2. Run `AnalyzePotentialDensoMaps.py` via the Ghidra Script Manager.
3. This will output a `potential_maps.csv` containing thousands of structurally valid map candidates.

### Step 2: Locate Master Interpolation Functions
*The mass-extraction scripts require the exact memory address of the ECU's 2D and 3D interpolation algorithms.*
1. Open the Visualizer app and go to **⚙ Global Settings**. Select the **Potential Maps** mode and load the `potential_maps.csv`.
2. Enable the **Smart Axis Filter (Hide Noise)** checkbox on the left panel to filter out structural noise and leave only maps with valid monotonic axes.
3. Find a highly probable map (e.g., a standard 16x16 3D map). Take note of its **Z Data / Curve Data** address.
4. In Ghidra, jump (`G`) to that Data address. 
5. Find cross-references (`X-Refs`) to that data to identify the Map Wrapper struct.
6. Find references to that Wrapper to locate the `CALL` or branch instruction that processes it. This is your **Master 3D Interpolation Function**.
7. Repeat the process using a 2D curve to find the **Master 2D Interpolation Function**.

### Step 3: Mass Extraction
1. Edit `Analyze2DMaps.py` and `Analyze3DMaps.py`. Update the `target_addr` variable with the master function addresses you located in Step 2.
2. Run both scripts in Ghidra. They will trace all calls to these functions and generate your definitive `2d_maps_review.csv` and `3d_maps_review.csv`.

### Step 4: DTC Tracing (Optional)
1. Run `AnalyzeDTCsAll.py` in Ghidra.
2. When prompted, select the 2D and 3D CSVs generated in Step 3. The script will trace RAM variables and output a mapped CSV linking maps to their respective diagnostic task functions.

### Step 5: Visualization & Editing
1. In the visualizer, go to **⚙ Global Settings**, load your definitive CSVs and the original `.bin` file, and switch the Application Mode to **Map Viewer**.
2. Use the left panel to search, filter by tags, and select maps.
3. Modify formats, factors, and offsets. Values modified in the table will highlight in red.
4. Use the **Export Mod. Bin** button to save your patched binary.

---

## ⚠️ Disclaimer
This toolset is provided for educational, research, and reverse-engineering purposes only. Modifying ECU binaries without a proper understanding of combustion engine dynamics, checksum corrections, and hardware limitations can result in catastrophic engine failure or illegal emissions outputs. The authors take no responsibility for any damage caused by the use of these tools.