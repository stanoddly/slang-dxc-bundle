#!/usr/bin/env python3

import argparse
import sys
import zipfile
from pathlib import Path

from toolchain_layout import RUNTIME_IDENTIFIERS, SDK_PACKAGE_ID, package_file_entries, read_nuspec


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--package-version", required=True)
    parser.add_argument("--maximum-size", type=int, required=True)
    arguments = parser.parse_args()

    if not arguments.package.is_file():
        raise RuntimeError(f"Package does not exist: {arguments.package}")
    package_size = arguments.package.stat().st_size
    if package_size >= arguments.maximum_size:
        raise RuntimeError(
            f"Package is {package_size} bytes; limit is {arguments.maximum_size} bytes"
        )

    version_props_entry = f"Sdk/{SDK_PACKAGE_ID}.Version.props"
    guard_entry = f"buildTransitive/{SDK_PACKAGE_ID}.targets"
    with zipfile.ZipFile(arguments.package, "r") as package:
        entries = package_file_entries(package)
        package_id, package_version, dependencies = read_nuspec(package)
        if package_id != SDK_PACKAGE_ID:
            raise RuntimeError(f"Expected package ID {SDK_PACKAGE_ID}, got {package_id}")
        if package_version != arguments.package_version:
            raise RuntimeError(
                f"Expected package version {arguments.package_version}, got {package_version}"
            )
        if dependencies:
            raise RuntimeError("SDK package must not have package dependencies")

        required_package_files = {
            "README.md",
            "PACKAGE-LICENSE.txt",
            "LICENSE",
            "Sdk/Sdk.props",
            "Sdk/Sdk.targets",
            version_props_entry,
            guard_entry,
        }
        missing_package_files = sorted(required_package_files - entries.keys())
        if missing_package_files:
            raise RuntimeError(
                "Package is missing required files: " + ", ".join(missing_package_files)
            )
        unexpected_files = sorted(entries.keys() - required_package_files - {
            name for name in entries if name.startswith(("_rels/", "package/")) or name.endswith((".nuspec", "[Content_Types].xml"))
        })
        if unexpected_files:
            raise RuntimeError("Package contains unexpected files: " + ", ".join(unexpected_files))

        version_props = package.read(version_props_entry).decode("utf-8")
        expected_version_text = f"<SlangDxcToolchainVersion>{arguments.package_version}</SlangDxcToolchainVersion>"
        if expected_version_text not in version_props:
            raise RuntimeError(f"Version props do not pin {arguments.package_version}")

        sdk_props = package.read("Sdk/Sdk.props").decode("utf-8")
        for required_text in (
            f'<Import Project="{SDK_PACKAGE_ID}.Version.props" />',
            "<_SlangDxcToolchainSdkImported>true</_SlangDxcToolchainSdkImported>",
            *(f">{rid}</_SlangDxcToolchainHostRid>" for rid in RUNTIME_IDENTIFIERS.values()),
            '<PackageReference Include="$(_SlangDxcToolchainPackageId)" Version="[$(SlangDxcToolchainVersion)]" PrivateAssets="all" />',
            '<PackageVersion Remove="$(_SlangDxcToolchainPackageId)" />',
            '<PackageVersion Include="$(_SlangDxcToolchainPackageId)" Version="[$(SlangDxcToolchainVersion)]" />',
            '<PackageReference Include="$(_SlangDxcToolchainPackageId)" PrivateAssets="all" />',
        ):
            if required_text not in sdk_props:
                raise RuntimeError(f"Sdk.props is missing: {required_text}")

        sdk_targets = package.read("Sdk/Sdk.targets").decode("utf-8")
        for required_text in (
            "does not support this build host",
            "is not restored",
            "More than one SlangDxcBundle.Toolchain platform package is restored",
            "but this build host is",
        ):
            if required_text not in sdk_targets:
                raise RuntimeError(f"Sdk.targets is missing the check: {required_text}")

        guard = package.read(guard_entry).decode("utf-8")
        if "is an MSBuild project SDK" not in guard or "'$(_SlangDxcToolchainSdkImported)' != 'true'" not in guard:
            raise RuntimeError("buildTransitive guard does not reject a PackageReference")

    print(f"Verified {arguments.package} ({package_size} bytes)")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (KeyError, RuntimeError, ValueError, zipfile.BadZipFile) as error:
        print(f"error: {error}", file=sys.stderr)
        sys.exit(1)
