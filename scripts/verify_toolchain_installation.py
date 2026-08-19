#!/usr/bin/env python3

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

from toolchain_layout import PLATFORMS, binary_entries, compiler_entry


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--slang-version", required=True)
    parser.add_argument("--dxc-version", required=True)
    parser.add_argument("--expected-platform", choices=PLATFORMS)
    arguments = parser.parse_args()

    if not arguments.root.is_dir():
        raise RuntimeError(f"Toolchain root does not exist: {arguments.root}")

    digest = hashlib.sha256()
    for platform in PLATFORMS:
        platform_root = arguments.root / platform
        if not platform_root.is_dir():
            raise RuntimeError(f"Toolchain platform does not exist: {platform_root}")
        for entry in binary_entries(platform, arguments.slang_version):
            path = platform_root / Path(entry)
            if not path.is_file():
                raise RuntimeError(f"Toolchain file does not exist: {path}")
        if not (platform_root / "LICENSE").is_file():
            raise RuntimeError(
                f"Toolchain license does not exist: {platform_root / 'LICENSE'}"
            )
        licenses = [
            path for path in (platform_root / "LICENSES").rglob("*") if path.is_file()
        ]
        if not licenses:
            raise RuntimeError(
                f"Toolchain licenses do not exist: {platform_root / 'LICENSES'}"
            )
        manifest_path = platform_root / "SLANG-DXC-BUNDLE.json"
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except FileNotFoundError as error:
            raise RuntimeError(
                f"Toolchain manifest does not exist: {manifest_path}"
            ) from error
        if manifest.get("platform") != platform:
            raise RuntimeError(f"{manifest_path} has the wrong platform")
        if str(manifest["slang"]["tag"]).removeprefix("v") != arguments.slang_version:
            raise RuntimeError(f"{manifest_path} has the wrong Slang version")
        if str(manifest["dxc"]["tag"]).removeprefix("v") != arguments.dxc_version:
            raise RuntimeError(f"{manifest_path} has the wrong DXC version")

    generated_caches = sorted(arguments.root.rglob("slang-glsl-module.bin"))
    if generated_caches:
        raise RuntimeError(
            "Toolchain installation contains generated caches: "
            + ", ".join(str(path) for path in generated_caches)
        )

    if arguments.expected_platform:
        compiler = arguments.root / arguments.expected_platform / compiler_entry(
            arguments.expected_platform
        )
        if os.name != "nt" and not os.access(compiler, os.X_OK):
            raise RuntimeError(f"Toolchain compiler is not executable: {compiler}")

    for path in sorted(arguments.root.rglob("*")):
        if not path.is_file():
            continue
        relative_path = path.relative_to(arguments.root).as_posix()
        digest.update(relative_path.encode("utf-8"))
        digest.update(b"\0")
        with path.open("rb") as file:
            while chunk := file.read(1024 * 1024):
                digest.update(chunk)
        digest.update(b"\0")

    print(digest.hexdigest())
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (KeyError, RuntimeError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        sys.exit(1)
