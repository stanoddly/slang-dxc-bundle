#!/usr/bin/env python3

import argparse
import json
import sys
import zipfile
from pathlib import Path

from toolchain_layout import (
    PLATFORMS,
    RUNTIME_IDENTIFIERS,
    binary_entries,
    package_entry,
    package_file_entries,
    platform_package_id,
    read_nuspec,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--platform", choices=PLATFORMS, required=True)
    parser.add_argument("--package-version", required=True)
    parser.add_argument("--slang-version", required=True)
    parser.add_argument("--dxc-version", required=True)
    parser.add_argument("--maximum-size", type=int, required=True)
    arguments = parser.parse_args()

    if not arguments.package.is_file():
        raise RuntimeError(f"Package does not exist: {arguments.package}")
    package_size = arguments.package.stat().st_size
    if package_size >= arguments.maximum_size:
        raise RuntimeError(
            f"Package is {package_size} bytes; limit is {arguments.maximum_size} bytes"
        )

    expected_package_id = platform_package_id(arguments.platform)
    props_entry = f"buildTransitive/{expected_package_id}.props"
    with zipfile.ZipFile(arguments.package, "r") as package:
        entries = package_file_entries(package)
        package_id, package_version, dependencies = read_nuspec(package)
        if package_id != expected_package_id:
            raise RuntimeError(f"Expected package ID {expected_package_id}, got {package_id}")
        if package_version != arguments.package_version:
            raise RuntimeError(
                f"Expected package version {arguments.package_version}, got {package_version}"
            )
        if dependencies:
            raise RuntimeError("Platform package must not have package dependencies")

        required_package_files = {"README.md", "PACKAGE-LICENSE.txt", "LICENSE", props_entry}
        missing_package_files = sorted(required_package_files - entries.keys())
        if missing_package_files:
            raise RuntimeError(
                "Package is missing required files: " + ", ".join(missing_package_files)
            )
        unexpected_build_assets = sorted(
            name
            for name in entries
            if name.startswith(("build/", "buildTransitive/", "buildMultitargeting/", "Sdk/"))
            and name != props_entry
        )
        if unexpected_build_assets:
            raise RuntimeError(
                "Package contains unexpected build assets: " + ", ".join(unexpected_build_assets)
            )

        props = package.read(props_entry).decode("utf-8")
        for required_text in (
            "<SlangDxcToolchainRoot ",
            "tools/slang/",
            f"<SlangDxcToolchainPlatform Condition=\"'$(SlangDxcToolchainPlatform)' == ''\">{arguments.platform}<",
            f"<SlangDxcToolchainDirectory Condition=\"'$(SlangDxcToolchainDirectory)' == ''\">$(SlangDxcToolchainRoot){arguments.platform}/<",
            f"<SlangDxcToolchainPackage Include=\"{RUNTIME_IDENTIFIERS[arguments.platform]}\" />",
        ):
            if required_text not in props:
                raise RuntimeError(f"buildTransitive props are missing: {required_text}")

        prefix = f"tools/slang/{arguments.platform}/"
        platform_entries = {name.removeprefix(prefix) for name in entries if name.startswith(prefix)}
        required_entries = set(binary_entries(arguments.platform, arguments.slang_version))
        required_entries.update({"LICENSE", "SLANG-DXC-BUNDLE.json"})
        missing_entries = sorted(required_entries - platform_entries)
        if missing_entries:
            raise RuntimeError(
                f"{arguments.platform} is missing required entries: " + ", ".join(missing_entries)
            )
        if not any(name.startswith("LICENSES/") for name in platform_entries):
            raise RuntimeError(f"{arguments.platform} has no LICENSES entries")
        unexpected_entries = sorted(
            name
            for name in platform_entries
            if name not in required_entries and not name.startswith("LICENSES/")
        )
        if unexpected_entries:
            raise RuntimeError(
                f"{arguments.platform} has unexpected entries: " + ", ".join(unexpected_entries)
            )
        if any(name.endswith("slang-glsl-module.bin") for name in platform_entries):
            raise RuntimeError(f"{arguments.platform} contains a generated GLSL module cache")

        manifest = json.loads(package.read(package_entry(arguments.platform, "SLANG-DXC-BUNDLE.json")))
        if manifest.get("platform") != arguments.platform:
            raise RuntimeError(f"{arguments.platform} manifest has the wrong platform")
        if str(manifest["slang"]["tag"]).removeprefix("v") != arguments.slang_version:
            raise RuntimeError(f"{arguments.platform} manifest has the wrong Slang version")
        if str(manifest["dxc"]["tag"]).removeprefix("v") != arguments.dxc_version:
            raise RuntimeError(f"{arguments.platform} manifest has the wrong DXC version")

        other_tool_entries = sorted(
            name for name in entries if name.startswith("tools/") and not name.startswith(prefix)
        )
        if other_tool_entries:
            raise RuntimeError(
                "Package contains files outside its platform: " + ", ".join(other_tool_entries)
            )

    print(f"Verified {arguments.package} ({package_size} bytes)")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (KeyError, RuntimeError, ValueError, zipfile.BadZipFile) as error:
        print(f"error: {error}", file=sys.stderr)
        sys.exit(1)
