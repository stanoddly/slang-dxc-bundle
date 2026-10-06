#!/usr/bin/env python3

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

from toolchain_layout import PLATFORMS, package_ids


GITHUB_API_URL = "https://api.github.com"
NUGET_FLAT_CONTAINER_URL = "https://api.nuget.org/v3-flatcontainer"
SLANG_REPOSITORY = "shader-slang/slang"
# Versions up to this one are single all-platform packages under the SDK's ID; nuget.org versions are immutable, so they stay legacy.
LAST_LEGACY_VERSION = "2026.18.0"
REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
PIN_FILE = "release.json"
# Changes under these paths change what a release contains or how it is verified; each one raises the revision. Mirrored by the push paths in release.yml.
RELEASE_PATHS = (PIN_FILE, "packaging", "scripts", ".github/workflows/release.yml")


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


def request_text(url: str, token: str) -> str:
    headers = {"User-Agent": "slang-dxc-bundle"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request) as response:
        return response.read().decode("utf-8")


def extract_cmake_value(source: str, variable: str) -> str:
    pattern = rf'set\(\s*{re.escape(variable)}\s+"([^"]+)"\s*\)'
    match = re.search(pattern, source, flags=re.MULTILINE)
    if match is None:
        raise RuntimeError(f"Unable to find {variable} in Slang's FetchDXC.cmake")
    return match.group(1)


def read_pinned_slang_tag(repository_root: Path = REPOSITORY_ROOT) -> str:
    return json.loads((repository_root / PIN_FILE).read_text(encoding="utf-8"))["slang_tag"]


def get_slang_release(tag: str, token: str) -> dict:
    return request_json(f"{GITHUB_API_URL}/repos/{SLANG_REPOSITORY}/releases/tags/{tag}", token)


def validate_slang_release(slang_release: dict) -> None:
    slang_tag = slang_release["tag_name"]
    if slang_release["draft"]:
        raise RuntimeError(f"Slang release {slang_tag} is a draft")

    slang_version = slang_tag.removeprefix("v")
    expected_assets = {f"slang-{slang_version}-{platform}.zip" for platform in PLATFORMS}
    missing_assets = sorted(expected_assets - {asset["name"] for asset in slang_release["assets"]})
    if missing_assets:
        raise RuntimeError(f"Slang release {slang_tag} is missing required assets: " + ", ".join(missing_assets))


def git(repository_root: Path, *arguments: str) -> str:
    return subprocess.run(["git", "-C", str(repository_root), *arguments], check=True, capture_output=True, text=True).stdout.strip()


# Git height: commits touching the release paths since the pin first named the current Slang tag, counting that commit as 1; also returns the last such commit.
# Counting from the first pin keeps revisions rising when the pin returns to an earlier tag, so a released version is never reused.
def release_revision(repository_root: Path = REPOSITORY_ROOT) -> tuple[int, str]:
    if git(repository_root, "rev-parse", "--is-shallow-repository") == "true":
        raise RuntimeError("The release revision needs the full history; check out with fetch-depth: 0")

    def pinned_tag(commit: str) -> str:
        return json.loads(git(repository_root, "show", f"{commit}:{PIN_FILE}"))["slang_tag"]

    slang_tag = pinned_tag("HEAD")
    pin_commits = git(repository_root, "log", "--reverse", "--diff-filter=d", "--format=%H", "--", PIN_FILE).splitlines()
    pin_commit = next(commit for commit in pin_commits if pinned_tag(commit) == slang_tag)
    release_commit = git(repository_root, "log", "-1", "--format=%H", "--", *RELEASE_PATHS)
    height = int(git(repository_root, "rev-list", "--count", f"{pin_commit}..{release_commit}", "--", *RELEASE_PATHS))
    return height + 1, release_commit


def get_release(repository: str, tag: str, token: str) -> dict | None:
    url = f"{GITHUB_API_URL}/repos/{repository}/releases/tags/{tag}"
    try:
        return request_json(url, token)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return None
        raise


def nuget_package_exists(package_id: str, version: str) -> bool:
    package_id_lower = package_id.lower()
    url = f"{NUGET_FLAT_CONTAINER_URL}/{package_id_lower}/index.json"
    try:
        response = request_json(url, "")
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return False
        raise

    versions = {str(value).lower() for value in response.get("versions", [])}
    return version.lower() in versions


def missing_toolchain_packages(version: str, package_exists=nuget_package_exists) -> list[str]:
    return [package_id for package_id in package_ids() if not package_exists(package_id, version)]


def nuget_version_key(version: str) -> tuple:
    numeric, _, prerelease = version.partition("-")
    components = [int(component) for component in numeric.split(".")]
    while len(components) < 4:
        components.append(0)
    # A prerelease sorts below its release; an empty marker ranks highest.
    return (tuple(components), prerelease == "", prerelease)


def is_legacy_toolchain_version(version: str) -> bool:
    return nuget_version_key(version) <= nuget_version_key(LAST_LEGACY_VERSION)


def normalize_nuget_version(version: str) -> str:
    match = re.fullmatch(
        r"(?P<numeric>[0-9]+(?:\.[0-9]+){0,3})"
        r"(?P<prerelease>-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
        r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?",
        version,
    )
    if match is None:
        raise RuntimeError(f"Invalid NuGet package version derived from Slang: {version}")

    components = [
        str(int(component)) for component in match.group("numeric").split(".")
    ]
    while len(components) < 3:
        components.append("0")
    if len(components) == 4 and components[3] == "0":
        components.pop()

    return ".".join(components) + (match.group("prerelease") or "")


def toolchain_package_version(slang_version: str, revision: int) -> str:
    numeric, separator, prerelease = normalize_nuget_version(slang_version).partition("-")
    if numeric.count(".") != 2:
        raise RuntimeError(f"Slang version {slang_version} leaves no NuGet version component for the release revision")
    return f"{numeric}.{revision}{separator}{prerelease}"


def write_output(name: str, value: str) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path:
        with open(output_path, "a", encoding="utf-8") as output:
            output.write(f"{name}={value}\n")
    else:
        print(f"{name}={value}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", required=True)
    parser.add_argument("--token", default=os.environ.get("GITHUB_TOKEN", ""))
    arguments = parser.parse_args()

    slang_tag = read_pinned_slang_tag()
    slang_release = get_slang_release(slang_tag, arguments.token)
    validate_slang_release(slang_release)
    revision, release_commit = release_revision()

    slang_version = slang_tag.removeprefix("v")
    fetch_dxc_url = (
        f"https://raw.githubusercontent.com/{SLANG_REPOSITORY}/"
        f"{slang_tag}/cmake/FetchDXC.cmake"
    )
    fetch_dxc = request_text(fetch_dxc_url, arguments.token)
    dxc_tag = extract_cmake_value(fetch_dxc, "_dxc_version_tag")
    dxc_commit = extract_cmake_value(fetch_dxc, "_dxc_expected_git_commit")
    dxc_version = dxc_tag.removeprefix("v")
    # Archives are named after their content; the tag also names the packaging revision that produced them.
    bundle_name = f"slang-{slang_version}-dxc-{dxc_version}"
    bundle_tag = f"{bundle_name}-r{revision}"

    bundle_release = get_release(arguments.repository, bundle_tag, arguments.token)
    bundle_release_exists = bundle_release is not None
    expected_bundle_assets = {
        f"{bundle_name}-{platform}.zip" for platform in PLATFORMS
    }
    bundle_assets = (
        {asset["name"] for asset in bundle_release["assets"]}
        if bundle_release is not None
        else set()
    )
    if bundle_release_exists:
        missing_bundle_assets = sorted(expected_bundle_assets - bundle_assets)
        if missing_bundle_assets:
            raise RuntimeError(
                f"Bundle release {bundle_tag} is incomplete: "
                + ", ".join(missing_bundle_assets)
            )

    package_version = toolchain_package_version(slang_version, revision)
    package_full_version = f"{package_version}+{release_commit[:7]}"
    toolchain_version_is_legacy = is_legacy_toolchain_version(package_version)
    missing_packages = (
        [] if toolchain_version_is_legacy else missing_toolchain_packages(package_version)
    )
    # A legacy version counts as handled whether or not it was ever published; the legacy layout is no longer built.
    toolchain_package_exists = not missing_packages
    should_build_bundle = not bundle_release_exists
    should_prepare_toolchain = not toolchain_package_exists
    if toolchain_version_is_legacy:
        print(
            f"Toolchain package version {package_version} belongs to the legacy single-package layout, "
            f"which is no longer built; the SDK layout starts after {LAST_LEGACY_VERSION}",
            file=sys.stderr,
        )

    write_output("should_build_bundle", str(should_build_bundle).lower())
    write_output("should_prepare_toolchain", str(should_prepare_toolchain).lower())
    write_output("toolchain_package_exists", str(toolchain_package_exists).lower())
    write_output("toolchain_package_version", package_version)
    write_output("toolchain_package_full_version", package_full_version)
    write_output("revision", str(revision))
    write_output("release_commit", release_commit)
    write_output("slang_tag", slang_tag)
    write_output("slang_version", slang_version)
    write_output("dxc_tag", dxc_tag)
    write_output("dxc_version", dxc_version)
    write_output("dxc_commit", dxc_commit)
    write_output("bundle_name", bundle_name)
    write_output("bundle_tag", bundle_tag)

    print(
        json.dumps(
            {
                "should_build_bundle": should_build_bundle,
                "should_prepare_toolchain": should_prepare_toolchain,
                "toolchain_package_exists": toolchain_package_exists,
                "toolchain_package_version": package_version,
                "toolchain_package_full_version": package_full_version,
                "revision": revision,
                "release_commit": release_commit,
                "missing_toolchain_packages": missing_packages,
                "toolchain_version_is_legacy": toolchain_version_is_legacy,
                "slang_tag": slang_tag,
                "dxc_tag": dxc_tag,
                "dxc_commit": dxc_commit,
                "bundle_tag": bundle_tag,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (RuntimeError, urllib.error.HTTPError, subprocess.CalledProcessError) as error:
        print(f"error: {error}", file=sys.stderr)
        sys.exit(1)
