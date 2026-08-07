#!/usr/bin/env python3

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request


GITHUB_API_URL = "https://api.github.com"
SLANG_REPOSITORY = "shader-slang/slang"


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


def release_exists(repository: str, tag: str, token: str) -> bool:
    url = f"{GITHUB_API_URL}/repos/{repository}/releases/tags/{tag}"
    try:
        request_json(url, token)
        return True
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return False
        raise


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
    parser.add_argument("--slang-tag")
    parser.add_argument("--token", default=os.environ.get("GITHUB_TOKEN", ""))
    arguments = parser.parse_args()

    if arguments.slang_tag:
        slang_tag = arguments.slang_tag
        slang_release = request_json(
            f"{GITHUB_API_URL}/repos/{SLANG_REPOSITORY}/releases/tags/{slang_tag}",
            arguments.token,
        )
    else:
        slang_release = request_json(
            f"{GITHUB_API_URL}/repos/{SLANG_REPOSITORY}/releases/latest",
            arguments.token,
        )
        slang_tag = slang_release["tag_name"]

    if slang_release["draft"]:
        raise RuntimeError(f"Slang release {slang_tag} is a draft")
    if slang_release["prerelease"] and not arguments.slang_tag:
        raise RuntimeError("The latest stable Slang endpoint returned a prerelease")

    slang_version = slang_tag.removeprefix("v")
    fetch_dxc_url = (
        f"https://raw.githubusercontent.com/{SLANG_REPOSITORY}/"
        f"{slang_tag}/cmake/FetchDXC.cmake"
    )
    fetch_dxc = request_text(fetch_dxc_url, arguments.token)
    dxc_tag = extract_cmake_value(fetch_dxc, "_dxc_version_tag")
    dxc_commit = extract_cmake_value(fetch_dxc, "_dxc_expected_git_commit")
    dxc_version = dxc_tag.removeprefix("v")
    bundle_tag = f"slang-{slang_version}-dxc-{dxc_version}"

    expected_assets = {
        f"slang-{slang_version}-windows-x86_64.zip",
        f"slang-{slang_version}-linux-x86_64.zip",
        f"slang-{slang_version}-linux-aarch64.zip",
        f"slang-{slang_version}-macos-x86_64.zip",
        f"slang-{slang_version}-macos-aarch64.zip",
    }
    release_assets = {asset["name"] for asset in slang_release["assets"]}
    missing_assets = sorted(expected_assets - release_assets)
    if missing_assets:
        raise RuntimeError(
            f"Slang release {slang_tag} is missing required assets: "
            + ", ".join(missing_assets)
        )

    should_build = not release_exists(arguments.repository, bundle_tag, arguments.token)

    write_output("should_build", str(should_build).lower())
    write_output("slang_tag", slang_tag)
    write_output("slang_version", slang_version)
    write_output("dxc_tag", dxc_tag)
    write_output("dxc_version", dxc_version)
    write_output("dxc_commit", dxc_commit)
    write_output("bundle_tag", bundle_tag)

    print(
        json.dumps(
            {
                "should_build": should_build,
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
    except (RuntimeError, urllib.error.HTTPError) as error:
        print(f"error: {error}", file=sys.stderr)
        sys.exit(1)
