$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$SrcPath = Join-Path $ProjectRoot "src"
$Launcher = Join-Path $ProjectRoot "SafeBox.pyw"
$AssetsDir = Join-Path $ProjectRoot "src\safebox\ui\assets"
$AssetsData = "$AssetsDir;safebox\ui\assets"
$Icon = Join-Path $ProjectRoot "src\safebox\ui\assets\safebox.ico"
$BuildDir = Join-Path $ProjectRoot "build"
$DistDir = Join-Path $ProjectRoot "dist"
$ZipPath = Join-Path $DistDir "SafeBox-portable.zip"

if (Test-Path -LiteralPath $ZipPath) {
    Remove-Item -LiteralPath $ZipPath -Force
}

python -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --name SafeBox `
    --icon "$Icon" `
    --paths "$SrcPath" `
    --add-data "$AssetsData" `
    "$Launcher"

if (Test-Path -LiteralPath $ZipPath) {
    Remove-Item -LiteralPath $ZipPath -Force
}

Compress-Archive -Path (Join-Path $DistDir "SafeBox") -DestinationPath $ZipPath -Force
Write-Host "Built portable package: $ZipPath"
