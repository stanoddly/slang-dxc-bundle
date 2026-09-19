import zipfile
from pathlib import PurePosixPath
from xml.etree import ElementTree


PLATFORMS = (
    "linux-aarch64",
    "linux-x86_64",
    "macos-aarch64",
    "macos-x86_64",
    "windows-x86_64",
)

RUNTIME_IDENTIFIERS = {
    "linux-aarch64": "linux-arm64",
    "linux-x86_64": "linux-x64",
    "macos-aarch64": "osx-arm64",
    "macos-x86_64": "osx-x64",
    "windows-x86_64": "win-x64",
}

SDK_PACKAGE_ID = "SlangDxcBundle.Toolchain"


def platform_package_id(platform: str) -> str:
    if platform not in RUNTIME_IDENTIFIERS:
        raise RuntimeError(f"Unsupported platform: {platform}")
    return f"{SDK_PACKAGE_ID}.{RUNTIME_IDENTIFIERS[platform]}"


def package_ids() -> tuple[str, ...]:
    return (SDK_PACKAGE_ID, *(platform_package_id(platform) for platform in PLATFORMS))


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


def read_nuspec(package: zipfile.ZipFile) -> tuple[str, str, list[str]]:
    nuspec_names = [name for name in package.namelist() if name.endswith(".nuspec")]
    if len(nuspec_names) != 1:
        raise RuntimeError("Package must contain exactly one .nuspec file")
    nuspec = ElementTree.fromstring(package.read(nuspec_names[0]))
    namespace = {"n": nuspec.tag.partition("}")[0].removeprefix("{")}
    package_id = nuspec.findtext("n:metadata/n:id", namespaces=namespace)
    package_version = nuspec.findtext("n:metadata/n:version", namespaces=namespace)
    dependencies = [
        element.get("id") for element in nuspec.findall(".//n:dependency", namespaces=namespace)
    ]
    return package_id, package_version, dependencies


def package_file_entries(package: zipfile.ZipFile) -> dict[str, zipfile.ZipInfo]:
    entries = [entry for entry in package.infolist() if not entry.is_dir()]
    unique_entries = {entry.filename: entry for entry in entries}
    if len(unique_entries) != len(entries):
        raise RuntimeError("Package contains duplicate file entries")
    return unique_entries
