"""Loading, decoding and patching of Denso calibration data.

Owns the binary, the map catalogue (as a normalised DataFrame), user tags and
custom per-map settings. Knows nothing about Qt.
"""

import ast
import json
import os
from contextlib import contextmanager

import numpy as np
import pandas as pd

from . import formats
from .integrity import export_report
from .state import Baseline, MapMode

DEFAULT_CSV_3D = "3d_maps_review.csv"
DEFAULT_CSV_2D = "2d_maps_review.csv"
DEFAULT_CSV_DTC = "2d_and_3D_maps_DTC_Mapped.csv"
DEFAULT_CSV_POTENTIAL = "potential_maps.csv"
DEFAULT_BIN = os.path.join("research", "115_e3a4d17c28.bin")

#: Addresses that mean "no axis / no pointer".
NULL_ADDRESSES = {"", "0", "0X0", "0x0", "00000000"}


class BinaryUnavailable(RuntimeError):
    """The calibration binary could not be read.

    Raised rather than returning empty data, because every silent-empty path in
    the previous design ended with the user being told an operation succeeded
    when their edits had actually been dropped.
    """


def _clean_addr(value):
    """Normalise an address cell to an uppercase bare-hex string."""
    text = str(value).strip().upper()
    if text.startswith("0X"):
        text = text[2:]
    return text


def parse_address(value):
    """Parse an address cell, or return ``None`` when it is null/unparseable."""
    text = _clean_addr(value)
    if text in NULL_ADDRESSES or not text:
        return None
    try:
        return int(text, 16)
    except ValueError:
        return None


class DataManager:
    def __init__(self):
        self.project_path = ""
        self.bin_path = DEFAULT_BIN
        self.csv_3d_path = DEFAULT_CSV_3D
        self.csv_2d_path = DEFAULT_CSV_2D
        self.csv_dtc_path = DEFAULT_CSV_DTC
        self.csv_potential_path = DEFAULT_CSV_POTENTIAL

        self.dtc_data = {}
        #: address (hex str) -> {"tags": [...], "length": int}
        self.tags = {}
        #: address (hex str) -> {"tags": [...], "length": int, "chunks": [...]}
        self.hexdump_tags = {}
        self.z_format_3d = ">H"
        self.z_format_2d = ">f"
        self.ax_format = "f"

        self.df = pd.DataFrame()
        self.current_index = 0
        self.total_maps = 0
        self.current_map_addr = ""
        self.custom_map_settings = {}

        self.show_modified = True
        self.bin_data = b""
        self.map_array = None
        self.map_dicts = {}
        self.map_dicts_tuples = {}

        self._bin_data_cache = b""
        self._modified_bin_data = bytearray()
        self._cached_bin_path = ""
        self._reference_bin_data = b""
        self._pending_diff = {}
        self._axis_cache = {}

    # ------------------------------------------------------------------
    # Binary access
    # ------------------------------------------------------------------

    def load_binary(self):
        """(Re)read the binary from disk.

        Returns ``(True, "")`` or ``(False, reason)``. Never raises — callers
        that must have data use :meth:`require_binary` instead.
        """
        path = self.bin_path
        if not path:
            return False, "No binary file is configured."
        if not os.path.exists(path):
            return False, f"Binary not found: {path}"
        try:
            with open(path, "rb") as handle:
                data = handle.read()
        except OSError as exc:
            return False, f"Could not read {path}: {exc}"

        if not data:
            return False, f"Binary is empty: {path}"

        self._bin_data_cache = data
        self._modified_bin_data = bytearray(data)
        self._cached_bin_path = path
        self._axis_cache.clear()

        if self._pending_diff:
            pending, self._pending_diff = self._pending_diff, {}
            applied, skipped = self._write_diff(pending)
            if skipped:
                return True, (
                    f"Loaded, but {skipped} of {applied + skipped} saved edits fall "
                    f"outside this binary and were dropped."
                )
        return True, ""

    def _ensure_bin_loaded(self):
        if self._cached_bin_path != self.bin_path or not self._bin_data_cache:
            self.load_binary()

    def require_binary(self):
        """Return the active byte view, raising :class:`BinaryUnavailable`."""
        self._ensure_bin_loaded()
        if not self._bin_data_cache:
            raise BinaryUnavailable(f"No calibration binary loaded ({self.bin_path or 'no path set'}).")
        return self.get_bin_data()

    def get_bin_data(self):
        self._ensure_bin_loaded()
        if self.show_modified and self._modified_bin_data:
            return self._modified_bin_data
        return self._bin_data_cache

    @property
    def has_binary(self):
        self._ensure_bin_loaded()
        return bool(self._bin_data_cache)

    @property
    def has_edits(self):
        return bool(self._bin_data_cache) and self._bin_data_cache != bytes(self._modified_bin_data)

    def get_bin_diff(self):
        if not self._bin_data_cache or not self._modified_bin_data:
            return dict(self._pending_diff)
        original = np.frombuffer(self._bin_data_cache, dtype=np.uint8)
        modified = np.frombuffer(bytes(self._modified_bin_data), dtype=np.uint8)
        limit = min(len(original), len(modified))
        differing = np.nonzero(original[:limit] != modified[:limit])[0]
        return {str(int(i)): int(modified[i]) for i in differing}

    def _write_diff(self, diff_dict):
        """Apply ``{offset: byte}``. Returns ``(applied, skipped)``."""
        applied = skipped = 0
        for key, value in diff_dict.items():
            try:
                index = int(key)
            except (TypeError, ValueError):
                skipped += 1
                continue
            if 0 <= index < len(self._modified_bin_data):
                self._modified_bin_data[index] = int(value) & 0xFF
                applied += 1
            else:
                skipped += 1
        return applied, skipped

    def apply_bin_diff(self, diff_dict):
        """Apply saved edits, deferring them if the binary is not loaded yet.

        Deferring matters: a project whose ``bin_path`` is momentarily wrong used
        to discard every stored edit while reporting success.
        """
        if not diff_dict:
            return 0, 0
        self._ensure_bin_loaded()
        if not self._modified_bin_data:
            self._pending_diff = dict(diff_dict)
            return 0, 0
        return self._write_diff(diff_dict)

    def is_map_modified(self, start_addr, size):
        self._ensure_bin_loaded()
        if not self._modified_bin_data or not self._bin_data_cache:
            return False
        if start_addr is None or start_addr < 0 or start_addr + size > len(self._modified_bin_data):
            return False
        return self._bin_data_cache[start_addr:start_addr + size] != self._modified_bin_data[start_addr:start_addr + size]

    def apply_edit(self, address, new_val, fmt):
        """Write one value at ``address``. Returns ``(True, "")`` or ``(False, why)``."""
        if not self._modified_bin_data:
            return False, "No binary loaded."

        width = formats.value_size(fmt)
        if address < 0 or address + width > len(self._modified_bin_data):
            return False, (
                f"Address 0x{address:X} + {width} bytes is outside the binary "
                f"({len(self._modified_bin_data)} bytes)."
            )
        try:
            raw = formats.pack_value(new_val, fmt)
        except ValueError as exc:
            return False, str(exc)

        self._modified_bin_data[address:address + width] = raw
        self._axis_cache.clear()
        return True, ""

    def revert_all_edits(self):
        """Discard every pending edit and go back to the on-disk binary."""
        self._ensure_bin_loaded()
        self._modified_bin_data = bytearray(self._bin_data_cache)
        self._pending_diff.clear()
        self._axis_cache.clear()

    def export_summary(self):
        """``(total_bytes, region_count, lines)`` describing the pending edit."""
        return export_report(self._bin_data_cache, bytes(self._modified_bin_data))

    def write_modified_bin(self, file_path):
        if not self._modified_bin_data:
            return False, "No binary loaded."
        try:
            with open(file_path, "wb") as handle:
                handle.write(self._modified_bin_data)
        except OSError as exc:
            return False, str(exc)
        return True, ""

    def load_reference_bin(self, file_path):
        try:
            with open(file_path, "rb") as handle:
                self._reference_bin_data = handle.read()
        except OSError as exc:
            return False, str(exc)
        if not self._reference_bin_data:
            return False, "Reference binary is empty."
        return True, ""

    @property
    def reference_bin_data(self):
        return self._reference_bin_data

    # ------------------------------------------------------------------
    # Map catalogue
    # ------------------------------------------------------------------

    def _tags_for_addresses(self, *addresses):
        """Union of tags attached to any of ``addresses``, in first-seen order.

        A map has several identities — the config struct, the call site that
        consumes it, and the data block. The heuristic scanner records the
        struct address while the mass extractors record the call site, so a tag
        applied in one mode used to be invisible in the other. Looking under
        every identity makes tags mode-independent.
        """
        seen = []
        for address in addresses:
            key = _clean_addr(address)
            if not key or key in NULL_ADDRESSES:
                continue
            for source in (self.tags, self.hexdump_tags):
                for tag in source.get(key, {}).get("tags", []):
                    if tag not in seen:
                        seen.append(tag)
        return seen

    def custom_settings_for(self, row):
        """Per-map overrides, preferring the canonical key but honouring legacy ones.

        Projects saved before the data address became the canonical key stored
        their overrides under the call-site address. Reading both means those
        projects keep working; writes always go to the canonical key.
        """
        for key in self.identity_keys(row):
            settings = self.custom_map_settings.get(key)
            if settings:
                return settings
        return {}

    @staticmethod
    def identity_keys(row):
        """Every address this row can be recognised by, canonical one first."""
        keys = []
        for column in ("Data_Addr", "Struct_Addr", "Call_Site_Addr", "Wrapper_Addr"):
            key = _clean_addr(row.get(column, ""))
            if key and key not in NULL_ADDRESSES and key not in keys:
                keys.append(key)
        return keys

    @staticmethod
    def canonical_key(row):
        """The key new settings are written under: the data address."""
        keys = DataManager.identity_keys(row)
        return keys[0] if keys else ""

    def set_custom_setting(self, row, **values):
        key = self.canonical_key(row)
        if not key:
            return ""
        self.custom_map_settings.setdefault(key, {}).update(values)
        return key

    def _normalise_catalogue(self, df, map_type):
        """Bring one CSV into the internal schema, accepting old and new headers.

        Historical column meanings that this untangles:

        * ``Wrapper_Addr`` in ``potential_maps.csv`` is the **config struct**
          address, but in the review CSVs it is the **call site**. Same header,
          disjoint meanings — their overlap is exactly zero rows.
        * 2D curves name their data column ``Curve_Data_Addr``, 3D maps use
          ``Map_Z_Addr``.
        """
        df = df.copy()
        df.columns = [str(c).strip() for c in df.columns]

        if "Data_Addr" not in df.columns:
            if "Map_Z_Addr" in df.columns:
                df["Data_Addr"] = df["Map_Z_Addr"]
            elif "Curve_Data_Addr" in df.columns:
                df["Data_Addr"] = df["Curve_Data_Addr"]
            else:
                df["Data_Addr"] = ""

        if "Struct_Addr" not in df.columns:
            df["Struct_Addr"] = df["Wrapper_Addr"] if map_type == "potential" and "Wrapper_Addr" in df.columns else ""
        if "Call_Site_Addr" not in df.columns:
            df["Call_Site_Addr"] = df["Wrapper_Addr"] if map_type != "potential" and "Wrapper_Addr" in df.columns else ""

        for column in ("Size_X", "Size_Y", "Axis_X_Addr", "Axis_Y_Addr"):
            if column not in df.columns:
                df[column] = "1" if column.startswith("Size") else ""

        for column in ("Data_Addr", "Struct_Addr", "Call_Site_Addr", "Axis_X_Addr", "Axis_Y_Addr", "Wrapper_Addr"):
            if column in df.columns:
                df[column] = df[column].map(_clean_addr)

        # Keep Wrapper_Addr populated so saved projects and DTC lookups still resolve.
        if "Wrapper_Addr" not in df.columns:
            df["Wrapper_Addr"] = df["Call_Site_Addr"].where(df["Call_Site_Addr"] != "", df["Struct_Addr"])

        return df

    def _apply_tags(self, df):
        df["Tag"] = [
            ", ".join(self._tags_for_addresses(*self.identity_keys(row), row.get("Axis_X_Addr", "")))
            for _, row in df.iterrows()
        ]
        return df

    def _tags_frame(self):
        rows = []
        for addr_hex, data in self.hexdump_tags.items():
            length = int(data.get("length", 1) or 1)
            chunks = data.get("chunks")
            custom = self.custom_map_settings.get(_clean_addr(addr_hex), {})
            width = formats.value_size(custom.get("z_format", self.z_format_3d))
            elements = max(1, length // width if width else length)

            size_x = int(custom.get("Size_X", min(elements, 16)))
            size_y = int(custom.get("Size_Y", max(1, elements // max(size_x, 1))))

            rows.append({
                "Map_Type": "tags",
                "Data_Addr": _clean_addr(addr_hex),
                "Struct_Addr": "",
                "Call_Site_Addr": "",
                "Wrapper_Addr": _clean_addr(addr_hex),
                "Axis_X_Addr": "",
                "Axis_Y_Addr": "",
                "Size_X": str(size_x),
                "Size_Y": str(size_y),
                "Tag": ", ".join(data.get("tags", [])),
                "Tag_Length": length,
                "Chunks": str(chunks) if chunks else "",
            })
        return pd.DataFrame(rows)

    def _read_catalogue_csv(self, path, map_type):
        if not path or not os.path.exists(path):
            return None, f"Not found: {path}"
        try:
            df = pd.read_csv(path, dtype=str).fillna("")
        except (OSError, ValueError, pd.errors.ParserError) as exc:
            return None, f"Could not parse {os.path.basename(path)}: {exc}"
        if df.empty:
            return None, f"{os.path.basename(path)} has no rows."
        return df, ""

    def load_csv(self, map_mode, potential_mode=False):
        """Populate ``self.df``. Returns ``(ok, message)``.

        ``message`` is non-empty even when ``ok`` is True if something was
        skipped, so the caller can surface a partial-load warning instead of
        showing an empty list with no explanation.
        """
        if isinstance(map_mode, MapMode):
            map_mode = map_mode.value

        self._axis_cache.clear()
        previous_addr = self.current_map_addr
        problems = []

        if potential_mode:
            df, error = self._read_catalogue_csv(self.csv_potential_path, "potential")
            if df is None:
                self.df = pd.DataFrame()
                self.total_maps = 0
                return False, error
            df = self._normalise_catalogue(df, "potential")
            if "Map_Type" not in df.columns:
                df["Map_Type"] = "3d"
            df["Map_Type"] = df["Map_Type"].str.lower()
            if map_mode in ("3d", "2d"):
                df = df[df["Map_Type"] == map_mode]
            elif map_mode == "tags":
                df = df.iloc[0:0]
            frames = [self._apply_tags(df.reset_index(drop=True))]
        else:
            frames = []
            wanted = [map_mode] if map_mode != "all" else ["3d", "2d", "tags"]
            for mode in wanted:
                if mode == "tags":
                    tags_df = self._tags_frame()
                    if not tags_df.empty:
                        frames.append(tags_df)
                    continue
                path = self.csv_3d_path if mode == "3d" else self.csv_2d_path
                df, error = self._read_catalogue_csv(path, mode)
                if df is None:
                    problems.append(error)
                    continue
                df = self._normalise_catalogue(df, mode)
                df["Map_Type"] = mode
                frames.append(self._apply_tags(df))

        frames = [f for f in frames if not f.empty]
        self.df = pd.concat(frames, ignore_index=True).fillna("") if frames else pd.DataFrame()
        self.total_maps = len(self.df)
        self._restore_selection(previous_addr)

        if self.df.empty:
            return False, problems[0] if problems else "No maps to show for this mode."
        return True, "; ".join(problems)

    def _restore_selection(self, previous_addr):
        """Keep the same map selected across a reload when it still exists.

        Matched against every identity, so switching between Map Viewer and
        Potential Maps -- which key rows differently -- keeps your place.
        """
        self.current_index = 0

        if self.df.empty:
            self.current_map_addr = ""
            return

        target = _clean_addr(previous_addr)
        if not target:
            self.current_map_addr = ""
            return

        for column in ("Data_Addr", "Wrapper_Addr", "Struct_Addr", "Call_Site_Addr"):
            if column not in self.df.columns:
                continue
            matches = self.df.index[self.df[column] == target].tolist()
            if matches:
                self.current_index = int(matches[0])
                self.current_map_addr = target
                return

        self.current_map_addr = ""

    def current_row(self):
        if self.df.empty:
            return None
        index = min(max(self.current_index, 0), len(self.df) - 1)
        return self.df.iloc[index]

    # ------------------------------------------------------------------
    # Decoding
    # ------------------------------------------------------------------

    def read_axis(self, hex_addr, size, fmt):
        """Read ``size`` axis values, falling back to ``0..size-1`` indices.

        A null pointer is a legitimate "this axis is just an index" in Denso
        calibrations, so that case is not an error. A genuine read failure also
        falls back, but is not silent: it is cached and reported by
        :meth:`axis_is_synthetic`.
        """
        address = parse_address(hex_addr)
        if address is None or size <= 0:
            return np.arange(max(size, 0), dtype=float)

        cache_key = (address, size, formats.normalise(fmt))
        cached = self._axis_cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            values = np.array(formats.unpack_array(self.get_bin_data(), fmt, size, address), dtype=float)
        except (ValueError, BinaryUnavailable):
            values = np.arange(size, dtype=float)

        self._axis_cache[cache_key] = values
        return values

    def _formats_for(self, row):
        """``(z_format, axis_format)`` for a row, honouring per-map overrides."""
        custom = self.custom_settings_for(row)
        map_type = row.get("Map_Type", "3d")
        if map_type == "2d":
            default_z = self.z_format_2d
        else:
            default_z = self.z_format_3d
        return custom.get("z_format", default_z), custom.get("ax_format", self.ax_format)

    def read_map(self, row, as_2d=False):
        """Decode any row into ``(matrix, axis_x, axis_y, size_y, size_x, addr)``.

        Replaces the three near-identical ``read_map_3d`` / ``read_map_2d`` /
        ``read_map_tags`` methods; the differences are three lines, not three
        functions.
        """
        map_type = row.get("Map_Type", "3d")
        if map_type == "tags":
            return self._read_tag_block(row, as_2d=as_2d)

        z_format, ax_format = self._formats_for(row)
        addr_hex = _clean_addr(row.get("Data_Addr", ""))
        address = parse_address(addr_hex)
        if address is None:
            raise ValueError(f"Row has no usable data address ({row.get('Data_Addr', '')!r}).")

        size_x = max(1, int(row.get("Size_X", 1) or 1))
        size_y = max(1, int(row.get("Size_Y", 1) or 1)) if map_type == "3d" else 1

        try:
            values = formats.unpack_array(self.get_bin_data(), z_format, size_x * size_y, address)
        except ValueError as exc:
            raise ValueError(f"Map at {addr_hex} ({size_x}x{size_y}, {z_format}) {exc}") from exc

        axis_x = self.read_axis(row.get("Axis_X_Addr", ""), size_x, ax_format)
        if map_type == "3d":
            matrix = np.array(values).reshape((size_y, size_x))
            axis_y = self.read_axis(row.get("Axis_Y_Addr", ""), size_y, ax_format)
        else:
            matrix = np.array(values)
            axis_y = np.array([1.0])

        return matrix, axis_x, axis_y, size_y, size_x, addr_hex

    @contextmanager
    def _reading_from(self, baseline):
        """Temporarily decode against a different image.

        Comparison modes need the same row read from the pristine binary or from
        an externally loaded one. Doing that by hand meant assigning to private
        caches and restoring a hardcoded ``True`` afterwards, which silently did
        the wrong thing whenever the previous state was not ``True``. This saves
        and restores whatever was actually there.
        """
        previous_show = self.show_modified
        previous_cache = self._bin_data_cache
        previous_axis_cache = self._axis_cache
        self._axis_cache = {}
        try:
            if baseline is Baseline.EXTERNAL_BIN:
                if not self._reference_bin_data:
                    raise BinaryUnavailable("No external reference binary is loaded.")
                self._bin_data_cache = self._reference_bin_data
            self.show_modified = False
            yield
        finally:
            self.show_modified = previous_show
            self._bin_data_cache = previous_cache
            self._axis_cache = previous_axis_cache

    def read_map_baseline(self, row, baseline, as_2d=False):
        """Decode ``row`` from the comparison baseline, or ``None`` if there is none."""
        if baseline is Baseline.NONE:
            return None
        if baseline is Baseline.REFERENCE_MAP:
            return None  # The reference matrix is held by the UI, not re-read here.
        with self._reading_from(baseline):
            return self.read_map(row, as_2d=as_2d)

    def _read_tag_block(self, row, as_2d=False):
        z_format, _ = self._formats_for(row)
        width = formats.value_size(z_format)
        addr_hex = _clean_addr(row.get("Data_Addr", ""))
        length = int(row.get("Tag_Length", 1) or 1)

        chunks = self._parse_chunks(row.get("Chunks", ""))
        data = self.get_bin_data()
        values = []
        chunk_size_x = chunk_size_y = None

        if chunks:
            chunk_size_y = len(chunks)
            for index, (chunk_addr, chunk_len) in enumerate(chunks):
                count = chunk_len // width if width else chunk_len
                if index == 0:
                    chunk_size_x = count
                if count > 0:
                    try:
                        values.extend(formats.unpack_array(data, z_format, count, chunk_addr))
                    except ValueError:
                        # A chunk beyond the end of the binary contributes nothing
                        # rather than aborting the whole tag.
                        continue
        if not values:
            address = parse_address(addr_hex)
            if address is None:
                raise ValueError(f"Tag has no usable address ({addr_hex!r}).")
            count = max(1, length // width if width else length)
            values = list(formats.unpack_array(data, z_format, count, address))
            chunk_size_x = chunk_size_y = None

        array = np.array(values, dtype=float)

        if as_2d:
            return array, np.arange(len(array), dtype=float), np.array([0.0]), 1, len(array), addr_hex

        custom = self.custom_settings_for(row)
        default_x = chunk_size_x if chunk_size_x else min(len(array), 16)
        default_y = chunk_size_y if chunk_size_y else max(1, len(array) // max(default_x, 1))
        size_x = max(1, int(custom.get("Size_X", row.get("Size_X", default_x)) or default_x))
        size_y = max(1, int(custom.get("Size_Y", row.get("Size_Y", default_y)) or default_y))

        wanted = size_x * size_y
        if len(array) > wanted:
            array = array[:wanted]
        elif len(array) < wanted:
            array = np.pad(array, (0, wanted - len(array)), "constant")

        matrix = array.reshape((size_y, size_x))
        return matrix, np.arange(size_x, dtype=float), np.arange(size_y, dtype=float), size_y, size_x, addr_hex

    @staticmethod
    def _parse_chunks(chunks_str):
        text = str(chunks_str or "").strip()
        if not text:
            return []
        try:
            parsed = ast.literal_eval(text)
        except (ValueError, SyntaxError):
            return []
        if not isinstance(parsed, (list, tuple)):
            return []
        chunks = []
        for item in parsed:
            if isinstance(item, (list, tuple)) and len(item) == 2:
                try:
                    chunks.append((int(item[0]), int(item[1])))
                except (TypeError, ValueError):
                    continue
        return chunks

    def value_size_for(self, row):
        z_format, _ = self._formats_for(row)
        return formats.value_size(z_format)

    def map_byte_length(self, row):
        """Bytes occupied by a row's data block, or ``None`` when unknown."""
        try:
            size_x = max(1, int(row.get("Size_X", 1) or 1))
            size_y = max(1, int(row.get("Size_Y", 1) or 1)) if row.get("Map_Type") == "3d" else 1
        except (TypeError, ValueError):
            return None
        return size_x * size_y * self.value_size_for(row)

    def val_to_hex(self, value, fmt):
        try:
            return formats.pack_value(value, fmt).hex().upper()
        except (ValueError, TypeError):
            return "??"

    # ------------------------------------------------------------------
    # DTC catalogue
    # ------------------------------------------------------------------

    def load_dtc_csv(self):
        self.dtc_data = {}
        if not self.csv_dtc_path or not os.path.exists(self.csv_dtc_path):
            return False, f"DTC CSV not found: {self.csv_dtc_path}"
        try:
            df = pd.read_csv(self.csv_dtc_path, dtype=str).fillna("")
        except (OSError, ValueError, pd.errors.ParserError) as exc:
            return False, str(exc)

        for _, row in df.iterrows():
            entry = {
                "map_data_addr": _clean_addr(row.get("Map_Data_Addr", "")),
                "ram_var": _clean_addr(row.get("Target_RAM_Var", "")),
                "dtc_func": str(row.get("Potential_DTC_Func", "")).strip(),
                "confidence": str(row.get("Confidence", "")).strip(),
                "evidence": str(row.get("Evidence", "")).strip(),
            }
            # Index under both identities so a lookup works from either CSV.
            for key in (_clean_addr(row.get("Wrapper_Addr", "")), entry["map_data_addr"]):
                if key and key not in NULL_ADDRESSES:
                    self.dtc_data.setdefault(key, entry)
        return True, ""

    def dtc_for(self, row):
        for key in self.identity_keys(row):
            entry = self.dtc_data.get(key)
            if entry:
                return entry
        return None

    # ------------------------------------------------------------------
    # Projects
    # ------------------------------------------------------------------

    def save_project(self, file_path):
        data = {
            "format_version": 2,
            "bin_path": self.bin_path,
            "csv_3d_path": self.csv_3d_path,
            "csv_2d_path": self.csv_2d_path,
            "csv_dtc_path": self.csv_dtc_path,
            "csv_potential_path": self.csv_potential_path,
            "tags": self.tags,
            "hexdump_tags": self.hexdump_tags,
            "z_format_3d": self.z_format_3d,
            "z_format_2d": self.z_format_2d,
            "ax_format": self.ax_format,
            "custom_map_settings": self.custom_map_settings,
            "bin_diff": self.get_bin_diff(),
        }
        try:
            with open(file_path, "w", encoding="utf-8") as handle:
                json.dump(data, handle, indent=4, ensure_ascii=False)
        except OSError as exc:
            return False, str(exc)
        self.project_path = file_path
        return True, ""

    @staticmethod
    def _coerce_tag_entry(value):
        """Accept every tag shape ever written by an older version."""
        if isinstance(value, dict) and "tags" in value:
            return value
        if isinstance(value, list):
            return {"tags": value, "length": 1}
        if isinstance(value, str):
            return {"tags": [t.strip() for t in value.split(",") if t.strip()], "length": 1}
        return None

    def load_project(self, file_path):
        """Load a project. Returns ``(ok, message)``; message may warn on success."""
        if not os.path.exists(file_path):
            return False, f"File not found: {file_path}"
        try:
            with open(file_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            return False, f"Could not read project: {exc}"
        if not isinstance(data, dict):
            return False, "Project file is not a JSON object."

        self.bin_path = data.get("bin_path", "")
        self.csv_3d_path = data.get("csv_3d_path", DEFAULT_CSV_3D)
        self.csv_2d_path = data.get("csv_2d_path", DEFAULT_CSV_2D)
        self.csv_dtc_path = data.get("csv_dtc_path", DEFAULT_CSV_DTC)
        self.csv_potential_path = data.get("csv_potential_path", DEFAULT_CSV_POTENTIAL)

        self.tags = {}
        for key, value in (data.get("tags") or {}).items():
            entry = self._coerce_tag_entry(value)
            if entry:
                self.tags[_clean_addr(key)] = entry

        self.hexdump_tags = {}
        for key, value in (data.get("hexdump_tags") or {}).items():
            entry = self._coerce_tag_entry(value)
            if entry:
                self.hexdump_tags[_clean_addr(key)] = entry

        # Older versions wrote hexdump tags (identified by "chunks") into `tags`.
        for key in [k for k, v in self.tags.items() if "chunks" in v]:
            self.hexdump_tags[key] = self.tags.pop(key)

        self.z_format_3d = formats.normalise(data.get("z_format_3d", ">H"))
        self.z_format_2d = formats.normalise(data.get("z_format_2d", ">f"))
        self.ax_format = formats.type_char(data.get("ax_format", "f"))
        self.custom_map_settings = {
            _clean_addr(k): v for k, v in (data.get("custom_map_settings") or {}).items()
        }
        self.project_path = file_path

        warnings = []
        ok, message = self.load_binary()
        if not ok:
            warnings.append(message)
        elif message:
            warnings.append(message)

        diff = data.get("bin_diff") or {}
        applied, skipped = self.apply_bin_diff(diff)
        if diff and not ok:
            warnings.append(
                f"{len(diff)} saved byte edit(s) are held in memory and will be "
                f"applied once a binary is loaded. They are NOT lost."
            )
        elif skipped:
            warnings.append(f"{skipped} saved byte edit(s) fall outside the binary and were dropped.")

        return True, "\n\n".join(w for w in warnings if w)

    # ------------------------------------------------------------------
    # Hex-view colouring
    # ------------------------------------------------------------------

    def build_color_map(self, highlight_3d=True, highlight_2d=True, highlight_custom=True):
        """Build the byte -> map-id array backing the hex view overlays.

        Uses a numpy array with slice assignment. The previous implementation
        allocated a 1.5-million-element Python list and filled it one byte at a
        time in nested loops, which dominated every hex-view refresh.
        """
        self.bin_data = self.get_bin_data()
        self.map_dicts = {}
        self.map_dicts_tuples = {}

        if not self.bin_data:
            self.map_array = np.full(0, -1, dtype=np.int32)
            return False

        self.map_array = np.full(len(self.bin_data), -1, dtype=np.int32)
        map_id = 0
        painted_addresses = set()

        def paint(start, length, colour, label, addr):
            nonlocal map_id
            if start is None or start < 0 or length <= 0 or start + length > len(self.map_array):
                return False
            self.map_array[start:start + length] = map_id
            self.map_dicts_tuples[map_id] = {"color": colour, "tag": label, "addr": start}
            map_id += 1
            return True

        catalogue = [
            (highlight_3d, self.csv_3d_path, "3d", (0, 191, 255), self.z_format_3d),
            (highlight_2d, self.csv_2d_path, "2d", (50, 205, 50), self.z_format_2d),
        ]

        for enabled, path, map_type, colour, default_fmt in catalogue:
            if not enabled or not path or not os.path.exists(path):
                continue
            try:
                df = pd.read_csv(path, dtype=str).fillna("")
            except (OSError, ValueError, pd.errors.ParserError):
                continue
            df = self._normalise_catalogue(df, map_type)
            df["Map_Type"] = map_type

            for _, row in df.iterrows():
                address = parse_address(row.get("Data_Addr", ""))
                if address is None:
                    continue
                custom = self.custom_settings_for(row)
                width = formats.value_size(custom.get("z_format", default_fmt))
                try:
                    size_x = max(1, int(row.get("Size_X", 1) or 1))
                    size_y = max(1, int(row.get("Size_Y", 1) or 1)) if map_type == "3d" else 1
                except (TypeError, ValueError):
                    continue
                label = ", ".join(self._tags_for_addresses(*self.identity_keys(row)))
                if not label:
                    label = f"{map_type.upper()} {row['Data_Addr']} {size_x}x{size_y}"
                if paint(address, size_x * size_y * width, colour, label, address):
                    painted_addresses.add(address)

        if highlight_custom:
            for source in (self.tags, self.hexdump_tags):
                for addr_hex, data in source.items():
                    address = parse_address(addr_hex)
                    tags_list = data.get("tags", [])
                    if address is None or not tags_list or address in painted_addresses:
                        continue
                    label = ", ".join(tags_list)
                    chunks = self._parse_chunks(data.get("chunks", "")) or data.get("chunks") or []
                    if chunks:
                        first = True
                        for chunk_start, chunk_len in chunks:
                            if paint(chunk_start, chunk_len, (255, 165, 0), label if first else "", chunk_start):
                                first = False
                    else:
                        paint(address, int(data.get("length", 1) or 1), (255, 165, 0), label, address)

        return True

    # ------------------------------------------------------------------
    # Heuristic filtering
    # ------------------------------------------------------------------

    def check_map_axes(self, row):
        """True when every defined axis is monotonic.

        The discrete derivative of a real calibration axis never changes sign;
        random bytes that happen to satisfy the struct layout almost always do.
        This is what separates the ~725 real maps from the ~3,876 candidates the
        heuristic scanner emits.
        """
        _, ax_format = self._formats_for(row)

        def is_monotonic(values):
            if len(values) < 2:
                return True
            diffs = np.diff(values)
            rising = bool(np.all(diffs >= 0) and np.any(diffs > 0))
            falling = bool(np.all(diffs <= 0) and np.any(diffs < 0))
            return rising or falling

        try:
            size_x = max(1, int(row.get("Size_X", 1) or 1))
        except (TypeError, ValueError):
            return False

        if parse_address(row.get("Axis_X_Addr", "")) is not None:
            if not is_monotonic(self.read_axis(row.get("Axis_X_Addr", ""), size_x, ax_format)):
                return False

        if row.get("Map_Type") == "3d" and parse_address(row.get("Axis_Y_Addr", "")) is not None:
            try:
                size_y = max(1, int(row.get("Size_Y", 1) or 1))
            except (TypeError, ValueError):
                return False
            if not is_monotonic(self.read_axis(row.get("Axis_Y_Addr", ""), size_y, ax_format)):
                return False

        return True
