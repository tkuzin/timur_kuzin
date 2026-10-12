$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$pythonExe = Join-Path (Get-Location) '.venv/Scripts/python.exe'
$stdout = Join-Path (Get-Location) '.local/server.out.log'
$stderr = Join-Path (Get-Location) '.local/server.err.log'
$proc = Start-Process -FilePath $pythonExe -ArgumentList @('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8080', '--no-access-log') -WorkingDirectory (Get-Location) -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru
$proc.Id | Set-Content '.local/server.pid'
Write-Output "timur_kuzin: http://127.0.0.1:8080 (PID $($proc.Id))"
