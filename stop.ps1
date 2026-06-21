<#
  gemini-main 一键停止脚本 (Windows / PowerShell)
  结束占用前端 :21573(node/vite)与后端 :21574(python/uvicorn)的本项目进程树。

  用法(推荐双击 stop.bat):
    .\stop.ps1           仅结束"本项目期望进程"(前端 node / 后端 python)占用的端口
    .\stop.ps1 -Force    端口被任意进程占用也一并结束(谨慎)
#>
[CmdletBinding()]
param([switch]$Force)

$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}

$FrontPort = 21573
$BackPort  = 21574

function Write-Ok($m)   { Write-Host "  [OK] $m" -ForegroundColor Green }
function Write-Note($m) { Write-Host "  [!]  $m" -ForegroundColor Yellow }

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

# 结束指定端口监听者的整棵进程树;仅当进程名匹配 $Names 或 -Force 时执行
function Stop-PortTree {
  param([int]$Port, [string[]]$Names, [string]$Label)
  $ids = Get-ListenerPids -Port $Port
  if ($ids.Count -eq 0) { Write-Note "$Label 端口 $Port 未在监听,跳过"; return }
  foreach ($id in $ids) {
    if ($id -le 0) { continue }
    try { $p = Get-Process -Id $id -ErrorAction Stop } catch { continue }
    $match = [bool]($Names | Where-Object { $p.ProcessName -like $_ })
    if (-not $match -and -not $Force) {
      Write-Note "$Label 端口 $Port 被无关进程占用:$($p.ProcessName) PID=$($p.Id) — 未结束(加 -Force 可强制)"
      continue
    }
    try {
      taskkill /PID $id /T /F 2>&1 | Out-Null
      Write-Ok "$Label 已结束:$($p.ProcessName) PID=$id(含子进程树)"
    } catch {
      Write-Note "$Label 结束 PID=$id 失败:$($_.Exception.Message)"
    }
  }
}

Write-Host ''
Write-Host '==================================================' -ForegroundColor Green
Write-Host ' gemini-main 一键停止' -ForegroundColor Green
Write-Host '==================================================' -ForegroundColor Green

Stop-PortTree -Port $FrontPort -Names @('node*')             -Label '前端'
Stop-PortTree -Port $BackPort  -Names @('python*','pythonw*') -Label '后端'

Start-Sleep -Milliseconds 600
$frontUp = (Get-ListenerPids -Port $FrontPort).Count -gt 0
$backUp  = (Get-ListenerPids -Port $BackPort).Count -gt 0
Write-Host ''
if (-not $frontUp) { Write-Ok "前端端口 $FrontPort 已释放" } else { Write-Note "前端端口 $FrontPort 仍被占用" }
if (-not $backUp)  { Write-Ok "后端端口 $BackPort 已释放" }  else { Write-Note "后端端口 $BackPort 仍被占用" }
Write-Host '==================================================' -ForegroundColor Green
