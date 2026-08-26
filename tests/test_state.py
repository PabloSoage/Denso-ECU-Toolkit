"""The enums that replaced widget-text state and magic combo indices."""

import pytest

from viewer.core.state import (
    AppMode,
    Baseline,
    CompareMode,
    MapMode,
    PlotDim,
    ViewMode,
)


class TestAppMode:
    def test_label_matches_the_button_text_format(self):
        assert AppMode.MAP_VIEWER.label == "Mode: Map Viewer"
        assert AppMode.HEX_DUMP.label == "Mode: Hex Dump"

    def test_next_cycles_through_every_mode(self):
        mode = AppMode.MAP_VIEWER
        seen = [mode]
        for _ in range(len(AppMode) - 1):
            mode = mode.next
            seen.append(mode)
        assert set(seen) == set(AppMode)
        assert mode.next is AppMode.MAP_VIEWER

    def test_only_potential_maps_is_read_only(self):
        read_only = [m for m in AppMode if m.is_read_only]
        assert read_only == [AppMode.POTENTIAL_MAPS]

    def test_hex_dump_does_not_use_the_map_list(self):
        assert not AppMode.HEX_DUMP.uses_map_list
        assert AppMode.MAP_VIEWER.uses_map_list
        assert AppMode.POTENTIAL_MAPS.uses_map_list


class TestMapMode:
    def test_combo_index_round_trip(self):
        for mode in MapMode:
            assert MapMode.from_combo_index(mode.combo_index) is mode

    def test_out_of_range_index_is_all(self):
        assert MapMode.from_combo_index(99) is MapMode.ALL
        assert MapMode.from_combo_index(-1) is MapMode.ALL


class TestViewMode:
    def test_cycle(self):
        assert ViewMode.PLOT.next is ViewMode.TABLE
        assert ViewMode.TABLE.next is ViewMode.SPLIT
        assert ViewMode.SPLIT.next is ViewMode.PLOT

    def test_split_shows_both(self):
        assert ViewMode.SPLIT.shows_plot and ViewMode.SPLIT.shows_table
        assert ViewMode.PLOT.shows_plot and not ViewMode.PLOT.shows_table
        assert ViewMode.TABLE.shows_table and not ViewMode.TABLE.shows_plot


class TestPlotDim:
    def test_other_toggles(self):
        assert PlotDim.D2.other is PlotDim.D3
        assert PlotDim.D3.other is PlotDim.D2

    def test_label(self):
        assert PlotDim.D3.label == "Plot Mode: 3D"


class TestCompareMode:
    def test_labels_cover_every_member_in_order(self):
        """The toolbar combo is built from this list, so a missing entry would
        silently shift every index."""
        labels = CompareMode.labels()
        assert len(labels) == len(CompareMode)
        assert all(isinstance(label, str) and label for label in labels)

    def test_index_round_trip(self):
        for mode in CompareMode:
            assert CompareMode.from_index(int(mode)) is mode

    def test_unknown_index_is_normal(self):
        assert CompareMode.from_index(42) is CompareMode.NORMAL

    @pytest.mark.parametrize(
        "mode, baseline",
        [
            (CompareMode.NORMAL, Baseline.NONE),
            (CompareMode.SHOW_ORIGINAL, Baseline.NONE),
            (CompareMode.DIFF_ORIGINAL, Baseline.ORIGINAL_BIN),
            (CompareMode.DIFF_PERCENT, Baseline.ORIGINAL_BIN),
            (CompareMode.DIFF_REFERENCE, Baseline.REFERENCE_MAP),
            (CompareMode.TWIN_ORIGINAL, Baseline.ORIGINAL_BIN),
            (CompareMode.TWIN_REFERENCE, Baseline.REFERENCE_MAP),
            (CompareMode.DIFF_EXTERNAL, Baseline.EXTERNAL_BIN),
            (CompareMode.TWIN_EXTERNAL, Baseline.EXTERNAL_BIN),
        ],
    )
    def test_baseline_mapping(self, mode, baseline):
        assert mode.baseline is baseline

    def test_groups_match_the_old_magic_index_sets(self):
        """These sets were previously written out by hand in two files:
        (2,3,5,7,8) read a baseline binary, (5,6,8) were twins,
        (4,6) used the stored reference, (2,7) subtracted."""
        assert {int(m) for m in CompareMode if m.reads_baseline_bin} == {2, 3, 5, 7, 8}
        assert {int(m) for m in CompareMode if m.is_twin} == {5, 6, 8}
        assert {int(m) for m in CompareMode if m.uses_reference_map} == {4, 6}
        assert {int(m) for m in CompareMode if m.subtracts} == {2, 4, 7}

    def test_only_show_original_hides_edits(self):
        hiding = [m for m in CompareMode if not m.shows_modified_bin]
        assert hiding == [CompareMode.SHOW_ORIGINAL]

    def test_comparison_starts_after_show_original(self):
        assert not CompareMode.NORMAL.is_comparison
        assert not CompareMode.SHOW_ORIGINAL.is_comparison
        assert all(m.is_comparison for m in CompareMode if int(m) > 1)

    def test_every_mode_has_a_baseline_title(self):
        for mode in CompareMode:
            assert isinstance(mode.baseline_title, str)
