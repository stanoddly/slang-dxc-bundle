# Unofficial Slang/DXC Toolchain Bundle (single build host)

Build-host tooling from [Slang](https://github.com/shader-slang/slang) for one host platform, bundled with the source-built [DirectX Shader Compiler](https://github.com/microsoft/DirectXShaderCompiler) library pinned by that Slang release.

The package contains the expanded tool tree for its host platform under `tools/slang/<platform>/` and exposes three transitive MSBuild properties:

- `SlangDxcToolchainRoot`: the `tools/slang/` directory.
- `SlangDxcToolchainPlatform`: the Slang platform name, such as `linux-x86_64`.
- `SlangDxcToolchainDirectory`: the platform directory below the root, containing `bin/` and `lib/`.

Most consumers should not reference this package directly. The [SlangDxcBundle.Toolchain](https://www.nuget.org/packages/SlangDxcBundle.Toolchain) MSBuild project SDK selects the package that matches the build host during restore:

```xml
<Project Sdk="Microsoft.NET.Sdk">
  <Sdk Name="SlangDxcBundle.Toolchain" Version="2026.17.1" />
</Project>
```

A direct `PackageReference` is supported for consumers that select the build host themselves. The package does not run any tools and does not depend on the application's target runtime.

Package versions match their Slang version after NuGet normalization, so a two-component Slang version such as `2026.14` becomes package version `2026.14.0`. Exact DXC versions, source revisions, and binary digests are recorded in `SLANG-DXC-BUNDLE.json`.

The packaging integration is MIT-licensed. The bundled binaries retain their upstream licenses and notices within the platform directory.
