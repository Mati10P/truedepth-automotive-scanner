param([switch]$Demo, [double]$Seconds = 600, [double]$Fps = 5, [switch]$SaveDepth,
      [ValidateSet('persistent', 'legacy')][string]$Transport = 'persistent')
$ErrorActionPreference = 'Stop'
$receiver = Join-Path $PSScriptRoot 'apps/windows/capture_sequence.py'
$captureArgs = @('--duration', $Seconds.ToString([cultureinfo]::InvariantCulture), '--fps', $Fps.ToString([cultureinfo]::InvariantCulture))
$captureArgs += @('--transport', $Transport)
if ($Demo) { $captureArgs += '--demo' }
if ($SaveDepth) { $captureArgs += '--save-depth' }
& python $receiver @captureArgs
if ($LASTEXITCODE -ne 0) { throw 'La sesión terminó con un error. Revisá el mensaje anterior.' }
