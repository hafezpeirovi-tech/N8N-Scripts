$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Common.ps1')
$testDir = Join-Path ([IO.Path]::GetTempPath()) ('agent-file-sender-test-' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $testDir | Out-Null
$passed = 0
function Check([bool]$Condition, [string]$Name) {
    if (-not $Condition) { throw "FAILED: $Name" }
    $script:passed++
}
try {
    $filePath = Join-Path $testDir 'sample.txt'
    [IO.File]::WriteAllText($filePath, 'sample')
    Check ((Assert-DeliveryFile $filePath 'caption').Length -eq 6) 'valid local file'
    $rejected = $false
    try { Assert-DeliveryFile $filePath ('x' * 1025) | Out-Null } catch { $rejected = $true }
    Check $rejected 'reject overlong caption'
    $empty = Join-Path $testDir 'empty.txt'
    [IO.File]::WriteAllText($empty, '')
    $rejected = $false
    try { Assert-DeliveryFile $empty '' | Out-Null } catch { $rejected = $true }
    Check $rejected 'reject empty file'
    $a = Get-DeliveryFingerprint 'abc' 'sample.txt' 'caption' '123'
    Check ($a -eq (Get-DeliveryFingerprint 'abc' 'sample.txt' 'caption' '123')) 'deterministic request identity'
    Check ($a -ne (Get-DeliveryFingerprint 'def' 'sample.txt' 'caption' '123')) 'changed content has a new identity'
    Check ($a -ne (Get-DeliveryFingerprint 'abc' 'sample.txt' 'different' '123')) 'caption belongs to request identity'
    $response = @{data=@{resultData=@{runData=@{'Send file to owner'=@(@{data=@{main=@(,@(@{json=@{message_id=77;date=1790000000;chat=@{id=123};document=@{file_name='sample.txt';file_size=6}}}))}})}}}}
    $logPath = Join-Path $testDir 'execution.log'
    [IO.File]::WriteAllText($logPath, "startup log`n" + ($response | ConvertTo-Json -Depth 20) + "`nshutdown log")
    Check ((Read-TelegramReceipt $logPath '123' 'sample.txt' 6).messageId -eq 77) 'extract confirmed receipt with surrounding logs'
    Check ($null -eq (Read-TelegramReceipt $logPath '999' 'sample.txt' 6)) 'reject wrong destination'
    Check ($null -eq (Read-TelegramReceipt $logPath '123' 'other.txt' 6)) 'reject wrong filename'
    Check ($null -eq (Read-TelegramReceipt $logPath '123' 'sample.txt' 9)) 'reject wrong file size'
    [IO.File]::WriteAllText($logPath, '{"data":')
    Check ($null -eq (Read-TelegramReceipt $logPath '123' 'sample.txt' 6)) 'truncated result is not a success'
    [pscustomobject]@{tests=$passed;failures=0} | ConvertTo-Json -Compress
} finally {
    # Only fixed files created by this test are removed; no recursive deletion.
    foreach ($name in @('sample.txt','empty.txt','execution.log')) {
        $target = Join-Path $testDir $name
        if (Test-Path -LiteralPath $target) { Remove-Item -LiteralPath $target }
    }
    if (Test-Path -LiteralPath $testDir) { Remove-Item -LiteralPath $testDir }
}
