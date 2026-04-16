import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Button
import struct
import sys

# ================= CONFIGURATION =================
CSV_FILE = "3d_maps_v0.2.csv"         # Put the name of your 3D CSV file here
ORI_FILE = "115_e3a4d17c28.bin"       # Put the exact name of your original ECU read file here
# =================================================

try:
    # Read CSV ensuring hexadecimal addresses are read as strings
    df = pd.read_csv(CSV_FILE, dtype=str)
except Exception as e:
    print(f"Error reading CSV: {e}")
    sys.exit()

# Global variables for navigation and state
current_index = 0
total_maps = len(df)
is_signed = False
is_16bit = True    # Default to 16-bit, but can be toggled to 8-bit

# Set up the matplotlib window
fig = plt.figure(figsize=(12, 8))
fig.canvas.manager.set_window_title('Denso Map Viewer 3D')
ax = fig.add_subplot(111, projection='3d')
plt.subplots_adjust(bottom=0.2) # Leave space for buttons

def read_map(index, signed, use_16bit):
    """Opens the binary file, reads the bytes and converts them to a 3D matrix"""
    row = df.iloc[index]
    
    size_y = int(row['Size_Y'])
    size_x = int(row['Size_X'])
    map_z_hex = row['Map_Z_Addr']
    
    # Convert hex address to int for file offset
    offset = int(map_z_hex, 16)
    total_points = size_y * size_x
    
    # Calculate how many bytes to read (2 bytes per point for 16-bit, 1 byte for 8-bit)
    bytes_to_read = total_points * 2 if use_16bit else total_points
    
    with open(ORI_FILE, "rb") as f:
        f.seek(offset)
        raw_data = f.read(bytes_to_read)
        
    # Denso SH7058/7059 processors use Big Endian (>)
    if use_16bit:
        format_char = "h" if signed else "H"
    else:
        format_char = "b" if signed else "B"
        
    values = struct.unpack(f">{total_points}{format_char}", raw_data)
    
    # Convert to Numpy matrix (Rows x Columns)
    matrix_z = np.array(values).reshape((size_y, size_x))
    
    return matrix_z, size_y, size_x, map_z_hex

def draw_map(index):
    """Updates the 3D chart onscreen"""
    ax.clear()
    
    try:
        matrix_z, size_y, size_x, map_z_hex = read_map(index, is_signed, is_16bit)
        
        # Create X and Y axis grid
        x = np.arange(0, size_x, 1)
        y = np.arange(0, size_y, 1)
        X, Y = np.meshgrid(x, y)
        
        # Draw the 3D surface
        surf = ax.plot_surface(X, Y, matrix_z, cmap='jet', edgecolor='k', linewidth=0.3, alpha=0.9)
        
        sign_text = "Signed" if is_signed else "Unsigned"
        bit_text = "16-bit" if is_16bit else "8-bit"
        
        ax.set_title(f"Map {index + 1} of {total_maps} | Addr: {map_z_hex} | Size: {size_y}x{size_x} | {bit_text} {sign_text}", fontsize=12)
        ax.set_xlabel('X Axis (Columns)')
        ax.set_ylabel('Y Axis (Rows)')
        ax.set_zlabel('Z Data')
        
    except Exception as e:
        ax.text2D(0.5, 0.5, f"Error reading map at index {index}\nError: {str(e)}", 
                  transform=ax.transAxes, ha='center', color='red')
        print(f"Failed to read map at index {index}: {e}")

    fig.canvas.draw_idle()

# --- Button functions ---
def next_map(event):
    global current_index
    if current_index < total_maps - 1:
        current_index += 1
        draw_map(current_index)

def prev_map(event):
    global current_index
    if current_index > 0:
        current_index -= 1
        draw_map(current_index)

def toggle_sign(event):
    global is_signed
    is_signed = not is_signed
    draw_map(current_index)

def toggle_bit(event):
    global is_16bit
    is_16bit = not is_16bit
    draw_map(current_index)

# --- Create interface buttons ---
axprev = plt.axes([0.15, 0.05, 0.15, 0.075])
axnext = plt.axes([0.35, 0.05, 0.15, 0.075])
axsign = plt.axes([0.55, 0.05, 0.15, 0.075])
axbit  = plt.axes([0.75, 0.05, 0.15, 0.075])

bnext = Button(axnext, 'Next ->')
bnext.on_clicked(next_map)

bprev = Button(axprev, '<- Previous')
bprev.on_clicked(prev_map)

bsign = Button(axsign, 'Toggle Sign')
bsign.on_clicked(toggle_sign)

bbit = Button(axbit, '8-bit / 16-bit')
bbit.on_clicked(toggle_bit)

# Draw first map at startup
draw_map(current_index)
plt.show()