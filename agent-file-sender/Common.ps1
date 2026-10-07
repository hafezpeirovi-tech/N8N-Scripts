Set-StrictMode -Version Latest

function Write-DeliveryJson {
    param([string]$Path, [object]$Value)
    $text = $Value | ConvertTo-Json -Depth 30
    [IO.File]::WriteAllText($Path, $text, [Text.UTF8Encoding]::new($false))
}

function Get-DeliveryFingerprint {
    param([string]$FileHash, [string]$FileName, [string]$Caption, [string]$ChatId)
    $data = @($FileHash, $FileName, $Caption, $ChatId) | ConvertTo-Json -Compress
    $sha = [Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($data)))).Replace('-', '').ToLowerInvariant() }
    finally { $sha.Dispose() }
}

function Assert-DeliveryFile {
    param([string]$FilePath, [string]$Caption)
    if ($Caption.Length -gt 1024) { throw 'Caption exceeds 1024 UTF-16 characters.' }
    $file = Get-Item -LiteralPath $FilePath -ErrorAction Stop
    if ($file.PSIsContainer -or $file.PSProvider.Name -ne 'FileSystem') { throw 'A local file is required.' }
    if ($file.Length -eq 0) { throw 'Empty files cannot be sent.' }
    if ($file.Length -gt 50000000) { throw 'File exceeds the configured Telegram limit of 50,000,000 bytes.' }
    return $file
}

function Read-TelegramReceipt {
    param([string]$LogPath, [string]$ChatId, [string]$FileName, [long]$FileSize)
    if (-not (Test-Path -LiteralPath $LogPath)) { return $null }
    $raw = [IO.File]::ReadAllText($LogPath)
    $starts = [regex]::Matches($raw, '(?m)^\{\r?$')
    $ends = [regex]::Matches($raw, '(?m)^\}\r?$')
    foreach ($start in $starts) {
        foreach ($end in $ends) {
            if ($end.Index -le $start.Index) { continue }
            try {
                $result = $raw.Substring($start.Index, $end.Index + 1 - $start.Index) | ConvertFrom-Json -ErrorAction Stop
                if (-not $result.PSObject.Properties['data']) { continue }
                if (-not $result.data.PSObject.Properties['resultData']) { continue }
                if (-not $result.data.resultData.PSObject.Properties['runData']) { continue }
                $runData = $result.data.resultData.runData
                if (-not $runData.PSObject.Properties['Send file to owner']) { continue }
                foreach ($run in $runData.'Send file to owner') {
                    if (-not $run.PSObject.Properties['data']) { continue }
                    foreach ($batch in $run.data.main) {
                        foreach ($item in $batch) {
                            $message = $item.json
                            if ($message.PSObject.Properties['result']) { $message = $message.result }
                            if (-not $message.PSObject.Properties['document'] -or -not $message.PSObject.Properties['message_id']) { continue }
                            if ([string]$message.chat.id -ne $ChatId) { continue }
                            if ([string]$message.document.file_name -ne $FileName -or [long]$message.document.file_size -ne $FileSize) { continue }
                            return [pscustomobject]@{
                                messageId = [long]$message.message_id
                                chatId = [string]$message.chat.id
                                fileName = [string]$message.document.file_name
                                bytes = [long]$message.document.file_size
                                telegramDate = [long]$message.date
                            }
                        }
                    }
                }
            } catch { continue }
        }
    }
    return $null
}

function Assert-LocalDeliveryAuthorization {
    param([ValidateSet('CHAT_ADMIN','HERMES_CONFIG_WRITE')][string]$Category)
    $guard = Join-Path ([Environment]::GetFolderPath('UserProfile')) '.n8n\security\hermes-local-guard\Test-HermesSession.ps1'
    if (-not (Test-Path -LiteralPath $guard)) { throw 'The existing local authorization guard is required.' }
    $authorization = @(& $guard -Category $Category)
    if (-not ($authorization -match "LOCAL_SESSION_AUTHORIZED category=$Category boot_bound=true")) {
        throw 'Local authorization was not confirmed. Do not send or bypass the guard.'
    }
}

function Set-DeliveryProcessEnvironment {
    param([object]$Config, [string]$AllowedDirectory)
    $names = @('NODE_USE_ENV_PROXY','HTTP_PROXY','HTTPS_PROXY','NO_PROXY','N8N_RUNNERS_BROKER_PORT','N8N_RESTRICT_FILE_ACCESS_TO')
    $old = @{}
    foreach ($name in $names) { $old[$name] = [Environment]::GetEnvironmentVariable($name, 'Process') }
    if ($Config.proxyUrl) {
        $env:NODE_USE_ENV_PROXY = '1'
        $env:HTTP_PROXY = $Config.proxyUrl
        $env:HTTPS_PROXY = $Config.proxyUrl
        $env:NO_PROXY = 'localhost,127.0.0.1,::1'
    }
    $env:N8N_RUNNERS_BROKER_PORT = [string]$Config.brokerPort
    $env:N8N_RESTRICT_FILE_ACCESS_TO = $AllowedDirectory
    return $old
}

function Restore-DeliveryProcessEnvironment {
    param([hashtable]$Previous)
    foreach ($name in $Previous.Keys) { [Environment]::SetEnvironmentVariable($name, $Previous[$name], 'Process') }
}
