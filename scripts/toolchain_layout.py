from pathlib import PurePosixPath


PLATFORMS = (
    "linux-aarch64",
    "linux-x86_64",
    "macos-aarch64",
    "macos-x86_64",
    "windows-x86_64",
)


def binary_entries(platform: str, slang_version: str) -> tuple[str, ...]:
    if platform.startswith("linux-"):
        return (
            "bin/slangc",
            f"lib/libslang-compiler.so.0.{slang_version}",
            f"lib/libslang-glslang-{slang_version}.so",
            f"lib/libslang-glsl-module-{slang_version}.so",
            "lib/libdxcompiler.so",
        )

    if platform.startswith("macos-"):
        return (
            "bin/slangc",
            f"lib/libslang-compiler.0.{slang_version}.dylib",
            f"lib/libslang-glslang-{slang_version}.dylib",
            f"lib/libslang-glsl-module-{slang_version}.dylib",
            "lib/libdxcompiler.dylib",
        )

    if platform == "windows-x86_64":
        return (
            "bin/slangc.exe",
            "bin/slang-compiler.dll",
            "bin/slang-glslang.dll",
            "bin/slang-glsl-module.dll",
            "bin/dxcompiler.dll",
        )

    raise RuntimeError(f"Unsupported platform: {platform}")


def compiler_entry(platform: str) -> str:
    return "bin/slangc.exe" if platform == "windows-x86_64" else "bin/slangc"


def dxcompiler_entry(platform: str) -> str:
    if platform.startswith("linux-"):
        return "lib/libdxcompiler.so"
    if platform.startswith("macos-"):
        return "lib/libdxcompiler.dylib"
    if platform == "windows-x86_64":
        return "bin/dxcompiler.dll"
    raise RuntimeError(f"Unsupported platform: {platform}")


def toolchain_archive_name(
    slang_version: str,
    dxc_version: str,
    platform: str,
) -> str:
    if platform not in PLATFORMS:
        raise RuntimeError(f"Unsupported platform: {platform}")

    return (
        f"slang-{slang_version}-dxc-{dxc_version}-toolchain-{platform}.zip"
    )


def package_entry(platform: str, entry: str) -> str:
    return str(PurePosixPath("tools", "slang", platform, entry))
