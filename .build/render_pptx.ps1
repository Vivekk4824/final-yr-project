param(
    [Parameter(Mandatory = $true)][string]$InputPath,
    [Parameter(Mandatory = $true)][string]$OutputPdf
)

$powerPoint = $null
$presentation = $null
try {
    $powerPoint = New-Object -ComObject PowerPoint.Application
    $presentation = $powerPoint.Presentations.Open($InputPath, $true, $true, $false)
    $presentation.SaveAs($OutputPdf, 32)
}
finally {
    if ($presentation) { $presentation.Close() }
    if ($powerPoint) { $powerPoint.Quit() }
    if ($presentation) { [System.Runtime.InteropServices.Marshal]::ReleaseComObject($presentation) | Out-Null }
    if ($powerPoint) { [System.Runtime.InteropServices.Marshal]::ReleaseComObject($powerPoint) | Out-Null }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}
