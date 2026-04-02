param(
  [string]$ApiBase = "http://127.0.0.1:8000",
  [Parameter(Mandatory = $true)][string]$Identifier,
  [Parameter(Mandatory = $true)][string]$Password,
  [string]$LockedIdentifier = "",
  [string]$LockedPassword = "",
  [string]$ContractIdForStepUp = ""
)

$ErrorActionPreference = "Stop"
$ApiBase = $ApiBase.TrimEnd('/')

function Write-Section($text) {
  Write-Host "`n=== $text ===" -ForegroundColor Cyan
}

function Invoke-Api {
  param(
    [string]$Method,
    [string]$Path,
    [object]$Body = $null,
    [string]$Token = "",
    [hashtable]$ExtraHeaders = @{}
  )

  $uri = "$ApiBase$Path"
  $headers = @{}
  if ($Token) { $headers["Authorization"] = "Bearer $Token" }
  foreach ($k in $ExtraHeaders.Keys) { $headers[$k] = $ExtraHeaders[$k] }

  try {
    $args = @{ Method = $Method; Uri = $uri; Headers = $headers; ContentType = "application/json" }
    if ($Body -ne $null) { $args["Body"] = ($Body | ConvertTo-Json -Depth 10) }
    $resp = Invoke-RestMethod @args
    return @{ ok = $true; status = 200; data = $resp }
  }
  catch {
    $status = 0
    $raw = ""
    try { $status = [int]$_.Exception.Response.StatusCode } catch {}
    try {
      $stream = $_.Exception.Response.GetResponseStream()
      $reader = New-Object System.IO.StreamReader($stream)
      $raw = $reader.ReadToEnd()
      $reader.Close()
    } catch {
      $raw = $_.Exception.Message
    }
    $detail = $raw
    try { $detail = (ConvertFrom-Json $raw).detail } catch {}
    return @{ ok = $false; status = $status; detail = $detail; raw = $raw }
  }
}

function Assert-Ok($result, $label) {
  if (-not $result.ok) {
    Write-Host "[FAIL] $label => status=$($result.status), detail=$($result.detail)" -ForegroundColor Red
    return $false
  }
  Write-Host "[PASS] $label" -ForegroundColor Green
  return $true
}

function Assert-Fail($result, $label) {
  if ($result.ok) {
    Write-Host "[FAIL] $label => expected failure but got success" -ForegroundColor Red
    return $false
  }
  Write-Host "[PASS] $label => status=$($result.status), detail=$($result.detail)" -ForegroundColor Green
  return $true
}

$summary = @()

Write-Section "CASE 1 - Password login success"
$loginOk = Invoke-Api -Method "POST" -Path "/auth/login" -Body @{ identifier = $Identifier; password = $Password }
$case1 = Assert-Ok $loginOk "Login bang account hop le"
$summary += @{ case = 1; passed = $case1 }
if (-not $case1) { throw "Khong the tiep tuc vi CASE 1 that bai" }

$token = $loginOk.data.accessToken
$role = $loginOk.data.user.vaiTro
Write-Host "Role sau login: $role"

Write-Section "Kiem tra /auth/me sau login"
$me = Invoke-Api -Method "GET" -Path "/auth/me" -Token $token
$summary += @{ case = "me"; passed = (Assert-Ok $me "Lay current session") }

Write-Section "CASE 2 - Password login fail"
$loginBad = Invoke-Api -Method "POST" -Path "/auth/login" -Body @{ identifier = $Identifier; password = "wrong-password-123" }
$summary += @{ case = 2; passed = (Assert-Fail $loginBad "Sai password bi tu choi") }

if ($LockedIdentifier -and $LockedPassword) {
  Write-Section "CASE 3 - Locked user"
  $locked = Invoke-Api -Method "POST" -Path "/auth/login" -Body @{ identifier = $LockedIdentifier; password = $LockedPassword }
  $summary += @{ case = 3; passed = (Assert-Fail $locked "Tai khoan bi khoa/khong hoat dong bi chan") }
} else {
  Write-Section "CASE 3 - Locked user (SKIP)"
  Write-Host "[SKIP] Chua cung cap LockedIdentifier/LockedPassword" -ForegroundColor Yellow
  $summary += @{ case = 3; passed = $false; skipped = $true }
}

Write-Section "CASE 5 - Wallet chua lien ket"
$unlinkedWallet = "0x1111111111111111111111111111111111111111"
$walletChallengeFail = Invoke-Api -Method "POST" -Path "/auth/wallet/challenge" -Body @{ walletAddress = $unlinkedWallet; chainId = 1; purpose = "login_wallet" }
$summary += @{ case = 5; passed = (Assert-Fail $walletChallengeFail "Vi chua lien ket khong duoc login") }

Write-Section "CASE 7 - Signature sai"
$linkWallet = "0x2222222222222222222222222222222222222222"
$linkChallenge = Invoke-Api -Method "POST" -Path "/wallet/link/challenge" -Body @{ walletAddress = $linkWallet; chainId = 1; purpose = "link_wallet" } -Token $token
if (Assert-Ok $linkChallenge "Tao challenge link_wallet") {
  $badVerify = Invoke-Api -Method "POST" -Path "/wallet/link/verify" -Token $token -Body @{
    challengeId = $linkChallenge.data.challengeId
    walletAddress = $linkChallenge.data.walletAddress
    nonce = $linkChallenge.data.nonce
    message = $linkChallenge.data.message
    signature = "0xdeadbeef"
    purpose = "link_wallet"
  }
  $summary += @{ case = 7; passed = (Assert-Fail $badVerify "Signature sai bi tu choi") }
} else {
  $summary += @{ case = 7; passed = $false }
}

if ($ContractIdForStepUp) {
  Write-Section "CASE 8 (phan negative) - Step-up required"
  $withoutStepUp = Invoke-Api -Method "POST" -Path "/api/contracts/$ContractIdForStepUp/lock-deposit" -Token $token -Body @{}
  $summary += @{ case = 8; passed = (Assert-Fail $withoutStepUp "Khong co X-Step-Up-Challenge-Id thi bi chan") }
} else {
  Write-Section "CASE 8 (phan negative) - Step-up required (SKIP)"
  Write-Host "[SKIP] Chua cung cap ContractIdForStepUp" -ForegroundColor Yellow
  $summary += @{ case = 8; passed = $false; skipped = $true }
}

Write-Section "Logout"
$logout = Invoke-Api -Method "POST" -Path "/auth/logout" -Token $token -Body @{}
$summary += @{ case = "logout"; passed = (Assert-Ok $logout "Logout session hien tai") }

Write-Section "Tong ket"
$passCount = ($summary | Where-Object { $_.passed -eq $true }).Count
$allCount = $summary.Count
Write-Host "Passed: $passCount/$allCount"
$summary | ForEach-Object {
  $tag = if ($_.passed) { "PASS" } elseif ($_.skipped) { "SKIP" } else { "FAIL" }
  Write-Host ("- Case {0}: {1}" -f $_.case, $tag)
}

Write-Host "`nLuu y: CASE 4, 6, 8 (thanh cong) va CASE 9 can test UI + MetaMask manual theo checklist." -ForegroundColor Yellow
