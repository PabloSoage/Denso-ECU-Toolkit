import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Button, RadioButtons, TextBox
import struct
import sys

# ================= CONFIGURATION =================
CSV_FILE = "3d_maps_review.csv"
ORI_FILE = "115_e3a4d17c28.bin"       
# =================================================

try:
    df = pd.read_csv(CSV_FILE, dtype=str)
except Exception as e:
    print(f"Error reading CSV: {e}")
    sys.exit()

# Variables globales
current_index = 0
total_maps = len(df)
current_dtype = '>H'       # Formato Z: 16-bit Big Endian por defecto
current_axis_dtype = 'f'   # Formato Ejes: 'f' = Float32, 'H' = Uint16
current_view = '3d'
factor_z = 1.0
offset_z = 0.0

fig = plt.figure(figsize=(15, 9))
fig.canvas.manager.set_window_title('Denso Map Viewer 3D - Engineer Edition')
ax3d = fig.add_subplot(111, projection='3d')
ax_table = fig.add_axes([0.05, 0.25, 0.9, 0.65])
ax_table.set_visible(False)
ax_table.axis('off')

# Espacio extra inferior para los nuevos botones
plt.subplots_adjust(bottom=0.30, left=0.10, right=0.95) 

def safe_read_axis(addr_hex, size, endian, axis_format):
    """Lee el eje aplicando el formato correcto (16-bit Int o 32-bit Float)"""
    try:
        addr = int(str(addr_hex).strip(), 16)
        if addr == 0 or addr >= 0xFFFF0000:
            return np.arange(size)
            
        bytes_per_value = 4 if axis_format == 'f' else 2
        
        with open(ORI_FILE, "rb") as f:
            f.seek(addr)
            raw = f.read(size * bytes_per_value)
            
        return np.array(struct.unpack(f"{endian}{size}{axis_format}", raw))
    except:
        return np.arange(size)

def read_map(index, dtype_str, axis_format):
    row = df.iloc[index]
    
    size_x = int(row['Size_X'])
    size_y = int(row['Size_Y'])
    map_z_hex = str(row['Map_Z_Addr']).strip()
    axis_x_hex = str(row['Axis_X_Addr']).strip()
    axis_y_hex = str(row['Axis_Y_Addr']).strip()
    
    endian = dtype_str[0]
    bytes_per_value = 2 if 'h' in dtype_str.lower() else 1
    
    # Leer Z (Datos del mapa)
    with open(ORI_FILE, "rb") as f:
        f.seek(int(map_z_hex, 16))
        raw_z_data = f.read(size_y * size_x * bytes_per_value)
        
    z_values = struct.unpack(f"{endian}{size_y * size_x}{dtype_str[-1]}", raw_z_data)
    matrix_z = np.array(z_values).reshape((size_y, size_x))
    
    # Leer X e Y aplicando el formato seleccionado de ejes
    axis_x = safe_read_axis(axis_x_hex, size_x, endian, axis_format)
    axis_y = safe_read_axis(axis_y_hex, size_y, endian, axis_format)
    
    return matrix_z, axis_x, axis_y, size_y, size_x, map_z_hex

def draw_map(*args):
    try:
        raw_matrix, axis_x, axis_y, size_y, size_x, map_z_hex = read_map(current_index, current_dtype, current_axis_dtype)
        
        # Aplicar factor y offset a Z
        matrix_z = (raw_matrix * factor_z) + offset_z
        
        title_text = f"Map {current_index + 1}/{total_maps} | Addr: {map_z_hex} | Z: {current_dtype} | Axis: {'>' if current_dtype=='>H' else '<'}{current_axis_dtype} | Factor: {factor_z}"
        
        # Formatear ejes para quitar decimales feos (ej. 600.0 -> 600)
        clean_axis_x = [str(round(v, 2)).rstrip('0').rstrip('.') for v in axis_x]
        clean_axis_y = [str(round(v, 2)).rstrip('0').rstrip('.') for v in axis_y]

        if current_view == '3d':
            ax_table.set_visible(False)
            ax3d.set_visible(True)
            ax3d.clear()
            
            x_grid = np.arange(size_x)
            y_grid = np.arange(size_y)
            X, Y = np.meshgrid(x_grid, y_grid)
            
            surf = ax3d.plot_surface(X, Y, matrix_z, cmap='jet', edgecolor='k', linewidth=0.3, alpha=0.9)
            
            # Aplicar etiquetas reales a la malla uniforme
            ax3d.set_xticks(x_grid)
            ax3d.set_xticklabels(clean_axis_x, rotation=45, ha='right', fontsize=8)
            ax3d.set_yticks(y_grid)
            ax3d.set_yticklabels(clean_axis_y, fontsize=8)
            
            ax3d.set_title(title_text, fontsize=12, fontweight='bold')
            ax3d.set_xlabel('\n\nX Axis (RPM)')
            ax3d.set_ylabel('\n\nY Axis (Load)')
            ax3d.set_zlabel('Z Data')
            
            # Perspectiva WinOLS
            ax3d.invert_yaxis() 
            try:
                ax3d.set_box_aspect((2.5, 2.0, 0.6))
            except AttributeError:
                pass
            ax3d.view_init(elev=35, azim=135)
            
        elif current_view == 'table':
            ax3d.set_visible(False)
            ax_table.set_visible(True)
            ax_table.clear()
            ax_table.axis('off')
            ax_table.set_title(title_text + " (DATA VIEW)", fontsize=12, pad=10, fontweight='bold')
            
            display_matrix = np.round(matrix_z, 2)
            
            table = ax_table.table(cellText=display_matrix, 
                                   rowLabels=clean_axis_y,
                                   colLabels=clean_axis_x,
                                   loc='center', cellLoc='center')
            table.auto_set_font_size(False)
            table.set_fontsize(8)
            table.scale(1, 1.2)
            
            print(f"\n--- MAP {current_index + 1} ({map_z_hex}) ---")
            print(pd.DataFrame(display_matrix, index=clean_axis_y, columns=clean_axis_x).to_string())
            
    except Exception as e:
        if current_view == '3d':
            ax3d.text2D(0.5, 0.5, f"Error rendering map:\n{str(e)}", transform=ax3d.transAxes, ha='center', color='red')
        else:
            ax_table.text(0.5, 0.5, f"Error rendering table:\n{str(e)}", ha='center', color='red')

    fig.canvas.draw_idle()

# --- Callbacks ---
def next_map(event):
    global current_index; 
    if current_index < total_maps - 1: current_index += 1; draw_map()

def previous_map(event):
    global current_index; 
    if current_index > 0: current_index -= 1; draw_map()

def toggle_view(event):
    global current_view
    current_view = 'table' if current_view == '3d' else '3d'; draw_map()

def change_dtype(label):
    global current_dtype
    if '8-bit' in label: current_dtype = '>B'
    elif '16-bit Unsigned' in label: current_dtype = '>H'
    else: current_dtype = '>h'
    draw_map()

def change_axis_dtype(label):
    global current_axis_dtype
    if '32-bit Float' in label: current_axis_dtype = 'f'
    else: current_axis_dtype = 'H'
    draw_map()

def submit_factor(text):
    global factor_z
    try: factor_z = float(text); draw_map()
    except: pass

def submit_offset(text):
    global offset_z
    try: offset_z = float(text); draw_map()
    except: pass

# --- UI Layout ---
# Selectores Z Data
rax_z = plt.axes([0.02, 0.02, 0.20, 0.12], facecolor='lightgray')
radio_z = RadioButtons(rax_z, ('16-bit Unsigned (>H)', '8-bit Unsigned (>B)', '16-bit Signed (>h)'), active=0)
radio_z.on_clicked(change_dtype)

# Selectores Ejes (Añadido nuevo)
rax_ax = plt.axes([0.23, 0.02, 0.16, 0.09], facecolor='lightblue')
radio_ax = RadioButtons(rax_ax, ('Axis: 32-bit Float (f)', 'Axis: 16-bit Int (H)'), active=0)
radio_ax.on_clicked(change_axis_dtype)

# Botones Navegación
axprev = plt.axes([0.41, 0.04, 0.08, 0.06])
axnext = plt.axes([0.50, 0.04, 0.08, 0.06])
bprev = Button(axprev, '<- Prev')
bnext = Button(axnext, 'Next ->')
bprev.on_clicked(previous_map)
bnext.on_clicked(next_map)

# Toggle 3D/Table
axtoggle = plt.axes([0.60, 0.04, 0.12, 0.06])
btoggle = Button(axtoggle, 'Toggle 3D / Table')
btoggle.on_clicked(toggle_view)

# Factor y Offset Z
axbox_f = plt.axes([0.83, 0.08, 0.1, 0.04])
text_box_f = TextBox(axbox_f, 'Factor Z: ', initial=str(factor_z))
text_box_f.on_submit(submit_factor)

axbox_o = plt.axes([0.83, 0.02, 0.1, 0.04])
text_box_o = TextBox(axbox_o, 'Offset Z: ', initial=str(offset_z))
text_box_o.on_submit(submit_offset)

draw_map()
plt.show()