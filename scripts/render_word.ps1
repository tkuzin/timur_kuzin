param([Parameter(Mandatory=$true)][string]$InputDocx,[Parameter(Mandatory=$true)][string]$OutputPdf,[switch]$Update)
$ErrorActionPreference = 'Stop'
$InputDocx = [System.IO.Path]::GetFullPath($InputDocx).Replace('/', '\')
$OutputPdf = [System.IO.Path]::GetFullPath($OutputPdf).Replace('/', '\')
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
try {
    $doc = $word.Documents.Open($InputDocx, $false, (-not $Update.IsPresent), $false)
    if ($Update) {
        $doc.Fields.Update() | Out-Null
        foreach ($toc in $doc.TablesOfContents) { $toc.Update() }
        $doc.Repaginate()
        foreach ($toc in $doc.TablesOfContents) { $toc.UpdatePageNumbers() }
        $doc.Save()
    }
    $doc.ExportAsFixedFormat($OutputPdf, 17)
    Write-Output "Pages: $($doc.ComputeStatistics(2)); PDF: $OutputPdf"
    $doc.Close(0)
} finally {
    $word.Quit(0)
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null
}
