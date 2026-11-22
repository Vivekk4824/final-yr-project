$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
$sourceDir = 'C:\Users\kalya\vendor-map\.build\report-diagrams'

$jobs = @(
    @{ Source='page-29.png'; Target='er-model.png'; X=95; Y=720; W=885; H=610 },
    @{ Source='page-30.png'; Target='dfd-level-0.png'; X=85; Y=345; W=905; H=520 },
    @{ Source='page-30.png'; Target='dfd-level-1.png'; X=85; Y=825; W=905; H=560 },
    @{ Source='page-31.png'; Target='use-case.png'; X=85; Y=430; W=905; H=525 },
    @{ Source='page-32.png'; Target='component.png'; X=120; Y=70; W=835; H=275 },
    @{ Source='page-32.png'; Target='sequence.png'; X=80; Y=590; W=915; H=535 },
    @{ Source='page-33.png'; Target='activity.png'; X=95; Y=60; W=885; H=535 }
)

foreach ($job in $jobs) {
    $source = Join-Path $sourceDir $job.Source
    $target = Join-Path $sourceDir $job.Target
    $image = [System.Drawing.Bitmap]::FromFile($source)
    try {
        $rect = [System.Drawing.Rectangle]::new($job.X, $job.Y, $job.W, $job.H)
        $crop = $image.Clone($rect, $image.PixelFormat)
        try { $crop.Save($target, [System.Drawing.Imaging.ImageFormat]::Png) }
        finally { $crop.Dispose() }
    }
    finally { $image.Dispose() }
}
