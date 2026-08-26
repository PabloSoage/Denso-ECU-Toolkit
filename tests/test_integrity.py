"""Edit reporting for the export path."""

from viewer.core import integrity


class TestModifiedRegions:
    def test_identical_buffers_have_no_regions(self):
        data = bytes(range(16))
        assert integrity.modified_regions(data, bytearray(data)) == []

    def test_single_byte(self):
        original = bytes(8)
        modified = bytearray(original)
        modified[3] = 0xFF
        assert integrity.modified_regions(original, modified) == [(3, 1)]

    def test_contiguous_run_is_one_region(self):
        original = bytes(8)
        modified = bytearray(original)
        modified[2:5] = b"\x01\x02\x03"
        assert integrity.modified_regions(original, modified) == [(2, 3)]

    def test_a_single_matching_byte_splits_the_run(self):
        """Scattered edits should read as scattered -- that is the signal that a
        stray keystroke landed somewhere unexpected."""
        original = bytes(8)
        modified = bytearray(original)
        modified[1] = 0xAA
        modified[3] = 0xBB
        assert integrity.modified_regions(original, modified) == [(1, 1), (3, 1)]

    def test_run_reaching_the_end(self):
        original = bytes(4)
        modified = bytearray(b"\x00\x00\x01\x01")
        assert integrity.modified_regions(original, modified) == [(2, 2)]

    def test_empty_inputs(self):
        assert integrity.modified_regions(b"", b"") == []
        assert integrity.modified_regions(b"", b"\x01") == []

    def test_length_change_is_reported_not_ignored(self):
        regions = integrity.modified_regions(bytes(4), bytearray(6))
        assert regions == [(4, 2)]


class TestSum32:
    def test_sum_of_bytes(self):
        assert integrity.sum32(bytes([1, 2, 3])) == 6

    def test_range(self):
        assert integrity.sum32(bytes([1, 2, 3, 4]), 1, 3) == 5

    def test_truncates_to_32_bits(self):
        assert integrity.sum32(b"\xff" * 0x1000000) == (0xFF * 0x1000000) & 0xFFFFFFFF


class TestDescribeRegions:
    def test_no_regions(self):
        assert integrity.describe_regions([]) == ["No differences."]

    def test_formats_address_range(self):
        lines = integrity.describe_regions([(0x1000, 4)])
        assert lines == ["00001000 - 00001003  (4 bytes)"]

    def test_singular_byte(self):
        assert "(1 byte)" in integrity.describe_regions([(0, 1)])[0]

    def test_caps_the_list(self):
        regions = [(i * 4, 1) for i in range(30)]
        lines = integrity.describe_regions(regions, max_listed=5)
        assert len(lines) == 6
        assert "25 more region(s)" in lines[-1]


class TestExportReport:
    def test_totals(self):
        original = bytes(16)
        modified = bytearray(original)
        modified[0] = 1
        modified[8:10] = b"\x02\x03"
        total, count, lines = integrity.export_report(original, modified)
        assert total == 3
        assert count == 2
        assert len(lines) == 2


def test_checksum_support_is_off():
    """Nothing in the toolkit can recompute this ECU's checksum. If this flag
    is ever flipped, an actual algorithm must exist and be verified against a
    known-good pair of images."""
    assert integrity.CHECKSUM_SUPPORT is False
    assert "NOT" in integrity.CHECKSUM_WARNING
