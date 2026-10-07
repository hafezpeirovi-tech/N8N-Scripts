[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$CredentialId,
    [Parameter(Mandatory)][string]$ChatId,
    [string]$RuntimeRoot = (Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'Codex\AgentFileSender'),
    [string]$TemplatePath = (Join-Path (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent) 'workflows\agent-file-sender.json'),
    [string]$ProxyUrl = '',
    [ValidateRange(1024,65535)][int]$BrokerPort = 5682
)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Common.ps1')
Assert-LocalDeliveryAuthorization -Category HERMES_CONFIG_WRITE
New-Item -ItemType Directory -Path $RuntimeRoot -Force | Out-Null
$configPath = Join-Path $RuntimeRoot 'config.json'
if (Test-Path -LiteralPath $configPath) { throw 'Already installed. Preserve its workflow ID; do not create a duplicate installation.' }
$n8n = (Get-Command n8n.ps1 -ErrorAction Stop).Source
$workflow = Get-Content -LiteralPath $TemplatePath -Raw | ConvertFrom-Json
$workflowId = 'AF' + [Guid]::NewGuid().ToString('N').Substring(0,14)
$workflow | Add-Member -NotePropertyName id -NotePropertyValue $workflowId
($workflow.nodes | Where-Object name -eq 'Read delivery request').parameters.filePath = Join-Path $RuntimeRoot 'current-request.json'
$send = $workflow.nodes | Where-Object name -eq 'Send file to owner'
$send.parameters.chatId = $ChatId
$send | Add-Member -NotePropertyName credentials -NotePropertyValue @{telegramApi=@{id=$CredentialId;name='Existing Telegram credential'}}
$runtimeWorkflow = Join-Path $RuntimeRoot 'installed-workflow.json'
Write-DeliveryJson $runtimeWorkflow $workflow
$config = [pscustomobject]@{workflowId=$workflowId;chatId=$ChatId;n8nPath=$n8n;proxyUrl=$ProxyUrl;brokerPort=$BrokerPort;version=1}
$previousEnv = Set-DeliveryProcessEnvironment $config $RuntimeRoot
try {
    $importLog = Join-Path $RuntimeRoot 'install.log'
    & $n8n import:workflow "--input=$runtimeWorkflow" --activeState=false *> $importLog
    if (-not ((Get-Content -LiteralPath $importLog -Raw) -match 'Successfully imported 1 workflow')) {
        throw "Import not confirmed. Inspect $importLog before retrying; use the ID in installed-workflow.json to avoid duplication."
    }
    Write-DeliveryJson $configPath $config
    [pscustomobject]@{status='installed';workflowId=$workflowId;runtimeRoot=$RuntimeRoot;mode='manual-cli'} | ConvertTo-Json -Compress
} finally { Restore-DeliveryProcessEnvironment $previousEnv }
