$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$SrcPath = Join-Path $ProjectRoot "src"
$Launcher = Join-Path $ProjectRoot "SafeBox.pyw"
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (Test-Path -LiteralPath $VenvPython) {
    $Python = $VenvPython
} else {
    $Python = (Get-Command python).Source
}
$Version = (& $Python -c "import pathlib, tomllib; print(tomllib.loads(pathlib.Path('pyproject.toml').read_text(encoding='utf-8'))['project']['version'])").Trim()
$AssetsDir = Join-Path $ProjectRoot "src\safebox\ui\assets"
$AssetsData = "$AssetsDir;safebox\ui\assets"
$Icon = Join-Path $ProjectRoot "src\safebox\ui\assets\safebox.ico"
$DistDir = Join-Path $ProjectRoot "dist"
$ExePath = Join-Path $DistDir "SafeBox.exe"
$VersionedExePath = Join-Path $DistDir "SafeBox-v$Version-Windows-x64.exe"
$DesktopDir = [Environment]::GetFolderPath("Desktop")
if ([string]::IsNullOrWhiteSpace($DesktopDir)) {
    $DesktopDir = Join-Path $HOME "Desktop"
}
if (-not (Test-Path -LiteralPath $DesktopDir)) {
    $DesktopCandidate = Get-ChildItem -LiteralPath "C:\Users" -Directory |
        Where-Object { $_.Name -notin @("Public", "Default", "Default User", "All Users") } |
        ForEach-Object {
            $Candidate = Join-Path $_.FullName "Desktop"
            if (Test-Path -LiteralPath $Candidate -ErrorAction SilentlyContinue) {
                $Candidate
            }
        } |
        Select-Object -First 1
    if (-not [string]::IsNullOrWhiteSpace($DesktopCandidate)) {
        $DesktopDir = $DesktopCandidate
    }
}
$DesktopPath = Join-Path $DesktopDir "SafeBox.exe"

if (Test-Path -LiteralPath $ExePath) {
    Remove-Item -LiteralPath $ExePath -Force
}

if (Test-Path -LiteralPath $VersionedExePath) {
    Remove-Item -LiteralPath $VersionedExePath -Force
}

if (Test-Path -LiteralPath $DesktopPath) {
    Remove-Item -LiteralPath $DesktopPath -Force
}

& $Python -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --onefile `
    --name SafeBox `
    --icon "$Icon" `
    --paths "$SrcPath" `
    --add-data "$AssetsData" `
    "$Launcher"

Copy-Item -LiteralPath $ExePath -Destination $VersionedExePath -Force
Copy-Item -LiteralPath $ExePath -Destination $DesktopPath -Force
Write-Host "Built single-file executable: $VersionedExePath"
Write-Host "Copied latest executable: $DesktopPath"
