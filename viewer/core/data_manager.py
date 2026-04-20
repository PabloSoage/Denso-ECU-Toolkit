import os
import struct
import json
import math
import numpy as np
import pandas as pd

class DataManager:
    def __init__(self):
        self.project_path = ""
        self.bin_path = ""
        self.csv_3d_path = ""
        self.csv_2d_path = ""
        
        self.tags = {}  # { hex_address: {"tags": ["Tag1", ...], "length": int} }
        self.hexdump_tags = {}  # { hex_address: {"tags": ["Tag1", ...], "length": int, "chunks": [...]} }
        self.z_format_3d = '>H'
        self.z_format_2d = '>f'
        self.ax_format = 'f'
        
        self.current_index = 0
        self.total_maps = 0
        self.current_map_addr = ""
        self.custom_map_settings = {}

    def load_csv(self, map_mode):
        modes_to_load = [map_mode] if map_mode != 'all' else ['3d', '2d', 'tags']
        df_list = []
        
        for m in modes_to_load:
            if m == 'tags':
                rows = []
                for addr_hex, data in self.hexdump_tags.items():
                    tags_str = ', '.join(data.get('tags', []))
                    length = data.get('length', 1)
                    chunks = data.get('chunks', None)
                    
                    # You might want to grab user defined shape from custom map settings if defined
                    custom = self.custom_map_settings.get(addr_hex, {})
                    user_sx = custom.get('Size_X', min(length, 16))
                    user_sy = custom.get('Size_Y', max(1, length // min(length, 16)))
                    
                    rows.append({
                        'Map_Z_Addr': addr_hex,
                        'Curve_Data_Addr': addr_hex,
                        'Wrapper_Addr': addr_hex,
                        'Size_X': str(user_sx),
                        'Size_Y': str(user_sy),
                        'Tag': tags_str,
                        'Tag_Length': length,
                        'Map_Type': 'tags',
                        'Chunks': str(chunks) if chunks else ''
                    })
                df_tags = pd.DataFrame(rows)
                df_list.append(df_tags)
            else:
                target_csv = self.csv_3d_path if m == '3d' else self.csv_2d_path
                if os.path.exists(target_csv):
                    try:
                        df_csv = pd.read_csv(target_csv, dtype=str)
                        df_csv['Map_Type'] = m
                        tags_list = []
                        for _, row in df_csv.iterrows():
                            addr = str(row.get('Wrapper_Addr', '')).strip().upper()
                            tags_list.append(', '.join(self.tags.get(addr, {}).get('tags', [])))
                        df_csv['Tag'] = tags_list
                        df_list.append(df_csv)
                    except:
                        pass
        
        if df_list:
            self.df = pd.concat(df_list, ignore_index=True)
            self.df = self.df.fillna('')
        else:
            self.df = pd.DataFrame()
            
        self.total_maps = len(self.df)
        self.current_index = 0
        self.current_map_addr = ''
        return True, ''

    def read_axis(self, hex_addr, size, endian, axis_format):
        try:
            addr = int(str(hex_addr).strip(), 16)
            if addr == 0 or addr >= 0xFFFF0000:
                return np.arange(size)
            
            f_char = axis_format[-1].lower()
            if f_char == 'f': bytes_per_value = 4
            elif f_char == 'h': bytes_per_value = 2
            elif f_char in ('i', 'l'): bytes_per_value = 4
            else: bytes_per_value = 1
            
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
        wrapper_addr_hex = str(row['Wrapper_Addr']).strip()
        
        custom = self.custom_map_settings.get(wrapper_addr_hex, {})
        z_format = custom.get('z_format', self.z_format_3d)
        ax_fmt = custom.get('ax_format', self.ax_format)
        
        endian = z_format[0]
        fmt_char = z_format[-1]

        if fmt_char == 'f': bytes_per_value = 4
        elif fmt_char.lower() == 'h': bytes_per_value = 2
        elif fmt_char.lower() in ('i', 'l'): bytes_per_value = 4
        else: bytes_per_value = 1

        with open(self.bin_path, "rb") as f:
            f.seek(int(map_z_hex, 16))
            raw_z_data = f.read(size_y * size_x * bytes_per_value)

        z_values = struct.unpack(f"{endian}{size_y * size_x}{fmt_char}", raw_z_data)
        matrix_z = np.array(z_values).reshape((size_y, size_x))
        axis_x = self.read_axis(str(row['Axis_X_Addr']).strip(), size_x, endian, ax_fmt)
        axis_y = self.read_axis(str(row['Axis_Y_Addr']).strip(), size_y, endian, ax_fmt)
        return matrix_z, axis_x, axis_y, size_y, size_x, map_z_hex

    def read_map_2d(self):
        row = self.df.iloc[self.current_index]
        size_x = int(row['Size_X'])
        curve_data_hex = str(row['Curve_Data_Addr']).strip()
        wrapper_addr_hex = str(row['Wrapper_Addr']).strip()

        custom = self.custom_map_settings.get(wrapper_addr_hex, {})
        z_format = custom.get('z_format', self.z_format_2d)
        ax_fmt = custom.get('ax_format', self.ax_format)

        endian = z_format[0]
        fmt_char = z_format[-1]

        if fmt_char == 'f': bytes_per_value = 4
        elif fmt_char.lower() == 'h': bytes_per_value = 2
        elif fmt_char.lower() in ('i', 'l'): bytes_per_value = 4
        else: bytes_per_value = 1

        with open(self.bin_path, "rb") as f:
            f.seek(int(curve_data_hex, 16))
            raw_z = f.read(size_x * bytes_per_value)

        z_values = struct.unpack(f"{endian}{size_x}{fmt_char}", raw_z)
        curve_z = np.array(z_values)
        axis_x = self.read_axis(str(row['Axis_X_Addr']).strip(), size_x, endian, ax_fmt)

        axis_y_dummy = np.array([1])
        size_y_dummy = 1

        return curve_z, axis_x, axis_y_dummy, size_y_dummy, size_x, curve_data_hex
    def read_map_tags(self, as_2d=False):
        row = self.df.iloc[self.current_index]
        addr_hex = str(row['Map_Z_Addr']).strip()
        length = int(row['Tag_Length'])

        custom = self.custom_map_settings.get(addr_hex, {})
        z_format = custom.get('z_format', self.z_format_3d)

        endian = z_format[0]
        fmt_char = z_format[-1]

        bpc = 1
        if fmt_char == 'f': bpc = 4
        elif fmt_char.lower() == 'h': bpc = 2
        elif fmt_char.lower() in ('i', 'l'): bpc = 4

        num_elements = length // bpc
        if num_elements == 0:
            num_elements = 1
            bpc = length
            
        chunks_str = str(row.get('Chunks', ''))
        z_values = []
        with open(self.bin_path, "rb") as f:
            if chunks_str:
                import ast
                try:
                    chunks = ast.literal_eval(chunks_str)
                    for c_addr, c_len in chunks:
                        f.seek(c_addr)
                        raw_z = f.read(c_len)
                        c_elements = c_len // bpc
                        if c_elements > 0:
                            z_values.extend(struct.unpack(f"{endian}{c_elements}{fmt_char}", raw_z))
                except:
                    f.seek(int(addr_hex, 16))
                    raw_z = f.read(num_elements * bpc)
                    z_values = list(struct.unpack(f"{endian}{num_elements}{fmt_char}", raw_z))
            else:
                f.seek(int(addr_hex, 16))
                raw_z = f.read(num_elements * bpc)
                z_values = list(struct.unpack(f"{endian}{num_elements}{fmt_char}", raw_z))

        num_elements = len(z_values)

        if as_2d:
            size_y = 1
            size_x = num_elements
            matrix_z = np.array(z_values)
        else:
            size_x = int(row.get('Size_X', min(num_elements, 16)))
            size_y = int(row.get('Size_Y', max(1, num_elements // max(size_x, 1))))
            actual_elements = size_x * size_y

            # Truncate or pad to fit matrix
            z_array = np.array(z_values)
            if len(z_array) > actual_elements:
                z_array = z_array[:actual_elements]
            elif len(z_array) < actual_elements:
                z_array = np.pad(z_array, (0, actual_elements - len(z_array)), 'constant')

            matrix_z = z_array.reshape((size_y, size_x))

        axis_x = np.arange(size_x)
        axis_y = np.arange(size_y)

        return matrix_z, axis_x, axis_y, size_y, size_x, addr_hex
    def val_to_hex(self, val, fmt_char, endian):
        try:
            v_float = float(val)
            if fmt_char == 'f':
                return struct.pack(f"{endian}f", v_float).hex().upper()
            elif fmt_char.lower() == 'h':
                return struct.pack(f"{endian}{fmt_char}", int(v_float)).hex().upper()
            elif fmt_char.lower() in ('i', 'l'):
                return struct.pack(f"{endian}{fmt_char}", int(v_float)).hex().upper()
            else:
                return struct.pack(f"{endian}{fmt_char}", int(v_float)).hex().upper()
        except:
            return "??"

    def save_project(self, file_path):
        data = {
            "bin_path": self.bin_path,
            "csv_3d_path": self.csv_3d_path,
            "csv_2d_path": self.csv_2d_path,
            "tags": self.tags,
            "hexdump_tags": self.hexdump_tags,
            "z_format_3d": self.z_format_3d,
            "z_format_2d": self.z_format_2d,
            "ax_format": self.ax_format,
            "custom_map_settings": self.custom_map_settings
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
            
            old_hexdump = data.get("hexdump_tags", {})
            self.hexdump_tags = {}
            for k, v in old_hexdump.items():
                if isinstance(v, dict) and "tags" in v:
                    self.hexdump_tags[k] = v
            # To fix previous save where hexdump tags were injected into self.tags but had "chunks"
            keys_to_move = []
            for k, v in self.tags.items():
                if "chunks" in v:
                    self.hexdump_tags[k] = v
                    keys_to_move.append(k)
            for k in keys_to_move:
                del self.tags[k]

            self.z_format_3d = data.get("z_format_3d", ">H")
            self.z_format_2d = data.get("z_format_2d", ">f")
            self.ax_format = data.get("ax_format", "f")
            self.custom_map_settings = data.get("custom_map_settings", {})
            
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
            for source_dict in (self.tags, self.hexdump_tags):
                for addr_hex, tag_data in source_dict.items():
                    try:
                        addr = int(addr_hex, 16)
                        if addr in csv_addrs:
                            continue  # Skip 2D/3D map tagging so it remains green/blue
                        tags_list = tag_data.get("tags", [])
                        if not tags_list: continue

                        has_painted = False
                        
                        chunks = tag_data.get("chunks")
                        if chunks:
                            for chunk_start, chunk_len in chunks:
                                if chunk_start + chunk_len <= len(self.map_array):  
                                    for i in range(chunk_start, chunk_start + chunk_len):
                                        if i < len(self.map_array):
                                            self.map_array[i] = map_id
                                            has_painted = True
                        else:
                            length = tag_data.get("length", 1)
                            if addr + length <= len(self.map_array):
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
