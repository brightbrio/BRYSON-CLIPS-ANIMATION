$platforms = @('tiktok','facebook','instagram','google_flow','capcut')
foreach ($p in $platforms) {
    [System.IO.File]::WriteAllText("body.json", "{`"platform`":`"$p`\"}")
    $r = curl.exe -s --max-time 10 -X POST -H "Content-Type: application/json" -d @body.json "http://127.0.0.1:8081/api/auth/save"
    Write-Host "$p : $r"
}
