"""DataManager: addressing, decoding, editing and project round-trips.

Built on a synthetic binary rather than the real firmware, so the suite runs
in a clone that has no access to the private research repository.
"""

import json
import struct

import numpy as np
import pandas as pd
import pytest

from viewer.core.data_manager import DataManager, parse_address
from viewer.core.state import Baseline

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

AXIS_X_ADDR = 0x100
AXIS_Y_ADDR = 0x120
MAP_ADDR = 0x200
CURVE_AXIS_ADDR = 0x300
CURVE_ADDR = 0x320

AXIS_X = [1000, 1500, 2000, 2500]
AXIS_Y = [10, 20, 30]
MAP_VALUES = list(range(12))          # 3 rows x 4 columns
CURVE_AXIS = [0, 25, 50, 75]
CURVE_VALUES = [100, 200, 300, 400]


def build_binary(size=0x400):
    """A little ROM with one 4x3 map and one 4-point curve at known offsets."""
    data = bytearray(size)

    def put(address, values):
        packed = struct.pack(f">{len(values)}H", *values)
        data[address:address + len(packed)] = packed

    put(AXIS_X_ADDR, AXIS_X)
    put(AXIS_Y_ADDR, AXIS_Y)
    put(MAP_ADDR, MAP_VALUES)
    put(CURVE_AXIS_ADDR, CURVE_AXIS)
    put(CURVE_ADDR, CURVE_VALUES)
    return bytes(data)


@pytest.fixture
def binary_path(tmp_path):
    path = tmp_path / "test.bin"
    path.write_bytes(build_binary())
    return path


@pytest.fixture
def manager(binary_path):
    dm = DataManager()
    dm.bin_path = str(binary_path)
    dm.z_format_3d = ">H"
    dm.z_format_2d = ">H"
    dm.ax_format = "H"
    ok, _ = dm.load_binary()
    assert ok
    return dm


def map_row(**overrides):
    row = {
        "Map_Type": "3d",
        "Data_Addr": f"{MAP_ADDR:08X}",
        "Struct_Addr": "0000ABCD",
        "Call_Site_Addr": "00001234",
        "Wrapper_Addr": "00001234",
        "Axis_X_Addr": f"{AXIS_X_ADDR:08X}",
        "Axis_Y_Addr": f"{AXIS_Y_ADDR:08X}",
        "Size_X": "4",
        "Size_Y": "3",
        "Tag": "",
    }
    row.update(overrides)
    return pd.Series(row)


def curve_row(**overrides):
    row = {
        "Map_Type": "2d",
        "Data_Addr": f"{CURVE_ADDR:08X}",
        "Struct_Addr": "",
        "Call_Site_Addr": "00005678",
        "Wrapper_Addr": "00005678",
        "Axis_X_Addr": f"{CURVE_AXIS_ADDR:08X}",
        "Axis_Y_Addr": "",
        "Size_X": "4",
        "Size_Y": "1",
        "Tag": "",
    }
    row.update(overrides)
    return pd.Series(row)


# ---------------------------------------------------------------------------
# Addressing
# ---------------------------------------------------------------------------

class TestParseAddress:
    @pytest.mark.parametrize("text", ["", "0", "0X0", "0x0", "00000000", "   "])
    def test_null_addresses(self, text):
        assert parse_address(text) is None

    def test_bare_hex(self):
        assert parse_address("000CB584") == 0xCB584

    def test_prefixed_and_lowercase(self):
        assert parse_address("0xcb584") == 0xCB584

    def test_whitespace(self):
        assert parse_address("  1A2B  ") == 0x1A2B

    def test_garbage_is_none_not_an_exception(self):
        assert parse_address("not-hex") is None
        assert parse_address(None) is None


class TestIdentityKeys:
    def test_data_address_comes_first(self):
        keys = DataManager.identity_keys(map_row())
        assert keys[0] == f"{MAP_ADDR:08X}"
        assert DataManager.canonical_key(map_row()) == f"{MAP_ADDR:08X}"

    def test_includes_struct_and_call_site(self):
        keys = DataManager.identity_keys(map_row())
        assert "0000ABCD" in keys
        assert "00001234" in keys

    def test_no_duplicates(self):
        keys = DataManager.identity_keys(map_row())
        assert len(keys) == len(set(keys))

    def test_null_columns_are_dropped(self):
        keys = DataManager.identity_keys(
            map_row(Struct_Addr="", Call_Site_Addr="00000000", Wrapper_Addr="")
        )
        assert keys == [f"{MAP_ADDR:08X}"]


# ---------------------------------------------------------------------------
# Decoding
# ---------------------------------------------------------------------------

class TestReadMap:
    def test_3d_shape_and_values(self, manager):
        matrix, axis_x, axis_y, size_y, size_x, address = manager.read_map(map_row())
        assert matrix.shape == (3, 4)
        assert size_y == 3 and size_x == 4
        assert address == f"{MAP_ADDR:08X}"
        np.testing.assert_array_equal(matrix.flatten(), MAP_VALUES)
        np.testing.assert_array_equal(axis_x, AXIS_X)
        np.testing.assert_array_equal(axis_y, AXIS_Y)

    def test_2d_curve(self, manager):
        curve, axis_x, _, size_y, size_x, _ = manager.read_map(curve_row(), as_2d=True)
        assert size_y == 1 and size_x == 4
        np.testing.assert_array_equal(curve, CURVE_VALUES)
        np.testing.assert_array_equal(axis_x, CURVE_AXIS)

    def test_missing_axis_falls_back_to_indices(self, manager):
        _, axis_x, _, _, _, _ = manager.read_map(map_row(Axis_X_Addr="00000000"))
        np.testing.assert_array_equal(axis_x, [0, 1, 2, 3])

    def test_map_past_the_end_says_so(self, manager):
        with pytest.raises(ValueError) as excinfo:
            manager.read_map(map_row(Data_Addr="000003F0", Size_X="64", Size_Y="64"))
        message = str(excinfo.value)
        assert "000003F0" in message
        assert "bytes" in message

    def test_unusable_address_is_rejected(self, manager):
        with pytest.raises(ValueError):
            manager.read_map(map_row(Data_Addr=""))

    def test_format_override_changes_the_decode(self, manager):
        manager.custom_map_settings[f"{MAP_ADDR:08X}"] = {"z_format": ">B"}
        matrix, _, _, _, _, _ = manager.read_map(map_row())
        # 12 bytes read as u8 instead of 6 u16 values.
        assert matrix.shape == (3, 4)
        assert list(matrix.flatten())[:4] == [0, 0, 0, 1]


class TestAxisCache:
    def test_repeated_reads_hit_the_cache(self, manager):
        first = manager.read_axis(f"{AXIS_X_ADDR:08X}", 4, "H")
        second = manager.read_axis(f"{AXIS_X_ADDR:08X}", 4, "H")
        assert first is second

    def test_editing_invalidates_the_cache(self, manager):
        manager.read_axis(f"{AXIS_X_ADDR:08X}", 4, "H")
        manager.apply_edit(AXIS_X_ADDR, 4242, ">H")
        refreshed = manager.read_axis(f"{AXIS_X_ADDR:08X}", 4, "H")
        assert refreshed[0] == 4242


# ---------------------------------------------------------------------------
# Editing
# ---------------------------------------------------------------------------

class TestApplyEdit:
    def test_writes_the_value(self, manager):
        ok, error = manager.apply_edit(MAP_ADDR, 999, ">H")
        assert ok and error == ""
        matrix, _, _, _, _, _ = manager.read_map(map_row())
        assert matrix[0, 0] == 999

    def test_rejects_out_of_range_address(self, manager):
        ok, error = manager.apply_edit(0x3FFF, 1, ">H")
        assert not ok
        assert "outside the binary" in error

    def test_rejects_negative_address(self, manager):
        ok, error = manager.apply_edit(-4, 1, ">H")
        assert not ok

    def test_rejects_a_value_that_does_not_fit(self, manager):
        ok, error = manager.apply_edit(MAP_ADDR, 70000, ">H")
        assert not ok
        assert "does not fit" in error

    def test_original_is_preserved(self, manager):
        manager.apply_edit(MAP_ADDR, 999, ">H")
        assert manager.has_edits
        manager.show_modified = False
        matrix, _, _, _, _, _ = manager.read_map(map_row())
        assert matrix[0, 0] == MAP_VALUES[0]

    def test_revert(self, manager):
        manager.apply_edit(MAP_ADDR, 999, ">H")
        manager.revert_all_edits()
        assert not manager.has_edits

    def test_is_map_modified_tracks_the_range(self, manager):
        assert not manager.is_map_modified(MAP_ADDR, 24)
        # Cell 5 of the map, which holds 5; write something genuinely different.
        manager.apply_edit(MAP_ADDR + 10, 4242, ">H")
        assert manager.is_map_modified(MAP_ADDR, 24)
        assert not manager.is_map_modified(CURVE_ADDR, 8)

    def test_rewriting_the_same_value_is_not_a_modification(self, manager):
        manager.apply_edit(MAP_ADDR + 10, MAP_VALUES[5], ">H")
        assert not manager.is_map_modified(MAP_ADDR, 24)
        assert not manager.has_edits


class TestBinDiff:
    def test_round_trip(self, manager):
        manager.apply_edit(MAP_ADDR, 999, ">H")
        diff = manager.get_bin_diff()
        assert len(diff) == 2  # one 16-bit value

        fresh = DataManager()
        fresh.bin_path = manager.bin_path
        fresh.load_binary()
        applied, skipped = fresh.apply_bin_diff(diff)
        assert (applied, skipped) == (2, 0)
        assert bytes(fresh._modified_bin_data) == bytes(manager._modified_bin_data)

    def test_out_of_range_offsets_are_counted_not_silently_dropped(self, manager):
        applied, skipped = manager.apply_bin_diff({"0": 1, "999999": 2})
        assert applied == 1
        assert skipped == 1


# ---------------------------------------------------------------------------
# Comparison baselines
# ---------------------------------------------------------------------------

class TestBaselineReads:
    def test_original_baseline_ignores_edits(self, manager):
        manager.apply_edit(MAP_ADDR, 999, ">H")
        result = manager.read_map_baseline(map_row(), Baseline.ORIGINAL_BIN)
        assert result[0][0, 0] == MAP_VALUES[0]

    def test_state_is_restored_afterwards(self, manager):
        manager.show_modified = True
        manager.read_map_baseline(map_row(), Baseline.ORIGINAL_BIN)
        assert manager.show_modified is True

    def test_state_is_restored_even_when_it_was_false(self, manager):
        """The old implementation restored a hardcoded True here."""
        manager.show_modified = False
        manager.read_map_baseline(map_row(), Baseline.ORIGINAL_BIN)
        assert manager.show_modified is False

    def test_external_without_a_reference_raises(self, manager):
        from viewer.core.data_manager import BinaryUnavailable

        with pytest.raises(BinaryUnavailable):
            manager.read_map_baseline(map_row(), Baseline.EXTERNAL_BIN)

    def test_none_baseline_returns_none(self, manager):
        assert manager.read_map_baseline(map_row(), Baseline.NONE) is None


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------

class TestTagResolution:
    def test_tag_on_the_call_site_is_found_from_the_data_address(self, manager):
        """A tag applied in Map Viewer mode (keyed by call site) must still show
        in Potential Maps mode (keyed by struct address), and vice versa."""
        manager.tags["00001234"] = {"tags": ["Boost"], "length": 1}
        assert manager._tags_for_addresses(*DataManager.identity_keys(map_row())) == ["Boost"]

    def test_tag_on_the_struct_address_is_also_found(self, manager):
        manager.tags["0000ABCD"] = {"tags": ["Rail Pressure"], "length": 1}
        assert "Rail Pressure" in manager._tags_for_addresses(*DataManager.identity_keys(map_row()))

    def test_tags_are_unioned_without_duplicates(self, manager):
        manager.tags["00001234"] = {"tags": ["Boost", "Turbo"], "length": 1}
        manager.tags["0000ABCD"] = {"tags": ["Turbo", "VNT"], "length": 1}
        result = manager._tags_for_addresses(*DataManager.identity_keys(map_row()))
        # Ordered by identity: data address, then struct (ABCD), then call site
        # (1234). "Turbo" appears in both and is listed once, where first seen.
        assert result == ["Turbo", "VNT", "Boost"]


class TestCustomSettings:
    def test_legacy_key_is_still_read(self, manager):
        """Projects saved before the data address became canonical keyed their
        overrides by call site."""
        manager.custom_map_settings["00001234"] = {"factor": 0.5}
        assert manager.custom_settings_for(map_row()) == {"factor": 0.5}

    def test_canonical_key_wins(self, manager):
        manager.custom_map_settings["00001234"] = {"factor": 0.5}
        manager.custom_map_settings[f"{MAP_ADDR:08X}"] = {"factor": 2.0}
        assert manager.custom_settings_for(map_row())["factor"] == 2.0

    def test_writes_go_to_the_canonical_key(self, manager):
        manager.set_custom_setting(map_row(), factor=1.25)
        assert manager.custom_map_settings[f"{MAP_ADDR:08X}"]["factor"] == 1.25


# ---------------------------------------------------------------------------
# Catalogue loading
# ---------------------------------------------------------------------------

class TestCatalogueNormalisation:
    def test_legacy_3d_headers(self, manager):
        df = pd.DataFrame([{
            "Wrapper_Addr": "00001234", "Size_X": "4", "Size_Y": "3",
            "Axis_X_Addr": "00000100", "Axis_Y_Addr": "00000120",
            "Map_Z_Addr": "00000200",
        }])
        result = manager._normalise_catalogue(df, "3d")
        assert result.loc[0, "Data_Addr"] == "00000200"
        assert result.loc[0, "Call_Site_Addr"] == "00001234"
        assert result.loc[0, "Struct_Addr"] == ""

    def test_legacy_2d_headers(self, manager):
        df = pd.DataFrame([{
            "Wrapper_Addr": "00005678", "Size_X": "4",
            "Axis_X_Addr": "00000300", "Curve_Data_Addr": "00000320",
        }])
        result = manager._normalise_catalogue(df, "2d")
        assert result.loc[0, "Data_Addr"] == "00000320"

    def test_potential_wrapper_column_means_the_struct(self, manager):
        """Same header, different meaning: in potential_maps.csv Wrapper_Addr is
        the descriptor address, in the review CSVs it is the call site. Their
        overlap on the reference image is exactly zero rows."""
        df = pd.DataFrame([{
            "Map_Type": "3d", "Wrapper_Addr": "0000ABCD", "Size_X": "4", "Size_Y": "3",
            "Axis_X_Addr": "00000100", "Axis_Y_Addr": "00000120", "Map_Z_Addr": "00000200",
        }])
        result = manager._normalise_catalogue(df, "potential")
        assert result.loc[0, "Struct_Addr"] == "0000ABCD"
        assert result.loc[0, "Call_Site_Addr"] == ""

    def test_current_headers_pass_through(self, manager):
        df = pd.DataFrame([{
            "Call_Site_Addr": "00001234", "Struct_Addr": "0000ABCD",
            "Size_X": "4", "Size_Y": "3", "Axis_X_Addr": "00000100",
            "Axis_Y_Addr": "00000120", "Data_Addr": "00000200",
        }])
        result = manager._normalise_catalogue(df, "3d")
        assert result.loc[0, "Data_Addr"] == "00000200"
        assert result.loc[0, "Struct_Addr"] == "0000ABCD"

    def test_addresses_are_normalised(self, manager):
        df = pd.DataFrame([{"Wrapper_Addr": " 0x1234 ", "Map_Z_Addr": "0xcb584", "Size_X": "1"}])
        result = manager._normalise_catalogue(df, "3d")
        assert result.loc[0, "Data_Addr"] == "CB584"
        assert result.loc[0, "Call_Site_Addr"] == "1234"


class TestSmartAxisFilter:
    def test_monotonic_axes_pass(self, manager):
        assert manager.check_map_axes(map_row())

    def test_non_monotonic_x_axis_fails(self, manager):
        # 0x300 holds [0, 25, 50, 75] followed by padding zeros, so an 8-point
        # read rises and then drops -- exactly the shape of a false positive.
        assert not manager.check_map_axes(
            map_row(Map_Type="2d", Axis_X_Addr="00000300", Size_X="8", Axis_Y_Addr="")
        )

    def test_flat_axis_is_not_monotonic(self, manager):
        # Address 0x000 is all zeros in the synthetic image.
        assert not manager.check_map_axes(
            map_row(Axis_X_Addr="00000010", Size_X="4", Axis_Y_Addr="")
        )

    def test_single_point_axis_passes(self, manager):
        assert manager.check_map_axes(map_row(Size_X="1", Size_Y="1", Axis_Y_Addr=""))


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------

class TestProjects:
    def test_round_trip(self, manager, tmp_path):
        manager.tags["00001234"] = {"tags": ["Boost"], "length": 1}
        manager.custom_map_settings["00000200"] = {"factor": 0.5}
        manager.apply_edit(MAP_ADDR, 999, ">H")

        path = tmp_path / "project.dproj"
        ok, error = manager.save_project(str(path))
        assert ok, error

        fresh = DataManager()
        ok, warning = fresh.load_project(str(path))
        assert ok
        assert warning == ""
        assert fresh.tags["00001234"]["tags"] == ["Boost"]
        assert fresh.custom_map_settings["00000200"]["factor"] == 0.5
        matrix, _, _, _, _, _ = fresh.read_map(map_row())
        assert matrix[0, 0] == 999

    def test_missing_binary_keeps_the_edits_and_warns(self, manager, tmp_path):
        """Regression: a project whose bin_path no longer resolved used to drop
        every stored edit while reporting success."""
        manager.apply_edit(MAP_ADDR, 999, ">H")
        path = tmp_path / "project.dproj"
        manager.save_project(str(path))

        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["bin_path"] = str(tmp_path / "gone.bin")
        path.write_text(json.dumps(payload), encoding="utf-8")

        fresh = DataManager()
        ok, warning = fresh.load_project(str(path))
        assert ok
        assert "NOT lost" in warning
        assert fresh._pending_diff, "edits must be held, not discarded"

        # Point it at a real binary; the held edits must land.
        fresh.bin_path = manager.bin_path
        fresh.load_binary()
        matrix, _, _, _, _, _ = fresh.read_map(map_row())
        assert matrix[0, 0] == 999

    def test_legacy_list_shaped_tags(self, tmp_path):
        path = tmp_path / "old.dproj"
        path.write_text(json.dumps({"tags": {"00001234": ["Boost", "Turbo"]}}), encoding="utf-8")
        dm = DataManager()
        ok, _ = dm.load_project(str(path))
        assert ok
        assert dm.tags["00001234"]["tags"] == ["Boost", "Turbo"]

    def test_legacy_string_shaped_tags(self, tmp_path):
        path = tmp_path / "old.dproj"
        path.write_text(json.dumps({"tags": {"00001234": "Boost, Turbo"}}), encoding="utf-8")
        dm = DataManager()
        dm.load_project(str(path))
        assert dm.tags["00001234"]["tags"] == ["Boost", "Turbo"]

    def test_hexdump_tags_stored_in_the_wrong_bucket_are_moved(self, tmp_path):
        path = tmp_path / "old.dproj"
        path.write_text(json.dumps({
            "tags": {"00000200": {"tags": ["Region"], "length": 8, "chunks": [[512, 8]]}}
        }), encoding="utf-8")
        dm = DataManager()
        dm.load_project(str(path))
        assert "00000200" in dm.hexdump_tags
        assert "00000200" not in dm.tags

    def test_corrupt_project_reports_instead_of_raising(self, tmp_path):
        path = tmp_path / "bad.dproj"
        path.write_text("{not json", encoding="utf-8")
        ok, message = DataManager().load_project(str(path))
        assert not ok
        assert "Could not read project" in message

    def test_missing_file(self, tmp_path):
        ok, message = DataManager().load_project(str(tmp_path / "nope.dproj"))
        assert not ok
        assert "not found" in message.lower()


# ---------------------------------------------------------------------------
# Colour map
# ---------------------------------------------------------------------------

class TestBuildColorMap:
    def test_no_binary_yields_an_empty_array(self):
        dm = DataManager()
        dm.bin_path = "does-not-exist.bin"
        assert dm.build_color_map() is False
        assert len(dm.map_array) == 0

    def test_custom_tag_is_painted(self, manager):
        manager.hexdump_tags["00000200"] = {"tags": ["Region"], "length": 8}
        assert manager.build_color_map(highlight_3d=False, highlight_2d=False)
        painted = np.nonzero(manager.map_array != -1)[0]
        assert list(painted) == list(range(0x200, 0x208))

    def test_array_is_integer_typed(self, manager):
        manager.build_color_map()
        assert manager.map_array.dtype == np.int32


# ---------------------------------------------------------------------------
# Formats from descriptors
# ---------------------------------------------------------------------------

DESC_3D_ADDR = 0x380
DESC_2D_ADDR = 0x3A0


@pytest.fixture
def described(tmp_path):
    """The test binary plus one 3D and one 2D descriptor pointing at its tables."""
    data = bytearray(build_binary())
    data[DESC_3D_ADDR:DESC_3D_ADDR + 0x1C] = struct.pack(
        ">HHIIIB3xff", 4, 3, AXIS_X_ADDR, AXIS_Y_ADDR, MAP_ADDR, 0x08, 0.5, -10.0)
    data[DESC_2D_ADDR:DESC_2D_ADDR + 0x14] = struct.pack(
        ">HBBIIff", 4, 0x10, 0, CURVE_AXIS_ADDR, CURVE_ADDR, 0.25, 0.0)
    path = tmp_path / "described.bin"
    path.write_bytes(bytes(data))
    dm = DataManager()
    dm.bin_path = str(path)
    assert dm.load_binary()[0]
    dm.df = pd.DataFrame([
        map_row(Struct_Addr=f"{DESC_3D_ADDR:08X}"),
        curve_row(Struct_Addr=f"{DESC_2D_ADDR:08X}"),
    ])
    return dm


class TestDescriptorFormats:
    def test_applies_format_factor_and_offset(self, described):
        applied, kept, failed = described.apply_descriptor_formats()
        assert (applied, kept, failed) == (2, 0, [])
        s3 = described.custom_settings_for(described.df.iloc[0])
        s2 = described.custom_settings_for(described.df.iloc[1])
        assert s3 == {"z_format": ">H", "factor": 0.5, "offset": -10.0}
        assert s2 == {"z_format": ">h", "factor": 0.25, "offset": 0.0}

    def test_existing_overrides_are_kept(self, described):
        described.set_custom_setting(described.df.iloc[0], factor=9.0)
        applied, kept, _ = described.apply_descriptor_formats()
        assert (applied, kept) == (1, 1)
        assert described.custom_settings_for(described.df.iloc[0]) == {"factor": 9.0}

    def test_overwrite_replaces_them(self, described):
        described.set_custom_setting(described.df.iloc[0], factor=9.0)
        applied, kept, _ = described.apply_descriptor_formats(overwrite=True)
        assert (applied, kept) == (2, 0)
        assert described.custom_settings_for(described.df.iloc[0])["factor"] == 0.5

    def test_pointer_mismatch_is_reported_not_applied(self, described):
        described.df.loc[0, "Data_Addr"] = "00000210"
        applied, _, failed = described.apply_descriptor_formats()
        assert applied == 1
        assert failed and "does not match" in failed[0][1]

    def test_rows_without_descriptor_are_skipped(self, manager):
        manager.df = pd.DataFrame([curve_row()])
        assert manager.apply_descriptor_formats() == (0, 0, [])
