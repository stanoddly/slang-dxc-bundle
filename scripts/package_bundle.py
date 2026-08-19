#!/usr/bin/env python3

import argparse
import hashlib
import json
import os
import shutil
import stat
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path


GITHUB_API_URL = "https://api.github.com"
SLANG_REPOSITORY = "shader-slang/slang"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        while chunk := file.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def request_json(url: str, token: str) -> dict:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "slang-dxc-bundle",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request) as response:
        return json.load(response)


def download(url: str, destination: Path, token: str = "") -> None:
    headers = {"User-Agent": "slang-dxc-bundle"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request) as response, destination.open("wb") as output:
        shutil.copyfileobj(response, output)


def write_archive_entry(
    archive: zipfile.ZipFile,
    source: Path,
    destination: str,
    executable: bool = False,
) -> None:
    info = zipfile.ZipInfo(destination)
    info.compress_type = zipfile.ZIP_DEFLATED
    permissions = 0o755 if executable else 0o644
    info.external_attr = (stat.S_IFREG | permissions) << 16
    info.create_system = 3
    archive.writestr(info, source.read_bytes())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slang-tag", required=True)
    parser.add_argument("--slang-version", required=True)
    parser.add_argument("--dxc-tag", required=True)
    parser.add_argument("--dxc-commit", required=True)
    parser.add_argument("--platform", required=True)
    parser.add_argument("--slang-asset", required=True)
    parser.add_argument("--dxcompiler", type=Path, required=True)
    parser.add_argument("--dxc-source", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--token", default=os.environ.get("GITHUB_TOKEN", ""))
    arguments = parser.parse_args()

    if not arguments.dxcompiler.is_file():
        raise RuntimeError(f"DXC library does not exist: {arguments.dxcompiler}")

    dxc_license = arguments.dxc_source / "LICENSE.TXT"
    dxc_notices = arguments.dxc_source / "ThirdPartyNotices.txt"
    if not dxc_license.is_file() or not dxc_notices.is_file():
        raise RuntimeError("DXC source checkout is missing required license files")

    release = request_json(
        f"{GITHUB_API_URL}/repos/{SLANG_REPOSITORY}/releases/tags/{arguments.slang_tag}",
        arguments.token,
    )
    matching_assets = [
        asset for asset in release["assets"] if asset["name"] == arguments.slang_asset
    ]
    if len(matching_assets) != 1:
        raise RuntimeError(
            f"Expected one {arguments.slang_asset} asset in {arguments.slang_tag}"
        )

    asset = matching_assets[0]
    expected_digest = asset.get("digest")
    if not expected_digest or not expected_digest.startswith("sha256:"):
        raise RuntimeError(f"Upstream asset {arguments.slang_asset} has no SHA-256 digest")

    library_destinations = {
        "windows-x86_64": "bin/dxcompiler.dll",
        "linux-x86_64": "lib/libdxcompiler.so",
        "linux-aarch64": "lib/libdxcompiler.so",
        "macos-x86_64": "lib/libdxcompiler.dylib",
        "macos-aarch64": "lib/libdxcompiler.dylib",
    }
    try:
        library_destination = library_destinations[arguments.platform]
    except KeyError as error:
        raise RuntimeError(f"Unsupported platform: {arguments.platform}") from error

    arguments.output_directory.mkdir(parents=True, exist_ok=True)
    bundle_name = (
        f"slang-{arguments.slang_version}-dxc-"
        f"{arguments.dxc_tag.removeprefix('v')}-{arguments.platform}.zip"
    )
    bundle_path = arguments.output_directory / bundle_name

    with tempfile.TemporaryDirectory() as temporary_directory:
        upstream_archive = Path(temporary_directory) / arguments.slang_asset
        download(asset["browser_download_url"], upstream_archive)
        actual_digest = sha256_file(upstream_archive)
        if actual_digest != expected_digest.removeprefix("sha256:"):
            raise RuntimeError(
                f"Digest mismatch for {arguments.slang_asset}: "
                f"expected {expected_digest}, got sha256:{actual_digest}"
            )

        shutil.copyfile(upstream_archive, bundle_path)

    manifest = {
        "schemaVersion": 1,
        "platform": arguments.platform,
        "slang": {
            "repository": SLANG_REPOSITORY,
            "tag": arguments.slang_tag,
            "asset": arguments.slang_asset,
            "assetDigest": expected_digest,
        },
        "dxc": {
            "repository": "microsoft/DirectXShaderCompiler",
            "tag": arguments.dxc_tag,
            "commit": arguments.dxc_commit,
            "library": library_destination,
            "libraryDigest": f"sha256:{sha256_file(arguments.dxcompiler)}",
        },
    }

    with zipfile.ZipFile(bundle_path, "a", allowZip64=True) as archive:
        existing_names = set(archive.namelist())
        additions = {
            library_destination,
            "LICENSES/DXC-LICENSE.txt",
            "LICENSES/DXC-ThirdPartyNotices.txt",
            "SLANG-DXC-BUNDLE.json",
        }
        duplicates = sorted(existing_names & additions)
        if duplicates:
            raise RuntimeError(
                "Upstream archive already contains bundle destinations: "
                + ", ".join(duplicates)
            )

        write_archive_entry(
            archive,
            arguments.dxcompiler,
            library_destination,
            executable=not arguments.platform.startswith("windows-"),
        )
        write_archive_entry(
            archive, dxc_license, "LICENSES/DXC-LICENSE.txt"
        )
        write_archive_entry(
            archive, dxc_notices, "LICENSES/DXC-ThirdPartyNotices.txt"
        )
        archive.writestr(
            "SLANG-DXC-BUNDLE.json",
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        )

    print(bundle_path)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RuntimeError as error:
        print(f"error: {error}", file=sys.stderr)
        sys.exit(1)
