import os
import struct
import json
import numpy as np
import pandas as pd

class DataManager:
    def __init__(self):
        self.project_path = ""
        self.bin_path = ""
        self.csv_3d_path = ""
        self.csv_2d_path = ""
        
        self.tags = {}  # { hex_address: {"tags": ["Tag1", ...], "length": int} }
        self.df = pd.DataFrame()
        self.bin_data = b""
        
        self.map_array = []
        self.map_dicts_tuples = {} # Tuples for color RGB to decouple from PyQt
        self.map_dicts = {} # We still store original just in case
        
        self.z_format_3d = '>H'
        self.z_format_2d = '>f'
        self.ax_format = 'f'
        
        self.current_index = 0
        self.total_maps = 0
        self.current_map_addr = ""

    def load_csv(self, map_mode):
        target_csv = self.csv_3d_path if map_mode == '3d' else self.csv_2d_path
        if not os.path.exists(target_csv):
            self.df = pd.DataFrame()
            self.total_maps = 0
            return False, f"File not found: {target_csv}"
            
        try:
            self.df = pd.read_csv(target_csv, dtype=str)
            # Add Tags column
            tags_list = []
            for _, row in self.df.iterrows():
                addr_col = 'Map_Z_Addr' if map_mode == '3d' else 'Curve_Data_Addr'
                addr = str(row.get(addr_col, "")).strip().upper()
                tags_list.append(", ".join(self.tags.get(addr, {}).get("tags", [])))
            self.df['Tag'] = tags_list
            
            self.total_maps = len(self.df)
            self.current_index = 0
            self.current_map_addr = ""
            return True, ""
        except Exception as e:
            self.df = pd.DataFrame()
            return False, f"Could not read CSV:\n{e}"

    def read_axis(self, hex_addr, size, endian, axis_format):
        try:
            addr = int(str(hex_addr).strip(), 16)
            if addr == 0 or addr >= 0xFFFF0000:
                return np.arange(size)
            bytes_per_value = 4 if axis_format == 'f' else 2
            
            with open(self.bin_path, "rb") as f:
                f.seek(addr)
                raw = f.read(size * bytes_per_value)
            return np.array(struct.unpack(f"{endian}{size}{axis_format}", raw)) 
        except:
            return np.arange(size)

    def read_map_3d(self):
        row = self.df.iloc[self.current_index]
        size_x = int(row['Size_X'])
        size_y = int(row['Size_Y'])
        map_z_hex = str(row['Map_Z_Addr']).strip()
        endian = self.z_format_3d[0]
        fmt_char = self.z_format_3d[-1]

        if fmt_char == 'f': bytes_per_value = 4
        elif fmt_char.lower() == 'h': bytes_per_value = 2
        else: bytes_per_value = 1

        with open(self.bin_path, "rb") as f:
            f.seek(int(map_z_hex, 16))
            raw_z_data = f.read(size_y * size_x * bytes_per_value)

        z_values = struct.unpack(f"{endian}{size_y * size_x}{fmt_char}", raw_z_data)
        matrix_z = np.array(z_values).reshape((size_y, size_x))
        axis_x = self.read_axis(str(row['Axis_X_Addr']).strip(), size_x, endian, self.ax_format)
        axis_y = self.read_axis(str(row['Axis_Y_Addr']).strip(), size_y, endian, self.ax_format)
        return matrix_z, axis_x, axis_y, size_y, size_x, map_z_hex

    def read_map_2d(self):
        row = self.df.iloc[self.current_index]
        size_x = int(row['Size_X'])
        curve_data_hex = str(row['Curve_Data_Addr']).strip()

        endian = self.z_format_2d[0]
        fmt_char = self.z_format_2d[-1]

        if fmt_char == 'f': bytes_per_value = 4
        elif fmt_char.lower() == 'h': bytes_per_value = 2
        else: bytes_per_value = 1

        with open(self.bin_path, "rb") as f:
            f.seek(int(curve_data_hex, 16))
            raw_z = f.read(size_x * bytes_per_value)

        z_values = struct.unpack(f"{endian}{size_x}{fmt_char}", raw_z)
        curve_z = np.array(z_values)
        axis_x = self.read_axis(str(row['Axis_X_Addr']).strip(), size_x, endian, self.ax_format)

        axis_y_dummy = np.array([1])
        size_y_dummy = 1

        return curve_z, axis_x, axis_y_dummy, size_y_dummy, size_x, curve_data_hex

    def val_to_hex(self, val, fmt_char, endian):
        try:
            v_float = float(val)
            if fmt_char == 'f':
                return struct.pack(f"{endian}f", v_float).hex().upper()
            elif fmt_char.lower() == 'h':
                return struct.pack(f"{endian}H", int(v_float)).hex().upper()    
            else:
                return struct.pack(f"{endian}B", int(v_float)).hex().upper()    
        except:
            return "??"

    def save_project(self, file_path):
        data = {
            "bin_path": self.bin_path,
            "csv_3d_path": self.csv_3d_path,
            "csv_2d_path": self.csv_2d_path,
            "tags": self.tags,
            "z_format_3d": self.z_format_3d,
            "z_format_2d": self.z_format_2d,
            "ax_format": self.ax_format
        }
        try:
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=4)
            self.project_path = file_path
            return True, ""
        except Exception as e:
            return False, str(e)

    def load_project(self, file_path):
        if not os.path.exists(file_path):
            return False, "File not found"
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            self.bin_path = data.get("bin_path", "")
            self.csv_3d_path = data.get("csv_3d_path", "")
            self.csv_2d_path = data.get("csv_2d_path", "")
            old_tags = data.get("tags", {})
            self.tags = {}
            for k, v in old_tags.items():
                if isinstance(v, dict) and "tags" in v:
                    self.tags[k] = v
                elif isinstance(v, list):
                    self.tags[k] = {"tags": v, "length": 1}
                elif isinstance(v, str):
                    self.tags[k] = {"tags": [t.strip() for t in v.split(",") if t.strip()], "length": 1}
            self.z_format_3d = data.get("z_format_3d", ">H")
            self.z_format_2d = data.get("z_format_2d", ">f")
            self.ax_format = data.get("ax_format", "f")
            
            self.project_path = file_path
            return True, ""
        except Exception as e:
            return False, str(e)

    def build_color_map(self, highlight_3d=True, highlight_2d=True, highlight_custom=True):
        if not os.path.exists(self.bin_path): return False
        try:
            with open(self.bin_path, "rb") as f:
                self.bin_data = f.read()
        except: return False

        self.map_array = [-1] * len(self.bin_data)
        self.map_dicts = {}
        self.map_dicts_tuples = {}

        def get_bperval(fmt):
            if not fmt: return 1
            f = fmt[-1].lower()
            if f == 'f': return 4
            elif f == 'h': return 2
            return 1

        map_id = 0
        csv_addrs = set()

        if highlight_3d and os.path.exists(self.csv_3d_path):
            try:
                df3 = pd.read_csv(self.csv_3d_path, dtype=str)
                bpv = get_bperval(self.z_format_3d)
                for _, row in df3.iterrows():
                    addr_str = str(row.get('Map_Z_Addr', '0')).strip()
                    addr = int(addr_str, 16)
                    csv_addrs.add(addr)
                    sx = int(row.get('Size_X', 1))
                    sy = int(row.get('Size_Y', 1))
                    length = sx * sy * bpv
                    if addr + length <= len(self.map_array):
                        for i in range(addr, addr + length):
                            self.map_array[i] = map_id
                        tag_data = self.tags.get(addr_str.upper(), {})
                        tag_name = ", ".join(tag_data.get("tags", []))
                        if not tag_name: tag_name = f"3D {addr_str} {sx}x{sy}"
                            
                        self.map_dicts_tuples[map_id] = {
                            'color': (0, 191, 255), # DeepSkyBlue
                            'tag': tag_name,
                            'addr': addr
                        }
                    map_id += 1
            except: pass

        if highlight_2d and os.path.exists(self.csv_2d_path):
            try:
                df2 = pd.read_csv(self.csv_2d_path, dtype=str)
                bpv = get_bperval(self.z_format_2d)
                for _, row in df2.iterrows():
                    addr_str = str(row.get('Curve_Data_Addr', '0')).strip()     
                    addr = int(addr_str, 16)
                    csv_addrs.add(addr)
                    sx = int(row.get('Size_X', 1))
                    length = sx * bpv
                    if addr + length <= len(self.map_array):
                        for i in range(addr, addr + length):
                            self.map_array[i] = map_id
                        
                        tag_data = self.tags.get(addr_str.upper(), {})
                        tag_name = ", ".join(tag_data.get("tags", []))
                        if not tag_name: tag_name = f"2D {addr_str} {sx}x1"
                        
                        self.map_dicts_tuples[map_id] = {
                            'color': (50, 205, 50), # LimeGreen
                            'tag': tag_name,
                            'addr': addr
                        }
                    map_id += 1
            except: pass
            
        if highlight_custom:
            for addr_hex, tag_data in self.tags.items():
                try:
                    addr = int(addr_hex, 16)
                    if addr in csv_addrs:
                        continue  # Skip 2D/3D map tagging so it remains green/blue
                    length = tag_data.get("length", 1)
                    if addr + length <= len(self.map_array):
                        tags_list = tag_data.get("tags", [])
                        if not tags_list: continue

                        has_painted = False
                        for i in range(addr, addr + length):
                            if i < len(self.map_array):
                                self.map_array[i] = map_id
                                has_painted = True
                                
                        if has_painted:
                            tag_name = ", ".join(tags_list)
                            self.map_dicts_tuples[map_id] = {
                                'color': (255, 165, 0), # Orange
                                'tag': tag_name,
                                'addr': addr
                            }
                            map_id += 1
                except: pass

        return True

