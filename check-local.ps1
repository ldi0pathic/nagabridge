param(
    [switch]$Setup,
    [switch]$CheckOnly,
    [switch]$SkipMypy,
    [switch]$SkipPytest,
    [string]$PythonPath
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $RepoRoot

function Invoke-Step {
    param(
        [string]$Name,
        [scriptblock]$Command
    )

    Write-Host ""
    Write-Host "==> $Name" -ForegroundColor Cyan
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Name failed with exit code $LASTEXITCODE"
    }
}

function Test-Python {
    param([string]$PythonPath)

    if (-not $PythonPath) {
        return $false
    }

    try {
        & $PythonPath --version *> $null
        return $LASTEXITCODE -eq 0
    }
    catch {
        return $false
    }
}

function Find-BasePython {
    if ($PythonPath) {
        if (Test-Python $PythonPath) {
            return $PythonPath
        }
        throw "PythonPath ist nicht lauffaehig: $PythonPath"
    }

    foreach ($Candidate in @("py -3.12", "py -3", "python")) {
        $Parts = $Candidate.Split(" ")
        $Exe = $Parts[0]
        $Args = @()
        if ($Parts.Count -gt 1) {
            $Args = $Parts[1..($Parts.Count - 1)]
        }

        try {
            & $Exe @Args --version *> $null
            if ($LASTEXITCODE -eq 0) {
                return $Candidate
            }
        }
        catch {
        }
    }

    throw "Kein lauffaehiger Python gefunden. Installiere Python 3.12 oder uebergib -PythonPath."
}

function Invoke-Python {
    param(
        [string]$PythonCommand,
        [string[]]$Arguments
    )

    $Parts = $PythonCommand.Split(" ")
    $Exe = $Parts[0]
    $BaseArgs = @()
    if ($Parts.Count -gt 1) {
        $BaseArgs = $Parts[1..($Parts.Count - 1)]
    }

    & $Exe @BaseArgs @Arguments
}

$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$VenvExists = Test-Path (Join-Path $RepoRoot ".venv")

if (-not (Test-Python $VenvPython)) {
    if ($VenvExists) {
        throw ".venv existiert, ist aber nicht lauffaehig. Entferne sie einmalig mit: Remove-Item .venv -Recurse -Force; danach: .\check-local.ps1 -Setup"
    }

    if (-not $Setup) {
        throw ".venv fehlt. Starte zuerst: .\check-local.ps1 -Setup"
    }

    $BasePython = Find-BasePython
    Write-Host "Erzeuge .venv mit: $BasePython"
    Invoke-Step "Create virtual environment" {
        Invoke-Python $BasePython @("-m", "venv", ".venv")
    }
}

$Python = $VenvPython
Write-Host "Python: $Python"

if ($Setup) {
    Invoke-Step "Install dev dependencies" {
        Invoke-Python $Python @("-m", "pip", "install", "--upgrade", "pip")
        if ($LASTEXITCODE -ne 0) {
            exit $LASTEXITCODE
        }
        Invoke-Python $Python @("-m", "pip", "install", "-e", ".[dev]")
    }
}

$TempDir = Join-Path $RepoRoot ".tmp"
New-Item -ItemType Directory -Force -Path $TempDir | Out-Null
$env:TEMP = $TempDir
$env:TMP = $TempDir

if ($CheckOnly) {
    Invoke-Step "Ruff check" {
        Invoke-Python $Python @("-m", "ruff", "check", "src/", "tests/")
    }
    Invoke-Step "Ruff format check" {
        Invoke-Python $Python @("-m", "ruff", "format", "--check", "src/", "tests/")
    }
}
else {
    Invoke-Step "Ruff fix" {
        Invoke-Python $Python @("-m", "ruff", "check", "src/", "tests/", "--fix")
    }
    Invoke-Step "Ruff format" {
        Invoke-Python $Python @("-m", "ruff", "format", "src/", "tests/")
    }
}
if (-not $SkipMypy) {
    Invoke-Step "Mypy" {
        Invoke-Python $Python @("-m", "mypy", "src/")
    }
}

if (-not $SkipPytest) {
    Invoke-Step "Pytest" {
        Invoke-Python $Python @("-m", "pytest", "tests/", "-v", "--cov=src", "--cov-report=term")
    }
}

Write-Host ""
Write-Host "All local checks passed." -ForegroundColor Green
