<#
.SYNOPSIS
Send one explicitly requested local file through the existing n8n Telegram credential.
.EXAMPLE
& .\Send-AgentFile.ps1 -FilePath 'C:\Work\report.pdf' -Caption 'گزارش نهایی'
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$FilePath,
    [string]$Caption = '',
    [ValidatePattern('^[A-Za-z0-9_-]{1,100}$')][string]$RequestId,
    [switch]$Resend,
    [switch]$ValidateOnly,
    [string]$RuntimeRoot = (Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'Codex\AgentFileSender')
)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Common.ps1')
$lock = $null
$previousEnv = $null
$currentRequest = Join-Path $RuntimeRoot 'current-request.json'
$stagedFile = $null
$mayRemoveRequest = $false
try {
    $file = Assert-DeliveryFile -FilePath $FilePath -Caption $Caption
    $config = Get-Content -LiteralPath (Join-Path $RuntimeRoot 'config.json') -Raw | ConvertFrom-Json
    if ($ValidateOnly) {
        [pscustomobject]@{status='validated';fileName=$file.Name;bytes=$file.Length;workflowId=$config.workflowId;sendsFile=$false} | ConvertTo-Json -Compress
        return
    }
    Assert-LocalDeliveryAuthorization -Category CHAT_ADMIN
    try { $lock = [IO.File]::Open((Join-Path $RuntimeRoot 'sender.lock'), 'OpenOrCreate', 'ReadWrite', 'None') }
    catch { throw 'SENDER_BUSY: another delivery is running. No file was sent by this invocation.' }
    $sourceHash = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    $fingerprint = Get-DeliveryFingerprint $sourceHash $file.Name $Caption ([string]$config.chatId)
    if (-not $RequestId) { $RequestId = $fingerprint.Substring(0,32) }
    if ($Resend) { $RequestId += '-' + [Guid]::NewGuid().ToString('N').Substring(0,8) }
    $requestDir = Join-Path (Join-Path $RuntimeRoot 'requests') $RequestId
    New-Item -ItemType Directory -Path $requestDir -Force | Out-Null
    $receiptPath = Join-Path $requestDir 'receipt.json'
    $attemptPath = Join-Path $requestDir 'attempt.json'
    $logPath = Join-Path $requestDir 'execution.log'
    if (Test-Path -LiteralPath $attemptPath) {
        $old = Get-Content -LiteralPath $attemptPath -Raw | ConvertFrom-Json
        if ($old.fingerprint -ne $fingerprint) { throw 'REQUEST_ID_CONFLICT: this request ID belongs to different content.' }
        if (Test-Path -LiteralPath $receiptPath) {
            $receipt = Get-Content -LiteralPath $receiptPath -Raw | ConvertFrom-Json
            $receipt.status = 'already_sent'
            $receipt | ConvertTo-Json -Compress
            return
        }
        $recovered = Read-TelegramReceipt $logPath ([string]$config.chatId) $file.Name $file.Length
        if ($recovered) {
            $receipt = [ordered]@{status='sent';requestId=$RequestId;sha256=$sourceHash;receiptPath=$receiptPath;messageId=$recovered.messageId;fileName=$recovered.fileName;bytes=$recovered.bytes;telegramDate=$recovered.telegramDate;recovered=$true}
            Write-DeliveryJson $receiptPath $receipt
            $receipt | ConvertTo-Json -Compress
            return
        }
        throw 'DELIVERY_UNCERTAIN: a prior attempt has no confirmed receipt. Inspect its execution; do not automatically resend.'
    }
    $staging = Join-Path $requestDir 'staged'
    New-Item -ItemType Directory -Path $staging -Force | Out-Null
    $stagedFile = Join-Path $staging $file.Name
    Copy-Item -LiteralPath $file.FullName -Destination $stagedFile
    $stagedHash = (Get-FileHash -LiteralPath $stagedFile -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($stagedHash -ne $sourceHash) { throw 'SOURCE_CHANGED: file changed while preparing. No send was started.' }
    Write-DeliveryJson $currentRequest @{requestId=$RequestId;filePath=$stagedFile;caption=$Caption;sha256=$sourceHash;createdUtc=[DateTime]::UtcNow.ToString('o')}
    $mayRemoveRequest = $true
    Write-DeliveryJson $attemptPath @{requestId=$RequestId;fingerprint=$fingerprint;status='attempting';startedUtc=[DateTime]::UtcNow.ToString('o');fileName=$file.Name;bytes=$file.Length;sha256=$sourceHash}
    $previousEnv = Set-DeliveryProcessEnvironment -Config $config -AllowedDirectory $RuntimeRoot
    & $config.n8nPath execute "--id=$($config.workflowId)" --rawOutput *> $logPath
    $confirmed = Read-TelegramReceipt $logPath ([string]$config.chatId) $file.Name $file.Length
    if (-not $confirmed) { throw "DELIVERY_UNCONFIRMED: n8n finished without a matching Telegram receipt. Inspect $logPath; do not automatically resend." }
    $receipt = [ordered]@{status='sent';requestId=$RequestId;sha256=$sourceHash;receiptPath=$receiptPath;messageId=$confirmed.messageId;fileName=$confirmed.fileName;bytes=$confirmed.bytes;telegramDate=$confirmed.telegramDate}
    Write-DeliveryJson $receiptPath $receipt
    Remove-Item -LiteralPath $stagedFile -ErrorAction SilentlyContinue
    $receipt | ConvertTo-Json -Compress
} finally {
    if ($null -ne $previousEnv) { Restore-DeliveryProcessEnvironment $previousEnv }
    if ($mayRemoveRequest -and (Test-Path -LiteralPath $currentRequest)) { Remove-Item -LiteralPath $currentRequest -ErrorAction SilentlyContinue }
    if ($null -ne $lock) { $lock.Dispose() }
}
