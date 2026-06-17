from __future__ import annotations

import base64
import csv
import hashlib
import os
import pathlib
import tarfile
import tempfile
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


NAME = "labelohlcv"
VERSION = "0.1.0"
DIST_INFO = f"{NAME}-{VERSION}.dist-info"
WHEEL_NAME = f"{NAME}-{VERSION}-py3-none-any.whl"
SDIST_NAME = f"{NAME}-{VERSION}.tar.gz"
ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src" / NAME
SRC_ROOT = ROOT / "src"


def get_requires_for_build_wheel(config_settings=None):  # noqa: D401
    return []


def get_requires_for_build_sdist(config_settings=None):  # noqa: D401
    return []


def get_requires_for_build_editable(config_settings=None):  # noqa: D401
    return []


def prepare_metadata_for_build_wheel(metadata_directory, config_settings=None):
    dist_info = Path(metadata_directory) / DIST_INFO
    dist_info.mkdir(parents=True, exist_ok=True)
    _write_metadata_files(dist_info)
    return DIST_INFO


def prepare_metadata_for_build_editable(metadata_directory, config_settings=None):
    return prepare_metadata_for_build_wheel(metadata_directory, config_settings)


def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
    wheel_path = Path(wheel_directory) / WHEEL_NAME
    return _build_wheel(wheel_path, editable=False)


def build_editable(wheel_directory, config_settings=None, metadata_directory=None):
    wheel_path = Path(wheel_directory) / WHEEL_NAME
    return _build_wheel(wheel_path, editable=True)


def build_sdist(sdist_directory, config_settings=None):
    sdist_path = Path(sdist_directory) / SDIST_NAME
    base = f"{NAME}-{VERSION}"

    files = [
        "pyproject.toml",
        "README.md",
        "build_backend.py",
        "src/labelohlcv/__init__.py",
        "src/labelohlcv/__main__.py",
        "src/labelohlcv/cli.py",
        "src/labelohlcv/modules/base.py",
        "src/labelohlcv/modules/__init__.py",
        "src/labelohlcv/modules/default.py",
        "src/labelohlcv/modules/vn30f1m.py",
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_root = Path(tmpdir) / base
        tmp_root.mkdir(parents=True, exist_ok=True)

        for rel in files:
            src = ROOT / rel
            dst = tmp_root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(src.read_bytes())

        with tarfile.open(sdist_path, "w:gz") as tf:
            tf.add(tmp_root, arcname=base)

    return sdist_path.name


def _metadata_bytes() -> bytes:
    text = (
        "Metadata-Version: 2.1\n"
        f"Name: {NAME}\n"
        f"Version: {VERSION}\n"
        "Summary: Utilities for labeling OHLCV market data.\n"
        "License: MIT\n"
        "Requires-Python: >=3.10\n"
    )
    return text.encode("utf-8")


def _write_metadata_files(dist_info: Path) -> None:
    (dist_info / "METADATA").write_bytes(_metadata_bytes())
    (dist_info / "WHEEL").write_bytes(_wheel_bytes())
    (dist_info / "entry_points.txt").write_bytes(_entry_points_bytes())


def _wheel_bytes() -> bytes:
    text = (
        "Wheel-Version: 1.0\n"
        "Generator: build_backend\n"
        "Root-Is-Purelib: true\n"
        "Tag: py3-none-any\n"
    )
    return text.encode("utf-8")


def _entry_points_bytes() -> bytes:
    return b"[console_scripts]\nlabelohlcv = labelohlcv.cli:main\n"


def _editable_pth_bytes() -> bytes:
    return f"{SRC_ROOT}\n".encode("utf-8")


def _build_wheel(wheel_path: Path, *, editable: bool) -> str:
    record_rows: list[tuple[str, str, str]] = []

    with ZipFile(wheel_path, "w", compression=ZIP_DEFLATED) as zf:
        if editable:
            _write_zip_file(zf, f"{NAME}.pth", _editable_pth_bytes(), record_rows)
        else:
            wheel_files = {
                f"{NAME}/__init__.py": SRC / "__init__.py",
                f"{NAME}/__main__.py": SRC / "__main__.py",
                f"{NAME}/cli.py": SRC / "cli.py",
                f"{NAME}/modules/base.py": SRC / "modules" / "base.py",
                f"{NAME}/modules/__init__.py": SRC / "modules" / "__init__.py",
                f"{NAME}/modules/default.py": SRC / "modules" / "default.py",
                f"{NAME}/modules/vn30f1m.py": SRC / "modules" / "vn30f1m.py",
            }

            for arcname, src_path in wheel_files.items():
                _write_zip_file(zf, arcname, src_path.read_bytes(), record_rows)

        dist_info_files = {
            f"{DIST_INFO}/METADATA": _metadata_bytes(),
            f"{DIST_INFO}/WHEEL": _wheel_bytes(),
            f"{DIST_INFO}/entry_points.txt": _entry_points_bytes(),
        }

        for arcname, payload in dist_info_files.items():
            _write_zip_file(zf, arcname, payload, record_rows)

        record_rows.append((f"{DIST_INFO}/RECORD", "", ""))
        zf.writestr(f"{DIST_INFO}/RECORD", _record_bytes(record_rows))

    return wheel_path.name


def _write_zip_file(zf: ZipFile, arcname: str, payload: bytes, record_rows: list[tuple[str, str, str]]) -> None:
    zf.writestr(arcname, payload)
    digest = hashlib.sha256(payload).digest()
    hash_text = "sha256=" + base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    record_rows.append((arcname, hash_text, str(len(payload))))


def _record_bytes(record_rows: list[tuple[str, str, str]]) -> bytes:
    buffer = StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerows(record_rows)
    return buffer.getvalue().encode("utf-8")
