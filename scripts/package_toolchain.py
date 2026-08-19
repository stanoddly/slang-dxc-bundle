#!/usr/bin/env python3

import argparse
import copy
import hashlib
import json
import sys
import zipfile
from collections import Counter
from pathlib import Path

from toolchain_layout import (
    PLATFORMS,
    binary_entries,
    dxcompiler_entry,
    toolchain_archive_name,
)


def sha256_stream(stream) -> str:
    digest = hashlib.sha256()
    while chunk := stream.read(1024 * 1024):
        digest.update(chunk)
    return digest.hexdigest()


def sha256_file(path: Path) -> str:
    with path.open("rb") as file:
        return sha256_stream(file)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--slang-version", required=True)
    parser.add_argument("--platform", choices=PLATFORMS, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    arguments = parser.parse_args()

    if not arguments.bundle.is_file():
        raise RuntimeError(f"Bundle does not exist: {arguments.bundle}")

    with zipfile.ZipFile(arguments.bundle, "r") as bundle:
        names = [entry.filename for entry in bundle.infolist()]
        name_counts = Counter(names)
        duplicate_names = sorted(
            name for name, count in name_counts.items() if count > 1
        )
        if duplicate_names:
            raise RuntimeError(
                "Bundle contains duplicate entries: " + ", ".join(duplicate_names)
            )

        try:
            manifest = json.loads(bundle.read("SLANG-DXC-BUNDLE.json"))
        except KeyError as error:
            raise RuntimeError("Bundle has no SLANG-DXC-BUNDLE.json") from error
        except json.JSONDecodeError as error:
            raise RuntimeError("Bundle manifest is not valid JSON") from error

        if manifest.get("schemaVersion") != 1:
            raise RuntimeError("Bundle manifest has an unsupported schema version")
        if manifest.get("platform") != arguments.platform:
            raise RuntimeError(
                f"Expected platform {arguments.platform}, got {manifest.get('platform')}"
            )

        slang = manifest.get("slang", {})
        actual_slang_version = str(slang.get("tag", "")).removeprefix("v")
        if actual_slang_version != arguments.slang_version:
            raise RuntimeError(
                f"Expected Slang {arguments.slang_version}, got {actual_slang_version}"
            )

        dxc = manifest.get("dxc", {})
        dxc_version = str(dxc.get("tag", "")).removeprefix("v")
        if not dxc_version:
            raise RuntimeError("Bundle manifest has no DXC tag")

        expected_dxcompiler = dxcompiler_entry(arguments.platform)
        if dxc.get("library") != expected_dxcompiler:
            raise RuntimeError(
                f"Expected DXC library {expected_dxcompiler}, got {dxc.get('library')}"
            )

        try:
            with bundle.open(expected_dxcompiler) as library:
                actual_library_digest = f"sha256:{sha256_stream(library)}"
        except KeyError as error:
            raise RuntimeError(
                f"Bundle is missing DXC library: {expected_dxcompiler}"
            ) from error
        if dxc.get("libraryDigest") != actual_library_digest:
            raise RuntimeError(
                "DXC library digest does not match SLANG-DXC-BUNDLE.json"
            )

        licenses = sorted(
            name
            for name in names
            if name.startswith("LICENSES/") and not name.endswith("/")
        )
        if "LICENSE" not in name_counts or not licenses:
            raise RuntimeError("Bundle is missing required license material")

        required_entries = binary_entries(arguments.platform, arguments.slang_version)
        missing_entries = sorted(
            name for name in required_entries if name not in name_counts
        )
        if missing_entries:
            raise RuntimeError(
                "Bundle is missing required toolchain entries: "
                + ", ".join(missing_entries)
            )

        selected_entries = (
            *required_entries,
            "LICENSE",
            *licenses,
            "SLANG-DXC-BUNDLE.json",
        )

        arguments.output_directory.mkdir(parents=True, exist_ok=True)
        archive_path = arguments.output_directory / toolchain_archive_name(
            arguments.slang_version,
            dxc_version,
            arguments.platform,
        )
        with zipfile.ZipFile(
            archive_path,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
            allowZip64=True,
        ) as archive:
            for name in selected_entries:
                source_info = bundle.getinfo(name)
                destination_info = copy.copy(source_info)
                if destination_info.date_time < (1980, 1, 2, 0, 0, 0):
                    destination_info.date_time = (1980, 1, 2, 0, 0, 0)
                with bundle.open(source_info) as source:
                    archive.writestr(
                        destination_info,
                        source.read(),
                        compresslevel=9,
                    )

    archive_digest = sha256_file(archive_path)
    checksum_path = archive_path.with_suffix(archive_path.suffix + ".sha256")
    checksum_path.write_text(
        f"{archive_digest}  {archive_path.name}\n",
        encoding="utf-8",
    )
    print(archive_path)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (RuntimeError, zipfile.BadZipFile) as error:
        print(f"error: {error}", file=sys.stderr)
        sys.exit(1)
