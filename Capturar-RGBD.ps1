param([double]$Seconds = 15, [double]$Fps = 1)
$ErrorActionPreference = 'Stop'
& python (Join-Path $PSScriptRoot 'apps/windows/capture_sequence.py') --transport rgbd --viewer rgbd --save-depth --duration $Seconds.ToString([cultureinfo]::InvariantCulture) --fps $Fps.ToString([cultureinfo]::InvariantCulture)
if ($LASTEXITCODE -ne 0) { throw 'Revisá el resultado de la captura RGB-D.' }
