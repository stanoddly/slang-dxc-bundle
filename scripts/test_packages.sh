#!/usr/bin/env bash
# Exercises the SDK and platform packages from a local feed the way consumers use them.
# Required: PACKAGE_FEED (must hold the SDK and every platform package), PACKAGE_VERSION, SLANG_VERSION, DXC_VERSION, EXPECTED_PLATFORM.
# Optional: TARGET_RUNTIME (application RID that must not influence the toolchain), NUGET_PACKAGES.
set -euo pipefail

repository="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
tests="$repository/tests"
: "${PACKAGE_FEED:?}" "${PACKAGE_VERSION:?}" "${SLANG_VERSION:?}" "${DXC_VERSION:?}" "${EXPECTED_PLATFORM:?}"
target_runtime="${TARGET_RUNTIME:-win-x64}"
export NUGET_PACKAGES="${NUGET_PACKAGES:-$repository/build/test-packages}"
export DOTNET_NOLOGO=1 DOTNET_CLI_TELEMETRY_OPTOUT=1 DOTNET_SKIP_FIRST_TIME_EXPERIENCE=1

host_rid="$(python3 -c "import sys; sys.path.insert(0, '$repository/scripts'); from toolchain_layout import RUNTIME_IDENTIFIERS; print(RUNTIME_IDENTIFIERS['$EXPECTED_PLATFORM'])")"
other_rid="$(python3 -c "import sys; sys.path.insert(0, '$repository/scripts'); from toolchain_layout import RUNTIME_IDENTIFIERS; print(next(r for r in RUNTIME_IDENTIFIERS.values() if r != '$host_rid'))")"
package_root="$NUGET_PACKAGES/slangdxcbundle.toolchain.$host_rid/$PACKAGE_VERSION/tools/slang"
windows_host=false
if [[ "${RUNNER_OS:-$(uname -s)}" == "Windows" ]]; then
  windows_host=true
fi
common_properties=(
  --property:ToolchainPackageVersion="$PACKAGE_VERSION"
  --property:ToolchainOtherRid="$other_rid"
  --property:ExpectedSlangPlatform="$EXPECTED_PLATFORM"
  --property:ExpectedToolchainVersion="$PACKAGE_VERSION"
  --property:NuGetAudit=false
  -p:TreatWarningsAsErrors=true
)

restore_global_json() {
  git -C "$repository" checkout -- tests/global.json 2>/dev/null || true
}
trap restore_global_json EXIT

set_writable() {
  if [[ "$windows_host" == true ]]; then
    attrib -R "$(cygpath -w "$1")\\*" /S /D
  else
    chmod -R u+w "$1"
  fi
}

set_read_only() {
  if [[ "$windows_host" == true ]]; then
    attrib +R "$(cygpath -w "$1")\\*" /S /D
  else
    chmod -R a-w "$1"
  fi
}

# expect_failure <message fragment> <dotnet arguments...>
expect_failure() {
  local needle="$1"
  shift
  local output status
  set +e
  output="$(dotnet "$@" 2>&1)"
  status=$?
  set -e
  if [[ "$status" -eq 0 ]]; then
    echo "$output" >&2
    echo "Expected failure containing: $needle" >&2
    exit 1
  fi
  if ! grep -qF "$needle" <<< "$output"; then
    echo "$output" >&2
    echo "Failure did not contain: $needle" >&2
    exit 1
  fi
}

if [[ -d "$NUGET_PACKAGES" ]]; then
  set_writable "$NUGET_PACKAGES"
  rm -rf "$NUGET_PACKAGES"
fi
find "$tests" -type d \( -name bin -o -name obj \) -prune -exec rm -rf {} +
rm -rf "$tests/ToolchainExplicitVersion"

# The SDK resolver reads NuGet.Config and global.json; it ignores restore command-line sources.
cat > "$tests/NuGet.Config" <<EOF
<?xml version="1.0" encoding="utf-8"?>
<configuration>
  <packageSources>
    <clear />
    <add key="local" value="$PACKAGE_FEED" />
  </packageSources>
</configuration>
EOF
cat > "$tests/global.json" <<EOF
{
  "msbuild-sdks": {
    "SlangDxcBundle.Toolchain": "$PACKAGE_VERSION"
  }
}
EOF

echo "== Library built with the SDK carries no toolchain dependency"
dotnet pack "$tests/ToolchainConsumerDependency/ToolchainConsumerDependency.csproj" --configuration Release --output "$PACKAGE_FEED" "${common_properties[@]}"
python3 - "$PACKAGE_FEED/SlangDxcBundle.Toolchain.ConsumerTest.Dependency.1.0.0.nupkg" <<'EOF'
import sys, zipfile
from xml.etree import ElementTree
with zipfile.ZipFile(sys.argv[1]) as package:
    nuspec = ElementTree.fromstring(package.read("SlangDxcBundle.Toolchain.ConsumerTest.Dependency.nuspec"))
dependencies = [element.get("id") for element in nuspec.iter() if element.tag.endswith("}dependency")]
if any(dependency.startswith("SlangDxcBundle.Toolchain") for dependency in dependencies):
    raise SystemExit(f"error: library nuspec carries a toolchain dependency: {dependencies}")
print(f"dependencies: {dependencies}")
EOF

echo "== SDK consumer restores only the build host's platform package"
dotnet restore "$tests/ToolchainConsumer/ToolchainConsumer.csproj" "${common_properties[@]}" \
  --property:RuntimeIdentifier="$target_runtime" --property:UseAppHost=false --property:SelfContained=false
restored_platform_packages="$(find "$NUGET_PACKAGES" -maxdepth 1 -mindepth 1 -type d -name 'slangdxcbundle.toolchain.*' -not -name 'slangdxcbundle.toolchain.consumertest.*' -exec basename {} \; | sort)"
if [[ "$restored_platform_packages" != "slangdxcbundle.toolchain.$host_rid" ]]; then
  echo "Unexpected platform packages restored: $restored_platform_packages" >&2
  exit 1
fi
if [[ ! -d "$NUGET_PACKAGES/slangdxcbundle.toolchain/$PACKAGE_VERSION/Sdk" ]]; then
  echo "The SDK package was not resolved into $NUGET_PACKAGES" >&2
  exit 1
fi

echo "== Package installation is passive and read-only"
set_read_only "$package_root"
before=$(python3 "$repository/scripts/verify_toolchain_installation.py" --root "$package_root" --platform "$EXPECTED_PLATFORM" --slang-version "$SLANG_VERSION" --dxc-version "$DXC_VERSION")
dotnet build "$tests/ToolchainConsumer/ToolchainConsumer.csproj" --configuration Release --no-restore "${common_properties[@]}" \
  --property:RuntimeIdentifier="$target_runtime" --property:UseAppHost=false --property:SelfContained=false --property:RunToolchainSmoke=false
if find "$tests/ToolchainConsumer/obj" -name 'smoke.*' -print -quit | grep -q .; then
  echo "Passive package build unexpectedly generated shader output" >&2
  exit 1
fi
dotnet build "$tests/ToolchainConsumer/ToolchainConsumer.csproj" --configuration Release --no-restore "${common_properties[@]}" \
  --property:RuntimeIdentifier="$target_runtime" --property:UseAppHost=false --property:SelfContained=false
after=$(python3 "$repository/scripts/verify_toolchain_installation.py" --root "$package_root" --platform "$EXPECTED_PLATFORM" --slang-version "$SLANG_VERSION" --dxc-version "$DXC_VERSION")
if [[ "$before" != "$after" ]]; then
  echo "Package installation changed during the consumer build" >&2
  exit 1
fi
if find "$tests/ToolchainConsumer/obj" -type f \( -name slangc -o -name slangc.exe \) -print -quit | grep -q .; then
  echo "Consumer build created a project-local toolchain installation" >&2
  exit 1
fi

echo "== Explicit <Sdk Version> works without global.json"
mkdir -p "$tests/ToolchainExplicitVersion"
cat > "$tests/ToolchainExplicitVersion/ToolchainExplicitVersion.csproj" <<EOF
<Project Sdk="Microsoft.NET.Sdk">
    <Sdk Name="SlangDxcBundle.Toolchain" Version="$PACKAGE_VERSION" />
    <PropertyGroup>
        <TargetFramework>net10.0</TargetFramework>
        <EnableDefaultCompileItems>false</EnableDefaultCompileItems>
    </PropertyGroup>
    <Target Name="ValidateToolchainProperties" BeforeTargets="CoreCompile">
        <Error Text="Expected toolchain version \$(ExpectedToolchainVersion), got \$(SlangDxcToolchainVersion)." Condition="'\$(ExpectedToolchainVersion)' != '\$(SlangDxcToolchainVersion)'" />
        <Error Text="Toolchain directory does not exist: \$(SlangDxcToolchainDirectory)" Condition="!Exists('\$(SlangDxcToolchainDirectory)')" />
    </Target>
</Project>
EOF
cat > "$tests/ToolchainExplicitVersion/global.json" <<'EOF'
{ "msbuild-sdks": { } }
EOF
dotnet build "$tests/ToolchainExplicitVersion/ToolchainExplicitVersion.csproj" --configuration Release "${common_properties[@]}"

echo "== SDK replaces a stale central package version"
dotnet build "$tests/ToolchainCpmConsumer/ToolchainCpmConsumer.csproj" --configuration Release "${common_properties[@]}"

echo "== Direct platform package reference works without the SDK"
dotnet build "$tests/ToolchainDirectReference/ToolchainDirectReference.csproj" --configuration Release "${common_properties[@]}"

echo "== A downstream SDK can pin the toolchain through a nested import"
dotnet pack "$tests/ToolchainConsumerSdk/ToolchainConsumerSdk.csproj" --configuration Release --output "$PACKAGE_FEED" "${common_properties[@]}"
dotnet build "$tests/ToolchainNestedSdkConsumer/ToolchainNestedSdkConsumer.csproj" --configuration Release "${common_properties[@]}"

echo "== <Sdk> next to a stale PackageReference builds without warnings"
dotnet build "$tests/ToolchainDualReference/ToolchainDualReference.csproj" --configuration Release "${common_properties[@]}" -warnaserror

echo "== PackageReference to the SDK package fails with the migration message"
expect_failure "is an MSBuild project SDK" build "$tests/ToolchainLegacyReference/ToolchainLegacyReference.csproj" --configuration Release "${common_properties[@]}"

echo "== Two platform packages fail the build"
expect_failure "More than one SlangDxcBundle.Toolchain platform package is restored" build "$tests/ToolchainTwoPlatforms/ToolchainTwoPlatforms.csproj" --configuration Release "${common_properties[@]}"

echo "== An unsupported build host fails at restore"
expect_failure "does not support this build host" restore "$tests/ToolchainCpmConsumer/ToolchainCpmConsumer.csproj" "${common_properties[@]}" --property:_SlangDxcToolchainHostRid=

echo "== Assets restored on another host fail the build"
dotnet restore "$tests/ToolchainCpmConsumer/ToolchainCpmConsumer.csproj" "${common_properties[@]}" --property:_SlangDxcToolchainHostRid="$other_rid"
expect_failure "but this build host is $host_rid" build "$tests/ToolchainCpmConsumer/ToolchainCpmConsumer.csproj" --configuration Release --no-restore "${common_properties[@]}"

echo "All package tests passed for $EXPECTED_PLATFORM ($host_rid), toolchain $PACKAGE_VERSION"
