"""Descriptor decoding on synthetic bytes laid out like the firmware's."""

import struct

import pytest

from viewer.core import descriptor as dsc


def descriptor_3d(size_x=23, size_y=8, ax=0x1000, ay=0x1100, data=0x1200,
                  element_type=0x08, factor=0.005, offset=0.0):
    return struct.pack(">HHIIIB3xff", size_x, size_y, ax, ay, data, element_type, factor, offset)


def descriptor_2d(size_x=11, element_type=0x10, ax=0x2000, data=0x2100,
                  factor=0.0078125, offset=0.0):
    return struct.pack(">HBBIIff", size_x, element_type, 0, ax, data, factor, offset)


def test_3d_layout():
    raw = descriptor_3d()
    assert len(raw) == dsc.DESCRIPTOR_SIZE_3D
    d = dsc.read_3d(raw, 0)
    assert (d.size_x, d.size_y, d.axis_x, d.axis_y, d.data) == (23, 8, 0x1000, 0x1100, 0x1200)
    assert d.z_format == ">H"
    assert d.factor == pytest.approx(0.005)
    assert d.overrides() == {"z_format": ">H", "factor": pytest.approx(0.005), "offset": 0.0}


def test_2d_layout():
    raw = descriptor_2d()
    assert len(raw) == dsc.DESCRIPTOR_SIZE_2D
    d = dsc.read_2d(raw, 0)
    assert (d.size_x, d.size_y, d.axis_x, d.data) == (11, 1, 0x2000, 0x2100)
    assert d.z_format == ">h"
    assert d.factor == pytest.approx(1 / 128)


@pytest.mark.parametrize("element_type,fmt", sorted(dsc.ELEMENT_FORMATS.items()))
def test_every_element_type(element_type, fmt):
    assert dsc.read_3d(descriptor_3d(element_type=element_type), 0).z_format == fmt


def test_float_maps_ignore_factor_and_offset():
    # Type 0x00 returns the stored float as is; the factor slot holds no meaning.
    d = dsc.read_3d(descriptor_3d(element_type=0x00, factor=123.0, offset=4.0), 0)
    assert d.overrides() == {"z_format": ">f", "factor": 1.0, "offset": 0.0}


def test_unknown_type_is_rejected():
    with pytest.raises(dsc.DescriptorError):
        dsc.read_3d(descriptor_3d(element_type=0x14), 0)


def test_truncated_image_is_rejected():
    with pytest.raises(dsc.DescriptorError):
        dsc.read_3d(descriptor_3d()[:10], 0)


def test_read_at_offset():
    image = b"\xAA" * 0x40 + descriptor_2d(size_x=5)
    assert dsc.read(image, 0x40, is_3d=False).size_x == 5
