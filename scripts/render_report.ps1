param(
    [string]$QaDirectory = "evaluation/report_qa/rendered",
    [string]$Poppler = "C:/Program Files/WindowsApps/OpenAI.CodexPrimaryRuntime.v26-1112-611-0_26.1112.611.0_x64__3k8sg7r9htsxt/dependencies/native/poppler/Library/bin/pdftoppm.exe"
)
# Local-only fallback for Windows without LibreOffice. Never edit the source
# DOCX, close user documents, or treat successful export as visual review.
$ErrorActionPreference = "Stop"
$taskRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$inputPath = Join-Path $taskRoot "report/pre_results.docx"
$outputPath = Join-Path $taskRoot "report/pre_results.pdf"
$qaPath = [IO.Path]::GetFullPath((Join-Path $taskRoot $QaDirectory))
if (-not $qaPath.StartsWith($taskRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw "QA output must remain inside the repository."
}
if (Test-Path -LiteralPath $qaPath) { throw "Select a new QA directory; previous renders are retained." }
if (-not (Test-Path -LiteralPath $Poppler)) { throw "Supply the local pdftoppm executable path." }
$docxHash = (Get-FileHash -LiteralPath $inputPath -Algorithm SHA256).Hash.ToLowerInvariant()
$word = $null
$doc = $null
$ownsEmptyApplication = $false
try {
    $word = New-Object -ComObject Word.Application
    if ($word.Documents.Count -ne 0) { throw "Refusing to operate on a Word instance containing existing documents." }
    $ownsEmptyApplication = $true
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $doc = $word.Documents.Open($inputPath, $false, $true, $false)
    $doc.ExportAsFixedFormat($outputPath, 17)
    $pageCount = $doc.ComputeStatistics(2)
}
finally {
    if ($null -ne $doc) { $doc.Close(0); [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($doc) }
    if ($null -ne $word) {
        if ($ownsEmptyApplication) { $word.Quit(0) }
        [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($word)
    }
}
if ($docxHash -ne (Get-FileHash -LiteralPath $inputPath -Algorithm SHA256).Hash.ToLowerInvariant()) {
    throw "Read-only export unexpectedly changed the DOCX."
}
New-Item -ItemType Directory -Path $qaPath | Out-Null
& $Poppler -png -r 96 $outputPath (Join-Path $qaPath "page")
if ($LASTEXITCODE -ne 0) { throw "PDF rasterization failed." }
$pageFiles = @(Get-ChildItem -LiteralPath $qaPath -Filter "page-*.png")
if ($pageFiles.Count -ne $pageCount) { throw "PDF/Word page count mismatch." }
$record = [ordered]@{
    renderer = "Microsoft Word COM; hidden isolated instance; read-only source; Poppler 96 dpi"
    canonical_renderer_blocker = "LibreOffice soffice.exe unavailable on PATH"
    docx_sha256 = $docxHash
    pdf_sha256 = (Get-FileHash -LiteralPath $outputPath -Algorithm SHA256).Hash.ToLowerInvariant()
    total_pages = $pageCount
    all_pages_visually_reviewed = $false
    body_page_limit_verified = $false
    page_png_sha256 = [ordered]@{}
}
foreach ($page in $pageFiles) { $record.page_png_sha256[$page.Name] = (Get-FileHash -LiteralPath $page.FullName -Algorithm SHA256).Hash.ToLowerInvariant() }
$record | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $qaPath "render_machine.json") -Encoding UTF8
Write-Output "Exported $pageCount pages. Visual inspection remains required."
