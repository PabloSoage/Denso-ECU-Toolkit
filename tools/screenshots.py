"""Regenerate the README screenshots (``docs/img/*.png``).

    python tools/screenshots.py

No firmware is involved: the script builds a *synthetic* image that has smooth
made-up surfaces at the addresses of the published catalogue, so the pictures
show the viewer, the addresses and the tags, and not one OEM byte.
"""

import csv
import json
import math
import os
import struct
import sys
import tempfile
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "img")
IMAGE_SIZE = 0x180000

TORQUE_LIMITER = "00042F3C"
BOOST = "0003A6A6"

sys.path.insert(0, ROOT)
os.chdir(ROOT)


# ----------------------------------------------------------------------------
# Synthetic image
# ----------------------------------------------------------------------------

def _rows(name):
    with open(os.path.join(ROOT, name), newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _write_axis(image, address, size, low, high):
    for i in range(size):
        value = low + (high - low) * i / max(size - 1, 1)
        value = round(value / 50) * 50 if high > 1000 else round(value, 1)
        struct.pack_into(">f", image, address + 4 * i, value)


def _surface(size_x, size_y, seed):
    """A plateau with a soft peak, different for every map."""
    peak_x, peak_y = 0.35 + (seed % 7) * 0.05, 0.55 + (seed % 5) * 0.08
    top = 24000 + (seed % 11) * 2400
    for r in range(size_y):
        for c in range(size_x):
            x, y = c / max(size_x - 1, 1), r / max(size_y - 1, 1)
            hill = math.exp(-((x - peak_x) ** 2) / 0.12 - ((y - peak_y) ** 2) / 0.30)
            ramp = 1 / (1 + math.exp(-9 * (y - 0.25)))
            yield int(top * (0.15 + 0.55 * hill + 0.30 * ramp * (1 - 0.5 * x)))


def synthetic_image():
    image = bytearray(IMAGE_SIZE)
    for row in _rows("2d_maps_review.csv"):
        size = int(row["Size_X"])
        axis, data = int(row["Axis_X_Addr"], 16), int(row["Curve_Data_Addr"], 16)
        seed = zlib.crc32(row["Wrapper_Addr"].encode())
        _write_axis(image, axis, size, 0, 100)
        for i in range(size):
            value = 40 + 60 * math.sin(0.5 + 2.2 * i / size + seed % 3)
            struct.pack_into(">f", image, data + 4 * i, value)
    for row in _rows("3d_maps_review.csv"):
        size_x, size_y = int(row["Size_X"]), int(row["Size_Y"])
        axis_x, axis_y = int(row["Axis_X_Addr"], 16), int(row["Axis_Y_Addr"], 16)
        data = int(row["Map_Z_Addr"], 16)
        _write_axis(image, axis_x, size_x, 600, 4800)
        _write_axis(image, axis_y, size_y, 0, size_y - 1 if size_y <= 8 else 95)
        values = list(_surface(size_x, size_y, zlib.crc32(row["Wrapper_Addr"].encode())))
        if data + 2 * len(values) <= IMAGE_SIZE:
            struct.pack_into(f">{len(values)}H", image, data, *values)
    return image


def edited_map(image):
    """``{address: byte}`` raising part of the torque limiter, like a user edit."""
    row = next(r for r in _rows("3d_maps_review.csv") if r["Wrapper_Addr"] == TORQUE_LIMITER)
    size_x, size_y = int(row["Size_X"]), int(row["Size_Y"])
    data = int(row["Map_Z_Addr"], 16)
    diff = {}
    for r in range(2, size_y - 1):
        for c in range(6, size_x - 4):
            address = data + 2 * (r * size_x + c)
            old = struct.unpack_from(">H", image, address)[0]
            weight = math.sin(math.pi * (c - 6) / (size_x - 11))
            new = min(65535, int(old * (1 + 0.12 * weight)))
            for i, byte in enumerate(struct.pack(">H", new)):
                if image[address + i] != byte:
                    diff[address + i] = byte
    return diff


# ----------------------------------------------------------------------------
# Driving the viewer
# ----------------------------------------------------------------------------

def main():
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QApplication, QMessageBox

    from viewer.core.state import AppMode, CompareMode, MapMode, ViewMode

    # Nothing may block on a modal box while the pictures are taken.
    for name in ("information", "warning", "critical"):
        setattr(QMessageBox, name, staticmethod(lambda *a, **k: None))

    from viewer.ui.main_window import DensoViewerApp

    os.makedirs(OUT, exist_ok=True)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    with tempfile.TemporaryDirectory() as tmp:
        image = synthetic_image()
        image_path = os.path.join(tmp, "synthetic.bin")
        with open(image_path, "wb") as handle:
            handle.write(image)
        with open(os.path.join(ROOT, "A17DTR.dproj"), encoding="utf-8") as handle:
            project = json.load(handle)
        project["bin_path"] = image_path
        project["bin_diff"] = {}
        # The units of the real maps mean nothing on made-up data.
        project["custom_map_settings"] = {}
        project["z_format_3d"], project["z_format_2d"] = ">H", ">f"
        project_path = os.path.join(tmp, "demo.dproj")
        with open(project_path, "w", encoding="utf-8") as handle:
            json.dump(project, handle)

        window = DensoViewerApp()
        window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
        window.resize(1500, 880)
        window.show()
        ok, message = window.data_manager.load_project(project_path)
        assert ok, message
        window.load_data()

        def settle():
            for _ in range(30):
                app.processEvents()

        def select(wrapper):
            df = window.data_manager.df
            position = next(i for i in range(len(df)) if str(df.iloc[i]["Wrapper_Addr"]).upper() == wrapper)
            window.data_manager.current_index = position
            window.sync_listbox_selection()
            window.rebuild_plot_axes()
            window.draw_map()
            settle()

        def shot(name):
            settle()
            picture = window.grab().toImage()
            picture = picture.scaledToWidth(1500, Qt.TransformationMode.SmoothTransformation)
            picture.save(os.path.join(OUT, name + ".png"))
            print("docs/img/" + name + ".png")

        # 1. Catalogue and 3D plot
        select(BOOST)
        shot("map-viewer")

        # 2. Plot and table together
        window.view_mode = ViewMode.SPLIT
        window._sync_mode_widgets()
        select(TORQUE_LIMITER)
        shot("split-view")

        # 3. An edit against the original, side by side
        window.data_manager.apply_bin_diff(edited_map(image))
        window.update_list()
        window.cmb_compare_mode.setCurrentIndex(int(CompareMode.TWIN_ORIGINAL))
        select(TORQUE_LIMITER)
        shot("compare-twin")
        window.cmb_compare_mode.setCurrentIndex(int(CompareMode.NORMAL))

        # 4. 2D curves
        window.view_mode = ViewMode.PLOT
        window.cmb_map_type.setCurrentIndex(MapMode.TWO_D.combo_index)
        window.data_manager.current_index = 1
        window.sync_listbox_selection()
        window.rebuild_plot_axes()
        window.draw_map()
        shot("curve-2d")

        # 5. Hex dump with the overlays
        window.cmb_map_type.setCurrentIndex(MapMode.THREE_D.combo_index)
        select(TORQUE_LIMITER)
        window.hex_plot_visible = False
        window.set_app_mode(AppMode.HEX_DUMP)
        window.update_hex_view()
        row = int("0F6A30", 16) // window.hex_row_width
        window.hex_table.scrollTo(
            window.hex_table_model.index(row - 8, 0), window.hex_table.ScrollHint.PositionAtTop
        )
        shot("hex-dump")

        window.close()


if __name__ == "__main__":
    main()
