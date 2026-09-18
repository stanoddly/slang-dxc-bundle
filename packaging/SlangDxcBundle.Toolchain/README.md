# Unofficial Slang/DXC Toolchain Bundle

MSBuild project SDK that restores build-host tooling from [Slang](https://github.com/shader-slang/slang), bundled with the source-built [DirectX Shader Compiler](https://github.com/microsoft/DirectXShaderCompiler) library pinned by that Slang release.

During restore, the SDK detects the build host and references the matching platform package pinned to its own version: `SlangDxcBundle.Toolchain.linux-x64`, `.linux-arm64`, `.win-x64`, `.osx-x64`, or `.osx-arm64`. Only that package (about 60 MB) is downloaded.

```xml
<Project Sdk="Microsoft.NET.Sdk">
  <Sdk Name="SlangDxcBundle.Toolchain" Version="<version>" />
</Project>
```

The version can also live in `global.json`, in which case the project uses `<Sdk Name="SlangDxcBundle.Toolchain" />`:

```json
{ "msbuild-sdks": { "SlangDxcBundle.Toolchain": "<version>" } }
```

Another MSBuild project SDK can pin the toolchain for its own consumers with `<Import Project="Sdk.props" Sdk="SlangDxcBundle.Toolchain" Version="<version>" />` in its `Sdk.props` and the matching `Sdk.targets` import.

Versions up to and including `2026.18.0` are legacy single packages that contain all five platforms and are referenced with `PackageReference`; the SDK layout starts with the first Slang release after that.

The platform package exposes three MSBuild properties to the project that restores it:

- `SlangDxcToolchainRoot`: the `tools/slang/` directory.
- `SlangDxcToolchainPlatform`: the Slang platform name, such as `linux-x86_64`.
- `SlangDxcToolchainDirectory`: the platform directory below the root, containing `bin/` and `lib/`.

The SDK also exposes `SlangDxcToolchainVersion`. The packages do not run any tools. Downstream build integration selects and executes the compiler independently of the application target runtime.

The platform package reference is private to the project that uses the SDK; it never becomes a dependency of a packed library. Central Package Management is supported when `ManagePackageVersionsCentrally` is set in `Directory.Packages.props`; the SDK replaces any central entry for the platform package with its own pin.

A `PackageReference` to this package fails the build with a migration message; the SDK must be referenced through the `<Sdk>` element or `global.json`. MSBuild resolves a named SDK once per build, so all projects in one build share the first resolved toolchain version.

Package versions match their Slang version after NuGet normalization, so a two-component Slang version such as `2026.14` becomes package version `2026.14.0`. Exact DXC versions, source revisions, and binary digests are recorded in each platform package's `SLANG-DXC-BUNDLE.json`.

The packaging integration is MIT-licensed. The bundled binaries retain their upstream licenses and notices within every platform package.
