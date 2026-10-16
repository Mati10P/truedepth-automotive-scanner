param([switch]$Demo)
$ErrorActionPreference = 'Stop'
$receiver = Join-Path $PSScriptRoot 'apps/windows/receive_frame.py'
if ($Demo) { & python $receiver --demo } else { & python $receiver }
if ($LASTEXITCODE -ne 0) { throw 'La captura no se completó. Revisá el mensaje anterior.' }
