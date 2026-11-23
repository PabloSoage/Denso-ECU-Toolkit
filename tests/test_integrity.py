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


def _image_with_cal_header(fill=0x11, corrupt=False):
    """A synthetic image just large enough for the header at 0x13FF50."""
    img = bytearray(0x140000)
    start, end = 0x0C0000, 0x13FF4F
    for i in range(start, start + 0x100):
        img[i] = (i * 7 + fill) & 0xFF
    header = start.to_bytes(4, "big") + end.to_bytes(4, "big")
    img[0x13FF50:0x13FF58] = header
    img[0x13FF5C:0x13FF64] = header
    total = sum(int.from_bytes(img[i:i + 4], "big") for i in range(start, end + 1, 4))
    cks = (integrity.CAL_CHECKSUM_MAGIC - total) & 0xFFFFFFFF
    img[0x13FF58:0x13FF5C] = cks.to_bytes(4, "big")
    img[0x13FF64:0x13FF68] = cks.to_bytes(4, "big")
    if corrupt:
        img[start + 3] ^= 0x01
    return img


class TestCalChecksumStatus:
    def test_valid_header(self):
        st = integrity.cal_checksum_status(_image_with_cal_header())
        assert st["ok"] and st["copies_match"]
        assert (st["start"], st["end"]) == (0x0C0000, 0x13FF4F)

    def test_edit_in_range_breaks_it(self):
        st = integrity.cal_checksum_status(_image_with_cal_header(corrupt=True))
        assert st["ok"] is False
        assert st["stored"] != st["computed"]

    def test_header_is_part_of_the_check_only_via_its_copy(self):
        img = _image_with_cal_header()
        img[0x13FF64] ^= 0xFF  # damage the duplicate only
        st = integrity.cal_checksum_status(img)
        assert st["ok"] is True and st["copies_match"] is False

    def test_no_header(self):
        assert integrity.cal_checksum_status(bytes(0x140000)) is None

    def test_short_image(self):
        assert integrity.cal_checksum_status(bytes(0x1000)) is None

    def test_verify_only_does_not_enable_support(self):
        assert integrity.CHECKSUM_SUPPORT is False
