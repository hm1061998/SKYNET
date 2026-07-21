# Cai-Hermes.ps1 - Cai dat Hermes Agent va di tru du lieu tu Agent
# Chay: powershell -ExecutionPolicy Bypass -File F:\Project\Agent\hermes-migration\Cai-Hermes.ps1
# (Thong bao viet khong dau de tranh loi font tren PowerShell cu)

$ErrorActionPreference = "Stop"
try { [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12 } catch {}
$here = $PSScriptRoot

Write-Host "=== Di tru Agent -> Hermes Agent ===" -ForegroundColor Cyan

# --- 1. Cai Hermes Agent (neu chua co) ---
if (-not (Get-Command hermes -ErrorAction SilentlyContinue)) {
    Write-Host "[1/4] Chua thay lenh 'hermes' - dang chay trinh cai dat chinh thuc..." -ForegroundColor Yellow
    iex (irm https://hermes-agent.nousresearch.com/install.ps1)
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "User") + ";" +
                [Environment]::GetEnvironmentVariable("Path", "Machine")
    if (-not (Get-Command hermes -ErrorAction SilentlyContinue)) {
        Write-Host "Cai xong nhung 'hermes' chua co trong PATH cua phien nay." -ForegroundColor Yellow
        Write-Host "Hay MO LAI PowerShell roi chay lai script nay de hoan tat di tru." -ForegroundColor Yellow
        exit 0
    }
} else {
    Write-Host "[1/4] Hermes da duoc cai dat." -ForegroundColor Green
}

# --- Xac dinh thu muc du lieu cua Hermes (Windows native: AppData\Local\hermes) ---
$candidates = @(
    (Join-Path $env:LOCALAPPDATA "hermes"),
    (Join-Path $env:USERPROFILE ".hermes")
)
$hermesDir = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $hermesDir) { $hermesDir = $candidates[0]; New-Item -ItemType Directory -Force -Path $hermesDir | Out-Null }
Write-Host ("      Thu muc Hermes: " + $hermesDir)

# --- 2. Copy skills da di tru ---
Write-Host "[2/4] Copy skills (video-toolkit, meeting-minutes)..." -ForegroundColor Cyan
$skillsDst = Join-Path $hermesDir "skills"
New-Item -ItemType Directory -Force -Path $skillsDst | Out-Null
Copy-Item -Recurse -Force (Join-Path $here "skills\*") $skillsDst

# --- 3. Model + cau hinh (dung 'hermes config set' de gop vao config co san) ---
Write-Host "[3/4] Cau hinh model DeepSeek..." -ForegroundColor Cyan
hermes config set model.provider deepseek
hermes config set model.default deepseek-v4-pro
hermes config set skills.config.agent.ffmpeg_dir "F:\Project\Agent\Tool"
hermes config set skills.config.agent.uploads_dir "F:\Project\Agent\Uploads"

# --- 4. API keys (doc tu config.json cua Agent; 'config set' tu luu key vao .env) ---
Write-Host "[4/4] Ghi API key..." -ForegroundColor Cyan
$agentCfgPath = Join-Path (Split-Path $here -Parent) "config.json"
if (Test-Path $agentCfgPath) {
    $agentCfg = Get-Content $agentCfgPath -Raw | ConvertFrom-Json
    if (-not [string]::IsNullOrWhiteSpace($agentCfg.deepseek.api_key)) {
        hermes config set DEEPSEEK_API_KEY "$($agentCfg.deepseek.api_key)"
        Write-Host "      Da ghi DEEPSEEK_API_KEY." -ForegroundColor Green
    }
    if (-not [string]::IsNullOrWhiteSpace($agentCfg.openai.api_key)) {
        hermes config set OPENAI_API_KEY "$($agentCfg.openai.api_key)"
        Write-Host "      Da ghi OPENAI_API_KEY (dung cho Whisper transcribe)." -ForegroundColor Green
    }
} else {
    Write-Host "      Khong tim thay config.json cua Agent - tu them key: hermes config set DEEPSEEK_API_KEY <key>" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=== XONG! Buoc tiep theo ===" -ForegroundColor Green
Write-Host "1. Kiem tra:  hermes doctor"
Write-Host "2. Chay:  F:\Project\Agent\Chay-Hermes.bat   (hoac go 'hermes')"
Write-Host "3. Trong phien dau tien, dan cau sau de Hermes ghi nho boi canh cu cua Agent:"
Write-Host '   Doc file F:\Project\Agent\hermes-migration\MIGRATION-NOTES.md va luu cac fact quan trong vao memory'
Write-Host "4. Thu ngay:  'Tao bien ban cuoc hop tu video moi nhat trong Uploads'"
