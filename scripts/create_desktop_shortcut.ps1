$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Launcher = Join-Path $ProjectRoot "SafeBox.pyw"
$Icon = Join-Path $ProjectRoot "src\safebox\ui\assets\safebox.ico"
$Pythonw = Join-Path (Split-Path (Get-Command python).Source -Parent) "pythonw.exe"

if (-not (Test-Path -LiteralPath $Pythonw)) {
    throw "pythonw.exe was not found. Install Python and make sure the python command is available."
}

$Desktop = [Environment]::GetFolderPath('Desktop')
$ShortcutPath = Join-Path $Desktop "SafeBox.lnk"
$Shell = New-Object -ComObject WScript.Shell
$Shortcut = $Shell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $Pythonw
$Shortcut.Arguments = "`"$Launcher`""
$Shortcut.WorkingDirectory = $ProjectRoot
$Shortcut.IconLocation = $Icon
$Shortcut.Description = "SafeBox"
$Shortcut.Save()

Write-Host "Created desktop shortcut: $ShortcutPath"
