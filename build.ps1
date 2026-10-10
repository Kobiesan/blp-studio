param([string]$Python = 'py')
$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe')) {
        if ($Python -eq 'py') { & $Python -3.12 -m venv .venv }
        else { & $Python -m venv .venv }
        if ($LASTEXITCODE) { throw 'Creating virtual environment failed' }
    }
    $buildPython = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
    & $buildPython -m pip install -r requirements-build.txt
    if ($LASTEXITCODE) { throw 'Installing dependencies failed' }
    foreach ($test in @('test_blp_studio.py','test_formats.py','test_desktop.py')) {
        & $buildPython $test
        if ($LASTEXITCODE) { throw "Failed: $test" }
    }
    & $buildPython -m PyInstaller --noconfirm BLPStudio.spec
    if ($LASTEXITCODE) { throw 'Build failed' }
    & $buildPython test_release.py dist/BLPStudio.exe
    if ($LASTEXITCODE) { throw 'Executable checks failed' }
    & $buildPython package_release.py dist/BLPStudio.exe
    if ($LASTEXITCODE) { throw 'Packaging failed' }
} finally { Pop-Location }
