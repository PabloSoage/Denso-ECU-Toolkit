"""Map descriptors: dimensions, pointers, element type, factor and offset.

The master interpolation functions do not return the raw table value. They read
an element type and a factor/offset from the descriptor and return
``offset + raw * factor``. So the physical unit of every map is written in the
firmware, next to its dimensions, and nothing has to be guessed.

Layout, from the decompiled master functions of two calibrations (``NCLZQ60R``
at 0x80E4/0x8070 and ``NCLSW420AX36`` at 0x7128/0x70B4)::

    3D  +0x00 u16 size_x   +0x02 u16 size_y
        +0x04 u32 axis X   +0x08 u32 axis Y   +0x0C u32 data
        +0x10 u8  type     +0x14 f32 factor   +0x18 f32 offset
    2D  +0x00 u16 size_x   +0x02 u8  type     +0x03 u8  (unused here)
        +0x04 u32 axis X   +0x08 u32 data
        +0x0C f32 factor   +0x10 f32 offset

The type byte is also the offset into the element-reader table. The readers
are byte-identical in both calibrations; what each one loads:

    0x00 float   (``fmov.s``; factor and offset are not applied)
    0x04 u8      (``mov.b`` + ``extu.b``)
    0x08 u16     (``mov.w`` + ``extu.w``)
    0x0C s8      (``mov.b``, sign-extended)
    0x10 s16     (``mov.w``, sign-extended)

Axes are always big-endian floats.
"""

import struct
from dataclasses import dataclass

#: Element type byte -> struct format understood by ``viewer.core.formats``.
ELEMENT_FORMATS = {0x00: ">f", 0x04: ">B", 0x08: ">H", 0x0C: ">b", 0x10: ">h"}

DESCRIPTOR_SIZE_3D = 0x1C
DESCRIPTOR_SIZE_2D = 0x14


class DescriptorError(ValueError):
    """The bytes at an address do not form a descriptor this module understands."""


@dataclass(frozen=True)
class Descriptor:
    size_x: int
    size_y: int
    axis_x: int
    axis_y: int
    data: int
    element_type: int
    factor: float
    offset: float

    @property
    def z_format(self):
        return ELEMENT_FORMATS[self.element_type]

    @property
    def is_float(self):
        return self.element_type == 0x00

    def overrides(self):
        """Per-map settings for the viewer: format, factor and offset."""
        if self.is_float:
            return {"z_format": self.z_format, "factor": 1.0, "offset": 0.0}
        return {"z_format": self.z_format, "factor": self.factor, "offset": self.offset}


def _read(data, address, fmt):
    size = struct.calcsize(fmt)
    if address < 0 or address + size > len(data):
        raise DescriptorError(f"descriptor at 0x{address:X} runs past the end of the image")
    return struct.unpack(fmt, bytes(data[address:address + size]))


def _check_type(element_type, address):
    if element_type not in ELEMENT_FORMATS:
        raise DescriptorError(f"unknown element type 0x{element_type:02X} at 0x{address:X}")


def read_3d(data, address):
    size_x, size_y, axis_x, axis_y, ptr, element_type, _pad, factor, offset = _read(
        data, address, ">HHIIIB3sff")
    _check_type(element_type, address)
    return Descriptor(size_x, size_y, axis_x, axis_y, ptr, element_type, factor, offset)


def read_2d(data, address):
    size_x, element_type, _unused, axis_x, ptr, factor, offset = _read(data, address, ">HBBIIff")
    _check_type(element_type, address)
    return Descriptor(size_x, 1, axis_x, 0, ptr, element_type, factor, offset)


def read(data, address, is_3d):
    return read_3d(data, address) if is_3d else read_2d(data, address)
