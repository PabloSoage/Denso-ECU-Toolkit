import numpy as np
from mpl_toolkits.mplot3d import proj3d

class MouseEventsManager:
    def __init__(self, main_window):
        self.main_window = main_window

    def apply_3d_zoom(self):
        if not hasattr(self.main_window, 'map_size_x'): return
        
        base_x = max(1, self.main_window.map_size_x - 1) * 1.15
        base_y = max(1, self.main_window.map_size_y - 1) * 1.15
        
        x_range = base_x / self.main_window.cam_zoom
        y_range = base_y / self.main_window.cam_zoom
        
        min_c_x = x_range / 2
        max_c_x = (self.main_window.map_size_x - 1) - x_range / 2
        self.main_window.center_x = (self.main_window.map_size_x - 1) / 2.0 if min_c_x > max_c_x else max(min_c_x, min(self.main_window.center_x, max_c_x))
            
        min_c_y = y_range / 2
        max_c_y = (self.main_window.map_size_y - 1) - y_range / 2
        self.main_window.center_y = (self.main_window.map_size_y - 1) / 2.0 if min_c_y > max_c_y else max(min_c_y, min(self.main_window.center_y, max_c_y))
            
        self.main_window.ax.set_xlim(self.main_window.center_x - x_range/2, self.main_window.center_x + x_range/2)
        self.main_window.ax.set_ylim(self.main_window.center_y + y_range/2, self.main_window.center_y - y_range/2)
        
        if self.main_window.z_min == self.main_window.z_max: 
            self.main_window.ax.set_zlim(self.main_window.z_min - 1, self.main_window.z_max + 1)
        else: 
            self.main_window.ax.set_zlim(self.main_window.z_min, self.main_window.z_max)
            
        self.main_window.ax.set_autoscale_on(False)
            
        if hasattr(self.main_window, 'ax2'):
            self.main_window.ax2.set_xlim(self.main_window.center_x - x_range/2, self.main_window.center_x + x_range/2)
            self.main_window.ax2.set_ylim(self.main_window.center_y + y_range/2, self.main_window.center_y - y_range/2)
            
            z_orig_min = getattr(self.main_window, 'z_orig_min', self.main_window.z_min)
            z_orig_max = getattr(self.main_window, 'z_orig_max', self.main_window.z_max)
            
            if z_orig_min == z_orig_max: self.main_window.ax2.set_zlim(z_orig_min - 1, z_orig_max + 1)
            else: self.main_window.ax2.set_zlim(z_orig_min, z_orig_max)
            
            self.main_window.ax2.set_autoscale_on(False)
            
        self.main_window.canvas.draw_idle()

    def apply_2d_zoom(self):
        x_range = (self.main_window.abs_xlim[1] - self.main_window.abs_xlim[0]) / self.main_window.cam_zoom_2d
        y_range = (self.main_window.abs_ylim[1] - self.main_window.abs_ylim[0]) / self.main_window.cam_zoom_2d
        
        min_cx = self.main_window.abs_xlim[0] + x_range/2
        max_cx = self.main_window.abs_xlim[1] - x_range/2
        self.main_window.center_x_2d = max(min_cx, min(self.main_window.center_x_2d, max_cx))
        
        min_cy = self.main_window.abs_ylim[0] + y_range/2
        max_cy = self.main_window.abs_ylim[1] - y_range/2
        self.main_window.center_y_2d = max(min_cy, min(self.main_window.center_y_2d, max_cy))
        
        self.main_window.ax.set_xlim(self.main_window.center_x_2d - x_range/2, self.main_window.center_x_2d + x_range/2)
        self.main_window.ax.set_ylim(self.main_window.center_y_2d - y_range/2, self.main_window.center_y_2d + y_range/2)
        self.main_window.ax.set_autoscale_on(False)
        self.main_window.canvas.draw_idle()

    def on_mouse_press(self, event):
        if event.button == 1: 
            self.main_window.dragging = True
            self.main_window.mouse_x = event.x
            self.main_window.mouse_y = event.y
            
            if getattr(self.main_window.ax, "name", "") == "3d" or getattr(self.main_window.ax, "name", "") == "3d":
                self.main_window.start_elev = self.main_window.ax.elev
                self.main_window.start_azim = self.main_window.ax.azim
            else:
                self.main_window.start_center_x_2d = self.main_window.center_x_2d
                self.main_window.start_center_y_2d = self.main_window.center_y_2d

    def on_mouse_release(self, event):
        self.main_window.dragging = False
        if getattr(self.main_window.ax, "name", "") == "3d" or getattr(self.main_window.ax, "name", "") == "3d":
            self.main_window.start_elev = self.main_window.ax.elev
            self.main_window.start_azim = self.main_window.ax.azim

    def on_mouse_move(self, event):
        if self.main_window.data_manager.df.empty and self.main_window.btn_main_mode.text() != "Mode: Hex Dump": return
        
        if self.main_window.dragging:
            if event.x is None or event.y is None: return
            
            if getattr(self.main_window.ax, "name", "") == "3d" or getattr(self.main_window.ax, "name", "") == "3d":
                dx = event.x - self.main_window.mouse_x
                dy = event.y - self.main_window.mouse_y
                sens = 0.4
                new_elev = self.main_window.start_elev
                new_azim = self.main_window.start_azim
                
                if self.main_window.rot_mode == 'WinOLS':
                    new_elev = max(-90, min(90, self.main_window.start_elev - (dy * sens)))
                    new_azim = self.main_window.start_azim - (dx * sens)
                elif self.main_window.rot_mode == 'Z':
                    new_azim = self.main_window.start_azim - (dx * sens)
                elif self.main_window.rot_mode == 'Tilt':
                    new_elev = max(-90, min(90, self.main_window.start_elev - (dy * sens)))
                    
                self.main_window.ax.view_init(elev=new_elev, azim=new_azim)
                self.main_window._sync_3d_axes()
                self.main_window.canvas.draw_idle()
            
            else:
                dx_pixels = event.x - self.main_window.mouse_x
                dy_pixels = event.y - self.main_window.mouse_y
                
                inv = self.main_window.ax.transData.inverted()
                x0, y0 = inv.transform((0, 0))
                x1, y1 = inv.transform((1, 1))
                
                data_dx_per_pixel = x1 - x0
                data_dy_per_pixel = y1 - y0
                
                self.main_window.center_x_2d = self.main_window.start_center_x_2d - (dx_pixels * data_dx_per_pixel)
                self.main_window.center_y_2d = self.main_window.start_center_y_2d - (dy_pixels * data_dy_per_pixel)
                
                self.apply_2d_zoom()
            return
            
        else:
            self.main_window.mouse_x_data = event.xdata
            self.main_window.mouse_y_data = event.ydata
            
        if getattr(event, 'inaxes', None) != self.main_window.ax or len(self.main_window.z_flat) == 0:
            self.main_window.is_hovering = False
            if hasattr(self.main_window, 'cursor_marker') and self.main_window.cursor_marker.get_visible():
                self.main_window.cursor_marker.set_visible(False)
                self.main_window.status_lbl.setText("Hover over the graph to see values...")
                self.main_window.canvas.draw_idle()
            return

        try:
            is_3d = getattr(self.main_window.ax, 'name', '') == '3d'
            if is_3d:
                xs, ys, _ = proj3d.proj_transform(self.main_window.x_flat, self.main_window.y_flat, self.main_window.z_flat, self.main_window.ax.get_proj())
                points2d = self.main_window.ax.transData.transform(np.column_stack([xs, ys]))
            else:
                points2d = self.main_window.ax.transData.transform(np.column_stack([self.main_window.x_flat, self.main_window.z_flat]))

            dists = (points2d[:, 0] - event.x)**2 + (points2d[:, 1] - event.y)**2
            min_idx = np.argmin(dists)
            
            if dists[min_idx] < 600: 
                self.main_window.is_hovering = True
                
                if (self.main_window.map_mode == '3d' or (self.main_window.map_mode == 'tags' and self.main_window.hex_plot_mode == '3d')) or (self.main_window.btn_main_mode.text() == "Mode: Hex Dump" and self.main_window.hex_plot_mode == '3d'):
                    self.main_window.hover_x = self.main_window.x_flat[min_idx]
                    self.main_window.hover_y = self.main_window.y_flat[min_idx]
                    best_z = self.main_window.z_flat[min_idx]
                    self.main_window.cursor_marker.set_data([self.main_window.hover_x], [self.main_window.hover_y])
                    self.main_window.cursor_marker.set_3d_properties([best_z])
                    rx = self.main_window.real_axis_x[self.main_window.hover_x]
                    ry = self.main_window.real_axis_y[self.main_window.hover_y]
                    
                    if self.main_window.display_hex:
                        v_hex = best_z if self.main_window.apply_factor_to_hex else self.main_window.raw_flat[min_idx]
                        fmt = self.main_window.data_manager.z_format_3d
                        lbl = f"Target: X = {rx:g}   |   Y = {ry:g}   |   Z (HEX) = {self.main_window.data_manager.val_to_hex(v_hex, fmt[-1], fmt[0])}"
                    else:
                        lbl = f"Target: X = {rx:g}   |   Y = {ry:g}   |   Z = {best_z:.2f}"
                else:
                    best_x = self.main_window.x_flat[min_idx]
                    best_z = self.main_window.z_flat[min_idx]
                    self.main_window.cursor_marker.set_data([best_x], [best_z])
                    if self.main_window.display_hex:
                        v_hex = best_z if self.main_window.apply_factor_to_hex else self.main_window.raw_flat[min_idx]
                        fmt = self.main_window.data_manager.z_format_2d
                        lbl = f"Target: X = {best_x:g}   |   Z (HEX) = {self.main_window.data_manager.val_to_hex(v_hex, fmt[-1], fmt[0])}"
                    else:
                        lbl = f"Target: X = {best_x:g}   |   Z (Curve) = {best_z:.2f}"

                self.main_window.cursor_marker.set_visible(True)
                self.main_window.status_lbl.setText(lbl)
                self.main_window.canvas.draw_idle()
            else:
                self.main_window.is_hovering = False
                self.main_window.cursor_marker.set_visible(False)
                self.main_window.status_lbl.setText("Hover over the graph to see values...")
                self.main_window.canvas.draw_idle()
        except: pass
