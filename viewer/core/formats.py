"""Struct format handling, in one place.

The width-of-a-value question used to be answered by an ad-hoc ``if/elif`` chain
repeated in ten different functions, and not all of them agreed: two of them
forgot ``'i'``/``'l'`` entirely, so choosing "32-bit" in the settings dialog made
the hex view and the map highlighting compute 1 byte per value instead of 4.

Formats are the two-character strings ``struct`` already understands: a byte
order prefix (``<`` or ``>``) plus one type character.
"""

import struct

#: Type character -> width in bytes. Lower/upper case only differ in signedness.
_WIDTHS = {
    "b": 1,
    "B": 1,
    "h": 2,
    "H": 2,
    "i": 4,
    "I": 4,
    "l": 4,
    "L": 4,
    "f": 4,
}

#: Human label used by the settings dialog -> (signed char, unsigned char).
SIZE_LABELS = {
    "8-bit": ("b", "B"),
    "16-bit": ("h", "H"),
    "32-bit": ("i", "I"),
    "Float": ("f", "f"),
}

DEFAULT_FORMAT = ">H"


def type_char(fmt):
    """Return the struct type character of ``fmt``, defaulting to unsigned short."""
    if not fmt:
        return "H"
    char = fmt[-1]
    return char if char in _WIDTHS else "H"


def byte_order(fmt):
    """Return ``'<'`` or ``'>'``; big endian is the Denso/SH705x default."""
    return "<" if fmt and fmt[0] == "<" else ">"


def value_size(fmt):
    """Width in bytes of a single value in ``fmt``.

    Accepts either a full format (``'>H'``) or a bare type character (``'H'``).
    """
    return _WIDTHS.get(type_char(fmt), 1)


def is_float(fmt):
    return type_char(fmt) == "f"


def normalise(fmt):
    """Return ``fmt`` as a canonical ``<order><char>`` pair."""
    return byte_order(fmt) + type_char(fmt)


def build(size_label, signed):
    """Compose a type character from a settings-dialog size label."""
    signed_char, unsigned_char = SIZE_LABELS.get(size_label, SIZE_LABELS["16-bit"])
    return signed_char if signed else unsigned_char


def describe(fmt):
    """Inverse of :func:`build`: ``('16-bit', '>', True)`` for ``'>h'``."""
    char = type_char(fmt)
    for label, (signed_char, unsigned_char) in SIZE_LABELS.items():
        if char in (signed_char, unsigned_char):
            size_label = label
            break
    else:
        size_label = "16-bit"
    # Float has no unsigned variant; report it as signed so the checkbox is stable.
    signed = True if char == "f" else char.islower()
    return size_label, byte_order(fmt), signed


def unpack_array(data, fmt, count, offset=0):
    """Unpack ``count`` consecutive values starting at ``offset``.

    Raises :class:`ValueError` with a message naming the shortfall when the
    buffer does not reach that far, instead of ``struct``'s opaque complaint.
    Callers rely on this to tell "the map runs off the end of the ROM" apart
    from "the format is wrong".
    """
    width = value_size(fmt)
    needed = count * width
    chunk = bytes(data[offset:offset + needed])
    if len(chunk) < needed:
        raise ValueError(
            f"needs {needed} bytes at 0x{offset:X} but only {len(chunk)} are "
            f"available (binary is {len(data)} bytes)"
        )
    return struct.unpack(f"{byte_order(fmt)}{count}{type_char(fmt)}", chunk)


def pack_value(value, fmt):
    """Pack a single value, rounding to int for the integer formats.

    Raises :class:`ValueError` when the value does not fit the target width,
    so the caller can say *why* an edit was rejected.
    """
    char = type_char(fmt)
    if char != "f":
        value = int(round(float(value)))
    try:
        return struct.pack(f"{byte_order(fmt)}{char}", value)
    except struct.error as exc:
        raise ValueError(f"{value} does not fit in format '{normalise(fmt)}': {exc}") from exc
