from PyQt6.QtWidgets import QListWidgetItem
from PyQt6.QtGui import QColor

class MapListManager:
    def __init__(self, main_window):
        self.main_window = main_window

    def update_tag_filter_menu(self):
        if not hasattr(self.main_window, 'tag_filter_menu'): return
        self.main_window.tag_filter_menu.clear()
        all_tags = set()
        
        if not self.main_window.data_manager.df.empty and 'Tag' in self.main_window.data_manager.df.columns:
            for tag_str in self.main_window.data_manager.df['Tag'].fillna(''):
                for t in str(tag_str).split(','):
                    t = t.strip()
                    if t:
                        all_tags.add(t)
                
        for t in sorted(all_tags):
            action = self.main_window.tag_filter_menu.addAction(t)
            action.setCheckable(True)
            action.setChecked(t in self.main_window.active_tag_filters)
            action.triggered.connect(lambda checked, tag=t: self.on_tag_filter_toggled(tag, checked))

    def on_tag_filter_toggled(self, tag, checked):
        if checked:
            self.main_window.active_tag_filters.add(tag)
        else:
            self.main_window.active_tag_filters.discard(tag)
        self.update_list()

    def on_map_type_changed(self, idx):
        if idx == 0: new_mode = '3d'
        elif idx == 1: new_mode = '2d'
        elif idx == 2: new_mode = 'tags'
        else: new_mode = 'all'
        
        if new_mode != self.main_window.map_mode:
            self.main_window.map_mode = new_mode
            if self.main_window.btn_main_mode.text() == "Mode: Map Viewer":
                self.main_window.btn_hex_plot_mode.setVisible(self.main_window.map_mode == 'tags')
            self.main_window.btn_edit_dims.setVisible(self.main_window.map_mode in ('tags', 'all'))
            self.main_window.load_data()

    def update_list(self):
        self.main_window.map_listbox.clear()
        self.main_window.filtered_indices = []
        if self.main_window.data_manager.df.empty: return
        
        search_term = self.main_window.search_box.text().lower()
        
        for idx, row in self.main_window.data_manager.df.iterrows():
            mtype = row.get('Map_Type', self.main_window.map_mode)
            
            # For 3D and Hexdump Tags, use Map_Z_Addr as the title. For 2D, Curve_Data_Addr
            addr_col = 'Map_Z_Addr' if mtype in ('3d', 'tags') else 'Curve_Data_Addr'
            addr = str(row.get(addr_col, '')).strip()
            tag = str(row.get('Tag', '')).strip()

            # Beautiful label indicating type
            prefix = {"3d": "3D Map", "2d": "2D Crv", "tags": "HexTag"}.get(mtype, "Map")
            
            display_text = f"{prefix} {idx+1}: {addr}"
            if tag:
                display_text += f" [{tag}]"

            term_match = (search_term in addr.lower() or search_term in tag.lower())
            
            tag_match = True
            if self.main_window.active_tag_filters:
                row_tags = [t.strip() for t in tag.split(',') if t.strip()]
                for f_tag in self.main_window.active_tag_filters:
                    if f_tag not in row_tags:
                        tag_match = False
                        break
                        
            if term_match and tag_match:
                item = QListWidgetItem(display_text)
                
                # Check for modifications
                try:
                    is_modified = False
                    if mtype == '3d':
                        sz_h_row = str(row.get('Wrapper_Addr', '')).strip()
                        cst = self.main_window.data_manager.custom_map_settings.get(sz_h_row, {})
                        fmt = cst.get('z_format', self.main_window.data_manager.z_format_3d)
                        fc = fmt[-1]
                        bpv = 4 if fc.lower() in ('f','i','l') else (2 if fc.lower() == 'h' else 1)
                        sx, sy = int(row.get('Size_X', 1)), int(row.get('Size_Y', 1))
                        addr_int = int(str(row.get('Map_Z_Addr', '0')).strip(), 16)
                        length = sx * sy * bpv
                        is_modified = self.main_window.data_manager.is_map_modified(addr_int, length)
                    elif mtype == '2d':
                        sz_h_row = str(row.get('Wrapper_Addr', '')).strip()
                        cst = self.main_window.data_manager.custom_map_settings.get(sz_h_row, {})
                        fmt = cst.get('z_format', self.main_window.data_manager.z_format_2d)
                        fc = fmt[-1]
                        bpv = 4 if fc.lower() in ('f','i','l') else (2 if fc.lower() == 'h' else 1)
                        sx = int(row.get('Size_X', 1))
                        addr_int = int(str(row.get('Curve_Data_Addr', '0')).strip(), 16)
                        length = sx * bpv
                        is_modified = self.main_window.data_manager.is_map_modified(addr_int, length)
                    if is_modified:
                        item.setForeground(QColor(255, 0, 0))
                except: pass
                
                self.main_window.map_listbox.addItem(item)
                self.main_window.filtered_indices.append(idx)

        if self.main_window.filtered_indices:
            self.sync_listbox_selection()

    def on_list_select(self):
        items = self.main_window.map_listbox.selectedIndexes()
        if items:
            visual_idx = items[0].row()
            if visual_idx < len(self.main_window.filtered_indices):
                self.main_window.data_manager.current_index = self.main_window.filtered_indices[visual_idx]
                self.main_window.draw_map()

    def sync_listbox_selection(self):
        if self.main_window.data_manager.current_index in self.main_window.filtered_indices:
            vis_idx = self.main_window.filtered_indices.index(self.main_window.data_manager.current_index)
            # Block signals temporarily to prevent triggering on_list_select
            self.main_window.map_listbox.blockSignals(True)
            self.main_window.map_listbox.setCurrentRow(vis_idx)
            self.main_window.map_listbox.blockSignals(False)
