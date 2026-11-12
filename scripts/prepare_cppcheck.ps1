# Explicit setup only. Extract the pinned official binary distribution locally.
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$toolsRoot = Join-Path $projectRoot '.local\tools'
$packagePath = Join-Path $toolsRoot 'cppcheck-2.22.0-x64-Setup.msi'
$extractRoot = Join-Path $toolsRoot 'cppcheck'
$executable = Join-Path $extractRoot 'PFiles\Cppcheck\cppcheck.exe'
$url = 'https://github.com/cppcheck-opensource/cppcheck/releases/download/2.22.0/cppcheck-2.22.0-x64-Setup.msi'
$expectedHash = '3929162bab7e71d1b9b18708ec054fb0188bfc8ea1660979ed95837f5a9f547b'
New-Item -ItemType Directory -Path $toolsRoot -Force | Out-Null
if (-not (Test-Path -LiteralPath $packagePath)) {
    Invoke-WebRequest -Uri $url -OutFile $packagePath -UseBasicParsing
}
if ((Get-FileHash -LiteralPath $packagePath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expectedHash) {
    throw 'Cppcheck package hash mismatch; extraction refused'
}
if (-not (Test-Path -LiteralPath $executable)) {
    $arguments = @('/a', ('"' + $packagePath + '"'), '/qn', ('TARGETDIR="' + $extractRoot + '"'))
    $process = Start-Process msiexec.exe -ArgumentList $arguments -WindowStyle Hidden -Wait -PassThru
    if ($process.ExitCode -ne 0) { throw "Cppcheck extraction failed: $($process.ExitCode)" }
}
$version = & $executable --version
if ($LASTEXITCODE -ne 0 -or $version -ne 'Cppcheck 2.22.0') { throw 'Cppcheck version mismatch' }
@{ version = $version; url = $url; sha256 = $expectedHash; executable = $executable } |
    ConvertTo-Json | Set-Content -LiteralPath (Join-Path $toolsRoot 'cppcheck-artifact.json') -Encoding UTF8
Write-Output "$version ready at $executable. No addons or restricted standards guidance are used."
