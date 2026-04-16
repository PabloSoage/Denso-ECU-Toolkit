import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Button, RadioButtons
import struct
import sys

# ================= CONFIGURATION =================
CSV_FILE = "3d_maps_review.csv"
ORI_FILE = "115_e3a4d17c28.bin"       
# =================================================

try:
    # Read CSV ensuring hexadecimal addresses are read as strings
    df = pd.read_csv(CSV_FILE, dtype=str)
except Exception as e:
    print(f"Error reading CSV: {e}")
    sys.exit()

# Global variables for state management
current_index = 0
total_maps = len(df)

# Denso SH7058/7059 processors generally use Big Endian (>). 
# 16-bit Unsigned (>H) is the standard for most Denso maps.
current_dtype = '>H' 

# Set up the matplotlib window
fig = plt.figure(figsize=(12, 8))
fig.canvas.manager.set_window_title('Denso Map Viewer 3D')
ax = fig.add_subplot(111, projection='3d')
plt.subplots_adjust(bottom=0.25, left=0.25) # Leave space for UI buttons

def read_map(index, dtype_str):
    """Opens the binary file, extracts the Z 3D matrix"""
    row = df.iloc[index]
    
    size_x = int(row['Size_X'])
    size_y = int(row['Size_Y'])
    map_z_hex = row['Map_Z_Addr']
    
    offset_z = int(map_z_hex, 16)
    
    # Calculate how many bytes to read per value based on the selected format
    # 'B'/'b' = 1 byte (8-bit), 'H'/'h' = 2 bytes (16-bit)
    bytes_per_value = 2 if 'h' in dtype_str.lower() else 1
    
    with open(ORI_FILE, "rb") as f:
        f.seek(offset_z)
        raw_z_data = f.read(size_y * size_x * bytes_per_value)
        
    # Unpack Z data based on user selection
    z_values = struct.unpack(f">{size_y * size_x}{dtype_str[-1]}", raw_z_data)
    
    # Convert flat tuple to a 2D Numpy array (Rows x Columns)
    matrix_z = np.array(z_values).reshape((size_y, size_x))
    
    return matrix_z, size_y, size_x, map_z_hex

def draw_map(*args):
    """Renders the 3D surface plot to match WinOLS isometric perspective"""
    ax.clear()
    try:
        matrix_z, size_y, size_x, map_z_hex = read_map(current_index, current_dtype)
        
        # We use grid indices (0 to size) to prevent mesh distortion.
        # Reading raw axis headers often results in garbage coordinates.
        x = np.arange(0, size_x, 1)
        y = np.arange(0, size_y, 1)
        X, Y = np.meshgrid(x, y)
        
        # Draw the 3D surface (cmap='jet' matches standard WinOLS thermal colors)
        surf = ax.plot_surface(X, Y, matrix_z, cmap='jet', edgecolor='k', linewidth=0.5, alpha=0.9)
        
        ax.set_title(f"Map {current_index + 1} of {total_maps} | Addr: {map_z_hex} | Size: {size_x}x{size_y} | Format: {current_dtype}", fontsize=12)
        
        # Labels
        ax.set_xlabel('X Axis (Columns)')
        ax.set_ylabel('Y Axis (Rows)')
        ax.set_zlabel('Z Data (Raw)')
        
        # --- WINOLS PERSPECTIVE MATCHING ---
        # Invert the X-axis to match WinOLS column rendering direction
        # ax.invert_xaxis() 
        ax.invert_yaxis() # Invert Y-axis to match WinOLS row rendering direction
        # Set isometric viewing angle similar to WinOLS default
        ax.view_init(elev=35, azim=135) 
        
    except Exception as e:
        ax.text2D(0.5, 0.5, f"Error rendering map:\n{str(e)}", transform=ax.transAxes, ha='center', color='red')

    fig.canvas.draw_idle()

# --- Navigation & Control Functions ---
def next_map(event):
    global current_index
    if current_index < total_maps - 1:
        current_index += 1
        draw_map()

def previous_map(event):
    global current_index
    if current_index > 0:
        current_index -= 1
        draw_map()

def change_dtype(label):
    """Switches the struct unpack format and re-renders"""
    global current_dtype
    if '8-bit' in label: current_dtype = '>B'
    elif '16-bit Unsigned' in label: current_dtype = '>H'
    else: current_dtype = '>h'
    draw_map()

# --- UI Button Placement ---
# Next / Previous Buttons
axprev = plt.axes([0.4, 0.05, 0.15, 0.075])
axnext = plt.axes([0.6, 0.05, 0.15, 0.075])
bnext = Button(axnext, 'Next ->')
bnext.on_clicked(next_map)
bprev = Button(axprev, '<- Previous')
bprev.on_clicked(previous_map)

# Data Type Radio Buttons (Bottom Left)
rax = plt.axes([0.05, 0.05, 0.25, 0.15], facecolor='lightgray')
radio = RadioButtons(rax, ('16-bit Unsigned (>H)', '8-bit Unsigned (>B)', '16-bit Signed (>h)'), active=0)
radio.on_clicked(change_dtype)

# Initial render
draw_map()
plt.show()