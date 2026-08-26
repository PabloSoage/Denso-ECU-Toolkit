# -*- coding: utf-8 -*-
# Forward dataflow: map -> result RAM variable -> the functions that read it.
#
# WHAT WAS WRONG WITH THE PREVIOUS VERSION
# ----------------------------------------
# It scanned the *containing function* from its first instruction and took the
# first reference matching `isWrite() or isData()`. In Ghidra `RefType.READ`
# also answers True to isData(), so that condition reduces to "any data access"
# -- and the first data access in a compiled function is almost always the
# prologue copying globals into locals.
#
# On the reference image the symptom was unmistakable: 587 rows resolving to
# only 94 distinct RAM variables, with a single address (FFFF4CF8) claimed as
# the output of 109 different maps. FFFF4CF8 is `uStack_4c = DAT_ffff4cf8;` --
# a prologue read in FUN_00049478.
#
# WHAT THIS DOES INSTEAD
# ----------------------
# Anchors on the *call site*, not the function, and scans forward a short window
# for the first genuine WRITE to RAM. That is where the interpolation result
# lands:
#
#     DAT_ffff7e5c = FUN_00008070((int)&PTR_LAB_0008c258);
#
# Then it reports which other functions read that variable, and scores how much
# the reader looks like diagnostic code. The column is a lead to follow in
# Ghidra, and the output says so -- it is not proof that a DTC was found.
#
# @category ECU_ReverseEngineering
# @runtime Jython

import java.lang.Exception as JavaException
from ghidra.program.model.mem import MemoryAccessException

RAM_BASE = 0xFFFF0000

#: How far past the call the result store is expected. The compiler emits it
#: within a handful of instructions; a wider window starts catching unrelated
#: stores from the next statement.
FORWARD_WINDOW = 12

#: Function-name fragments that suggest diagnostic code once symbols exist.
DIAGNOSTIC_HINTS = ("dtc", "diag", "fault", "fail", "error", "monitor", "check")

#: A RAM variable read by more functions than this is shared plumbing rather
#: than one map's output; reported, but flagged as low confidence.
BUSY_VARIABLE_READERS = 8


def parse_hex(text):
    text = str(text).strip().upper().replace("0X", "")
    if not text:
        return None
    try:
        return int(text, 16)
    except ValueError:
        return None


def read_catalogue(filepath):
    """Read a map CSV, tolerating both the old and the current header layouts."""
    handle = open(filepath, "r")
    try:
        lines = [line.strip() for line in handle.readlines() if line.strip()]
    finally:
        handle.close()

    if not lines:
        return []

    header = [column.strip() for column in lines[0].split(",")]

    def column_index(*names):
        for name in names:
            if name in header:
                return header.index(name)
        return None

    call_index = column_index("Call_Site_Addr", "Wrapper_Addr")
    data_index = column_index("Data_Addr", "Map_Z_Addr", "Curve_Data_Addr")
    struct_index = column_index("Struct_Addr")

    if call_index is None or data_index is None:
        print("  Unrecognised header: {}".format(",".join(header)))
        return []

    rows = []
    for line in lines[1:]:
        parts = [part.strip() for part in line.split(",")]
        if max(call_index, data_index) >= len(parts):
            continue
        rows.append({
            "call_site": parse_hex(parts[call_index]),
            "data": parts[data_index],
            "struct": parts[struct_index] if struct_index is not None and struct_index < len(parts) else "",
        })
    return [row for row in rows if row["call_site"] is not None]


def find_result_variable(listing, call_addr):
    """First RAM WRITE within the forward window after the call, or None.

    Only RefType.isWrite() counts. Reads are explicitly excluded -- conflating
    the two is what produced the previous version's false positives.
    """
    instruction = listing.getInstructionAt(call_addr)
    if instruction is None:
        return None

    for _ in range(FORWARD_WINDOW):
        instruction = instruction.getNext()
        if instruction is None:
            return None
        # Stop at the next call: anything stored past it belongs to that one.
        if instruction.getFlowType().isCall():
            return None
        try:
            references = instruction.getReferencesFrom()
        except JavaException:
            continue
        for reference in references:
            if not reference.getReferenceType().isWrite():
                continue
            destination = reference.getToAddress()
            if destination.getOffset() >= RAM_BASE:
                return destination
    return None


def find_readers(program, ram_address, writer_function):
    """Functions other than the writer that read this RAM variable."""
    readers = []
    seen = set()
    for reference in getReferencesTo(ram_address):
        if not reference.getReferenceType().isRead():
            continue
        function = program.getFunctionManager().getFunctionContaining(reference.getFromAddress())
        if function is None or function == writer_function:
            continue
        name = function.getName()
        if name not in seen:
            seen.add(name)
            readers.append(function)
    return readers


def score_reader(function, reader_count):
    """(confidence, evidence) for treating this reader as diagnostic code."""
    name = function.getName().lower()
    for hint in DIAGNOSTIC_HINTS:
        if hint in name:
            return "high", "function name contains '{}'".format(hint)
    if reader_count == 1:
        return "medium", "sole consumer of the result variable"
    if reader_count > BUSY_VARIABLE_READERS:
        return "low", "{} functions read this variable; likely shared state".format(reader_count)
    return "medium", "one of {} consumers".format(reader_count)


def process(filepath, map_type, program, out_handle):
    listing = program.getListing()
    rows = read_catalogue(filepath)
    if not rows:
        print("  No usable rows in {}".format(filepath))
        return 0, 0

    linked = 0
    no_write = 0

    for row in rows:
        call_addr = toAddr(row["call_site"])
        writer = program.getFunctionManager().getFunctionContaining(call_addr)

        try:
            ram_address = find_result_variable(listing, call_addr)
        except (MemoryAccessException, JavaException):
            ram_address = None

        if ram_address is None:
            no_write += 1
            continue

        readers = find_readers(program, ram_address, writer)
        if not readers:
            no_write += 1
            continue

        confidence, evidence = score_reader(readers[0], len(readers))
        out_handle.write("{},{:08X},{},{},{:08X},{},{},{}\n".format(
            map_type,
            row["call_site"],
            row["struct"],
            row["data"],
            ram_address.getOffset(),
            readers[0].getName(),
            confidence,
            evidence,
        ))
        linked += 1

    print("  {}: {} linked, {} without an identifiable result store.".format(
        map_type, linked, no_write))
    return linked, no_write


def main():
    program = getCurrentProgram()

    try:
        csv_2d = askFile("Select the 2D maps CSV", "Open").getAbsolutePath()
        csv_3d = askFile("Select the 3D maps CSV", "Open").getAbsolutePath()
        out_path = askFile("Save DTC-linked CSV", "Save").getAbsolutePath()
    except JavaException:
        print("Operation cancelled.")
        return

    if not out_path.endswith(".csv"):
        out_path += ".csv"

    print("=" * 66)
    print("Forward dataflow analysis (call site -> result RAM -> consumers)")

    handle = open(out_path, "w")
    try:
        handle.write("Map_Type,Wrapper_Addr,Struct_Addr,Map_Data_Addr,"
                     "Target_RAM_Var,Potential_DTC_Func,Confidence,Evidence\n")
        linked_2d, missed_2d = process(csv_2d, "2D", program, handle)
        linked_3d, missed_3d = process(csv_3d, "3D", program, handle)
    finally:
        handle.close()

    total = linked_2d + linked_3d
    print("-" * 66)
    print("{} maps linked to a consumer function.".format(total))
    print("{} maps had no identifiable result store within {} instructions.".format(
        missed_2d + missed_3d, FORWARD_WINDOW))
    print("")
    print("READ THIS BEFORE TRUSTING THE OUTPUT:")
    print("  'Potential_DTC_Func' is the first *other* function that reads the")
    print("  map's result. That is a dataflow link, not evidence of a DTC.")
    print("  Check the Confidence column, then confirm in Ghidra by following")
    print("  the cross-references before patching anything.")
    print("Saved to: {}".format(out_path))


main()
