# slang-dxc-bundle

Unofficial [Slang](https://github.com/shader-slang/slang) distributions bundled with a source-built [DirectX Shader Compiler](https://github.com/microsoft/DirectXShaderCompiler) library.

Slang supports DXIL through the downstream DXC library, but its official release archives do not include DXC. This repository preserves each official Slang archive and adds the `dxcompiler` library selected by that Slang release:

| Platform | Bundled library |
| --- | --- |
| Windows x64 | `bin/dxcompiler.dll` |
| Linux x64 | `lib/libdxcompiler.so` |
| Linux ARM64 | `lib/libdxcompiler.so` |
| macOS x64 | `lib/libdxcompiler.dylib` |
| macOS ARM64 | `lib/libdxcompiler.dylib` |

Building DXC from source also broadens platform coverage. DXC v1.9.2602 does not publish binary archives for macOS or Linux ARM64, while these bundles provide `dxcompiler` for both macOS architectures and Linux ARM64.

The separate `dxil` validator library is not included.

## Releases

Releases are named `slang-<Slang version>-dxc-<DXC version>`. Every bundle contains:

- the contents of the corresponding official Slang release archive;
- `dxcompiler`, built from the exact DXC commit pinned by that Slang source release;
- the DXC license and third-party notices;
- `SLANG-DXC-BUNDLE.json` with source revisions and SHA-256 digests.

## NuGet toolchain package

[SlangDxcBundle.Toolchain](https://www.nuget.org/packages/SlangDxcBundle.Toolchain) provides the slim build-host tool trees through NuGet restore. One package contains Linux x64/ARM64, Windows x64, and macOS x64/ARM64 under `tools/slang/{platform}`.

GitHub releases contain the full platform bundles; the slim tool trees are distributed only through the NuGet package.

The package is passive. Its only build integration is the transitive MSBuild property `SlangDxcToolchainRoot`, which points to the common `tools/slang/` directory. Downstream integrations select and execute the appropriate build-host compiler independently of the application's target runtime identifier.

The base package version is the NuGet-normalized Slang version, so a two-component Slang version such as `2026.14` becomes package version `2026.14.0`. The exact DXC version and source commit remain recorded in each `SLANG-DXC-BUNDLE.json`; a fourth NuGet version component is reserved for packaging-only corrections.

## Automation

[`release.yml`](.github/workflows/release.yml) checks the latest stable Slang release every six hours. If its corresponding bundle release does not exist, the workflow builds and tests all supported platforms before publishing it. If the corresponding NuGet package version is missing, the workflow prepares and tests the slim tool trees on every supported build host before publishing the package.

The workflow can also be started manually with a specific Slang tag. A `repository_dispatch` event of type `slang-release` may provide the tag as `client_payload.slang_tag` for external webhook integrations.

GitHub cannot subscribe directly to another repository's `release` event. The scheduled check is therefore the default trigger and may be delayed by GitHub Actions scheduling.

## Licensing

The scripts and workflows in this repository use the repository's [MIT license](LICENSE). Released archives and NuGet packages contain software from Slang, DXC, and their dependencies under their respective licenses. Their license material is preserved inside each archive and package.

### Why DXC is built from source

This repository intentionally does not copy DXC libraries from Microsoft's prebuilt release archives. In the [DXC v1.9.2602 release](https://github.com/microsoft/DirectXShaderCompiler/releases/tag/v1.9.2602), both the Windows and Linux archives contain `LICENSE-MS.txt`. Those binary-release terms limit installation and use to Windows and describe redistribution as distributable code included in applications that add significant primary functionality. The presence of those terms in the Linux archive is unclear, and a standalone compiler bundle does not fit that redistribution model cleanly. This project does not attempt to reinterpret that ambiguity.

Instead, the workflow builds `dxcompiler` from the exact DXC source commit pinned by Slang. That [source tree](https://github.com/microsoft/DirectXShaderCompiler/tree/21d28f727ad395b59394815ef76012e432f7e4e5) contains the permissive [`LICENSE.TXT`](https://github.com/microsoft/DirectXShaderCompiler/blob/21d28f727ad395b59394815ef76012e432f7e4e5/LICENSE.TXT) and [`ThirdPartyNotices.txt`](https://github.com/microsoft/DirectXShaderCompiler/blob/21d28f727ad395b59394815ef76012e432f7e4e5/ThirdPartyNotices.txt), but not `LICENSE-MS.txt`. The released bundles reproduce those source license materials alongside the resulting library. This gives every supported platform the same auditable source and licensing provenance without republishing Microsoft's prebuilt binaries.

This is a conservative project packaging policy, not legal advice.
