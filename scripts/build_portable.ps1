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
if (-not (Test-Path -LiteralPath $DistDir)) {
    New-Item -ItemType Directory -Path $DistDir | Out-Null
}
$ExePath = Join-Path $DistDir "SafeBox.exe"
$VersionedExePath = Join-Path $DistDir "SafeBox-v$Version-Windows-x64.exe"
$FastBuildDir = Join-Path $DistDir "SafeBox"
$FastReleaseDir = Join-Path $DistDir "SafeBox-v$Version-Windows-x64-fast"
$FastReleaseZip = Join-Path $DistDir "SafeBox-v$Version-Windows-x64-fast.zip"
$FastReleaseExe = Join-Path $FastReleaseDir "SafeBox.exe"
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
$DesktopShortcutPath = Join-Path $DesktopDir "SafeBox.lnk"

function Assert-UnderDirectory {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        [string]$Directory
    )

    $FullPath = [IO.Path]::GetFullPath($Path)
    $FullDirectory = [IO.Path]::GetFullPath($Directory).TrimEnd('\')
    if (-not $FullPath.StartsWith("$FullDirectory\", [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to delete path outside expected directory: $FullPath"
    }
}

if (Test-Path -LiteralPath $ExePath) {
    Remove-Item -LiteralPath $ExePath -Force
}

if (Test-Path -LiteralPath $VersionedExePath) {
    Remove-Item -LiteralPath $VersionedExePath -Force
}

Assert-UnderDirectory -Path $FastBuildDir -Directory $DistDir
if (Test-Path -LiteralPath $FastBuildDir) {
    Remove-Item -LiteralPath $FastBuildDir -Recurse -Force
}

Assert-UnderDirectory -Path $FastReleaseDir -Directory $DistDir
if (Test-Path -LiteralPath $FastReleaseDir) {
    Remove-Item -LiteralPath $FastReleaseDir -Recurse -Force
}

if (Test-Path -LiteralPath $FastReleaseZip) {
    Remove-Item -LiteralPath $FastReleaseZip -Force
}

if (Test-Path -LiteralPath $DesktopPath) {
    Remove-Item -LiteralPath $DesktopPath -Force
}

if (Test-Path -LiteralPath $DesktopShortcutPath) {
    Remove-Item -LiteralPath $DesktopShortcutPath -Force
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

& $Python -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --onedir `
    --name SafeBox `
    --icon "$Icon" `
    --paths "$SrcPath" `
    --add-data "$AssetsData" `
    "$Launcher"

Move-Item -LiteralPath $FastBuildDir -Destination $FastReleaseDir
Compress-Archive -LiteralPath $FastReleaseDir -DestinationPath $FastReleaseZip -Force

$Shell = New-Object -ComObject WScript.Shell
$Shortcut = $Shell.CreateShortcut($DesktopShortcutPath)
$Shortcut.TargetPath = $FastReleaseExe
$Shortcut.WorkingDirectory = $FastReleaseDir
$Shortcut.IconLocation = "$FastReleaseExe,0"
$Shortcut.Description = "SafeBox fast startup build"
$Shortcut.Save()

Write-Host "Built single-file executable: $VersionedExePath"
Write-Host "Built fast startup package: $FastReleaseZip"
Write-Host "Created desktop shortcut: $DesktopShortcutPath"
