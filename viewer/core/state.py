"""Application state as explicit enumerations.

Every mode the UI can be in used to be stored in the text or the visibility of a
widget (``btn_main_mode.text() == "Mode: Hex Dump"``, ``cmb_map_type.isVisible()``).
That made renaming a button a behavioural change and scattered magic combo-box
indices across three files. These enums are the single source of truth; widgets
render them, they never define them.
"""

from enum import Enum, IntEnum


class AppMode(Enum):
    """Top-level mode: what the main area is showing."""

    MAP_VIEWER = "Map Viewer"
    HEX_DUMP = "Hex Dump"
    POTENTIAL_MAPS = "Potential Maps"

    @property
    def label(self):
        return f"Mode: {self.value}"

    @property
    def next(self):
        members = list(AppMode)
        return members[(members.index(self) + 1) % len(members)]

    @property
    def uses_map_list(self):
        """True when the left-hand map list drives what is drawn."""
        return self in (AppMode.MAP_VIEWER, AppMode.POTENTIAL_MAPS)

    @property
    def is_read_only(self):
        """Potential Maps shows unconfirmed heuristic hits; editing them is unsafe."""
        return self is AppMode.POTENTIAL_MAPS


class MapMode(Enum):
    """Which family of entries the map list is populated from."""

    THREE_D = "3d"
    TWO_D = "2d"
    TAGS = "tags"
    ALL = "all"

    @property
    def combo_index(self):
        return list(MapMode).index(self)

    @classmethod
    def from_combo_index(cls, idx):
        members = list(cls)
        return members[idx] if 0 <= idx < len(members) else cls.ALL


class ViewMode(Enum):
    """Plot, table, or both."""

    PLOT = "plot"
    TABLE = "table"
    SPLIT = "split"

    @property
    def label(self):
        return f"View: {self.value.capitalize()}"

    @property
    def next(self):
        members = list(ViewMode)
        return members[(members.index(self) + 1) % len(members)]

    @property
    def shows_plot(self):
        return self in (ViewMode.PLOT, ViewMode.SPLIT)

    @property
    def shows_table(self):
        return self in (ViewMode.TABLE, ViewMode.SPLIT)


class PlotDim(Enum):
    """Dimensionality a map is rendered with."""

    D2 = "2d"
    D3 = "3d"

    @property
    def label(self):
        return f"Plot Mode: {self.value.upper()}"

    @property
    def other(self):
        return PlotDim.D2 if self is PlotDim.D3 else PlotDim.D3


class Baseline(Enum):
    """Where the "other" side of a comparison comes from."""

    NONE = "none"
    ORIGINAL_BIN = "original"
    REFERENCE_MAP = "reference"
    EXTERNAL_BIN = "external"


class CompareMode(IntEnum):
    """Comparison modes, in the order the toolbar combo lists them.

    The integer values ARE the combo indices — the combo is built from
    :meth:`labels` so the two can never drift apart.
    """

    NORMAL = 0
    SHOW_ORIGINAL = 1
    DIFF_ORIGINAL = 2
    DIFF_PERCENT = 3
    DIFF_REFERENCE = 4
    TWIN_ORIGINAL = 5
    TWIN_REFERENCE = 6
    DIFF_EXTERNAL = 7
    TWIN_EXTERNAL = 8

    @classmethod
    def labels(cls):
        return [_COMPARE_LABELS[m] for m in cls]

    @classmethod
    def from_index(cls, idx):
        try:
            return cls(idx)
        except ValueError:
            return cls.NORMAL

    @property
    def baseline(self):
        """Which source the comparison reads its baseline matrix from."""
        return _COMPARE_BASELINE[self]

    @property
    def is_comparison(self):
        """Any mode past SHOW_ORIGINAL compares two datasets."""
        return self > CompareMode.SHOW_ORIGINAL

    @property
    def reads_baseline_bin(self):
        """Baseline must be re-read from a binary rather than a stored matrix."""
        return self.baseline in (Baseline.ORIGINAL_BIN, Baseline.EXTERNAL_BIN)

    @property
    def uses_external_bin(self):
        return self.baseline is Baseline.EXTERNAL_BIN

    @property
    def uses_reference_map(self):
        return self.baseline is Baseline.REFERENCE_MAP

    @property
    def is_twin(self):
        """Side-by-side: needs a second set of axes and a second table."""
        return self in (
            CompareMode.TWIN_ORIGINAL,
            CompareMode.TWIN_REFERENCE,
            CompareMode.TWIN_EXTERNAL,
        )

    @property
    def subtracts(self):
        """Renders ``current - baseline`` in place of the raw values."""
        return self in (
            CompareMode.DIFF_ORIGINAL,
            CompareMode.DIFF_REFERENCE,
            CompareMode.DIFF_EXTERNAL,
        )

    @property
    def is_percent(self):
        return self is CompareMode.DIFF_PERCENT

    @property
    def shows_modified_bin(self):
        """SHOW_ORIGINAL is the only mode that hides pending edits."""
        return self is not CompareMode.SHOW_ORIGINAL

    @property
    def baseline_title(self):
        return {
            Baseline.ORIGINAL_BIN: "Original",
            Baseline.REFERENCE_MAP: "Reference Map",
            Baseline.EXTERNAL_BIN: "External Bin",
        }.get(self.baseline, "Baseline")


_COMPARE_LABELS = {
    CompareMode.NORMAL: "View: Normal",
    CompareMode.SHOW_ORIGINAL: "View: Show Original",
    CompareMode.DIFF_ORIGINAL: "Compare: Difference (Mod - Orig)",
    CompareMode.DIFF_PERCENT: "Compare: Difference (%)",
    CompareMode.DIFF_REFERENCE: "Compare: Vs Reference Map",
    CompareMode.TWIN_ORIGINAL: "Twin: Side-by-Side (Mod vs Orig)",
    CompareMode.TWIN_REFERENCE: "Twin: Side-by-Side (Mod vs Ref Map)",
    CompareMode.DIFF_EXTERNAL: "Compare: Difference (Mod - Ext. Bin)",
    CompareMode.TWIN_EXTERNAL: "Twin: Side-by-Side (Mod vs Ext. Bin)",
}

_COMPARE_BASELINE = {
    CompareMode.NORMAL: Baseline.NONE,
    CompareMode.SHOW_ORIGINAL: Baseline.NONE,
    CompareMode.DIFF_ORIGINAL: Baseline.ORIGINAL_BIN,
    CompareMode.DIFF_PERCENT: Baseline.ORIGINAL_BIN,
    CompareMode.DIFF_REFERENCE: Baseline.REFERENCE_MAP,
    CompareMode.TWIN_ORIGINAL: Baseline.ORIGINAL_BIN,
    CompareMode.TWIN_REFERENCE: Baseline.REFERENCE_MAP,
    CompareMode.DIFF_EXTERNAL: Baseline.EXTERNAL_BIN,
    CompareMode.TWIN_EXTERNAL: Baseline.EXTERNAL_BIN,
}


class RotationMode(Enum):
    """How dragging the mouse rotates the 3D view."""

    Z_ONLY = "Z"
    WINOLS = "WinOLS"
    TILT = "Tilt"


class SparklineStyle(Enum):
    BARS = "Bars"
    LINE = "Line"


class HexPlotPosition(Enum):
    TOP = "top"
    RIGHT = "right"
