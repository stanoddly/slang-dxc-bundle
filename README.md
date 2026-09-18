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

## NuGet toolchain packages

[SlangDxcBundle.Toolchain](https://www.nuget.org/packages/SlangDxcBundle.Toolchain) is an MSBuild project SDK that restores the slim build-host tool tree for the machine that runs the build. During restore it references the platform package pinned to its own version, so a consumer downloads one tree of about 60 MB instead of all five:

| Build host | Package |
| --- | --- |
| Linux x64 | `SlangDxcBundle.Toolchain.linux-x64` |
| Linux ARM64 | `SlangDxcBundle.Toolchain.linux-arm64` |
| Windows x64 | `SlangDxcBundle.Toolchain.win-x64` |
| macOS x64 | `SlangDxcBundle.Toolchain.osx-x64` |
| macOS ARM64 | `SlangDxcBundle.Toolchain.osx-arm64` |

```xml
<Project Sdk="Microsoft.NET.Sdk">
  <Sdk Name="SlangDxcBundle.Toolchain" Version="<version>" />
</Project>
```

The version can also live in `global.json` under `msbuild-sdks`, and another MSBuild project SDK can pin it for its own consumers with `<Import Project="Sdk.props" Sdk="SlangDxcBundle.Toolchain" Version="<version>" />` (the `Version` attribute of `<Import>` expands properties; the `<Sdk>` element does not). A `PackageReference` to `SlangDxcBundle.Toolchain` fails the build with a migration message. Consumers that select the build host themselves, for example on a host the SDK does not detect, can reference a platform package directly.

Versions up to and including `2026.18.0` are legacy single packages that contain all five platforms and are referenced with `PackageReference`; the SDK layout starts with the first Slang release after that. The legacy versions stay on nuget.org unchanged.

GitHub releases contain the full platform bundles; the slim tool trees are distributed only through the platform packages.

The packages are passive. The platform package exposes the MSBuild properties `SlangDxcToolchainRoot` (the `tools/slang/` directory), `SlangDxcToolchainPlatform` (the Slang platform name, such as `linux-x86_64`), and `SlangDxcToolchainDirectory` (the platform directory with `bin/` and `lib/`) to the project that restores it; the SDK exposes `SlangDxcToolchainVersion`. Downstream integrations execute the compiler independently of the application's target runtime identifier.

The platform package reference is private to the project that uses the SDK, so a packed library never lists the build host's toolchain as a dependency; each project that runs the compiler references the SDK itself. Central Package Management is supported when `ManagePackageVersionsCentrally` is set in `Directory.Packages.props`; the SDK replaces any central entry for the platform package with its own pin. MSBuild resolves a named project SDK once per build, so all projects in one build share the first resolved toolchain version (MSBuild warns with MSB4240 when versions differ), and `packages.lock.json` records the build host's platform package.

The base package version is the NuGet-normalized Slang version, so a two-component Slang version such as `2026.14` becomes package version `2026.14.0`. The exact DXC version and source commit remain recorded in each `SLANG-DXC-BUNDLE.json`; a fourth NuGet version component is reserved for packaging-only corrections.

## Automation

[`release.yml`](.github/workflows/release.yml) checks the latest stable Slang release every six hours. If its corresponding bundle release does not exist, the workflow builds and tests all supported platforms before publishing it. If any of the six NuGet packages is missing for that version, the workflow prepares the slim tool trees, packs the platform packages and the SDK, tests them as consumers on every supported build host, and publishes them.

The workflow can also be started manually with a specific Slang tag. A `repository_dispatch` event of type `slang-release` may provide the tag as `client_payload.slang_tag` for external webhook integrations.

GitHub cannot subscribe directly to another repository's `release` event. The scheduled check is therefore the default trigger and may be delayed by GitHub Actions scheduling.

## Licensing

The scripts and workflows in this repository use the repository's [MIT license](LICENSE). Released archives and NuGet packages contain software from Slang, DXC, and their dependencies under their respective licenses. Their license material is preserved inside each archive and package.

### Why DXC is built from source

This repository intentionally does not copy DXC libraries from Microsoft's prebuilt release archives. In the [DXC v1.9.2602 release](https://github.com/microsoft/DirectXShaderCompiler/releases/tag/v1.9.2602), both the Windows and Linux archives contain `LICENSE-MS.txt`. Those binary-release terms limit installation and use to Windows and describe redistribution as distributable code included in applications that add significant primary functionality. The presence of those terms in the Linux archive is unclear, and a standalone compiler bundle does not fit that redistribution model cleanly. This project does not attempt to reinterpret that ambiguity.

Instead, the workflow builds `dxcompiler` from the exact DXC source commit pinned by Slang. That [source tree](https://github.com/microsoft/DirectXShaderCompiler/tree/21d28f727ad395b59394815ef76012e432f7e4e5) contains the permissive [`LICENSE.TXT`](https://github.com/microsoft/DirectXShaderCompiler/blob/21d28f727ad395b59394815ef76012e432f7e4e5/LICENSE.TXT) and [`ThirdPartyNotices.txt`](https://github.com/microsoft/DirectXShaderCompiler/blob/21d28f727ad395b59394815ef76012e432f7e4e5/ThirdPartyNotices.txt), but not `LICENSE-MS.txt`. The released bundles reproduce those source license materials alongside the resulting library. This gives every supported platform the same auditable source and licensing provenance without republishing Microsoft's prebuilt binaries.

This is a conservative project packaging policy, not legal advice.
