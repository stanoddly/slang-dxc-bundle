# slang-dxc-bundle

Unofficial, reproducible [Slang](https://github.com/shader-slang/slang) distributions bundled with a source-built [DirectX Shader Compiler](https://github.com/microsoft/DirectXShaderCompiler) library.

Slang supports DXIL through the downstream DXC library, but its official release archives do not include DXC. This repository preserves each official Slang archive and adds the `dxcompiler` library selected by that Slang release:

| Platform | Bundled library |
| --- | --- |
| Windows x64 | `bin/dxcompiler.dll` |
| Linux x64 | `lib/libdxcompiler.so` |
| Linux ARM64 | `lib/libdxcompiler.so` |
| macOS x64 | `lib/libdxcompiler.dylib` |
| macOS ARM64 | `lib/libdxcompiler.dylib` |

The separate `dxil` validator library is not included.

## Releases

Releases are named `slang-<Slang version>-dxc-<DXC version>`. Every bundle contains:

- the corresponding official Slang release archive;
- `dxcompiler`, built from the exact DXC commit pinned by that Slang source release;
- the DXC license and third-party notices;
- `SLANG-DXC-BUNDLE.json` with source revisions and SHA-256 digests.

Each release also provides a `.sha256` file for every archive.

## Automation

[`release.yml`](.github/workflows/release.yml) checks the latest stable Slang release every six hours. If its corresponding bundle release does not exist, the workflow builds and tests all supported platforms before publishing it.

The workflow can also be started manually with a specific Slang tag. A `repository_dispatch` event of type `slang-release` may provide the tag as `client_payload.slang_tag` for external webhook integrations.

GitHub cannot subscribe directly to another repository's `release` event. The scheduled check is therefore the default trigger and may be delayed by GitHub Actions scheduling.

## Licensing

The scripts and workflows in this repository use the repository's [MIT license](LICENSE). Released archives contain software from Slang, DXC, and their dependencies under their respective licenses. Their license material is preserved inside each archive.
