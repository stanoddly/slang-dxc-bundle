#!/usr/bin/env python3

import argparse
import json
import os
import sys
import urllib.error

from resolve_release import (
    GITHUB_API_URL,
    PIN_FILE,
    REPOSITORY_ROOT,
    SLANG_REPOSITORY,
    get_slang_release,
    normalize_nuget_version,
    nuget_version_key,
    read_pinned_slang_tag,
    request_json,
    validate_slang_release,
    write_output,
)


def should_update(pinned_tag: str, candidate_tag: str, explicit: bool) -> bool:
    if candidate_tag == pinned_tag:
        return False
    # An explicit tag is a deliberate choice; the latest endpoint must never move the pin backwards.
    return explicit or nuget_version_key(normalize_nuget_version(candidate_tag.removeprefix("v"))) > nuget_version_key(
        normalize_nuget_version(pinned_tag.removeprefix("v"))
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slang-tag")
    parser.add_argument("--token", default=os.environ.get("GITHUB_TOKEN", ""))
    arguments = parser.parse_args()

    if arguments.slang_tag:
        slang_release = get_slang_release(arguments.slang_tag, arguments.token)
    else:
        slang_release = request_json(f"{GITHUB_API_URL}/repos/{SLANG_REPOSITORY}/releases/latest", arguments.token)
        if slang_release["prerelease"]:
            raise RuntimeError("The latest stable Slang endpoint returned a prerelease")
    validate_slang_release(slang_release)

    slang_tag = slang_release["tag_name"]
    pinned_tag = read_pinned_slang_tag()
    updated = should_update(pinned_tag, slang_tag, bool(arguments.slang_tag))
    if updated:
        (REPOSITORY_ROOT / PIN_FILE).write_text(json.dumps({"slang_tag": slang_tag}, indent=2) + "\n", encoding="utf-8")

    write_output("updated", str(updated).lower())
    write_output("slang_tag", slang_tag)
    print(f"Pinned Slang {pinned_tag}, candidate {slang_tag}: {'updated' if updated else 'unchanged'}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (RuntimeError, urllib.error.HTTPError) as error:
        print(f"error: {error}", file=sys.stderr)
        sys.exit(1)
