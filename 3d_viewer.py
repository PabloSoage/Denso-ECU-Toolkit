import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import struct
import sys
import tkinter as tk
from tkinter import ttk, messagebox
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from mpl_toolkits.mplot3d import proj3d

# ================= CONFIGURATION =================
CSV_FILE = "3d_maps_review.csv"
ORI_FILE = "115_e3a4d17c28.bin"       
# =================================================

class DensoViewerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Denso Map Viewer 3D")
        self.root.geometry("1400x850")
        
        # --- Protocolo de cierre seguro ---
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # --- Data State Variables ---
        self.df = pd.DataFrame()
        self.current_index = 0
        self.total_maps = 0
        self.factor_z = tk.DoubleVar(value=0.0025)
        self.offset_z = tk.DoubleVar(value=0.0)
        self.z_format = tk.StringVar(value='>H')
        self.ax_format = tk.StringVar(value='f')
        self.rot_mode = tk.StringVar(value='Z') 
        self.view_mode = '3d'
        
        # --- Mouse Tracking & Zoom Variables ---
        self.dragging = False
        self.mouse_x = 0
        self.mouse_y = 0
        self.start_elev = 35
        self.start_azim = 135
        self.cam_dist = 10.0 
        
        # Internal map data for hover tracking
        self.real_axis_x = []
        self.real_axis_y = []
        self.x_flat = []
        self.y_flat = []
        self.z_flat = []
        
        self.load_data()
        self.build_ui()
        self.draw_map()

    def on_closing(self):
        """Cierra todos los hilos y libera la terminal"""
        plt.close('all')
        self.root.quit()
        self.root.destroy()
        sys.exit()

    def load_data(self):
        try:
            self.df = pd.read_csv(CSV_FILE, dtype=str)
            self.total_maps = len(self.df)
        except Exception as e:
            messagebox.showerror("Error", f"Could not read CSV:\n{e}")
            sys.exit()

    def build_ui(self):
        # MAIN LAYOUT
        self.left_panel = tk.Frame(self.root, width=250, bg="#f0f0f0", padx=10, pady=10)
        self.left_panel.pack(side=tk.LEFT, fill=tk.Y)
        
        self.right_panel = tk.Frame(self.root)
        self.right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # --- LEFT PANEL (Search & List) ---
        tk.Label(self.left_panel, text="Search Map Address:", bg="#f0f0f0", font=("Arial", 10, "bold")).pack(anchor=tk.W)
        self.search_var = tk.StringVar()
        self.search_var.trace("w", self.update_list)
        self.search_entry = tk.Entry(self.left_panel, textvariable=self.search_var, font=("Arial", 11))
        self.search_entry.pack(fill=tk.X, pady=(0, 10))
        
        list_frame = tk.Frame(self.left_panel)
        list_frame.pack(fill=tk.BOTH, expand=True)
        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.map_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, font=("Consolas", 10))
        self.map_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.map_listbox.yview)
        
        self.map_listbox.bind("<<ListboxSelect>>", self.on_list_select)
        self.filtered_indices = []
        self.update_list() 
        
        # --- RIGHT PANEL (Toolbar) ---
        self.toolbar = tk.Frame(self.right_panel, bg="#e0e0e0", pady=5, padx=10)
        self.toolbar.pack(side=tk.TOP, fill=tk.X)
        
        tk.Button(self.toolbar, text="<- Prev Map", command=self.prev_map, width=12).pack(side=tk.LEFT, padx=5)
        tk.Button(self.toolbar, text="Next Map ->", command=self.next_map, width=12).pack(side=tk.LEFT, padx=5)
        tk.Button(self.toolbar, text="⚙ Settings", command=self.open_settings, bg="#d9edf7").pack(side=tk.RIGHT, padx=5)
        tk.Button(self.toolbar, text="Toggle 3D / Table", command=self.toggle_view, bg="#dff0d8").pack(side=tk.RIGHT, padx=5)
        
        self.lbl_title = tk.Label(self.toolbar, text="Map Info", bg="#e0e0e0", font=("Arial", 12, "bold"))
        self.lbl_title.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # --- CONTENT AREA (Canvas & Table) ---
        self.content_frame = tk.Frame(self.right_panel)
        self.content_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        self.fig = plt.figure(figsize=(8, 6))
        self.fig.subplots_adjust(left=0.01, right=0.99, bottom=0.05, top=0.95)
        self.ax3d = self.fig.add_subplot(111, projection='3d')
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.content_frame)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.pack(fill=tk.BOTH, expand=True)
        
        # Custom Interaction Bindings
        self.ax3d.set_navigate(False) 
        self.canvas.mpl_connect('button_press_event', self.on_mouse_press)
        self.canvas.mpl_connect('button_release_event', self.on_mouse_release)
        self.canvas.mpl_connect('motion_notify_event', self.on_mouse_move)
        self.canvas.mpl_connect('scroll_event', self.on_scroll)
        
        # --- BOTTOM STATUS BAR (Coordinates) ---
        self.status_bar = tk.Frame(self.right_panel, bg="#333", pady=5)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        self.lbl_coords = tk.Label(self.status_bar, text="Hover over the graph to see values...", fg="white", bg="#333", font=("Arial", 12, "bold"))
        self.lbl_coords.pack()
        
        # --- TABLE VIEW ---
        self.tree_frame = tk.Frame(self.content_frame)
        self.tree_scroll_y = tk.Scrollbar(self.tree_frame)
        self.tree_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree_scroll_x = tk.Scrollbar(self.tree_frame, orient=tk.HORIZONTAL)
        self.tree_scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.tree = ttk.Treeview(self.tree_frame, yscrollcommand=self.tree_scroll_y.set, xscrollcommand=self.tree_scroll_x.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.tree_scroll_y.config(command=self.tree.yview)
        self.tree_scroll_x.config(command=self.tree.xview)

    # --- UI LOGIC ---
    def update_list(self, *args):
        search_term = self.search_var.get().lower()
        self.map_listbox.delete(0, tk.END)
        self.filtered_indices = []
        
        for idx, row in self.df.iterrows():
            addr = str(row['Map_Z_Addr']).strip()
            if search_term in addr.lower():
                self.map_listbox.insert(tk.END, f"Map {idx+1}: {addr}")
                self.filtered_indices.append(idx)

    def on_list_select(self, event):
        selection = self.map_listbox.curselection()
        if selection:
            visual_idx = selection[0]
            self.current_index = self.filtered_indices[visual_idx]
            self.draw_map()

    def prev_map(self):
        if self.current_index > 0:
            self.current_index -= 1
            self.sync_listbox_selection()
            self.draw_map()

    def next_map(self):
        if self.current_index < self.total_maps - 1:
            self.current_index += 1
            self.sync_listbox_selection()
            self.draw_map()
            
    def sync_listbox_selection(self):
        if self.current_index in self.filtered_indices:
            vis_idx = self.filtered_indices.index(self.current_index)
            self.map_listbox.selection_clear(0, tk.END)
            self.map_listbox.selection_set(vis_idx)
            self.map_listbox.see(vis_idx)

    def toggle_view(self):
        if self.view_mode == '3d':
            self.view_mode = 'table'
            self.canvas_widget.pack_forget()
            self.status_bar.pack_forget()
            self.tree_frame.pack(fill=tk.BOTH, expand=True)
        else:
            self.view_mode = '3d'
            self.tree_frame.pack_forget()
            self.canvas_widget.pack(fill=tk.BOTH, expand=True)
            self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        self.draw_map()

    def open_settings(self):
        sett_win = tk.Toplevel(self.root)
        sett_win.title("Configuration")
        sett_win.geometry("380x420")
        sett_win.attributes('-topmost', True)
        
        lf_z = tk.LabelFrame(sett_win, text="Z Data Format", padx=10, pady=5)
        lf_z.pack(fill=tk.X, padx=10, pady=5)
        tk.Radiobutton(lf_z, text="16-bit Big Endian (>H)", variable=self.z_format, value='>H').pack(anchor=tk.W)
        tk.Radiobutton(lf_z, text="16-bit Little Endian (<H)", variable=self.z_format, value='<H').pack(anchor=tk.W)
        tk.Radiobutton(lf_z, text="8-bit Unsigned (>B)", variable=self.z_format, value='>B').pack(anchor=tk.W)
        
        lf_a = tk.LabelFrame(sett_win, text="Axis X/Y Format", padx=10, pady=5)
        lf_a.pack(fill=tk.X, padx=10, pady=5)
        tk.Radiobutton(lf_a, text="32-bit Float (f)", variable=self.ax_format, value='f').pack(anchor=tk.W)
        tk.Radiobutton(lf_a, text="16-bit Int (H)", variable=self.ax_format, value='H').pack(anchor=tk.W)
        
        lf_m = tk.LabelFrame(sett_win, text="Math", padx=10, pady=5)
        lf_m.pack(fill=tk.X, padx=10, pady=5)
        tk.Label(lf_m, text="Factor Z:").grid(row=0, column=0, sticky=tk.W)
        tk.Entry(lf_m, textvariable=self.factor_z, width=15).grid(row=0, column=1, padx=5)
        tk.Label(lf_m, text="Offset Z:").grid(row=1, column=0, sticky=tk.W, pady=5)
        tk.Entry(lf_m, textvariable=self.offset_z, width=15).grid(row=1, column=1, padx=5)
        
        lf_r = tk.LabelFrame(sett_win, text="Mouse Rotation Mode", padx=10, pady=5)
        lf_r.pack(fill=tk.X, padx=10, pady=5)
        tk.Radiobutton(lf_r, text="Z-Axis Only (Azimuth)", variable=self.rot_mode, value='Z').pack(anchor=tk.W)
        tk.Radiobutton(lf_r, text="WinOLS Style (Azimuth & Tilt)", variable=self.rot_mode, value='WinOLS').pack(anchor=tk.W)
        tk.Radiobutton(lf_r, text="Tilt Only (Elevation)", variable=self.rot_mode, value='Tilt').pack(anchor=tk.W)
        
        tk.Button(sett_win, text="Apply & Redraw", command=self.draw_map, bg="#5cb85c", fg="white", font=("Arial", 10, "bold")).pack(pady=10)

    # --- CUSTOM MOUSE INTERACTION (ZOOM & HOVER) ---
    def on_scroll(self, event):
        """Zoom robusto sin bloqueos de ejes."""
        if event.button == 'up':
            zoom_factor = 1.15  # Acercar
        elif event.button == 'down':
            zoom_factor = 0.85  # Alejar
        else:
            return

        try:
            # Modern Matplotlib (3.6+)
            current_zoom = self.ax3d.get_zoom()
            self.ax3d.set_zoom(current_zoom * zoom_factor)
        except AttributeError:
            # Older Matplotlib
            self.cam_dist /= zoom_factor
            self.ax3d.dist = max(1.0, min(self.cam_dist, 50.0))
            
        self.canvas.draw_idle()

    def on_mouse_press(self, event):
        if event.button != 1: return
        self.dragging = True
        self.mouse_x = event.x
        self.mouse_y = event.y
        self.start_elev = self.ax3d.elev
        self.start_azim = self.ax3d.azim

    def on_mouse_release(self, event):
        self.dragging = False

    def on_mouse_move(self, event):
        # 1. Rotación si arrastramos el ratón (incluso fuera del area de dibujo del eje 3d)
        if self.dragging:
            # Nos aseguramos de que el evento x/y no sea None
            if event.x is None or event.y is None: return
            
            dx = event.x - self.mouse_x
            dy = event.y - self.mouse_y
            sens = 0.4
            mode = self.rot_mode.get()
            
            if mode == 'WinOLS':
                new_elev = self.start_elev - (dy * sens) 
                new_azim = self.start_azim - (dx * sens)
                new_elev = max(-90, min(90, new_elev))
                self.ax3d.view_init(elev=new_elev, azim=new_azim)
            elif mode == 'Z':
                new_azim = self.start_azim - (dx * sens)
                self.ax3d.view_init(elev=self.start_elev, azim=new_azim)
            elif mode == 'Tilt':
                new_elev = self.start_elev - (dy * sens)
                new_elev = max(-90, min(90, new_elev))
                self.ax3d.view_init(elev=new_elev, azim=self.start_azim)
                
            self.canvas.draw_idle()
            return
            
        # 2. Tracking de coordenadas (Bolita roja)
        if event.inaxes != self.ax3d or self.dragging or len(self.z_flat) == 0:
            if hasattr(self, 'cursor_marker') and self.cursor_marker.get_visible():
                self.cursor_marker.set_visible(False)
                self.lbl_coords.config(text="Hover over the graph to see values...")
                self.canvas.draw_idle()
            return

        try:
            xs, ys, _ = proj3d.proj_transform(self.x_flat, self.y_flat, self.z_flat, self.ax3d.get_proj())
            points2d = self.ax3d.transData.transform(np.column_stack([xs, ys]))
            
            dists = (points2d[:, 0] - event.x)**2 + (points2d[:, 1] - event.y)**2
            min_idx = np.argmin(dists)
            
            if dists[min_idx] < 600: 
                best_x = self.x_flat[min_idx]
                best_y = self.y_flat[min_idx]
                best_z = self.z_flat[min_idx]
                
                self.cursor_marker.set_data([best_x], [best_y])
                self.cursor_marker.set_3d_properties([best_z])
                self.cursor_marker.set_visible(True)
                
                rx = self.real_axis_x[best_x]
                ry = self.real_axis_y[best_y]
                
                lbl = f"Point: X = {rx:g}   |   Y = {ry:g}   |   Z = {best_z:.2f}"
                self.lbl_coords.config(text=lbl)
                self.canvas.draw_idle()
            else:
                self.cursor_marker.set_visible(False)
                self.lbl_coords.config(text="Hover over the graph to see values...")
                self.canvas.draw_idle()
        except: pass

    # --- DATA READING ---
    def read_axis(self, hex_addr, size, endian, axis_format):
        try:
            addr = int(str(hex_addr).strip(), 16)
            if addr == 0 or addr >= 0xFFFF0000:
                return np.arange(size)
                
            bytes_per_value = 4 if axis_format == 'f' else 2
            with open(ORI_FILE, "rb") as f:
                f.seek(addr)
                raw = f.read(size * bytes_per_value)
                
            return np.array(struct.unpack(f"{endian}{size}{axis_format}", raw))
        except:
            return np.arange(size)

    def read_map(self):
        row = self.df.iloc[self.current_index]
        size_x = int(row['Size_X'])
        size_y = int(row['Size_Y'])
        map_z_hex = str(row['Map_Z_Addr']).strip()
        axis_x_hex = str(row['Axis_X_Addr']).strip()
        axis_y_hex = str(row['Axis_Y_Addr']).strip()
        
        z_fmt = self.z_format.get()
        a_fmt = self.ax_format.get()
        endian = z_fmt[0]
        bytes_per_value = 2 if 'h' in z_fmt.lower() else 1
        
        with open(ORI_FILE, "rb") as f:
            f.seek(int(map_z_hex, 16))
            raw_z_data = f.read(size_y * size_x * bytes_per_value)
            
        z_values = struct.unpack(f"{endian}{size_y * size_x}{z_fmt[-1]}", raw_z_data)
        matrix_z = np.array(z_values).reshape((size_y, size_x))
        
        axis_x = self.read_axis(axis_x_hex, size_x, endian, a_fmt)
        axis_y = self.read_axis(axis_y_hex, size_y, endian, a_fmt)
        
        return matrix_z, axis_x, axis_y, size_y, size_x, map_z_hex

    # --- RENDERING ---
    def draw_map(self):
        try:
            raw_matrix, axis_x, axis_y, size_y, size_x, map_z_hex = self.read_map()
            
            matrix_z = (raw_matrix * self.factor_z.get()) + self.offset_z.get()
            
            clean_axis_x = [str(round(v, 2)).rstrip('0').rstrip('.') for v in axis_x]
            clean_axis_y = [str(round(v, 2)).rstrip('0').rstrip('.') for v in axis_y]
            
            self.real_axis_x = axis_x
            self.real_axis_y = axis_y
            
            title = f"Map {self.current_index + 1}/{self.total_maps} | Addr: {map_z_hex}"
            self.lbl_title.config(text=title)

            if self.view_mode == '3d':
                self.ax3d.clear()
                
                x_grid = np.arange(size_x)
                y_grid = np.arange(size_y)
                X, Y = np.meshgrid(x_grid, y_grid)
                
                self.x_flat = X.flatten()
                self.y_flat = Y.flatten()
                self.z_flat = matrix_z.flatten()
                
                surf = self.ax3d.plot_surface(X, Y, matrix_z, cmap='jet', edgecolor='k', linewidth=0.3, alpha=0.9)
                
                self.cursor_marker, = self.ax3d.plot([0], [0], [0], marker='o', color='red', markersize=8, zorder=10)
                self.cursor_marker.set_visible(False)
                
                self.ax3d.set_xticks(x_grid)
                self.ax3d.set_xticklabels(clean_axis_x, rotation=45, ha='right', fontsize=8)
                self.ax3d.set_yticks(y_grid)
                self.ax3d.set_yticklabels(clean_axis_y, fontsize=8)
                
                self.ax3d.set_xlabel('\nX Axis')
                self.ax3d.set_ylabel('\nY Axis')
                self.ax3d.set_zlabel('Z Data')
                
                self.ax3d.invert_yaxis() 
                try:
                    self.ax3d.set_box_aspect((2.5, 2.0, 0.6))
                except AttributeError:
                    pass
                
                self.ax3d.view_init(elev=self.start_elev, azim=self.start_azim)
                
                # Restaurar el nivel de zoom actual para que no dé un salto brusco
                try:
                    self.ax3d.set_zoom(self.ax3d.get_zoom())
                except AttributeError:
                    self.ax3d.dist = self.cam_dist

                self.canvas.draw_idle()
                
            elif self.view_mode == 'table':
                self.tree.delete(*self.tree.get_children()) 
                self.tree["columns"] = ["Y/X"] + clean_axis_x
                self.tree.heading("Y/X", text="Y \\ X")
                self.tree.column("Y/X", width=60, anchor=tk.CENTER)
                
                for col in clean_axis_x:
                    self.tree.heading(col, text=col)
                    self.tree.column(col, width=60, anchor=tk.CENTER)
                
                for row_idx, row_data in enumerate(matrix_z):
                    y_label = clean_axis_y[row_idx]
                    values = [round(v, 2) for v in row_data]
                    self.tree.insert("", "end", text="", values=[y_label] + values)
                    
        except Exception as e:
            if self.view_mode == '3d':
                self.ax3d.clear()
                self.ax3d.text2D(0.5, 0.5, f"Error:\n{str(e)}", transform=self.ax3d.transAxes, ha='center', color='red')
                self.canvas.draw_idle()

if __name__ == "__main__":
    root = tk.Tk()
    app = DensoViewerApp(root)
    root.mainloop()