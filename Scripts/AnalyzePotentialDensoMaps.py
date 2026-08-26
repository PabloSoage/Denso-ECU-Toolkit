# -*- coding: utf-8 -*-
# Heuristic scanner for Denso 2D/3D map descriptors -> CSV
#
# Sweeps every initialised block looking for structures that match the Denso
# map descriptor layout. It is deliberately permissive: the output is a
# candidate list to be narrowed in the viewer (Smart Axis Filter), not a
# confirmed map list.
#
# On the reference A17DTR image this emits ~3,876 candidates that contain
# 100% of the 725 maps the call-site extractors later confirm.
#
# @category ECU_ReverseEngineering
# @runtime Jython

import java.lang.Exception as JavaException
from ghidra.program.model.mem import MemoryAccessException

# --- Descriptor layout -------------------------------------------------------
# 3D (16 bytes)             2D (12 bytes)
#   0x00 u16 Size_X           0x00 u16 Size_X
#   0x02 u16 Size_Y           0x02 u16 padding
#   0x04 u32 -> axis X        0x04 u32 -> axis X
#   0x08 u32 -> axis Y        0x08 u32 -> curve data
#   0x0C u32 -> Z data
STRUCT_SIZE_3D = 16
STRUCT_SIZE_2D = 12

MAX_AXIS_3D = 64
MAX_AXIS_2D = 128

RAM_BASE = 0xFFFF0000
ALIGNMENT = 4

#: Element widths worth reporting when the gap to the next block divides cleanly.
PLAUSIBLE_WIDTHS = (1, 2, 4)


def is_valid_rom_ptr(ptr_val, memory):
    """True when ptr_val points into an initialised (ROM) block."""
    if ptr_val >= RAM_BASE or ptr_val == 0:
        return False
    try:
        block = memory.getBlock(toAddr(ptr_val))
    except JavaException:
        return False
    return block is not None and block.isInitialized()


def infer_widths(rows, data_index, elements_index):
    """Annotate each row with a plausible element width.

    The descriptor does not record how wide a data element is, so the viewer
    otherwise makes the user guess globally. The distance from one data block to
    the next is an upper bound on this block's size; when that bound divides
    exactly by the element count and lands on 1, 2 or 4 bytes, it is a strong
    hint. Anything else is reported as empty rather than guessed at, because
    padding between blocks makes the bound loose.
    """
    ordered = sorted(range(len(rows)), key=lambda i: rows[i][data_index])
    widths = [""] * len(rows)

    for position, row_index in enumerate(ordered):
        start = rows[row_index][data_index]
        elements = rows[row_index][elements_index]
        if elements <= 0:
            continue
        # Skip duplicates that share a start address.
        next_start = None
        for following in ordered[position + 1:]:
            if rows[following][data_index] > start:
                next_start = rows[following][data_index]
                break
        if next_start is None:
            continue
        gap = next_start - start
        if gap <= 0 or gap % elements:
            continue
        width = gap // elements
        if width in PLAUSIBLE_WIDTHS:
            widths[row_index] = str(width)

    return widths


def run_heuristic_scanner():
    program = getCurrentProgram()
    memory = program.getMemory()

    try:
        save_file = askFile("Save Potential Maps (CSV)", "Save")
    except JavaException:
        print("Operation cancelled by user.")
        return

    filepath = save_file.getAbsolutePath()
    if not filepath.endswith(".csv"):
        filepath += ".csv"

    rows = []
    read_errors = 0

    for block in memory.getBlocks():
        if not block.isInitialized():
            continue

        curr_addr = block.getStart()
        end_addr = block.getEnd()
        print("Scanning block: {} to {}".format(curr_addr, end_addr))

        while curr_addr.compareTo(end_addr) < 0:
            try:
                if curr_addr.addWrap(STRUCT_SIZE_3D).compareTo(end_addr) > 0:
                    break

                size_x = memory.getShort(curr_addr) & 0xFFFF
                size_y = memory.getShort(curr_addr.add(2)) & 0xFFFF

                # --- 3D candidate ---
                if 1 < size_x <= MAX_AXIS_3D and 1 < size_y <= MAX_AXIS_3D:
                    ptr_x = memory.getInt(curr_addr.add(4)) & 0xFFFFFFFF
                    ptr_y = memory.getInt(curr_addr.add(8)) & 0xFFFFFFFF
                    ptr_z = memory.getInt(curr_addr.add(12)) & 0xFFFFFFFF
                    if (is_valid_rom_ptr(ptr_x, memory)
                            and is_valid_rom_ptr(ptr_y, memory)
                            and is_valid_rom_ptr(ptr_z, memory)
                            and ptr_z > ptr_x and ptr_z > ptr_y):
                        rows.append(["3d", curr_addr.getOffset(), size_x, size_y,
                                     ptr_x, ptr_y, ptr_z, size_x * size_y])
                        curr_addr = curr_addr.add(STRUCT_SIZE_3D)
                        continue

                # --- 2D candidate ---
                if 1 < size_x <= MAX_AXIS_2D:
                    ptr_x = memory.getInt(curr_addr.add(4)) & 0xFFFFFFFF
                    ptr_data = memory.getInt(curr_addr.add(8)) & 0xFFFFFFFF
                    if (is_valid_rom_ptr(ptr_x, memory)
                            and is_valid_rom_ptr(ptr_data, memory)
                            and ptr_data > ptr_x):
                        rows.append(["2d", curr_addr.getOffset(), size_x, 1,
                                     ptr_x, 0, ptr_data, size_x])
                        curr_addr = curr_addr.add(STRUCT_SIZE_2D)
                        continue

            except MemoryAccessException:
                # Expected at block edges; anything else is worth counting.
                read_errors += 1
            except JavaException:
                read_errors += 1

            curr_addr = curr_addr.add(ALIGNMENT)

    widths = infer_widths(rows, data_index=6, elements_index=7)

    with open(filepath, "w") as handle:
        handle.write("Map_Type,Struct_Addr,Size_X,Size_Y,Axis_X_Addr,Axis_Y_Addr,"
                     "Data_Addr,Inferred_Width\n")
        for index, row in enumerate(rows):
            map_type, struct_addr, size_x, size_y, ptr_x, ptr_y, ptr_data, _ = row
            handle.write("{},{:08X},{},{},{:08X},{:08X},{:08X},{}\n".format(
                map_type, struct_addr, size_x, size_y, ptr_x, ptr_y, ptr_data, widths[index]
            ))

    hits_3d = len([r for r in rows if r[0] == "3d"])
    hits_2d = len(rows) - hits_3d
    sized = len([w for w in widths if w])

    print("-" * 60)
    print("Scan finished: {} potential 3D maps, {} 2D curves.".format(hits_3d, hits_2d))
    print("Element width inferred for {} of {} candidates.".format(sized, len(rows)))
    if read_errors:
        print("NOTE: {} memory reads failed and were skipped.".format(read_errors))
    print("Saved to: {}".format(filepath))


run_heuristic_scanner()
