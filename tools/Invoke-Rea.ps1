param(
    [Parameter(Mandatory = $true)][string[]]$ReaArguments,
    [string]$JavaHome = 'C:\Program Files\Java\jdk-21',
    [string]$Heap = '1G',
    [ValidateRange(1, 2147483647)][int]$StartupTimeoutMs = 330000
)

# Local, version-pinned analysis tools; no global configuration is changed.
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$launcher = Join-Path $projectRoot '.local/tools/rea-runtime/node_modules/rea-agents/scripts/rea.mjs'
$ghidra = Join-Path $projectRoot '.local/tools/ghidra_12.1.4_PUBLIC'
if (-not (Test-Path -LiteralPath $launcher)) { throw 'Install rea-agents@6.4.0 locally as documented in docs/research/REA_FIRST_PASS.md.' }
if (-not (Test-Path -LiteralPath (Join-Path $ghidra 'support/analyzeHeadless.bat'))) { throw 'Local Ghidra 12.1.4 is missing.' }
if (-not (Test-Path -LiteralPath (Join-Path $JavaHome 'bin/javac.exe'))) { throw 'JavaHome must point to a full JDK.' }
$settings = @{
    GHIDRA_INSTALL_DIR = $ghidra
    JAVA_HOME = $JavaHome
    REA_ANALYSIS_PROVIDER = 'ghidra'
    GHIDRA_HEADLESS_MAXMEM = $Heap
    REA_GHIDRA_STARTUP_TIMEOUT_MS = [string]$StartupTimeoutMs
}
$previous = @{}
foreach ($key in $settings.Keys) {
    $previous[$key] = [Environment]::GetEnvironmentVariable($key, 'Process')
    [Environment]::SetEnvironmentVariable($key, $settings[$key], 'Process')
}
try {
    & node $launcher @ReaArguments
    $reaExit = $LASTEXITCODE
} finally {
    foreach ($key in $settings.Keys) {
        if ($null -eq $previous[$key]) {
            Remove-Item -LiteralPath "Env:$key" -ErrorAction SilentlyContinue
        } else {
            [Environment]::SetEnvironmentVariable($key, $previous[$key], 'Process')
        }
    }
}
exit $reaExit
