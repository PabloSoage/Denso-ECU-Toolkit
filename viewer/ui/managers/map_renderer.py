import numpy as np
from PyQt6.QtWidgets import QTableWidgetItem
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from widgets.sparkline_widget import SparklineWidget

class MapRenderer:
    def __init__(self, main_window):
        self.main_window = main_window

    def draw_map(self, auto_scroll=True):
        if self.main_window.data_manager.df.empty:
            if self.main_window.btn_main_mode.text() == "Mode: Hex Dump":
                self.main_window.update_hex_view(auto_scroll=auto_scroll)
            return
        try:
            row = self.main_window.data_manager.df.iloc[self.main_window.data_manager.current_index] 
            wrapper_addr_hex = str(row['Wrapper_Addr']).strip()
            custom = getattr(self.main_window.data_manager, "custom_map_settings", {}).get(wrapper_addr_hex, {})

            has_dtc = wrapper_addr_hex in getattr(self.main_window.data_manager, 'dtc_data', {})
            self.main_window.btn_dtc_info.setVisible(has_dtc)

            current_type = row.get('Map_Type', self.main_window.map_mode)

            # Update toggle button visibility dynamically for 'All' mode
            if self.main_window.btn_main_mode.text() == "Mode: Map Viewer":
                self.main_window.btn_hex_plot_mode.setVisible(current_type == 'tags' or self.main_window.map_mode == 'tags')

            # Auto-rebuild axes if switching between 2D and 3D in 'All' mode    
            is_currently_3d = hasattr(self.main_window.ax, 'plot_surface')
            needs_3d = (current_type == '3d' or (current_type == 'tags' and self.main_window.hex_plot_mode == '3d'))
            if is_currently_3d != needs_3d:
                self.main_window.rebuild_plot_axes()
            current_type = row.get('Map_Type', self.main_window.map_mode)
            
            # Auto-rebuild axes if switching between 2D and 3D in 'All' mode    
            is_currently_3d = hasattr(self.main_window.ax, 'plot_surface')
            needs_3d = (current_type == '3d' or (current_type == 'tags' and self.main_window.hex_plot_mode == '3d'))
            if is_currently_3d != needs_3d:
                self.main_window.rebuild_plot_axes()
            current_type = row.get('Map_Type', self.main_window.map_mode)
            if current_type == 'tags':
                is_2d = self.main_window.hex_plot_mode == '2d'
                raw_matrix, axis_x, axis_y, size_y, size_x, map_addr = self.main_window.data_manager.read_map_tags(as_2d=is_2d)
                if is_2d:
                    current_factor = custom.get('factor', self.main_window.factor_z_2d)
                    current_offset = custom.get('offset', self.main_window.offset_z_2d)
                    current_fmt = custom.get('z_format', self.main_window.data_manager.z_format_2d)
                else:
                    current_factor = custom.get('factor', self.main_window.factor_z_3d)
                    current_offset = custom.get('offset', self.main_window.offset_z_3d)
                    current_fmt = custom.get('z_format', self.main_window.data_manager.z_format_3d)
            elif current_type == '3d':
                raw_matrix, axis_x, axis_y, size_y, size_x, map_addr = self.main_window.data_manager.read_map_3d()
                current_factor = custom.get('factor', self.main_window.factor_z_3d)
                current_offset = custom.get('offset', self.main_window.offset_z_3d)
                current_fmt = custom.get('z_format', self.main_window.data_manager.z_format_3d)
            else:
                raw_matrix, axis_x, _, size_y, size_x, map_addr = self.main_window.data_manager.read_map_2d()
                current_factor = custom.get('factor', self.main_window.factor_z_2d)
                current_offset = custom.get('offset', self.main_window.offset_z_2d)
                current_fmt = custom.get('z_format', self.main_window.data_manager.z_format_2d)

            matrix_z = (raw_matrix * current_factor) + current_offset
            
            cmp_index = getattr(self.main_window, "cmb_compare_mode", None)
            cmp_idx = cmp_index.currentIndex() if cmp_index else 0
            matrix_orig = None
            raw_orig = None

            if cmp_idx > 1:
                if cmp_idx in (2, 3, 5, 7, 8):
                    self.main_window.data_manager.show_modified = False
                    
                    is_ext_bin = cmp_idx in (7, 8)
                    temp_cache = None
                    if is_ext_bin:
                        if self.main_window.data_manager._reference_bin_data:
                            temp_cache = self.main_window.data_manager._bin_data_cache
                            self.main_window.data_manager._bin_data_cache = self.main_window.data_manager._reference_bin_data
                        else:
                            is_ext_bin = False
                    
                    try:
                        if current_type == 'tags':
                            raw_orig, _, _, _, _, _ = self.main_window.data_manager.read_map_tags(as_2d=(self.main_window.hex_plot_mode == '2d'))
                        elif current_type == '3d':
                            raw_orig, _, _, _, _, _ = self.main_window.data_manager.read_map_3d()
                        else:
                            raw_orig, _, _, _, _, _ = self.main_window.data_manager.read_map_2d()
                    finally:
                        if is_ext_bin:
                            self.main_window.data_manager._bin_data_cache = temp_cache

                    self.main_window.data_manager.show_modified = True
                    matrix_orig = (raw_orig * current_factor) + current_offset
                    
                    if cmp_idx in (2, 7):
                        matrix_z = matrix_z - matrix_orig
                    elif cmp_idx == 3:
                        orig_safe = np.where(matrix_orig == 0, 1e-9, matrix_orig)
                        matrix_z = ((matrix_z - matrix_orig) / orig_safe) * 100
                elif cmp_idx in (4, 6):
                    if hasattr(self.main_window, "reference_matrix") and getattr(self.main_window, "reference_matrix", None) is not None:
                        raw_orig = self.main_window.reference_matrix
                        matrix_orig = (self.main_window.reference_matrix * current_factor) + current_offset
                        
                        if self.main_window.reference_matrix.shape != matrix_z.shape and cmp_idx == 4:
                            new_orig = np.zeros_like(matrix_z)
                            if len(matrix_z.shape) == 2 and len(self.main_window.reference_matrix.shape) == 2:
                                min_y = min(matrix_z.shape[0], self.main_window.reference_matrix.shape[0])
                                min_x = min(matrix_z.shape[1], self.main_window.reference_matrix.shape[1])
                                new_orig[:min_y, :min_x] = matrix_orig[:min_y, :min_x]
                            elif len(matrix_z.shape) == 1 and len(self.main_window.reference_matrix.shape) == 1:
                                min_x = min(matrix_z.shape[0], self.main_window.reference_matrix.shape[0])
                                new_orig[:min_x] = matrix_orig[:min_x]
                            matrix_orig = new_orig
                        
                        if cmp_idx == 4:
                            matrix_z = matrix_z - matrix_orig

            clean_axis_x = [str(round(v, 2)).rstrip('0').rstrip('.') for v in axis_x]
            if (current_type == '3d' or (current_type == 'tags' and self.main_window.hex_plot_mode == '3d')):
                clean_axis_y = [str(round(v, 2)).rstrip('0').rstrip('.') for v in axis_y]
                self.main_window.real_axis_y = axis_y
            
            self.main_window.real_axis_x = axis_x

            self.main_window.map_size_x = size_x
            self.main_window.map_size_y = size_y
            self.main_window.z_min = matrix_z.min()
            self.main_window.z_max = matrix_z.max()
            
            if cmp_idx in (5, 6, 8) and matrix_orig is not None:
                self.main_window.z_orig_min = matrix_orig.min()
                self.main_window.z_orig_max = matrix_orig.max()
            else:
                self.main_window.z_orig_min = self.main_window.z_min
                self.main_window.z_orig_max = self.main_window.z_max

            # Axis Tags logic
            axis_x_addr = str(row.get('Axis_X_Addr', '')).strip().upper()
            x_tag = " ".join(self.main_window.data_manager.tags.get(axis_x_addr, {}).get("tags", [])) if axis_x_addr and axis_x_addr not in ('0', '0X0', '00000000') else ""
            self.main_window.x_label_str = f"X Axis [{x_tag}]" if x_tag else "X Axis"

            if (current_type == '3d' or (current_type == 'tags' and self.main_window.hex_plot_mode == '3d')):
                axis_y_addr = str(row.get('Axis_Y_Addr', '')).strip().upper()
                y_tag = " ".join(self.main_window.data_manager.tags.get(axis_y_addr, {}).get("tags", [])) if axis_y_addr and axis_y_addr not in ('0', '0X0', '00000000') else ""
                self.main_window.y_label_str = f"Y Axis [{y_tag}]" if y_tag else "Y Axis"
            else:
                self.main_window.y_label_str = "Y Axis"

            map_addr_col = 'Map_Z_Addr' if (current_type == '3d' or (current_type == 'tags' and self.main_window.hex_plot_mode == '3d')) else 'Curve_Data_Addr'
            m_addr = str(row.get(map_addr_col, '0')).strip().upper()
            m_tag = " ".join(self.main_window.data_manager.tags.get(m_addr, {}).get("tags", []))
            self.main_window.z_label_3d_str = f"Z Data [{m_tag}]" if m_tag else "Z Data"
            self.main_window.z_label_2d_str = f"Curve Data [{m_tag}]" if m_tag else "Curve Data"

            # Added a check to see if we have switched between 3D and 2D
            needs_3d = (current_type == '3d' or (current_type == 'tags' and self.main_window.hex_plot_mode == '3d'))
            dim_changed = getattr(self.main_window, '_last_dim_3d', None) != needs_3d

            # Recalculate limits if the map orientation OR the plot dimensionality changes
            if self.main_window.data_manager.current_map_addr != map_addr or dim_changed:
                self.main_window.data_manager.current_map_addr = map_addr
                self.main_window._last_dim_3d = needs_3d
                
                self.main_window.abs_center_x = (size_x - 1) / 2.0
                self.main_window.abs_center_y = (size_y - 1) / 2.0
                self.main_window.center_x = self.main_window.abs_center_x
                self.main_window.center_y = self.main_window.abs_center_y
                self.main_window.cam_zoom = 1.0 
                
                x_margin = (axis_x.max() - axis_x.min()) * 0.05
                if x_margin == 0: x_margin = 1.0
                y_margin = (matrix_z.max() - matrix_z.min()) * 0.05
                if y_margin == 0: y_margin = 1.0
                
                self.main_window.abs_xlim = (axis_x.min() - x_margin, axis_x.max() + x_margin)
                self.main_window.abs_ylim = (matrix_z.min() - y_margin, matrix_z.max() + y_margin)
                self.main_window.center_x_2d = (self.main_window.abs_xlim[0] + self.main_window.abs_xlim[1]) / 2.0
                self.main_window.center_y_2d = (self.main_window.abs_ylim[0] + self.main_window.abs_ylim[1]) / 2.0
                self.main_window.cam_zoom_2d = 1.0 
                
                x_margin = (axis_x.max() - axis_x.min()) * 0.05
                if x_margin == 0: x_margin = 1.0
                y_margin = (matrix_z.max() - matrix_z.min()) * 0.05
                if y_margin == 0: y_margin = 1.0
                
                self.main_window.abs_xlim = (axis_x.min() - x_margin, axis_x.max() + x_margin)
                self.main_window.abs_ylim = (matrix_z.min() - y_margin, matrix_z.max() + y_margin)
                self.main_window.center_x_2d = (self.main_window.abs_xlim[0] + self.main_window.abs_xlim[1]) / 2.0
                self.main_window.center_y_2d = (self.main_window.abs_ylim[0] + self.main_window.abs_ylim[1]) / 2.0
                self.main_window.cam_zoom_2d = 1.0
            
            title = f"Map {self.main_window.data_manager.current_index + 1}/{self.main_window.data_manager.total_maps} | Addr: {map_addr} | Z: {current_fmt} | Factor: {current_factor}"
            self.main_window.lbl_title.setText(title)

            if self.main_window.btn_main_mode.text() == "Mode: Hex Dump":
                self.main_window.update_hex_view(auto_scroll=auto_scroll)
                self.main_window.update_hex_plot()
            else:
                if self.main_window.view_mode in ('plot', 'split'):
                    is_pg = (self.main_window.render_engine == 'pyqtgraph')
                    self.main_window.canvas.setVisible(not is_pg)
                    self.main_window.pg_canvas.setVisible(is_pg)

                    if is_pg:
                        if (current_type == '3d' or (current_type == 'tags' and self.main_window.hex_plot_mode == '3d')):
                            x_grid = np.arange(size_x)
                            y_grid = np.arange(size_y)
                            self.main_window.pg_canvas.draw_3d(x_grid, y_grid, matrix_z, clean_axis_x, clean_axis_y)
                        else:
                            self.main_window.pg_canvas.draw_2d(axis_x, matrix_z)
                    else:
                        self.main_window.ax.clear()
                        if hasattr(self.main_window, 'ax2'):
                            self.main_window.ax2.clear()

                        if (current_type == '3d' or (current_type == 'tags' and self.main_window.hex_plot_mode == '3d')):
                            x_grid = np.arange(size_x)
                            y_grid = np.arange(size_y)
                            X, Y = np.meshgrid(x_grid, y_grid)

                            self.main_window.x_flat = X.flatten()
                            self.main_window.y_flat = Y.flatten()
                            self.main_window.z_flat = matrix_z.flatten()
                            self.main_window.raw_flat = raw_matrix.flatten()

                            self.main_window.ax.plot_surface(X, Y, matrix_z, cmap='jet', edgecolor='k', linewidth=0.3, alpha=0.9)
                            self.main_window.cursor_marker, = self.main_window.ax.plot([0], [0], [0], marker='o', color='red', markersize=8, zorder=10)
                            self.main_window.cursor_marker.set_visible(False)

                            if hasattr(self.main_window, 'ax2') and cmp_idx in (5, 6, 8) and matrix_orig is not None:
                                self.main_window.ax.set_title("Modified Map", fontsize=10, pad=0)
                                if cmp_idx in (5, 6):
                                    self.main_window.ax2.set_title("Original" if cmp_idx == 5 else "Reference Map", fontsize=10, pad=0)
                                else:
                                    self.main_window.ax2.set_title("External Bin", fontsize=10, pad=0)

                                if cmp_idx == 6 and hasattr(self.main_window, "reference_matrix"):
                                    orig_x_grid = np.arange(self.main_window.reference_size_x)
                                    orig_y_grid = np.arange(self.main_window.reference_size_y)
                                    X_orig, Y_orig = np.meshgrid(orig_x_grid, orig_y_grid)
                                    orig_clean_axis_x = [str(round(v, 2)).rstrip('0').rstrip('.') for v in self.main_window.reference_axis_x]
                                    orig_clean_axis_y = [str(round(v, 2)).rstrip('0').rstrip('.') for v in self.main_window.reference_axis_y]
                                else:
                                    orig_x_grid, orig_y_grid = x_grid, y_grid
                                    X_orig, Y_orig = X, Y
                                    orig_clean_axis_x, orig_clean_axis_y = clean_axis_x, clean_axis_y

                                self.main_window.ax2.plot_surface(X_orig, Y_orig, matrix_orig, cmap='coolwarm', edgecolor='white', linewidth=0.3, alpha=0.9)
                                self.main_window.ax2.set_xticks(orig_x_grid)
                                self.main_window.ax2.set_xticklabels(orig_clean_axis_x, rotation=45, ha='right', fontsize=8)
                                self.main_window.ax2.set_yticks(orig_y_grid)
                                self.main_window.ax2.set_yticklabels(orig_clean_axis_y, fontsize=8)
                                self.main_window.ax2.set_xlabel('\n' + self.main_window.x_label_str, labelpad=12)
                                self.main_window.ax2.set_ylabel('\n' + self.main_window.y_label_str, labelpad=12)
                                self.main_window.ax2.set_zlabel(self.main_window.z_label_3d_str, labelpad=12)
                                self.main_window.ax2.invert_yaxis()
                                try: self.main_window.ax2.set_box_aspect((2.5, 2.0, 0.6))
                                except: pass
                                self.main_window.ax2.view_init(elev=self.main_window.start_elev, azim=self.main_window.start_azim)

                            self.main_window.ax.set_xticks(x_grid)
                            self.main_window.ax.set_xticklabels(clean_axis_x, rotation=45, ha='right', fontsize=8)
                            self.main_window.ax.set_yticks(y_grid)
                            self.main_window.ax.set_yticklabels(clean_axis_y, fontsize=8)

                            self.main_window.ax.set_xlabel('\n' + self.main_window.x_label_str, labelpad=12)
                            self.main_window.ax.set_ylabel('\n' + self.main_window.y_label_str, labelpad=12)
                            self.main_window.ax.set_zlabel(self.main_window.z_label_3d_str, labelpad=12)

                            self.main_window.ax.invert_yaxis()
                            try: self.main_window.ax.set_box_aspect((2.5, 2.0, 0.6))
                            except: pass

                            self.main_window.ax.view_init(elev=self.main_window.start_elev, azim=self.main_window.start_azim)
                            self.main_window.apply_3d_zoom()

                        elif (current_type == '2d' or (current_type == 'tags' and self.main_window.hex_plot_mode == '2d')):
                            self.main_window.x_flat = axis_x
                            self.main_window.z_flat = matrix_z
                            self.main_window.raw_flat = raw_matrix

                            if cmp_idx in (5, 6, 8) and matrix_orig is not None:
                                if cmp_idx == 6 and hasattr(self.main_window, "reference_matrix"):
                                    orig_ax = self.main_window.reference_axis_x
                                else:
                                    orig_ax = axis_x
                                lbl = 'Original' if cmp_idx in (5, 2, 3) else 'Ext. Bin' if cmp_idx in (7, 8) else 'Reference Map'
                                self.main_window.ax.plot(orig_ax, matrix_orig, marker='s', color='#888888', linestyle='--', linewidth=1.5, markersize=4, label=lbl)
                                self.main_window.ax.plot(axis_x, matrix_z, marker='o', color='b', linewidth=2, markersize=5, label='Modified')
                                self.main_window.ax.legend(loc='best')
                            else:
                                self.main_window.ax.plot(axis_x, matrix_z, marker='o', color='b', linewidth=2, markersize=5)
                            
                            self.main_window.cursor_marker, = self.main_window.ax.plot([], [], marker='o', color='red', markersize=8, zorder=10)
                            self.main_window.cursor_marker.set_visible(False)

                            self.main_window.ax.set_xlabel(self.main_window.x_label_str)
                            self.main_window.ax.set_ylabel(self.main_window.z_label_2d_str)
                            self.main_window.ax.grid(True, linestyle='--', alpha=0.7)
                            self.main_window.apply_2d_zoom()

                        self.main_window.canvas.draw_idle()

            if self.main_window.view_mode in ('table', 'split'):
                self.main_window.is_updating_table = True
                self.main_window.table.clear()
                self.main_window.table.setRowCount(size_y)
                if cmp_idx in (5, 6, 8) and matrix_orig is not None:
                    if cmp_idx == 6 and hasattr(self.main_window, "reference_matrix"):
                        orig_sz_y = self.main_window.reference_size_y
                        orig_sz_x = self.main_window.reference_size_x
                        orig_cx = [str(round(v, 2)).rstrip('0').rstrip('.') for v in self.main_window.reference_axis_x]
                        orig_cy = [str(round(v, 2)).rstrip('0').rstrip('.') for v in self.main_window.reference_axis_y]
                    else:
                        orig_sz_y, orig_sz_x = size_y, size_x
                        orig_cx, orig_cy = clean_axis_x, clean_axis_y

                    self.main_window.table_orig.setVisible(True)
                    self.main_window.table_orig.clear()
                    self.main_window.table_orig.setRowCount(orig_sz_y)
                    self.main_window.table_orig.setColumnCount(orig_sz_x)
                    self.main_window.table_orig.setHorizontalHeaderLabels(orig_cx)
                    if (current_type == '3d' or (current_type == 'tags' and self.main_window.hex_plot_mode == '3d')):
                        self.main_window.table_orig.setVerticalHeaderLabels(orig_cy)
                    else:
                        self.main_window.table_orig.setVerticalHeaderLabels(["Curve Data"])
                else:
                    self.main_window.table_orig.setVisible(False)

                # Sum +1 for the Sparkline column
                self.main_window.table.setColumnCount(size_x + 1)
                headers = clean_axis_x + ["Profile"]
                self.main_window.table.setHorizontalHeaderLabels(headers)

                # Calculate the global min and max for proper scaling of green bars
                raw_min = raw_matrix.min()
                raw_max = raw_matrix.max()

                f_char = current_fmt[-1].lower()
                if f_char == 'f': bpv = 4
                elif f_char == 'h': bpv = 2
                elif f_char in ('i', 'l'): bpv = 4
                else: bpv = 1
                base_addr = int(map_addr, 16)

                if (current_type == '3d' or (current_type == 'tags' and self.main_window.hex_plot_mode == '3d')):
                    self.main_window.table.setVerticalHeaderLabels(clean_axis_y)
                    for i in range(size_y):
                        for j in range(size_x):
                            if self.main_window.display_hex:
                                v = matrix_z[i, j] if self.main_window.apply_factor_to_hex else raw_matrix[i, j]
                                val_str = self.main_window.data_manager.val_to_hex(v, current_fmt[-1], current_fmt[0])
                            else:
                                val_str = f"{matrix_z[i, j]:.2f}"

                            item = QTableWidgetItem(val_str)
                            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                            if getattr(self.main_window.data_manager, 'show_modified', True) and self.main_window.data_manager._modified_bin_data:
                                cell_addr = base_addr + (i * size_x + j) * bpv
                                if self.main_window.data_manager._bin_data_cache[cell_addr:cell_addr+bpv] != self.main_window.data_manager._modified_bin_data[cell_addr:cell_addr+bpv]:
                                    item.setForeground(QColor(255, 0, 0))
                            if current_type != 'tags' and not (cmp_index and cmp_index.currentIndex() > 1):
                                item.setData(Qt.ItemDataRole.UserRole, {
                                    "address": base_addr + (i * size_x + j) * bpv,
                                    "fmt_char": current_fmt[-1],
                                    "endian": current_fmt[0],
                                    "factor": current_factor,
                                    "offset": current_offset,
                                    "apply_factor_to_hex": self.main_window.apply_factor_to_hex,
                                    "display_hex": self.main_window.display_hex
                                })
                            else:
                                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)

                            self.main_window.table.setItem(i, j, item)

                        # Insert Sparkline
                        spark = SparklineWidget(raw_matrix[i, :], raw_min, raw_max, self.main_window.sparkline_style)
                        self.main_window.table.setCellWidget(i, size_x, spark)

                else:
                    self.main_window.table.setVerticalHeaderLabels(["Curve Data"])
                    for j in range(size_x):
                        if self.main_window.display_hex:
                            v = matrix_z[j] if self.main_window.apply_factor_to_hex else raw_matrix[j]
                            val_str = self.main_window.data_manager.val_to_hex(v, current_fmt[-1], current_fmt[0])
                        else:
                            val_str = f"{matrix_z[j]:.2f}"

                        item = QTableWidgetItem(val_str)
                        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                        if getattr(self.main_window.data_manager, 'show_modified', True) and self.main_window.data_manager._modified_bin_data:
                            cell_addr = base_addr + (j) * bpv
                            if self.main_window.data_manager._bin_data_cache[cell_addr:cell_addr+bpv] != self.main_window.data_manager._modified_bin_data[cell_addr:cell_addr+bpv]:
                                item.setForeground(QColor(255, 0, 0))

                        if current_type != 'tags' and not (cmp_index and cmp_index.currentIndex() > 1):
                            item.setData(Qt.ItemDataRole.UserRole, {
                                "address": base_addr + (j) * bpv,
                                "fmt_char": current_fmt[-1],
                                "endian": current_fmt[0],
                                "factor": current_factor,
                                "offset": current_offset,
                                "apply_factor_to_hex": self.main_window.apply_factor_to_hex,
                                "display_hex": self.main_window.display_hex
                            })
                        else:
                            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)

                        self.main_window.table.setItem(0, j, item)

                    # Insert Sparkline 2D
                    spark = SparklineWidget(raw_matrix, raw_min, raw_max, self.main_window.sparkline_style)
                    self.main_window.table.setCellWidget(0, size_x, spark)
                if cmp_idx in (5, 6, 8) and matrix_orig is not None:
                    is_3d = (current_type == '3d' or (current_type == 'tags' and self.main_window.hex_plot_mode == '3d'))
                    if cmp_idx == 6 and hasattr(self.main_window, "reference_matrix"):
                        orig_sz_y = self.main_window.reference_size_y
                        orig_sz_x = self.main_window.reference_size_x
                    else:
                        orig_sz_y, orig_sz_x = size_y, size_x
                    
                    if is_3d:
                        for i in range(orig_sz_y):
                            for j in range(orig_sz_x):
                                if self.main_window.display_hex:
                                    vo = int(matrix_orig[i, j])
                                    vo_str = self.main_window.data_manager.val_to_hex(vo, current_fmt[-1], current_fmt[0])
                                else:
                                    vo_str = f"{matrix_orig[i, j]:.2f}"
                                item_orig = QTableWidgetItem(vo_str)
                                item_orig.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                                item_orig.setFlags(item_orig.flags() & ~Qt.ItemFlag.ItemIsEditable)
                                item_orig.setForeground(QColor(80, 80, 80))
                                self.main_window.table_orig.setItem(i, j, item_orig)
                    else:
                        for j in range(orig_sz_x):
                            if self.main_window.display_hex:
                                vo = matrix_orig[j]
                                vo_str = self.main_window.data_manager.val_to_hex(vo, current_fmt[-1], current_fmt[0])
                            else:
                                vo_str = f"{matrix_orig[j]:.2f}"
                            item_orig = QTableWidgetItem(vo_str)
                            item_orig.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                            item_orig.setFlags(item_orig.flags() & ~Qt.ItemFlag.ItemIsEditable)
                            item_orig.setForeground(QColor(80, 80, 80))
                            self.main_window.table_orig.setItem(0, j, item_orig)





                self.main_window.table.resizeColumnsToContents()
                self.main_window.table.setColumnWidth(size_x, 150)
                if cmp_idx in (5, 6, 8) and matrix_orig is not None:
                    self.main_window.table_orig.resizeColumnsToContents()
                self.main_window.is_updating_table = False

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.main_window.is_updating_table = False
            if self.main_window.view_mode in ('plot', 'split'):
                self.main_window.ax.clear()
                if hasattr(self.main_window.ax, 'text2D'):
                    self.main_window.ax.text2D(0.5, 0.5, f"Error:\n{str(e)}", transform=self.main_window.ax.transAxes, ha='center', color='red')
                else:
                    self.main_window.ax.text(0.5, 0.5, f"Error:\n{str(e)}", transform=self.main_window.ax.transAxes, ha='center', color='red')
                self.main_window.canvas.draw_idle()
            if self.main_window.view_mode in ('table', 'split'):
                self.main_window.table.clear()

