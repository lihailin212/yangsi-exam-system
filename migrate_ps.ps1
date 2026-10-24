# Full migration using Python for data + PowerShell for HTTP
# Python handles local DB, PowerShell handles Railway API
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$BACKEND = "https://stellar-youth-production-1591.up.railway.app"
$FRONTEND = "https://yangsi-exam-system-production-6700.up.railway.app"
$TIMEOUT = 60

# Login
$loginBody = @{ employee_id = "admin"; password = "admin123" } | ConvertTo-Json
$loginResp = Invoke-RestMethod -Uri "$BACKEND/api/auth/login" -Method Post -ContentType "application/json" -Body $loginBody -TimeoutSec $TIMEOUT
$token = $loginResp.access_token
$headers = @{ "Authorization" = "Bearer $token" }
Write-Host "Logged in"

# Check existing
$rq = Invoke-RestMethod -Uri "$BACKEND/api/questions?limit=1000" -Headers $headers -TimeoutSec $TIMEOUT
$re = Invoke-RestMethod -Uri "$BACKEND/api/exams?limit=100" -Headers $headers -TimeoutSec $TIMEOUT
$rs = Invoke-RestMethod -Uri "$BACKEND/api/students?limit=100" -Headers $headers -TimeoutSec $TIMEOUT

$eq = @{}
foreach ($q in $rq.items) { $eq["$($q.content)|$($q.type)|$($q.answer)"] = $q.id }
$ee = @{}
foreach ($e in $re.items) { $ee[$e.title] = $e.id }
$es = @{}
foreach ($s in $rs.items) { $es[$s.employee_id] = $s.id }
Write-Host "Railway: $($eq.Count) q, $($ee.Count) e, $($es.Count) s"

# Read local data from JSON (exported by Python)
$jsonText = Get-Content "migration_data.json" -Raw -Encoding UTF8
$localData = $jsonText | ConvertFrom-Json

# Students
$smap = @{}
foreach ($s in $localData.students) {
    $emp = [string]$s.employee_id
    if ($es.ContainsKey($emp)) {
        $smap[[string]$s.id] = $es[$emp]
        Write-Host "  [SKIP] $($s.name)"
    } else {
        $body = @{
            employee_id = $emp
            name = $s.name
            password = "123456"
            dept = if ($s.dept) { $s.dept } else { "" }
            role = if ($s.role) { $s.role } else { "学员" }
        } | ConvertTo-Json
        try {
            $res = Invoke-RestMethod -Uri "$BACKEND/api/students" -Method Post -Headers $headers -ContentType "application/json" -Body $body -TimeoutSec $TIMEOUT
            $smap[[string]$s.id] = $res.id
            Write-Host "  [NEW] $($s.name) -> $($res.id)"
        } catch { Write-Host "  [FAIL] $($s.name): $($_.Exception.Message)" }
    }
}
Write-Host "Students: $($smap.Count) mapped"

# Questions
$qmap = @{}
foreach ($q in $localData.questions) {
    $key = "$($q.content)|$($q.type)|$($q.answer)"
    if ($eq.ContainsKey($key)) {
        $qmap[[string]$q.id] = $eq[$key]
        continue
    }
    $body = @{
        type = $q.type
        content = $q.content
        options = $q.options
        answer = $q.answer
        analysis = if ($q.analysis) { $q.analysis } else { "" }
        category = if ($q.category) { $q.category } else { "" }
    } | ConvertTo-Json
    try {
        $res = Invoke-RestMethod -Uri "$BACKEND/api/questions" -Method Post -Headers $headers -ContentType "application/json" -Body $body -TimeoutSec $TIMEOUT
        $qmap[[string]$q.id] = $res.id
        Write-Host "  [NEW] Q$($q.id) -> $($res.id)"
    } catch { Write-Host "  [FAIL] Q$($q.id): $($_.Exception.Message)" }
}
$allQids = @($qmap.Values | Sort-Object)
Write-Host "Questions: $($qmap.Count) mapped, $($allQids.Count) total"

# Exams
$emap = @{}
foreach ($e in $localData.exams) {
    if ($ee.ContainsKey($e.title)) {
        $emap[[string]$e.id] = $ee[$e.title]
        Write-Host "  [SKIP] $($e.title)"
        continue
    }
    $body = @{
        title = $e.title
        duration = if ($null -ne $e.duration) { $e.duration } else { 90 }
        pass_score = if ($null -ne $e.pass_score) { $e.pass_score } else { 60 }
        single_score = if ($null -ne $e.single_score) { $e.single_score } else { 10 }
        multiple_score = if ($null -ne $e.multiple_score) { $e.multiple_score } else { 20 }
        judgment_score = if ($null -ne $e.judgment_score) { $e.judgment_score } else { 5 }
        question_ids = $allQids
    } | ConvertTo-Json
    try {
        $res = Invoke-RestMethod -Uri "$BACKEND/api/exams" -Method Post -Headers $headers -ContentType "application/json" -Body $body -TimeoutSec $TIMEOUT
        $emap[[string]$e.id] = $res.id
        Write-Host "  [NEW] $($e.title) -> $($res.id)"
    } catch { Write-Host "  [FAIL] $($e.title): $($_.Exception.Message)" }
}
Write-Host "Exams: $($emap.Count) mapped"

# Distributions
$dc = 0
foreach ($d in $localData.dists) {
    if ($d.user_id -eq 1) { continue }
    $eid = $emap[[string]$d.exam_id]
    $uid = $smap[[string]$d.user_id]
    if (-not $eid -or -not $uid) { Write-Host "  [WARN] exam=$($d.exam_id) user=$($d.user_id)"; continue }
    $body = @{ exam_id = $eid; user_ids = @($uid) } | ConvertTo-Json
    try {
        $res = Invoke-RestMethod -Uri "$BACKEND/api/distributions" -Method Post -Headers $headers -ContentType "application/json" -Body $body -TimeoutSec $TIMEOUT
        $dc++
        foreach ($r in $res) {
            Write-Host "  $($r.user_name): $FRONTEND/#/invite/$($r.invite_code)"
        }
    } catch { Write-Host "  [FAIL] dist: $($_.Exception.Message)" }
}

Write-Host "Distributions: $dc"
Write-Host "Migration complete!"