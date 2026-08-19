#!/usr/bin/env python3

import argparse
import json
import sys
import zipfile
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree

from toolchain_layout import PLATFORMS, binary_entries, package_entry


PACKAGE_ID = "Stanoddly.SlangDxc.Toolchain"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", type=Path, required=True)
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

    with zipfile.ZipFile(arguments.package, "r") as package:
        entries = {
            entry.filename: entry
            for entry in package.infolist()
            if not entry.is_dir()
        }
        file_entry_count = len(
            [entry for entry in package.infolist() if not entry.is_dir()]
        )
        if len(entries) != file_entry_count:
            raise RuntimeError("Package contains duplicate file entries")

        nuspec_names = [name for name in entries if name.endswith(".nuspec")]
        if len(nuspec_names) != 1:
            raise RuntimeError("Package must contain exactly one .nuspec file")
        nuspec = ElementTree.fromstring(package.read(nuspec_names[0]))
        namespace = {"n": nuspec.tag.partition("}")[0].removeprefix("{")}
        package_id = nuspec.findtext("n:metadata/n:id", namespaces=namespace)
        package_version = nuspec.findtext("n:metadata/n:version", namespaces=namespace)
        if package_id != PACKAGE_ID:
            raise RuntimeError(f"Expected package ID {PACKAGE_ID}, got {package_id}")
        if package_version != arguments.package_version:
            raise RuntimeError(
                f"Expected package version {arguments.package_version}, "
                f"got {package_version}"
            )
        dependencies = nuspec.findall(".//n:dependency", namespaces=namespace)
        if dependencies:
            raise RuntimeError("Toolchain package must not have package dependencies")

        required_package_files = {
            "README.md",
            "PACKAGE-LICENSE.txt",
            "LICENSE",
            f"buildTransitive/{PACKAGE_ID}.props",
        }
        missing_package_files = sorted(required_package_files - entries.keys())
        if missing_package_files:
            raise RuntimeError(
                "Package is missing required files: " + ", ".join(missing_package_files)
            )
        unexpected_build_assets = sorted(
            name
            for name in entries
            if name.startswith(("build/", "buildTransitive/", "buildMultitargeting/"))
            and name != f"buildTransitive/{PACKAGE_ID}.props"
        )
        if unexpected_build_assets:
            raise RuntimeError(
                "Package contains unexpected build assets: "
                + ", ".join(unexpected_build_assets)
            )

        props = package.read(f"buildTransitive/{PACKAGE_ID}.props").decode("utf-8")
        if "SlangDxcToolchainRoot" not in props or "tools\\slang" not in props:
            raise RuntimeError("buildTransitive props do not expose the toolchain root")

        for platform in PLATFORMS:
            prefix = f"tools/slang/{platform}/"
            platform_entries = {
                name.removeprefix(prefix)
                for name in entries
                if name.startswith(prefix)
            }
            required_entries = set(binary_entries(platform, arguments.slang_version))
            required_entries.update({"LICENSE", "SLANG-DXC-BUNDLE.json"})
            missing_entries = sorted(required_entries - platform_entries)
            if missing_entries:
                raise RuntimeError(
                    f"{platform} is missing required entries: "
                    + ", ".join(missing_entries)
                )
            if not any(name.startswith("LICENSES/") for name in platform_entries):
                raise RuntimeError(f"{platform} has no LICENSES entries")
            unexpected_entries = sorted(
                name
                for name in platform_entries
                if name not in required_entries and not name.startswith("LICENSES/")
            )
            if unexpected_entries:
                raise RuntimeError(
                    f"{platform} has unexpected entries: "
                    + ", ".join(unexpected_entries)
                )
            if any(name.endswith("slang-glsl-module.bin") for name in platform_entries):
                raise RuntimeError(f"{platform} contains a generated GLSL module cache")

            manifest_path = package_entry(platform, "SLANG-DXC-BUNDLE.json")
            manifest = json.loads(package.read(manifest_path))
            actual_slang_version = str(manifest["slang"]["tag"]).removeprefix("v")
            actual_dxc_version = str(manifest["dxc"]["tag"]).removeprefix("v")
            if manifest.get("platform") != platform:
                raise RuntimeError(f"{platform} manifest has the wrong platform")
            if actual_slang_version != arguments.slang_version:
                raise RuntimeError(f"{platform} manifest has the wrong Slang version")
            if actual_dxc_version != arguments.dxc_version:
                raise RuntimeError(f"{platform} manifest has the wrong DXC version")

        tools_prefix = PurePosixPath("tools", "slang").as_posix() + "/"
        unknown_platforms = sorted(
            {
                name.removeprefix(tools_prefix).partition("/")[0]
                for name in entries
                if name.startswith(tools_prefix)
            }
            - set(PLATFORMS)
        )
        if unknown_platforms:
            raise RuntimeError(
                "Package contains unknown platforms: " + ", ".join(unknown_platforms)
            )

    print(f"Verified {arguments.package} ({package_size} bytes)")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (KeyError, RuntimeError, ValueError, zipfile.BadZipFile) as error:
        print(f"error: {error}", file=sys.stderr)
        sys.exit(1)
