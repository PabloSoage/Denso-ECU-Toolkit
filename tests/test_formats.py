"""Format handling: widths, round-trips and error messages."""

import pytest

from viewer.core import formats


class TestValueSize:
    @pytest.mark.parametrize(
        "fmt, expected",
        [
            (">b", 1), (">B", 1),
            (">h", 2), (">H", 2),
            (">i", 4), (">I", 4),
            (">l", 4), (">L", 4),
            (">f", 4),
            ("<H", 2),
            ("H", 2),   # bare type character
            ("f", 4),
        ],
    )
    def test_known_widths(self, fmt, expected):
        assert formats.value_size(fmt) == expected

    def test_32_bit_is_four_bytes(self):
        """Regression: two call sites used to omit 'i'/'l' and return 1 byte,
        so choosing "32-bit" laid out the hex grid and the map highlighting
        one byte per value."""
        assert formats.value_size(">i") == 4
        assert formats.value_size(">I") == 4

    def test_unknown_falls_back_to_unsigned_short(self):
        assert formats.type_char(">?") == "H"
        assert formats.value_size(">?") == 2

    def test_empty(self):
        assert formats.value_size("") == 2


class TestByteOrder:
    def test_big_endian_is_the_default(self):
        assert formats.byte_order("H") == ">"
        assert formats.byte_order("") == ">"

    def test_explicit(self):
        assert formats.byte_order("<H") == "<"
        assert formats.byte_order(">H") == ">"

    def test_normalise(self):
        assert formats.normalise("H") == ">H"
        assert formats.normalise("<f") == "<f"


class TestBuildDescribeRoundTrip:
    @pytest.mark.parametrize("label", ["8-bit", "16-bit", "32-bit", "Float"])
    @pytest.mark.parametrize("signed", [True, False])
    def test_round_trip(self, label, signed):
        char = formats.build(label, signed)
        size_label, order, described_signed = formats.describe(">" + char)
        assert size_label == label
        assert order == ">"
        # Float has no unsigned variant and is always reported as signed.
        assert described_signed == (True if label == "Float" else signed)

    def test_unknown_label_defaults_to_16_bit(self):
        assert formats.build("banana", True) == "h"


class TestUnpackArray:
    def test_big_endian_unsigned_short(self):
        data = bytes([0x12, 0x34, 0x56, 0x78])
        assert formats.unpack_array(data, ">H", 2) == (0x1234, 0x5678)

    def test_little_endian(self):
        data = bytes([0x12, 0x34])
        assert formats.unpack_array(data, "<H", 1) == (0x3412,)

    def test_offset(self):
        data = bytes([0xFF, 0xFF, 0x00, 0x2A])
        assert formats.unpack_array(data, ">H", 1, offset=2) == (0x2A,)

    def test_short_buffer_names_the_shortfall(self):
        """The message must distinguish "map runs off the end of the ROM" from
        "the format is wrong"; struct's own error does not."""
        with pytest.raises(ValueError) as excinfo:
            formats.unpack_array(bytes(4), ">H", 8)
        message = str(excinfo.value)
        assert "16 bytes" in message
        assert "only 4" in message

    def test_accepts_bytearray(self):
        assert formats.unpack_array(bytearray([0, 1]), ">H", 1) == (1,)


class TestPackValue:
    def test_rounds_for_integer_formats(self):
        assert formats.pack_value(4.7, ">H") == bytes([0x00, 0x05])

    def test_float_is_not_rounded(self):
        packed = formats.pack_value(1.5, ">f")
        assert formats.unpack_array(packed, ">f", 1) == (1.5,)

    def test_out_of_range_explains_itself(self):
        with pytest.raises(ValueError) as excinfo:
            formats.pack_value(70000, ">H")
        assert "does not fit" in str(excinfo.value)

    def test_negative_into_unsigned_is_rejected(self):
        with pytest.raises(ValueError):
            formats.pack_value(-1, ">H")

    def test_negative_into_signed_is_fine(self):
        assert formats.pack_value(-1, ">h") == bytes([0xFF, 0xFF])

    def test_round_trip_through_unpack(self):
        for value, fmt in [(1234, ">H"), (-5, ">h"), (7, ">B"), (100000, ">i")]:
            assert formats.unpack_array(formats.pack_value(value, fmt), fmt, 1) == (value,)
