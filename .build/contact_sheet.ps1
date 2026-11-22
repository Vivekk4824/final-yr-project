param(
    [Parameter(Mandatory = $true)][string]$InputDirectory,
    [Parameter(Mandatory = $true)][string]$OutputPath,
    [string]$Pattern = 'slide-*.jpg',
    [int]$Columns = 4,
    [int]$ThumbWidth = 360,
    [int]$ThumbHeight = 203
)

Add-Type -AssemblyName System.Drawing
$files = Get-ChildItem -LiteralPath $InputDirectory -File | Where-Object { $_.Name -like $Pattern } | Sort-Object Name
$rows = [Math]::Ceiling($files.Count / $Columns)
$labelHeight = 28
$canvas = New-Object System.Drawing.Bitmap ($Columns * $ThumbWidth), ($rows * ($ThumbHeight + $labelHeight))
$graphics = [System.Drawing.Graphics]::FromImage($canvas)
$graphics.Clear([System.Drawing.Color]::White)
$font = New-Object System.Drawing.Font('Arial', 12, [System.Drawing.FontStyle]::Bold)
$brush = [System.Drawing.Brushes]::Black

try {
    for ($i = 0; $i -lt $files.Count; $i++) {
        $x = ($i % $Columns) * $ThumbWidth
        $y = [Math]::Floor($i / $Columns) * ($ThumbHeight + $labelHeight)
        $image = [System.Drawing.Image]::FromFile($files[$i].FullName)
        try { $graphics.DrawImage($image, $x, $y, $ThumbWidth, $ThumbHeight) }
        finally { $image.Dispose() }
        $graphics.DrawString(($i + 1).ToString(), $font, $brush, $x + 8, $y + $ThumbHeight + 3)
    }
    $canvas.Save($OutputPath, [System.Drawing.Imaging.ImageFormat]::Jpeg)
}
finally {
    $font.Dispose()
    $graphics.Dispose()
    $canvas.Dispose()
}
