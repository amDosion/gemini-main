<#
  gemini-main 一键启动脚本 (Windows / PowerShell)
  前端 Vite :21573 / 后端 FastAPI(uvicorn) :21574
  后端经项目虚拟环境 backend\.venv 启动(与 `npm run dev` 同一 venv 与命令)。

  默认行为:为后端、前端各弹出一个独立终端窗口(关窗即停对应服务),就绪后自动打开浏览器。

  用法(推荐双击 start.bat,无需手动设执行策略):
    .\start.ps1                可见双终端启动(后端窗口 + 前端窗口)
    .\start.ps1 -Background    后台隐藏窗口启动,日志写到 .\logs\
    .\start.ps1 -NoBrowser     不自动打开浏览器
    .\start.ps1 -SkipChecks    跳过 PostgreSQL / Redis 端口探测
    .\start.ps1 -Force         端口被占用时也强制启动(绕过"已在运行"判断)

  停止:双击 stop.bat,或关闭弹出的两个服务终端。
#>
[CmdletBinding()]
param(
  [switch]$Background,
  [switch]$NoBrowser,
  [switch]$SkipChecks,
  [switch]$Force
)

$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}

# ---- 路径(锚定脚本所在目录,即项目根) ----
$Root    = $PSScriptRoot
$Backend = Join-Path $Root 'backend'
$LogDir  = Join-Path $Root 'logs'
$EnvFile = Join-Path $Backend '.env'

# 后端 venv python:与 scripts/backend-python.mjs 同源解析顺序
$VenvCandidates = @(
  (Join-Path $Backend '.venv\Scripts\python.exe'),
  (Join-Path $Backend '.venv\bin\python'),
  (Join-Path $Backend '.venv-linux\bin\python')
)
$VenvPy = $VenvCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1

# ---- 端口(单一真相源:与 npm run dev / vite.config.ts 保持一致) ----
$FrontPort = 21573   # 前端 Vite(vite.config.ts: server.port=21573)
$BackPort  = 21574   # 后端 uvicorn --port(根 package.json dev 脚本固定 21574)

# ---- 读取 backend\.env 任意键值(去引号/空白) ----
function Get-EnvValue {
  param([string]$Path, [string]$Key, [string]$Default)
  if (Test-Path -LiteralPath $Path) {
    $m = Select-String -LiteralPath $Path -Pattern ("^\s*{0}\s*=\s*(.+?)\s*$" -f [regex]::Escape($Key)) -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($m) { return $m.Matches[0].Groups[1].Value.Trim().Trim('"').Trim("'") }
  }
  return $Default
}

# 从 DATABASE_URL 解析 PG host:port(仅用于端口探测;绝不回显含密码的连接串) ----
function Get-DbHostPort {
  param([string]$Path)
  $res = [pscustomobject]@{ Host = '127.0.0.1'; Port = 5432 }
  if (Test-Path -LiteralPath $Path) {
    $m = Select-String -LiteralPath $Path -Pattern '^\s*DATABASE_URL\s*=\s*(.+?)\s*$' -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($m) {
      $url = $m.Matches[0].Groups[1].Value
      $mm = [regex]::Match($url, '@([^:@/]+):(\d+)')
      if ($mm.Success) { $res.Host = $mm.Groups[1].Value; $res.Port = [int]$mm.Groups[2].Value }
    }
  }
  return $res
}

$Db        = Get-DbHostPort $EnvFile
$PgHost    = $Db.Host
$PgPort    = $Db.Port
$RedisHost = Get-EnvValue $EnvFile 'REDIS_HOST' '127.0.0.1'
$RedisPort = [int](Get-EnvValue $EnvFile 'REDIS_PORT' '6379')

# ---- 输出小工具 ----
function Write-Step($m) { Write-Host "[启动] $m" -ForegroundColor Cyan }
function Write-Ok($m)   { Write-Host "  [OK] $m" -ForegroundColor Green }
function Write-Note($m) { Write-Host "  [!]  $m" -ForegroundColor Yellow }
function Write-Bad($m)  { Write-Host "  [×]  $m" -ForegroundColor Red }

# ---- TCP 就绪探测(不依赖 Test-NetConnection,PS5.1 兼容) ----
function Test-Port {
  param([string]$ComputerName = '127.0.0.1', [int]$Port, [int]$TimeoutMs = 700)
  $client = New-Object System.Net.Sockets.TcpClient
  try {
    $iar = $client.BeginConnect($ComputerName, $Port, $null, $null)
    if ($iar.AsyncWaitHandle.WaitOne($TimeoutMs) -and $client.Connected) {
      $client.EndConnect($iar); return $true
    }
    return $false
  } catch { return $false } finally { $client.Close() }
}

# ---- 取某端口的监听进程 PID(Get-NetTCPConnection 优先,netstat 回退) ----
function Get-ListenerPids {
  param([int]$Port)
  $ids = @()
  try {
    $conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction Stop
    $ids = @($conns | Select-Object -ExpandProperty OwningProcess -Unique)
  } catch {
    $rows = netstat -ano -p tcp 2>$null | Select-String -Pattern (":{0}\s" -f $Port)
    foreach ($r in $rows) {
      $mm = [regex]::Match($r.ToString(), 'LISTENING\s+(\d+)')
      if ($mm.Success) { $ids += [int]$mm.Groups[1].Value }
    }
    $ids = @($ids | Select-Object -Unique)
  }
  return $ids
}

# ---- 判断端口监听者是否本项目期望进程 ----
function Get-PortState {
  param([int]$Port, [string[]]$Names)
  $st = [pscustomobject]@{ Listening = $false; Mine = $false; Proc = $null }
  $ids = Get-ListenerPids -Port $Port
  if ($ids.Count -gt 0) { $st.Listening = $true }
  foreach ($id in $ids) {
    if ($id -le 0) { continue }
    try { $p = Get-Process -Id $id -ErrorAction Stop } catch { continue }
    if (-not $st.Proc) { $st.Proc = $p }
    if ($Names | Where-Object { $p.ProcessName -like $_ }) { $st.Mine = $true; $st.Proc = $p; break }
  }
  return $st
}

Write-Host ''
Write-Host '==================================================' -ForegroundColor Green
Write-Host (" gemini-main 一键启动 (frontend :{0} / backend :{1})" -f $FrontPort, $BackPort) -ForegroundColor Green
Write-Host '==================================================' -ForegroundColor Green

# ---- 1. 环境前置检查 ----
Write-Step '环境检查'
if (-not $VenvPy) {
  Write-Bad "未找到后端虚拟环境:$($Backend)\.venv\Scripts\python.exe"
  Write-Host '       首次请安装:cd backend; python -m venv .venv; .venv\Scripts\activate; pip install -r requirements.txt' -ForegroundColor Gray
  exit 1
}
Write-Ok "后端 venv 已就绪:$VenvPy"

if (-not (Test-Path -LiteralPath (Join-Path $Root 'node_modules'))) {
  Write-Bad '未找到前端依赖 node_modules(根目录)'
  Write-Host '       首次请执行:npm install' -ForegroundColor Gray
  exit 1
}
Write-Ok '前端 node_modules 已就绪'

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
  Write-Bad '未找到 node,请先安装 Node.js'
  exit 1
}
Write-Ok 'Node.js 已就绪(前端经 npx vite 启动)'

# ---- 2. 依赖服务探测(仅告警,不阻断;TCP 探测只验证端口可达,不校验账号/密码/库) ----
if (-not $SkipChecks) {
  if (Test-Port -ComputerName $PgHost -Port $PgPort) { Write-Ok "PostgreSQL ($($PgHost):$PgPort) 端口可达(未校验账号/密码/库)" }
  else { Write-Note "PostgreSQL ($($PgHost):$PgPort) 未连通 — 请确认数据库已启动且网络可达(连接信息见 backend\.env 的 DATABASE_URL)" }
  if (Test-Port -ComputerName $RedisHost -Port $RedisPort) { Write-Ok "Redis ($($RedisHost):$RedisPort) 端口可达(未校验密码/库)" }
  else { Write-Note "Redis ($($RedisHost):$RedisPort) 未连通 — 请确认 Redis 已启动且网络可达(连接信息见 backend\.env)" }
}

# ---- 3. 端口占用判定(本项目进程才视为"已在运行";无关进程占用即报冲突) ----
$backRunning = $false
$frontRunning = $false
if (-not $Force) {
  $bk = Get-PortState -Port $BackPort -Names @('python*', 'pythonw*')
  if ($bk.Listening) {
    if ($bk.Mine) { $backRunning = $true; Write-Note "后端端口 $BackPort 已由本项目 python 占用,跳过后端启动" }
    elseif (-not $bk.Proc) { $backRunning = $true; Write-Note "后端端口 $BackPort 已被占用(无法确认进程),跳过后端启动" }
    else {
      Write-Bad "后端端口 $BackPort 被无关进程占用:$($bk.Proc.ProcessName) PID=$($bk.Proc.Id)"
      Write-Host '       请先释放该端口 / 运行 stop.bat,或用 -Force 强制继续。' -ForegroundColor Gray
      exit 1
    }
  }
  $fk = Get-PortState -Port $FrontPort -Names @('node*')
  if ($fk.Listening) {
    if ($fk.Mine) { $frontRunning = $true; Write-Note "前端端口 $FrontPort 已由本项目 node 占用,跳过前端启动" }
    elseif (-not $fk.Proc) { $frontRunning = $true; Write-Note "前端端口 $FrontPort 已被占用(无法确认进程),跳过前端启动" }
    else {
      Write-Bad "前端端口 $FrontPort 被无关进程占用:$($fk.Proc.ProcessName) PID=$($fk.Proc.Id)"
      Write-Host '       请先释放该端口 / 运行 stop.bat,或用 -Force 强制继续。' -ForegroundColor Gray
      exit 1
    }
  }
} else {
  Write-Note '-Force 指定,跳过端口占用检查,直接尝试启动'
}

# 子进程继承 UTF-8 与无缓冲输出
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUNBUFFERED = '1'
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

# uvicorn 参数(与 npm run dev 完全一致)
$UvicornArgs = @('-m', 'uvicorn', 'app.main:app', '--reload', '--reload-dir', 'app', '--host', '0.0.0.0', '--port', "$BackPort", '--log-level', 'info')

# ---- 4. 启动后端(独立终端 / 后台) ----
if (-not $backRunning) {
  Write-Step "启动后端 (FastAPI :$BackPort, venv) — 独立终端"
  if ($Background) {
    $o = Join-Path $LogDir 'backend.out.log'; $e = Join-Path $LogDir 'backend.err.log'
    Start-Process -FilePath $VenvPy -ArgumentList $UvicornArgs -WorkingDirectory $Backend `
      -WindowStyle Hidden -RedirectStandardOutput $o -RedirectStandardError $e
    Write-Ok "后端已后台启动,日志:$o"
  } else {
    # WorkingDirectory=backend,用相对 .venv\Scripts\python.exe(路径无空格,规避 cmd /k 引号陷阱)
    $c = 'chcp 65001>nul && title gemini-backend :' + $BackPort + ' && set PYTHONIOENCODING=utf-8 && set PYTHONUNBUFFERED=1 && .venv\Scripts\python.exe ' + ($UvicornArgs -join ' ')
    Start-Process -FilePath 'cmd.exe' -ArgumentList '/k', $c -WorkingDirectory $Backend
    Write-Ok '后端独立终端已打开(关闭该窗口即停止后端)'
  }
}

# ---- 5. 启动前端(独立终端 / 后台) ----
if (-not $frontRunning) {
  Write-Step "启动前端 (Vite :$FrontPort) — 独立终端"
  if ($Background) {
    $o = Join-Path $LogDir 'frontend.out.log'; $e = Join-Path $LogDir 'frontend.err.log'
    Start-Process -FilePath 'cmd.exe' -ArgumentList '/c', 'chcp 65001>nul && npx vite' -WorkingDirectory $Root `
      -WindowStyle Hidden -RedirectStandardOutput $o -RedirectStandardError $e
    Write-Ok "前端已后台启动,日志:$o"
  } else {
    $c = 'chcp 65001>nul && title gemini-frontend :' + $FrontPort + ' && npx vite'
    Start-Process -FilePath 'cmd.exe' -ArgumentList '/k', $c -WorkingDirectory $Root
    Write-Ok '前端独立终端已打开(关闭该窗口即停止前端)'
  }
}

# ---- 6. 等待前端就绪并打开浏览器(墙钟上限 120s;Vite 首次冷启动依赖预打包较慢) ----
if (-not $NoBrowser) {
  if (-not $frontRunning) {
    Write-Step '等待前端就绪(最多 120 秒,Vite 首次编译较慢)…'
    $deadline = (Get-Date).AddSeconds(120)
    $ready = $false
    while ((Get-Date) -lt $deadline) {
      if (Test-Port -Port $FrontPort) { $ready = $true; break }
      Start-Sleep -Milliseconds 600
    }
    if ($ready) {
      Write-Ok '前端端口已就绪,正在打开浏览器'
      try { Start-Process "http://localhost:$FrontPort/" }
      catch { Write-Note "无法自动打开浏览器,请手动访问 http://localhost:$FrontPort/" }
    } else {
      Write-Note "等待超时,请稍后手动打开 http://localhost:$FrontPort/"
    }
  } else {
    try { Start-Process "http://localhost:$FrontPort/" } catch {}
  }
}

# ---- 7. 汇总 ----
Write-Host ''
Write-Host '==================================================' -ForegroundColor Green
Write-Host ' 启动完成' -ForegroundColor Green
Write-Host "  前端:  http://localhost:$FrontPort/" -ForegroundColor White
Write-Host "  后端:  http://localhost:$BackPort/docs" -ForegroundColor White
Write-Host '  账号:  使用你自己注册的账号登录(本项目无固定默认账号)' -ForegroundColor White
if ($Background) { Write-Host "  日志:  $LogDir" -ForegroundColor White }
Write-Host '  停止:  双击 stop.bat(或关闭两个服务终端)' -ForegroundColor White
Write-Host '==================================================' -ForegroundColor Green
