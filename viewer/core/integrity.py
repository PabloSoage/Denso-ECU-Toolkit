"""Binary integrity: what changed, and what the toolkit does *not* do about it.

The viewer can patch a calibration and write it back out. It cannot recompute
the ECU's checksums, because the checksum block of the Denso SH705x family has
not been located in this firmware (see ``docs/findings.md``). Flashing a
modified image whose checksum no longer matches is how ECUs stop booting.

So the honest contract is: describe the edit precisely, state plainly that the
checksum was not touched, and make the user acknowledge it. Everything here is
about producing that description; nothing here silently "fixes" anything.
"""

CHECKSUM_SUPPORT = False
"""No checksum algorithm is implemented for this platform. Do not flip this to
True until a block has actually been located and verified against a known-good
pair of images."""


def modified_regions(original, modified):
    """Contiguous runs of differing bytes as ``(start, length)`` tuples.

    Both arguments are byte sequences. A run is broken by any single matching
    byte, so a scattered edit reports many small regions — which is exactly the
    signal the user wants when a stray keystroke landed somewhere unexpected.
    """
    if not original or not modified:
        return []

    regions = []
    limit = min(len(original), len(modified))
    start = None

    for i in range(limit):
        if original[i] != modified[i]:
            if start is None:
                start = i
        elif start is not None:
            regions.append((start, i - start))
            start = None

    if start is not None:
        regions.append((start, limit - start))

    if len(modified) != len(original):
        # A length change is not an edit the viewer can make, but say so rather
        # than silently comparing only the common prefix.
        regions.append((limit, abs(len(modified) - len(original))))

    return regions


def sum32(data, start=0, end=None):
    """Little-endian-agnostic 32-bit additive checksum over ``data[start:end]``.

    Provided so that once a checksum block *is* identified, verifying it is one
    call rather than a fresh script. Additive sum-of-bytes truncated to 32 bits
    is the most common scheme in this ECU family, but it is a starting point for
    investigation, not a confirmed algorithm for this firmware.
    """
    end = len(data) if end is None else end
    return sum(data[start:end]) & 0xFFFFFFFF


def describe_regions(regions, max_listed=12):
    """Render regions as human-readable lines, capping the list length."""
    if not regions:
        return ["No differences."]

    lines = [
        f"{addr:08X} - {addr + length - 1:08X}  ({length} byte{'s' if length != 1 else ''})"
        for addr, length in regions[:max_listed]
    ]
    if len(regions) > max_listed:
        lines.append(f"... and {len(regions) - max_listed} more region(s).")
    return lines


def export_report(original, modified):
    """Summary shown before writing a patched binary out to disk.

    Returns ``(total_bytes, region_count, lines)``.
    """
    regions = modified_regions(original, modified)
    total = sum(length for _, length in regions)
    return total, len(regions), describe_regions(regions)


CHECKSUM_WARNING = (
    "This file has NOT had its checksums recalculated.\n\n"
    "No checksum block has been located in this firmware, so the toolkit "
    "cannot correct one. Flashing an image with a stale checksum can leave the "
    "ECU unable to boot.\n\n"
    "Before flashing: run the file through a checksum tool that knows this ECU, "
    "and make sure you have a verified bench read of the original and a way to "
    "recover via bootloader."
)
