# Stanoddly.SlangDxc.Toolchain

Cross-platform build-host tooling from [Slang](https://github.com/shader-slang/slang), bundled with the source-built [DirectX Shader Compiler](https://github.com/microsoft/DirectXShaderCompiler) library pinned by that Slang release.

The package contains expanded tool trees for Linux x64/ARM64, Windows x64, and macOS x64/ARM64. It exposes their common installation root through the transitive MSBuild property `SlangDxcToolchainRoot`.

The package does not select a platform or run any tools. Downstream build integration must select a build-host directory beneath the exposed root independently of the application target runtime.

Package versions initially match their Slang version after NuGet normalization, so a two-component Slang version such as `2026.14` becomes package version `2026.14.0`. Exact DXC versions, source revisions, and binary digests are recorded in each platform's `SLANG-DXC-BUNDLE.json`.

The packaging integration is MIT-licensed. The bundled binaries retain their upstream licenses and notices within every platform directory.
