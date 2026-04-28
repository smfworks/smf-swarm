# SMF Swarm — One-line installer for Windows
# Usage: Invoke-Expression (Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/smfworks/smf-swarm/main/install.ps1').Content
# Or (shorter): iwr -useb https://raw.githubusercontent.com/smfworks/smf-swarm/main/install.ps1 | iex

param(
    [string]$PythonMin = "3.10.0"
)

$REPO    = "https://github.com/smfworks/smf-swarm"
$BRANCH  = "main"

function Write-Banner {
    param([string]$Text)
    $pad = [math]::Max(0, 56 - $Text.Length)
    $left = [math]::Floor($pad / 2)
    $right = $pad - $left
    Write-Host "╔$([string]::new('═', 60))╗" -ForegroundColor Cyan
    Write-Host "║$([string]::new(' ', $left))$Text$([string]::new(' ', $right))║" -ForegroundColor Cyan
    Write-Host "╚$([string]::new('═', 60))╝" -ForegroundColor Cyan
}

function Test-VersionGeq {
    param([string]$verA, [string]$verB)
    try {
        $a = [version]$verA
        $b = [version]$verB
        return $a -ge $b
    } catch {
        return $false
    }
}

function Find-Python {
    $candidates = @("python", "python3", "py")
    foreach ($cmd in $candidates) {
        $found = Get-Command $cmd -ErrorAction SilentlyContinue
        if ($found) {
            $raw = & $cmd --version 2>&1
            if ($raw -match '(\d+\.\d+\.\d+)') {
                $ver = $matches[1]
                if (Test-VersionGeq -verA $ver -verB $PythonMin) {
                    return @{ Cmd = $cmd; Version = $ver }
                }
            }
        }
    }

    # py launcher path check
    $versionShort = ($PythonMin -split '\.')[0,1] -join '.'
    $pyLauncher = Get-Command "py" -ErrorAction SilentlyContinue
    if ($pyLauncher) {
        $raw = & py --version 2>&1
        if ($raw -match '(\d+\.\d+\.\d+)') {
            $ver = $matches[1]
            if (Test-VersionGeq -verA $ver -verB $PythonMin) {
                return @{ Cmd = "py"; Version = $ver }
            }
        }
    }

    # Check Python Launcher default
    Write-Host "`n❌ Python $versionShort or higher is required." -ForegroundColor Red
    Write-Host "   Download from: https://python.org/downloads/windows/" -ForegroundColor Yellow
    Write-Host "   Enable 'Add Python to PATH' during installation." -ForegroundColor Yellow
    Exit 1
}

function Find-Pip {
    param([string]$pythonCmd)
    $pipCmd = & $pythonCmd -m pip --version 2>&1
    if ($pipCmd -match 'pip\s+v?(\d+\.\d+)') {
        return $true
    }
    Write-Host "`n❌ pip not found. Installing via ensurepip..." -ForegroundColor Red
    & $pythonCmd -m ensurepip --default-pip | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "   Failed to install pip. Run:`n   $pythonCmd -m ensurepip --upgrade" -ForegroundColor Yellow
        Exit 1
    }
    return $true
}

# ═══════════════════════════════════════════════════════════
Write-Banner "SMF Swarm — One-Line Installer"
Write-Host ""

# ── 1. Find Python ────────────────────────────────────────
Write-Host "🔍 Checking Python..." -ForegroundColor Cyan
$py = Find-Python
$PYTHON = $py.Cmd
$PYVER  = $py.Version
Write-Host "✅ Python found: $PYTHON (v$PYVER)" -ForegroundColor Green

# ── 2. Check pip ──────────────────────────────────────────
Write-Host "🔍 Checking pip..." -ForegroundColor Cyan
Find-Pip -pythonCmd $PYTHON | Out-Null
Write-Host "✅ pip found" -ForegroundColor Green

# ── 3. Install package ────────────────────────────────────
Write-Host ""
Write-Host "📦 Installing smf-swarm from PyPI..." -ForegroundColor Cyan
Write-Host ""
& $PYTHON -m pip install --upgrade smf-swarm
if ($LASTEXITCODE -ne 0) {
    Write-Host "`n❌ pip install failed. Try running as Administrator." -ForegroundColor Red
    Exit 1
}

# ── 4. Verify ─────────────────────────────────────────────
Write-Host ""
Write-Host "🔍 Verifying installation..." -ForegroundColor Cyan

$smfSwarm = Get-Command smf-swarm -ErrorAction SilentlyContinue
if (-not $smfSwarm) {
    # Check Scripts dir in the same Python path
    $pyDir = Split-Path (Get-Command $PYTHON).Source -Parent
    $scriptsDir = Join-Path $pyDir "Scripts"
    $env:PATH = "$scriptsDir;$env:PATH"
    $smfSwarm = Get-Command smf-swarm -ErrorAction SilentlyContinue
}

if ($smfSwarm) {
    & smf-swarm version
    Write-Host ""
    Write-Banner "✅ SMF Swarm installed successfully!"
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Green
    Write-Host "  1. smf-swarm configure       # Run the setup wizard"
    Write-Host "  2. smf-swarm test             # Verify your LLM connection"
    Write-Host "  3. smf-swarm predict `"Will X happen?`" --mode full"
    Write-Host ""

    # ── 5. Check Ollama (optional) ─────────────────────
    Write-Host ""
    Write-Host "🔍 Checking for Ollama..." -ForegroundColor Cyan
    $ollama = Get-Command ollama -ErrorAction SilentlyContinue
    if ($ollama) {
        $ov = & ollama --version 2>&1 | Select-Object -First 1
        Write-Host "✅ Ollama found: $ov" -ForegroundColor Green
    } else {
        Write-Host "  ℹ Ollama not found. Install from: https://ollama.com/download/windows" -ForegroundColor Yellow
    }

    # ── 6. Post-install guidance ─────────────────────────
    Write-Host ""
    Write-Host "📌 Installation method note:" -ForegroundColor Cyan
    Write-Host "  For isolated installs (avoids admin), use pipx:" -ForegroundColor White
    Write-Host "    pipx install smf-swarm" -ForegroundColor White
    Write-Host ""
    Write-Host "  For containerized install:" -ForegroundColor White
    Write-Host "    docker compose up   (from the smf-swarm repo root)" -ForegroundColor White
    Write-Host ""
    Write-Host "Documentation: $REPO" -ForegroundColor DarkGray
    Write-Host "Support:       michael@smfworks.com | @michaelgannotti" -ForegroundColor DarkGray
    Exit 0
} else {
    Write-Host ""
    Write-Host "⚠️  Installation completed but 'smf-swarm' not found in PATH." -ForegroundColor Yellow
    Write-Host "   To fix, add your Python Scripts directory to PATH:" -ForegroundColor Yellow
    Write-Host "   `$env:PATH += `";C:\\Path\\To\\Python\\Scripts`"" -ForegroundColor Yellow
    Exit 1
}
