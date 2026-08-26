# -*- coding: utf-8 -*-
# Mass map extractor: every call site of the master interpolation functions.
#
# Replaces the separate Analyze2DMaps.py / Analyze3DMaps.py, which were the same
# 100 lines twice with three constants changed.
#
# Three things it does that the previous version did not:
#
#  1. Resolves the argument through R4 rather than "the first data reference in
#     the previous 20 instructions". The master functions take a single pointer
#     argument, which the SH ABI passes in R4, so the instruction that writes R4
#     is the one to dereference. Taking the first data reference found instead
#     picks up unrelated constants loaded nearby.
#
#  2. Checks the delay slot. SH-2A branches are delayed: the instruction after a
#     BSR/JSR executes before the callee does, and compilers routinely put the
#     argument load there. A backwards-only search silently misses those maps.
#
#  3. Validates the descriptor before emitting it -- pointers must land in
#     initialised ROM, and the data block must sit after the axes. The previous
#     version wrote whatever bytes it happened to read, so the "definitive" CSVs
#     could contain garbage rows.
#
# Failures are counted and reported instead of being swallowed, so a run that
# finds fewer maps than expected says why.
#
# @category ECU_ReverseEngineering
# @runtime Jython

import java.lang.Exception as JavaException
from ghidra.program.model.lang import Register
from ghidra.program.model.mem import MemoryAccessException

ARG_REGISTER = "r4"
MAX_LOOKBACK = 24

RAM_BASE = 0xFFFF0000
MAX_AXIS_3D = 64
MAX_AXIS_2D = 128
PLAUSIBLE_WIDTHS = (1, 2, 4)


# ---------------------------------------------------------------------------
# Memory helpers
# ---------------------------------------------------------------------------

def is_rom_pointer(memory, value):
    if value == 0 or value >= RAM_BASE:
        return False
    try:
        block = memory.getBlock(toAddr(value))
    except JavaException:
        return False
    return block is not None and block.isInitialized()


def read_u32(memory, address):
    return memory.getInt(address) & 0xFFFFFFFF


def read_u16(memory, address):
    return memory.getShort(address) & 0xFFFF


# ---------------------------------------------------------------------------
# Argument resolution
# ---------------------------------------------------------------------------

def writes_arg_register(instruction):
    """True when this instruction assigns the first-argument register."""
    try:
        results = instruction.getResultObjects()
    except JavaException:
        return False
    return any(
        isinstance(item, Register) and item.getName().lower() == ARG_REGISTER
        for item in results
    )


def literal_targets(instruction):
    """ROM addresses this instruction references as data (its literal pool slot)."""
    targets = []
    try:
        references = instruction.getReferencesFrom()
    except JavaException:
        return targets
    for reference in references:
        if not reference.isMemoryReference():
            continue
        if not reference.getReferenceType().isData():
            continue
        address = reference.getToAddress()
        if address.getOffset() < RAM_BASE:
            targets.append(address)
    return targets


def candidate_instructions(listing, call_addr):
    """Instructions that could set up the argument, most likely first.

    The delay slot comes first because on SH it executes last before the call
    and is the compiler's preferred home for the argument load.
    """
    call_instruction = listing.getInstructionAt(call_addr)
    if call_instruction is None:
        return []

    ordered = []
    delay_slot = call_instruction.getNext()
    if delay_slot is not None and delay_slot.isInDelaySlot():
        ordered.append(delay_slot)

    walker = call_instruction
    for _ in range(MAX_LOOKBACK):
        walker = walker.getPrevious()
        if walker is None:
            break
        # Another call means we have walked past this call's argument setup.
        if walker.getFlowType().isCall():
            break
        ordered.append(walker)

    return ordered


def resolve_descriptor_address(listing, memory, call_addr):
    """Address of the map descriptor passed to this call, or None."""
    candidates = candidate_instructions(listing, call_addr)

    # Two passes: instructions that provably write R4 win over any other
    # instruction that merely happens to reference a plausible pointer.
    for require_arg_register in (True, False):
        for instruction in candidates:
            if require_arg_register and not writes_arg_register(instruction):
                continue
            if not require_arg_register and writes_arg_register(instruction):
                continue
            for literal in literal_targets(instruction):
                try:
                    value = read_u32(memory, literal)
                except (MemoryAccessException, JavaException):
                    continue
                if is_rom_pointer(memory, value):
                    return toAddr(value)
    return None


# ---------------------------------------------------------------------------
# Descriptor decoding
# ---------------------------------------------------------------------------

def decode_3d(memory, descriptor):
    size_x = read_u16(memory, descriptor)
    size_y = read_u16(memory, descriptor.add(2))
    if not (0 < size_x <= MAX_AXIS_3D and 0 < size_y <= MAX_AXIS_3D):
        return None
    ptr_x = read_u32(memory, descriptor.add(4))
    ptr_y = read_u32(memory, descriptor.add(8))
    ptr_z = read_u32(memory, descriptor.add(12))
    if not (is_rom_pointer(memory, ptr_x) and is_rom_pointer(memory, ptr_y)
            and is_rom_pointer(memory, ptr_z)):
        return None
    if not (ptr_z > ptr_x and ptr_z > ptr_y):
        return None
    return (size_x, size_y, ptr_x, ptr_y, ptr_z, size_x * size_y)


def decode_2d(memory, descriptor):
    size_x = read_u16(memory, descriptor)
    if not 0 < size_x <= MAX_AXIS_2D:
        return None
    ptr_x = read_u32(memory, descriptor.add(4))
    ptr_data = read_u32(memory, descriptor.add(8))
    if not (is_rom_pointer(memory, ptr_x) and is_rom_pointer(memory, ptr_data)):
        return None
    if ptr_data <= ptr_x:
        return None
    return (size_x, 1, ptr_x, 0, ptr_data, size_x)


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------

def extract(program, target_addr, decoder, label):
    """Walk every CALL to target_addr and decode the descriptor behind it."""
    listing = program.getListing()
    memory = program.getMemory()

    results = []
    seen_descriptors = set()
    stats = {"calls": 0, "unresolved": 0, "rejected": 0, "duplicates": 0, "errors": 0}

    for reference in getReferencesTo(target_addr):
        if not reference.getReferenceType().isCall():
            continue
        stats["calls"] += 1
        call_addr = reference.getFromAddress()

        try:
            descriptor = resolve_descriptor_address(listing, memory, call_addr)
        except (MemoryAccessException, JavaException):
            stats["errors"] += 1
            continue

        if descriptor is None:
            stats["unresolved"] += 1
            continue

        offset = descriptor.getOffset()
        if offset in seen_descriptors:
            stats["duplicates"] += 1
            continue

        try:
            decoded = decoder(memory, descriptor)
        except (MemoryAccessException, JavaException):
            stats["errors"] += 1
            continue

        if decoded is None:
            stats["rejected"] += 1
            continue

        seen_descriptors.add(offset)
        size_x, size_y, ptr_x, ptr_y, ptr_data, elements = decoded
        results.append({
            "call_site": call_addr.getOffset(),
            "struct": offset,
            "size_x": size_x,
            "size_y": size_y,
            "ptr_x": ptr_x,
            "ptr_y": ptr_y,
            "data": ptr_data,
            "elements": elements,
        })

    print("-" * 66)
    print("{}: {} call sites -> {} unique maps".format(label, stats["calls"], len(results)))
    print("   {} duplicate descriptors, {} rejected as implausible,".format(
        stats["duplicates"], stats["rejected"]))
    print("   {} arguments unresolved, {} memory errors.".format(
        stats["unresolved"], stats["errors"]))
    if stats["unresolved"]:
        print("   -> Unresolved call sites usually mean the pointer arrives in a")
        print("      register from the caller. Inspect a few of them by hand.")
    return results


def infer_widths(results):
    """Plausible element width from the gap to the next data block.

    Only reported when the gap divides exactly by the element count and lands on
    1, 2 or 4 bytes. Padding between blocks makes this an upper bound, so a
    non-dividing gap is left blank rather than guessed at.
    """
    ordered = sorted(results, key=lambda item: item["data"])
    for index, entry in enumerate(ordered):
        entry["width"] = ""
        if entry["elements"] <= 0:
            continue
        following = None
        for candidate in ordered[index + 1:]:
            if candidate["data"] > entry["data"]:
                following = candidate
                break
        if following is None:
            continue
        gap = following["data"] - entry["data"]
        if gap > 0 and gap % entry["elements"] == 0:
            width = gap // entry["elements"]
            if width in PLAUSIBLE_WIDTHS:
                entry["width"] = str(width)


def write_csv(path, results, is_3d):
    if not path.endswith(".csv"):
        path += ".csv"
    with open(path, "w") as handle:
        if is_3d:
            handle.write("Call_Site_Addr,Struct_Addr,Size_X,Size_Y,Axis_X_Addr,"
                         "Axis_Y_Addr,Data_Addr,Inferred_Width\n")
            for entry in results:
                handle.write("{:08X},{:08X},{},{},{:08X},{:08X},{:08X},{}\n".format(
                    entry["call_site"], entry["struct"], entry["size_x"], entry["size_y"],
                    entry["ptr_x"], entry["ptr_y"], entry["data"], entry["width"]))
        else:
            handle.write("Call_Site_Addr,Struct_Addr,Size_X,Axis_X_Addr,"
                         "Data_Addr,Inferred_Width\n")
            for entry in results:
                handle.write("{:08X},{:08X},{},{:08X},{:08X},{}\n".format(
                    entry["call_site"], entry["struct"], entry["size_x"],
                    entry["ptr_x"], entry["data"], entry["width"]))
    print("Saved {} rows to {}".format(len(results), path))


def ask_address(prompt, default):
    try:
        text = askString(prompt, "Address (hex):", default)
    except JavaException:
        return None
    text = text.strip().lower().replace("0x", "")
    if not text:
        return None
    try:
        return toAddr(int(text, 16))
    except ValueError:
        print("Not a hex address: {}".format(text))
        return None


def main():
    program = getCurrentProgram()

    print("=" * 66)
    print("Denso master interpolation extractor")
    print("Enter the address of each master function, or leave blank to skip.")
    print("On the reference A17DTR image these are 000080E4 (3D) and 00008070 (2D).")
    print("They differ between calibrations -- see the README workflow.")
    print("=" * 66)

    addr_3d = ask_address("Master 3D interpolation function", "000080e4")
    addr_2d = ask_address("Master 2D interpolation function", "00008070")

    if addr_3d is None and addr_2d is None:
        print("Nothing to do.")
        return

    results_3d = extract(program, addr_3d, decode_3d, "3D maps") if addr_3d else []
    results_2d = extract(program, addr_2d, decode_2d, "2D curves") if addr_2d else []

    # Widths are inferred across both sets at once: 2D curves and 3D maps are
    # interleaved in the data area, so each bounds the other.
    infer_widths(results_3d + results_2d)

    if results_3d:
        save = askFile("Save 3D maps (CSV)", "Save")
        write_csv(save.getAbsolutePath(), results_3d, is_3d=True)
    if results_2d:
        save = askFile("Save 2D curves (CSV)", "Save")
        write_csv(save.getAbsolutePath(), results_2d, is_3d=False)

    print("=" * 66)
    print("Done. {} 3D maps, {} 2D curves.".format(len(results_3d), len(results_2d)))


main()
