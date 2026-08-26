"""Populates and filters the map list on the left panel."""

from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QListWidgetItem

from ...core.data_manager import parse_address

MODIFIED_COLOR = QColor(255, 0, 0)

TYPE_PREFIX = {"3d": "3D Map", "2d": "2D Crv", "tags": "HexTag"}


class MapListManager:
    def __init__(self, main_window):
        self.main_window = main_window

    # ------------------------------------------------------------------
    # Tag filter menu
    # ------------------------------------------------------------------

    def update_tag_filter_menu(self):
        mw = self.main_window
        menu = getattr(mw, "tag_filter_menu", None)
        if menu is None:
            return
        menu.clear()

        df = mw.data_manager.df
        all_tags = set()
        if not df.empty and "Tag" in df.columns:
            for tag_str in df["Tag"].fillna(""):
                all_tags.update(t.strip() for t in str(tag_str).split(",") if t.strip())

        # Drop filters whose tag no longer exists, or the list silently empties.
        mw.active_tag_filters &= all_tags

        for tag in sorted(all_tags):
            action = menu.addAction(tag)
            action.setCheckable(True)
            action.setChecked(tag in mw.active_tag_filters)
            action.triggered.connect(lambda checked, t=tag: self.on_tag_filter_toggled(t, checked))

    def on_tag_filter_toggled(self, tag, checked):
        if checked:
            self.main_window.active_tag_filters.add(tag)
        else:
            self.main_window.active_tag_filters.discard(tag)
        self.update_list()

    # ------------------------------------------------------------------
    # List
    # ------------------------------------------------------------------

    def update_list(self):
        mw = self.main_window
        mw.map_listbox.clear()
        mw.filtered_indices = []

        df = mw.data_manager.df
        if df.empty:
            return

        search_term = mw.search_box.text().strip().lower()
        smart_filter = mw.cb_smart_filter.isChecked() if hasattr(mw, "cb_smart_filter") else False
        active_filters = mw.active_tag_filters

        hidden_by_filter = 0

        for idx, row in df.iterrows():
            map_type = row.get("Map_Type", mw.map_mode.value)
            address = str(row.get("Data_Addr", "")).strip()
            tag = str(row.get("Tag", "")).strip()

            if search_term and search_term not in address.lower() and search_term not in tag.lower():
                continue

            if active_filters:
                row_tags = {t.strip() for t in tag.split(",") if t.strip()}
                if not active_filters.issubset(row_tags):
                    continue

            # Checked last: it decodes axes, which is by far the costliest test.
            if smart_filter and not mw.data_manager.check_map_axes(row):
                hidden_by_filter += 1
                continue

            label = f"{TYPE_PREFIX.get(map_type, 'Map')} {idx + 1}: {address}"
            if tag:
                label += f" [{tag}]"

            item = QListWidgetItem(label)
            if self._is_modified(row):
                item.setForeground(MODIFIED_COLOR)
            mw.map_listbox.addItem(item)
            mw.filtered_indices.append(idx)

        self._report(len(df), hidden_by_filter)

        if mw.filtered_indices:
            self.sync_listbox_selection()

    def _report(self, total, hidden):
        """Say how many rows the filters removed, rather than just showing fewer."""
        mw = self.main_window
        shown = len(mw.filtered_indices)
        if shown == total:
            mw.status_lbl.setText(f"{total} map(s).")
        elif hidden:
            mw.status_lbl.setText(
                f"{shown} of {total} map(s) — {hidden} hidden by the axis filter."
            )
        else:
            mw.status_lbl.setText(f"{shown} of {total} map(s) after filtering.")

    def _is_modified(self, row):
        dm = self.main_window.data_manager
        address = parse_address(row.get("Data_Addr", ""))
        if address is None:
            return False
        length = dm.map_byte_length(row)
        if not length:
            return False
        return dm.is_map_modified(address, length)

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------

    def on_list_select(self):
        mw = self.main_window
        selected = mw.map_listbox.selectedIndexes()
        if not selected:
            return
        visual_index = selected[0].row()
        if 0 <= visual_index < len(mw.filtered_indices):
            mw.data_manager.current_index = mw.filtered_indices[visual_index]
            mw.draw_map()

    def sync_listbox_selection(self):
        mw = self.main_window
        if mw.data_manager.current_index not in mw.filtered_indices:
            return
        visual_index = mw.filtered_indices.index(mw.data_manager.current_index)
        mw.map_listbox.blockSignals(True)
        mw.map_listbox.setCurrentRow(visual_index)
        mw.map_listbox.blockSignals(False)
