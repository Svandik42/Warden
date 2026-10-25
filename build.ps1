$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$python = ".\.venv\Scripts\python.exe"

& $python -m PyInstaller --noconfirm --clean --windowed `
    --name Warden `
    --icon resources\warden.ico `
    --add-data "resources;resources" `
    --add-data "docs;docs" `
    --exclude-module tkinter `
    main.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller selhal." }
Remove-Item "dist\Warden\_internal\PySide6\opengl32sw.dll" -ErrorAction SilentlyContinue
Write-Host "Program je ve složce dist\Warden (spouští se Warden.exe)."

$version = (Select-String -Path installer\warden.iss -Pattern '#define AppVersion "(.+)"').Matches[0].Groups[1].Value
New-Item -ItemType Directory -Force installer\Output | Out-Null
$zip = "installer\Output\Warden-$version-portable.zip"
foreach ($attempt in 1..3) {
    try {
        Compress-Archive -Path dist\Warden -DestinationPath $zip -Force -ErrorAction Stop
        break
    } catch {
        if ($attempt -eq 3) { throw }
        Start-Sleep -Seconds 5
    }
}
Write-Host "Přenosná verze: $zip"

$iscc = @(
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

if ($iscc) {
    & $iscc installer\warden.iss
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup selhal." }
    Write-Host "Instalátor je ve složce installer\Output."
} else {
    Write-Host "Inno Setup není nainstalovaný, instalátor se nevytvořil."
    Write-Host "Nainstaluj ho příkazem: winget install JRSoftware.InnoSetup"
}
