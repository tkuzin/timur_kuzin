$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$pgBin = if ($env:PG_BIN) { $env:PG_BIN } else { 'C:/Program Files/PostgreSQL/18/bin' }
if (-not (Test-Path "$pgBin/initdb.exe")) { throw 'Укажите PG_BIN: путь к bin PostgreSQL 18.' }
$localDir = Join-Path (Get-Location) '.local'
New-Item -ItemType Directory -Force $localDir | Out-Null
if (-not (Test-Path '.env')) {
    $dbPassword = [Guid]::NewGuid().ToString('N')
    $secret = [Guid]::NewGuid().ToString('N') + [Guid]::NewGuid().ToString('N')
    @("DATABASE_URL=postgresql+psycopg://timur_kuzin:$dbPassword@localhost:55432/timur_kuzin", "SESSION_SECRET=$secret", 'DEMO_PASSWORD=timur-demo-2026') | Set-Content -Encoding utf8 '.env'
    $dbPassword | Set-Content -Encoding ascii (Join-Path $localDir 'pg-password.txt')
}
$pgData = Join-Path $localDir 'pgdata'
if (-not (Test-Path (Join-Path $pgData 'PG_VERSION'))) {
    $pwFile = Join-Path $localDir 'pg-password.txt'
    & "$pgBin/initdb.exe" -D $pgData -U timur_kuzin --encoding=UTF8 --locale=C --auth=scram-sha-256 "--pwfile=$pwFile"
    if ($LASTEXITCODE -ne 0) { throw 'initdb failed' }
    Add-Content -Encoding ascii (Join-Path $pgData 'postgresql.conf') "`nlisten_addresses = 'localhost'`nport = 55432"
}
& "$pgBin/pg_ctl.exe" status -D $pgData
if ($LASTEXITCODE -ne 0) {
    $pgLog = Join-Path $localDir 'postgres.log'
    $pgArgs = @('start', '-D', ('"' + $pgData + '"'), '-l', ('"' + $pgLog + '"'), '-w')
    $proc = Start-Process -FilePath "$pgBin/pg_ctl.exe" -ArgumentList $pgArgs -WindowStyle Hidden -PassThru
    $proc.WaitForExit()
    if ($proc.ExitCode -ne 0) { throw "PostgreSQL не запущен: $pgLog" }
}
& '.venv/Scripts/python.exe' -m scripts.init_db
if ($LASTEXITCODE -ne 0) { throw 'Database initialization failed' }
