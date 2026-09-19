#!/usr/bin/env python3

import argparse
import sys
import time

from resolve_release import nuget_package_exists
from toolchain_layout import PLATFORMS, platform_package_id


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-version", required=True)
    parser.add_argument("--timeout-seconds", type=int, default=1800)
    parser.add_argument("--interval-seconds", type=int, default=30)
    arguments = parser.parse_args()

    pending = {platform_package_id(platform) for platform in PLATFORMS}
    deadline = time.monotonic() + arguments.timeout_seconds
    while pending:
        pending = {package_id for package_id in pending if not nuget_package_exists(package_id, arguments.package_version)}
        if not pending:
            break
        if time.monotonic() >= deadline:
            raise RuntimeError(
                f"Platform packages are still unavailable after {arguments.timeout_seconds} seconds: "
                + ", ".join(sorted(pending))
            )
        print(f"Waiting for {', '.join(sorted(pending))} {arguments.package_version}")
        time.sleep(arguments.interval_seconds)

    print(f"All platform packages {arguments.package_version} are available")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RuntimeError as error:
        print(f"error: {error}", file=sys.stderr)
        sys.exit(1)
