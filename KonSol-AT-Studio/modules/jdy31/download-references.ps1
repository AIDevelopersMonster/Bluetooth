# Download related primary manuals into a local, untracked reference folder.
# These documents are not certified as the exact JDY-31A V2.241 manual.
$ErrorActionPreference = "Stop"
$base = Join-Path $PSScriptRoot "references"
New-Item -ItemType Directory -Force -Path $base | Out-Null
$docs = @(
  @{name="JDY-31_legacy_manual.pdf"; url="https://adastra-soft.com/wp-content/uploads/2021/06/JDY-31_manual_2.pdf"; scope="Legacy JDY-31; NOT exact JDY-31A-V2.241"},
  @{name="JDY-33_related_dual_mode_manual.pdf"; url="https://fccid.io/2AXM8-JDY-33/User-Manual/15-JDY-33-UserMan-US-r2-4936883.pdf"; scope="Related JDY-33 dual-mode; NOT exact JDY-31A-V2.241"}
)
foreach ($doc in $docs) {
  $dest = Join-Path $base $doc.name
  try {
    Invoke-WebRequest -Uri $doc.url -OutFile $dest -MaximumRedirection 5
    $sig = [System.IO.File]::ReadAllBytes($dest)
    if ($sig.Length -lt 5 -or [System.Text.Encoding]::ASCII.GetString($sig,0,5) -ne "%PDF-") {
      Remove-Item -LiteralPath $dest -Force
      throw "Downloaded file is not a PDF"
    }
    $hash = (Get-FileHash -LiteralPath $dest -Algorithm SHA256).Hash
    [pscustomobject]@{file=$doc.name;source=$doc.url;scope=$doc.scope;sha256=$hash;retrieved_utc=(Get-Date).ToUniversalTime().ToString("o")} |
      ConvertTo-Json | Set-Content -LiteralPath ($dest+".source.json") -Encoding utf8
    Write-Host "SAVED $dest"
    Write-Host "SHA256 $hash"
  } catch {
    Write-Warning ("FAILED: " + $doc.url + " (" + $_.Exception.Message + ")")
  }
}
