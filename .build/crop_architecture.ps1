$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
$source = 'C:\Users\kalya\vendor-map\.build\architecture-report-21.png'
$target = 'C:\Users\kalya\vendor-map\.build\architecture-cropped.png'
$image = [System.Drawing.Bitmap]::FromFile($source)
try {
    $rect = [System.Drawing.Rectangle]::new(115, 90, 1010, 760)
    $crop = $image.Clone($rect, $image.PixelFormat)
    try { $crop.Save($target, [System.Drawing.Imaging.ImageFormat]::Png) }
    finally { $crop.Dispose() }
}
finally { $image.Dispose() }
