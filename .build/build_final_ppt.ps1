param(
    [string]$OutputPptx = "C:\Users\kalya\vendor-map\output\pptx\VendorMap_Final_Project_Examination.pptx",
    [string]$OutputPdf = "C:\Users\kalya\vendor-map\.build\final-preview\VendorMap_Final_Project_Examination.pdf"
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing

function Color([int]$r, [int]$g, [int]$b) { return $r + 256 * $g + 65536 * $b }

$Cream = Color 250 249 238
$Brown = Color 80 72 66
$Brown2 = Color 106 93 82
$Olive = Color 112 128 105
$PaleOlive = Color 229 234 224
$PaleBrown = Color 239 234 228
$Gold = Color 151 112 54
$Red = Color 169 74 61
$Blue = Color 64 104 142
$Black = Color 35 35 35
$White = Color 255 255 255
$Grey = Color 105 105 105
$LightGrey = Color 222 222 218

$workspace = 'C:\Users\kalya\vendor-map'
$background = Join-Path $workspace '.build\reference_unpack\ppt\media\image4.jpg'
$coverBackground = Join-Path $workspace '.build\reference_unpack\ppt\media\image2.jpg'
$nmcLogo = Join-Path $workspace 'frontend\public\nmc-logo.jpg'

function Add-Text($slide, [string]$text, [double]$x, [double]$y, [double]$w, [double]$h,
                  [double]$size = 16, [bool]$bold = $false, [int]$color = $Black,
                  [string]$font = 'Aptos', [int]$align = 1, [int]$valign = 1) {
    $shape = $slide.Shapes.AddTextbox(1, $x, $y, $w, $h)
    $shape.TextFrame.MarginLeft = 2
    $shape.TextFrame.MarginRight = 2
    $shape.TextFrame.MarginTop = 1
    $shape.TextFrame.MarginBottom = 1
    $shape.TextFrame.WordWrap = -1
    $shape.TextFrame.VerticalAnchor = $valign
    $shape.TextFrame.TextRange.Text = $text
    $shape.TextFrame.TextRange.Font.Name = $font
    $shape.TextFrame.TextRange.Font.Size = $size
    $shape.TextFrame.TextRange.Font.Bold = [int]$bold * -1
    $shape.TextFrame.TextRange.Font.Color.RGB = $color
    $shape.TextFrame.TextRange.ParagraphFormat.Alignment = $align
    $shape.Fill.Visible = 0
    $shape.Line.Visible = 0
    return $shape
}

function Add-Box($slide, [double]$x, [double]$y, [double]$w, [double]$h,
                 [int]$fill, [int]$line = $Brown, [double]$radiusShape = 5) {
    $shape = $slide.Shapes.AddShape($radiusShape, $x, $y, $w, $h)
    $shape.Fill.ForeColor.RGB = $fill
    $shape.Fill.Solid()
    $shape.Line.ForeColor.RGB = $line
    $shape.Line.Weight = 1
    return $shape
}

function Add-PictureFit($slide, [string]$path, [double]$x, [double]$y, [double]$w, [double]$h, [bool]$border = $true) {
    $img = [System.Drawing.Image]::FromFile($path)
    try {
        $scale = [Math]::Min($w / $img.Width, $h / $img.Height)
        $iw = $img.Width * $scale
        $ih = $img.Height * $scale
        $ix = $x + ($w - $iw) / 2
        $iy = $y + ($h - $ih) / 2
    }
    finally { $img.Dispose() }
    if ($border) {
        $frame = Add-Box $slide ($x - 3) ($y - 3) ($w + 6) ($h + 6) $White $LightGrey 1
        $frame.Line.Weight = 0.8
    }
    return $slide.Shapes.AddPicture($path, 0, -1, $ix, $iy, $iw, $ih)
}

function Add-Arrow($slide, [double]$x1, [double]$y1, [double]$x2, [double]$y2, [int]$color = $Brown, [double]$weight = 2) {
    $line = $slide.Shapes.AddConnector(1, $x1, $y1, $x2, $y2)
    $line.Line.ForeColor.RGB = $color
    $line.Line.Weight = $weight
    $line.Line.EndArrowheadStyle = 3
    return $line
}

function Add-Node($slide, [string]$title, [string]$body, [double]$x, [double]$y, [double]$w, [double]$h,
                  [int]$fill = $PaleOlive, [int]$accent = $Olive) {
    $box = Add-Box $slide $x $y $w $h $fill $accent 5
    Add-Text $slide $title ($x + 8) ($y + 6) ($w - 16) 22 14 $true $Brown 'Aptos' 2 3 | Out-Null
    if ($body) { Add-Text $slide $body ($x + 9) ($y + 31) ($w - 18) ($h - 36) 10 $false $Black 'Aptos' 2 1 | Out-Null }
    return $box
}

function Add-Base($presentation, [string]$title, [string]$section = 'PROJECT FINAL EXAMINATION') {
    $slide = $presentation.Slides.Add($presentation.Slides.Count + 1, 12)
    $slide.FollowMasterBackground = 0
    $slide.Background.Fill.ForeColor.RGB = $Cream
    $slide.Background.Fill.Solid()
    $slide.Shapes.AddPicture($background, 0, -1, 0, 0, 960, 540) | Out-Null
    Add-Text $slide $title 35 22 760 44 25 $true $Brown 'Times New Roman' 2 3 | Out-Null
    Add-Text $slide $section 35 73 540 15 7 $true $Grey 'Aptos' 1 3 | Out-Null
    Add-Text $slide 'Department of Information Technology | A.Y. 2026-27' 35 518 520 14 7 $false $Grey 'Aptos' 1 3 | Out-Null
    Add-Text $slide ([string]$slide.SlideIndex) 910 518 22 14 7 $false $Grey 'Aptos' 3 3 | Out-Null
    return $slide
}

function Add-Section($presentation, [string]$title, [string]$subtitle) {
    $slide = $presentation.Slides.Add($presentation.Slides.Count + 1, 12)
    $slide.Background.Fill.ForeColor.RGB = $Brown
    $slide.Background.Fill.Solid()
    $bar = Add-Box $slide 0 0 170 540 $Olive $Olive 1
    Add-Text $slide $title 220 205 650 70 33 $true $Cream 'Times New Roman' 1 3 | Out-Null
    Add-Text $slide $subtitle 223 282 610 55 15 $false (Color 226 220 210) 'Aptos' 1 1 | Out-Null
    Add-Text $slide ([string]$slide.SlideIndex) 910 518 22 14 7 $false $Cream 'Aptos' 3 3 | Out-Null
    return $slide
}

function Set-Cell($table, [int]$row, [int]$col, [string]$text, [double]$fontSize = 12,
                  [bool]$bold = $false, [int]$fill = $White, [int]$fontColor = $Black, [int]$align = 1) {
    $cell = $table.Table.Cell($row, $col).Shape
    $cell.Fill.ForeColor.RGB = $fill
    $cell.Fill.Solid()
    $cell.TextFrame.MarginLeft = 5
    $cell.TextFrame.MarginRight = 5
    $cell.TextFrame.MarginTop = 3
    $cell.TextFrame.MarginBottom = 2
    $cell.TextFrame.TextRange.Text = $text
    $cell.TextFrame.TextRange.Font.Name = 'Aptos'
    $cell.TextFrame.TextRange.Font.Size = $fontSize
    $cell.TextFrame.TextRange.Font.Bold = [int]$bold * -1
    $cell.TextFrame.TextRange.Font.Color.RGB = $fontColor
    $cell.TextFrame.TextRange.ParagraphFormat.Alignment = $align
}

$powerPoint = $null
$presentation = $null
try {
    New-Item -ItemType Directory -Force -Path (Split-Path $OutputPptx), (Split-Path $OutputPdf) | Out-Null
    $powerPoint = New-Object -ComObject PowerPoint.Application
    $presentation = $powerPoint.Presentations.Add()
    $presentation.PageSetup.SlideWidth = 960
    $presentation.PageSetup.SlideHeight = 540

    # 1 Cover
    $s = $presentation.Slides.Add(1, 12)
    $s.Shapes.AddPicture($coverBackground, 0, -1, 0, 0, 960, 540) | Out-Null
    Add-Text $s 'K. K. WAGH INSTITUTE OF ENGINEERING EDUCATION AND RESEARCH' 42 25 500 24 13 $true $White 'Times New Roman' 2 3 | Out-Null
    Add-Text $s 'Department of Information Technology | A.Y. 2026-27' 42 51 500 18 10 $false $White 'Aptos' 2 3 | Out-Null
    Add-Text $s 'VendorMap' 55 166 470 54 38 $true $Brown 'Times New Roman' 2 3 | Out-Null
    Add-Text $s 'A GIS-Enabled Data-Driven Decision Support System for Street Vendor Zoning, Allocation and Management' 62 224 455 96 20 $false $Black 'Aptos' 2 1 | Out-Null
    Add-Text $s 'PROJECT FINAL EXAMINATION' 62 335 455 30 14 $true $Red 'Aptos' 2 3 | Out-Null
    Add-Text $s 'Guide: Prof. R. M. Bora' 62 390 455 24 14 $true $Brown 'Aptos' 2 3 | Out-Null

    # 2 Team
    $s = Add-Base $presentation 'Team Members'
    $tbl = $s.Shapes.AddTable(5, 3, 92, 142, 776, 250)
    Set-Cell $tbl 1 1 'Roll No.' 13 $true $Brown $White 2
    Set-Cell $tbl 1 2 'Student' 13 $true $Brown $White 2
    Set-Cell $tbl 1 3 'Contribution Focus' 13 $true $Brown $White 2
    $team = @(
        @('19','Darshan Gavate','GIS pipeline, architecture and evaluation'),
        @('48','Vivek Patil','Backend services, database and allocation workflows'),
        @('65','Sneha Tingare','Frontend experience, multilingual and PWA flows'),
        @('66','Kalyani Ugale','Recommendation logic, testing and documentation')
    )
    for ($i=0; $i -lt $team.Count; $i++) {
        $fill = if ($i % 2 -eq 0) { $PaleBrown } else { $White }
        Set-Cell $tbl ($i+2) 1 $team[$i][0] 12 $true $fill $Brown 2
        Set-Cell $tbl ($i+2) 2 $team[$i][1] 12 $true $fill $Black 1
        Set-Cell $tbl ($i+2) 3 $team[$i][2] 11 $false $fill $Black 1
    }
    Add-Text $s 'Academic guide' 332 420 130 20 11 $true $Grey 'Aptos' 3 3 | Out-Null
    Add-Text $s 'Prof. R. M. Bora' 470 416 200 26 16 $true $Brown 'Times New Roman' 1 3 | Out-Null

    # 3 Story map
    $s = Add-Base $presentation 'Presentation Story'
    $story = @(
        @('1','Problem','Why current allocation needs evidence'),
        @('2','Data','NMC records, OSM and operational state'),
        @('3','Intelligence','K-Means profiles and MCDA ranking'),
        @('4','System','Vendor, officer and WhatsApp workflows'),
        @('5','Evidence','Tests, screenshots and sensitivity'),
        @('6','Plan','COCOMO, deployment and future work')
    )
    for ($i=0; $i -lt 6; $i++) {
        $x = 62 + ($i % 3) * 296
        $y = 132 + [Math]::Floor($i / 3) * 165
        $fill = if ($i -in 0,3,4) { $PaleBrown } else { $PaleOlive }
        $accent = if ($fill -eq $PaleBrown) { $Brown2 } else { $Olive }
        Add-Box $s $x $y 250 120 $fill $accent 5 | Out-Null
        Add-Text $s $story[$i][0] ($x+12) ($y+12) 34 34 22 $true $White 'Aptos' 2 3 | ForEach-Object { $_.Fill.Visible=-1; $_.Fill.ForeColor.RGB=$accent; $_.Line.Visible=0 }
        Add-Text $s $story[$i][1] ($x+58) ($y+12) 170 25 17 $true $Brown 'Times New Roman' 1 3 | Out-Null
        Add-Text $s $story[$i][2] ($x+18) ($y+54) 214 48 12 $false $Black 'Aptos' 1 1 | Out-Null
    }

    # 4 Problem
    $s = Add-Base $presentation 'Problem Definition'
    Add-Text $s 'Street-vendor allocation combines policy, capacity, livelihood and spatial constraints.' 58 120 820 36 21 $true $Brown 'Times New Roman' 2 3 | Out-Null
    $problems = @(
        @('Fragmented records','Vendor, zone, document and allocation data are difficult to reconcile.'),
        @('Manual decisions','Static lists do not explain why one zone is preferable to another.'),
        @('Live constraints','Capacity, status and relocation rules can change after a recommendation.'),
        @('Spatial uncertainty','Reference coordinates are analytical evidence, not legal boundaries.')
    )
    for ($i=0; $i -lt 4; $i++) {
        $x = 70 + ($i % 2) * 430
        $y = 190 + [Math]::Floor($i / 2) * 130
        Add-Node $s $problems[$i][0] $problems[$i][1] $x $y 380 92 $(if($i%2){$PaleOlive}else{$PaleBrown}) $(if($i%2){$Olive}else{$Brown2}) | Out-Null
    }
    Add-Text $s 'Decision-support goal: make evidence visible while keeping final municipal authority with the officer.' 90 446 780 30 15 $true $Red 'Aptos' 2 3 | Out-Null

    # 5 Scope
    $s = Add-Base $presentation 'Scope and Objectives'
    Add-Text $s 'In scope' 72 118 350 28 18 $true $Olive 'Times New Roman' 2 3 | Out-Null
    Add-Text $s "- Authenticated vendor and officer workspaces`n- Official-zone catalog and capacity controls`n- Explainable ranked recommendations`n- Request, approval and relocation lifecycle`n- Pilot slot geometry and navigation`n- Multilingual PWA and WhatsApp access" 80 158 365 245 15 $false $Black 'Aptos' 1 1 | Out-Null
    Add-Text $s 'Evidence boundary' 530 118 350 28 18 $true $Red 'Times New Roman' 2 3 | Out-Null
    Add-Text $s "- Recommendations remain advisory`n- K-Means describes environmental groups`n- MCDA expresses explicit factor trade-offs`n- Reference coordinates are not certified polygons`n- Field safety and legal approval require inspection`n- External providers need production configuration" 538 158 350 245 15 $false $Black 'Aptos' 1 1 | Out-Null
    Add-Box $s 58 420 844 56 $PaleOlive $Olive 5 | Out-Null
    Add-Text $s 'Outcome: a traceable workflow from evidence and ranking to controlled allocation.' 75 431 810 32 17 $true $Brown 'Aptos' 2 3 | Out-Null

    # 6 solution
    $s = Add-Base $presentation 'Implemented Solution'
    $labels = @(
        @('IDENTIFY','308 official zones and 7,259 historical vendor records'),
        @('UNDERSTAND','12 GIS features and K-Means environmental profiles'),
        @('RECOMMEND','Missing-data-aware MCDA with factor explanations'),
        @('ALLOCATE','Capacity checks, audit history and pilot slot assignment')
    )
    for($i=0;$i -lt 4;$i++){
        $x=45+$i*226
        Add-Node $s $labels[$i][0] $labels[$i][1] $x 170 190 145 $(if($i%2){$PaleOlive}else{$PaleBrown}) $(if($i%2){$Olive}else{$Brown2}) | Out-Null
        if($i -lt 3){ Add-Arrow $s ($x+190) 242 ($x+222) 242 $Red 2 | Out-Null }
    }
    Add-Text $s 'One shared service layer powers the web application and WhatsApp conversation flow.' 95 360 770 42 18 $true $Brown 'Times New Roman' 2 3 | Out-Null
    Add-Text $s 'Ranking never bypasses policy status, division, capacity, authentication or officer approval.' 110 415 740 30 14 $false $Grey 'Aptos' 2 3 | Out-Null

    # 7 data foundation
    $s = Add-Base $presentation 'Data Foundation'
    $metrics = @(
        @('308','official NMC zones'),@('7,259','historical vendor records'),@('258','usable zone references'),@('146','scoreable free-zone candidates')
    )
    for($i=0;$i -lt 4;$i++){
        $x=55+$i*222
        Add-Box $s $x 120 190 74 $(if($i%2){$PaleOlive}else{$PaleBrown}) $(if($i%2){$Olive}else{$Brown2}) 5 | Out-Null
        Add-Text $s $metrics[$i][0] ($x+8) 129 174 30 23 $true $Brown 'Times New Roman' 2 3 | Out-Null
        Add-Text $s $metrics[$i][1] ($x+10) 160 170 22 10 $false $Black 'Aptos' 2 3 | Out-Null
    }
    $tbl=$s.Shapes.AddTable(6,3,68,228,824,220)
    Set-Cell $tbl 1 1 'Source' 12 $true $Brown $White 2
    Set-Cell $tbl 1 2 'Prepared evidence' 12 $true $Brown $White 2
    Set-Cell $tbl 1 3 'Role in system' 12 $true $Brown $White 2
    $rows=@(
        @('NMC official records','Zone type, division, capacity, descriptions','Policy and eligibility'),
        @('Historical vendor registry','Business category and past associations','Context only; not live occupancy'),
        @('OpenStreetMap','Roads, facilities, transport and land-use layers','Environmental features'),
        @('Operational database','Profiles, requests, allocations, slots and audit events','Current system state'),
        @('Versioned model assets','K-Means model, MCDA policy and metadata','Reproducible analytics')
    )
    for($r=0;$r -lt $rows.Count;$r++){
        $fill=if($r%2){$White}else{$PaleBrown}
        for($c=0;$c -lt 3;$c++){Set-Cell $tbl ($r+2) ($c+1) $rows[$r][$c] 10 ($c -eq 0) $fill $Black 1}
    }

    # 8 pipeline diagram
    $s = Add-Base $presentation 'Data Processing Pipeline'
    $stages=@(
        @('1. Ingest',"NMC CSV/PDF extracts`nOSM GeoPackage layers"),
        @('2. Standardize',"IDs, categories, divisions`ntranslations and coordinates"),
        @('3. Validate',"Missingness, duplicates`ngeometry and provenance"),
        @('4. Engineer',"Road, POI, facility and`ntransport features"),
        @('5. Version',"Training snapshot, model`nmetadata and candidate catalog"),
        @('6. Serve',"Recommendation API, maps`nand evidence panels")
    )
    for($i=0;$i -lt 6;$i++){
        $x=45+($i%3)*303; $y=130+[Math]::Floor($i/3)*178
        Add-Node $s $stages[$i][0] $stages[$i][1] $x $y 250 112 $(if($i%2){$PaleOlive}else{$PaleBrown}) $(if($i%2){$Olive}else{$Brown2}) | Out-Null
        if($i%3 -lt 2){Add-Arrow $s ($x+250) ($y+56) ($x+293) ($y+56) $Red 2|Out-Null}
        if($i -eq 2){Add-Arrow $s 777 242 777 302 $Red 2|Out-Null}
    }
    Add-Text $s 'Every output retains source limitations; missing values never become invented facts.' 130 455 700 26 15 $true $Red 'Aptos' 2 3 | Out-Null

    # 9 feature engineering
    $s = Add-Base $presentation 'GIS Feature Engineering and Data Quality'
    Add-Text $s 'Twelve active environmental features' 62 118 405 26 18 $true $Brown 'Times New Roman' 2 3 | Out-Null
    Add-Text $s "Road access: distance to major road, road density, pedestrian-road density`nCommercial context: commercial, market and food POI counts`nTransport: bus access count and distance`nFacilities: healthcare, education, toilet and parking counts" 72 158 410 178 14 $false $Black 'Aptos' 1 1 | Out-Null
    Add-Text $s 'Quality controls' 535 118 350 26 18 $true $Olive 'Times New Roman' 2 3 | Out-Null
    Add-Text $s "- Projected metric analysis in EPSG:32643`n- Deduplicated transport and facility layers`n- 258 usable references; 50 missing references`n- Invalid geometry count: 0`n- Source confidence preserved in metadata`n- Ready-for-feature-engineering audit: passed" 548 158 340 178 14 $false $Black 'Aptos' 1 1 | Out-Null
    Add-Box $s 72 366 816 80 $PaleOlive $Olive 5 | Out-Null
    Add-Text $s 'Excluded from clustering' 92 377 190 22 15 $true $Brown 'Aptos' 1 3 | Out-Null
    Add-Text $s 'capacity, zone type, geometry area, historical vendor evidence and sparse land-use shares' 282 375 580 45 13 $false $Black 'Aptos' 1 1 | Out-Null

    # 10 KMeans
    $s = Add-Base $presentation 'K-Means Environmental Profiling'
    Add-PictureFit $s (Join-Path $workspace 'reports\kmeans\active_v2_k_selection\cluster_size_comparison.png') 48 122 410 225 | Out-Null
    Add-PictureFit $s (Join-Path $workspace 'reports\kmeans\active_v2_k_selection\cluster_profile_heatmap.png') 500 122 410 225 | Out-Null
    Add-Text $s 'Selected configuration' 72 372 220 24 16 $true $Brown 'Times New Roman' 1 3 | Out-Null
    Add-Text $s 'K = 2 | 258 rows | 12 features | five seeds' 72 400 310 24 14 $false $Black 'Aptos' 1 3 | Out-Null
    Add-Text $s 'Silhouette 0.3406   Davies-Bouldin 1.4645   ARI 1.0000' 410 400 440 24 14 $true $Olive 'Aptos' 1 3 | Out-Null
    Add-Text $s 'Interpretation: stable environmental typology, not a prediction of suitability or business success.' 90 451 780 24 13 $true $Red 'Aptos' 2 3 | Out-Null

    # 11 MCDA
    $s = Add-Base $presentation 'Explainable Zone Recommendation with MCDA'
    Add-Box $s 64 120 832 62 $PaleBrown $Brown2 5 | Out-Null
    Add-Text $s 'Score(z) = sum [ weight(i) x normalized factor(i,z) ]' 84 132 792 32 22 $true $Brown 'Times New Roman' 2 3 | Out-Null
    $factors=@(
        @('Business fit','25%'),@('Commercial activity','20%'),@('Access','20%'),@('Facilities','15%'),@('Vendor preference','10%'),@('Historical evidence','10%')
    )
    for($i=0;$i -lt 6;$i++){
        $x=60+($i%3)*300; $y=218+[Math]::Floor($i/3)*100
        Add-Box $s $x $y 250 70 $(if($i%2){$PaleOlive}else{$PaleBrown}) $(if($i%2){$Olive}else{$Brown2}) 5|Out-Null
        Add-Text $s $factors[$i][0] ($x+12) ($y+10) 170 22 13 $true $Brown 'Aptos' 1 3|Out-Null
        Add-Text $s $factors[$i][1] ($x+182) ($y+9) 55 26 18 $true $(if($i%2){$Olive}else{$Gold}) 'Times New Roman' 3 3|Out-Null
        Add-Text $s 'Contribution shown in every result' ($x+12) ($y+39) 220 18 9 $false $Grey 'Aptos' 1 3|Out-Null
    }
    Add-Text $s 'Eligibility filters run before ranking: division, zone type, live status, verified capacity and current-zone exclusion.' 90 432 780 36 13 $true $Red 'Aptos' 2 3|Out-Null

    # 12 sensitivity
    $s = Add-Base $presentation 'Recommendation Sensitivity and Interpretation'
    $sens=@(
        @('224','weight-perturbation scenarios'),@('100%','top result stability'),@('85.57%','mean top-3 retention'),@('0.9977','mean rank correlation')
    )
    for($i=0;$i -lt 4;$i++){
        $x=55+$i*222
        Add-Box $s $x 128 190 90 $(if($i%2){$PaleOlive}else{$PaleBrown}) $(if($i%2){$Olive}else{$Brown2}) 5|Out-Null
        Add-Text $s $sens[$i][0] ($x+8) 142 174 30 24 $true $Brown 'Times New Roman' 2 3|Out-Null
        Add-Text $s $sens[$i][1] ($x+12) 177 166 26 10 $false $Black 'Aptos' 2 1|Out-Null
    }
    Add-Text $s 'Documented scenario' 76 266 250 28 18 $true $Brown 'Times New Roman' 1 3|Out-Null
    Add-Text $s 'Food vendor | Nashik West | 146 candidates | Top 3: NW_F_025, NW_F_005, NW_F_001' 78 305 800 32 14 $false $Black 'Aptos' 1 3|Out-Null
    Add-Box $s 74 366 812 78 $PaleBrown $Red 5|Out-Null
    Add-Text $s 'What this proves' 92 377 160 24 15 $true $Red 'Aptos' 1 3|Out-Null
    Add-Text $s 'The first result is robust for this request. Lower-ranked positions still change, so the interface shows multiple candidates and factor evidence.' 250 374 610 54 13 $false $Black 'Aptos' 1 1|Out-Null

    # 13 end-to-end flow diagram
    $s = Add-Base $presentation 'End-to-End Recommendation and Allocation Flow'
    $flow=@(
        @('Authenticate','Role and ownership'),@('Load context','Profile, division and current zone'),@('Filter','Policy, capacity and live status'),@('Rank','MCDA score and contributions'),@('Explain','Map, factors and cautions'),@('Request','New allocation or relocation'),@('Review','Officer decision'),@('Commit','Transaction, capacity and audit')
    )
    for($i=0;$i -lt 8;$i++){
        $x=40+($i%4)*230; $y=128+[Math]::Floor($i/4)*190
        Add-Node $s $flow[$i][0] $flow[$i][1] $x $y 185 90 $(if($i%2){$PaleOlive}else{$PaleBrown}) $(if($i%2){$Olive}else{$Brown2})|Out-Null
        if($i -lt 4 -and $i%4 -lt 3){Add-Arrow $s ($x+185) ($y+45) ($x+222) ($y+45) $Red 2|Out-Null}
    }
    Add-Arrow $s 838 218 838 318 $Red 2|Out-Null
    Add-Arrow $s 730 363 690 363 $Red 2|Out-Null
    Add-Arrow $s 500 363 460 363 $Red 2|Out-Null
    Add-Arrow $s 270 363 230 363 $Red 2|Out-Null
    Add-Text $s 'The same ranking service supports the web application and WhatsApp conversation flow.' 120 453 720 24 13 $true $Brown 'Aptos' 2 3|Out-Null

    # 14 architecture
    $s = Add-Base $presentation 'Final System Architecture'
    Add-Node $s 'Vendor PWA' "React + Vite`nEnglish / Marathi / Hindi" 40 125 170 80 $PaleBrown $Brown2|Out-Null
    Add-Node $s 'Officer Workspace' "Dashboard, review`nand slot planning" 40 230 170 80 $PaleBrown $Brown2|Out-Null
    Add-Node $s 'WhatsApp Cloud API' "Signed webhook`nand simulator" 40 335 170 80 $PaleBrown $Brown2|Out-Null
    Add-Node $s 'FastAPI Service Layer' 'Authentication, schemas, role checks and API orchestration' 300 125 250 76 $PaleOlive $Olive|Out-Null
    Add-Node $s 'Domain Services' 'Recommendations, allocations, relocation, pilot geometry and explanations' 300 230 250 90 $PaleOlive $Olive|Out-Null
    Add-Node $s 'Analytics' "K-Means environmental model`nMCDA + AHP + sensitivity" 300 350 250 76 $PaleOlive $Olive|Out-Null
    Add-Node $s 'Operational Database' "SQLite / PostgreSQL`nprofiles, requests, allocations, slots, audit" 650 125 250 90 $PaleBrown $Brown2|Out-Null
    Add-Node $s 'Versioned GIS Assets' "GeoJSON / GeoPackage / CSV`nmodel and policy metadata" 650 260 250 90 $PaleBrown $Brown2|Out-Null
    Add-Node $s 'External Providers' 'OSM tiles, routing, OTP, Gemini and Meta' 650 382 250 64 $PaleBrown $Brown2|Out-Null
    foreach($y in 165,270,375){Add-Arrow $s 210 $y 292 $y $Red 2|Out-Null}
    Add-Arrow $s 550 165 642 165 $Red 2|Out-Null
    Add-Arrow $s 550 275 642 305 $Red 2|Out-Null
    Add-Arrow $s 550 390 642 412 $Red 2|Out-Null
    Add-Text $s 'Separation of concerns keeps analytical evidence distinct from mutable operational state.' 145 470 670 22 12 $true $Red 'Aptos' 2 3|Out-Null

    # 15 security/privacy
    $s = Add-Base $presentation 'Backend, Data and Privacy Controls'
    $tbl=$s.Shapes.AddTable(6,3,60,128,840,285)
    Set-Cell $tbl 1 1 'Control area' 12 $true $Brown $White 2
    Set-Cell $tbl 1 2 'Implemented control' 12 $true $Brown $White 2
    Set-Cell $tbl 1 3 'Why it matters' 12 $true $Brown $White 2
    $rows=@(
        @('Authorization','Server-enforced VENDOR, ONBOARDING and ADMIN roles','UI visibility alone never grants access'),
        @('Sessions','HttpOnly, SameSite cookies; hashed server tokens','Reduces token exposure'),
        @('Mobile identity','Conservative normalization and HMAC mapping','Plain phone numbers stay out of SQLite/model files'),
        @('Transactions','Atomic approval, capacity and relocation updates','Prevents final-slot race conditions'),
        @('PWA privacy','Static allowlist only; API and private pages bypass cache','No authenticated data in Cache Storage')
    )
    for($r=0;$r -lt 5;$r++){
        $fill=if($r%2){$White}else{$PaleBrown}
        for($c=0;$c -lt 3;$c++){Set-Cell $tbl ($r+2) ($c+1) $rows[$r][$c] 10 ($c -eq 0) $fill $Black 1}
    }
    Add-Text $s 'External provider credentials remain deployment secrets; debug OTP is restricted to development.' 110 438 740 34 13 $true $Red 'Aptos' 2 3|Out-Null

    # 16 vendor screenshots
    $s = Add-Base $presentation 'Vendor Journey: Discover, Compare and Apply'
    Add-PictureFit $s (Join-Path $workspace 'reports\vendormap\vendor-home-1440.png') 38 118 285 245|Out-Null
    Add-PictureFit $s (Join-Path $workspace 'reports\vendormap\recommendations-1440.png') 338 118 285 245|Out-Null
    Add-PictureFit $s (Join-Path $workspace 'reports\vendormap\application-tracking.png') 638 118 285 245|Out-Null
    Add-Text $s '1. Personal dashboard' 58 382 245 22 13 $true $Brown 'Times New Roman' 2 3|Out-Null
    Add-Text $s '2. Ranked recommendations' 358 382 245 22 13 $true $Brown 'Times New Roman' 2 3|Out-Null
    Add-Text $s '3. Server-backed request status' 658 382 245 22 13 $true $Brown 'Times New Roman' 2 3|Out-Null
    Add-Text $s 'Each recommendation includes map position, eligibility context, factor contributions and cautions.' 110 440 740 30 13 $true $Olive 'Aptos' 2 3|Out-Null

    # 17 admin screenshots
    $s = Add-Base $presentation 'Officer Journey: Review, Decide and Monitor'
    Add-PictureFit $s (Join-Path $workspace 'reports\vendormap\officer-home-1440.png') 42 118 410 210|Out-Null
    Add-PictureFit $s (Join-Path $workspace 'reports\vendormap\vendor-directory.png') 508 118 410 210|Out-Null
    Add-PictureFit $s (Join-Path $workspace 'reports\vendormap\relocation-planning.png') 42 352 410 115|Out-Null
    Add-PictureFit $s (Join-Path $workspace 'reports\vendormap\zone-details.png') 508 352 410 115|Out-Null
    Add-Text $s 'City overview and pending work' 90 326 320 20 12 $true $Brown 'Aptos' 2 3|Out-Null
    Add-Text $s 'Searchable vendor registry' 555 326 320 20 12 $true $Brown 'Aptos' 2 3|Out-Null

    # 18 maps and slots
    $s = Add-Base $presentation 'Spatial Decision Support and Pilot Slots'
    Add-PictureFit $s (Join-Path $workspace 'reports\vendormap\city-map.png') 42 122 420 260|Out-Null
    Add-PictureFit $s (Join-Path $workspace 'reports\vendormap\vending-slots.png') 500 122 420 260|Out-Null
    Add-Text $s 'Zone map' 100 397 300 24 15 $true $Brown 'Times New Roman' 2 3|Out-Null
    Add-Text $s 'Pilot slot map and inspector' 560 397 300 24 15 $true $Brown 'Times New Roman' 2 3|Out-Null
    Add-Text $s '10 saved test slots passed computational containment, spacing and clearance checks. Physical verification is still required.' 90 442 780 36 13 $true $Red 'Aptos' 2 3|Out-Null

    # 19 access channels
    $s = Add-Base $presentation 'Access Channels: Multilingual PWA and WhatsApp'
    $channels=@(
        @('Installable PWA','Production build supports installability, controlled updates and a generic offline page.'),
        @('Three languages','English, Marathi and Hindi labels use stable backend values and locale-aware display.'),
        @('WhatsApp bot','Direct Meta Cloud API webhook reuses authentication, recommendation and request services.'),
        @('Safe fallbacks','Routing, AI explanation and messaging failures return explicit alternatives without changing scores.')
    )
    for($i=0;$i -lt 4;$i++){
        $x=58+($i%2)*430; $y=125+[Math]::Floor($i/2)*160
        Add-Node $s $channels[$i][0] $channels[$i][1] $x $y 380 115 $(if($i%2){$PaleOlive}else{$PaleBrown}) $(if($i%2){$Olive}else{$Brown2})|Out-Null
    }
    Add-Text $s 'One domain model, multiple access paths.' 170 451 620 30 20 $true $Brown 'Times New Roman' 2 3|Out-Null

    # 20 testing
    $s = Add-Base $presentation 'Testing and Verification Evidence'
    $tests=@(
        @('97 / 97','focused backend tests in the final report'),@('64 / 64','current frontend unit tests'),@('1,690','modules transformed in verified production build'),@('234','backend cases currently collected')
    )
    for($i=0;$i -lt 4;$i++){
        $x=55+$i*222
        Add-Box $s $x 125 190 92 $(if($i%2){$PaleOlive}else{$PaleBrown}) $(if($i%2){$Olive}else{$Brown2}) 5|Out-Null
        Add-Text $s $tests[$i][0] ($x+8) 139 174 32 24 $true $Brown 'Times New Roman' 2 3|Out-Null
        Add-Text $s $tests[$i][1] ($x+12) 177 166 28 10 $false $Black 'Aptos' 2 1|Out-Null
    }
    $tbl=$s.Shapes.AddTable(5,3,80,252,800,190)
    Set-Cell $tbl 1 1 'Test layer' 12 $true $Brown $White 2
    Set-Cell $tbl 1 2 'Representative evidence' 12 $true $Brown $White 2
    Set-Cell $tbl 1 3 'Risk controlled' 12 $true $Brown $White 2
    $rows=@(
        @('Domain','MCDA, division, capacity, relocation and slot geometry','Incorrect recommendation or state transition'),
        @('Security','Sessions, roles, ownership, OTP and production config','Unauthorized access and insecure deployment'),
        @('Integration','Vendor-to-officer flow, PostgreSQL migration and WhatsApp','Broken cross-module workflow'),
        @('Frontend','PWA privacy, API client, localization and map grouping','Data leakage and UI inconsistency')
    )
    for($r=0;$r -lt 4;$r++){
        $fill=if($r%2){$White}else{$PaleBrown}
        for($c=0;$c -lt 3;$c++){Set-Cell $tbl ($r+2) ($c+1) $rows[$r][$c] 9 ($c -eq 0) $fill $Black 1}
    }

    # 21 results
    $s = Add-Base $presentation 'Verified Results and Project Contribution'
    $results=@(
        @('Data','Traceable NMC + OSM preparation with explicit missingness and provenance.'),
        @('Analytics','Stable two-cluster typology and scenario-specific MCDA sensitivity evidence.'),
        @('Software','Role-separated vendor/officer workflows with live capacity and transaction safety.'),
        @('Spatial','Interactive zone maps and computationally validated pilot slot geometry.'),
        @('Access','Responsive multilingual PWA plus shared WhatsApp service logic.'),
        @('Governance','Explanations, audit history and clear limits on automated authority.')
    )
    for($i=0;$i -lt 6;$i++){
        $x=52+($i%2)*445; $y=118+[Math]::Floor($i/2)*118
        Add-Node $s $results[$i][0] $results[$i][1] $x $y 410 82 $(if($i%2){$PaleOlive}else{$PaleBrown}) $(if($i%2){$Olive}else{$Brown2})|Out-Null
    }
    Add-Text $s 'VendorMap delivers a completed academic decision-support system, not an autonomous municipal authority.' 95 464 770 24 13 $true $Red 'Aptos' 2 3|Out-Null

    # 22 COCOMO size
    $s = Add-Base $presentation 'COCOMO II: Repository-Based Size Estimate'
    Add-Text $s 'Approximate maintained source size' 62 120 390 26 18 $true $Brown 'Times New Roman' 2 3|Out-Null
    Add-Text $s '31.5 KSLOC' 64 158 350 54 34 $true $Red 'Times New Roman' 2 3|Out-Null
    Add-Text $s 'Nonblank production and research source lines; tests and dependencies excluded.' 66 212 380 44 12 $false $Grey 'Aptos' 1 1|Out-Null
    $areas=@(
        @('Backend',20930,0.665,$Brown2),@('Scripts / models',5899,0.187,$Gold),@('Frontend',4664,0.148,$Olive)
    )
    for($i=0;$i -lt 3;$i++){
        $y=305+$i*48
        Add-Text $s $areas[$i][0] 66 $y 120 20 11 $true $Black 'Aptos' 1 3|Out-Null
        Add-Box $s 190 ($y+2) 520 18 $LightGrey $LightGrey 1|Out-Null
        Add-Box $s 190 ($y+2) (520*$areas[$i][2]) 18 $areas[$i][3] $areas[$i][3] 1|Out-Null
        Add-Text $s ([string]$areas[$i][1]) 730 ($y-2) 100 24 12 $true $Brown 'Aptos' 3 3|Out-Null
    }
    Add-Box $s 500 128 360 118 $PaleOlive $Olive 5|Out-Null
    Add-Text $s 'Model assumptions' 520 143 320 22 15 $true $Brown 'Times New Roman' 2 3|Out-Null
    Add-Text $s "Post-architecture form`nE = 1.1153`nEffort multiplier = 1.287" 535 176 290 58 13 $false $Black 'Aptos' 2 1|Out-Null

    # 23 COCOMO effort/cost
    $s = Add-Base $presentation 'COCOMO II: Effort, Schedule and Cost Scenario'
    $coco=@(
        @('177.37 PM','estimated professional effort'),@('19.35 months','estimated schedule'),@('9.17 FTE','implied average team'),@('INR 2.44 Cr','initial professional-equivalent budget')
    )
    for($i=0;$i -lt 4;$i++){
        $x=55+$i*222
        Add-Box $s $x 130 190 100 $(if($i%2){$PaleOlive}else{$PaleBrown}) $(if($i%2){$Olive}else{$Brown2}) 5|Out-Null
        Add-Text $s $coco[$i][0] ($x+8) 148 174 30 21 $true $Brown 'Times New Roman' 2 3|Out-Null
        Add-Text $s $coco[$i][1] ($x+12) 184 166 30 10 $false $Black 'Aptos' 2 1|Out-Null
    }
    Add-Text $s 'Effort formula' 78 284 190 24 15 $true $Brown 'Times New Roman' 1 3|Out-Null
    Add-Text $s 'PM = 2.94 x 31.493^1.1153 x 1.287' 78 316 360 26 17 $true $Olive 'Aptos' 1 3|Out-Null
    Add-Text $s 'Schedule formula' 520 284 190 24 15 $true $Brown 'Times New Roman' 1 3|Out-Null
    Add-Text $s 'TDEV = 3.67 x 177.37^0.32106' 520 316 360 26 17 $true $Olive 'Aptos' 1 3|Out-Null
    Add-Box $s 74 382 812 72 $PaleBrown $Red 5|Out-Null
    Add-Text $s 'Planning interpretation' 92 393 180 20 14 $true $Red 'Aptos' 1 3|Out-Null
    Add-Text $s 'This is a hypothetical replacement-cost model, not student expenditure or recorded project history. Field survey, security review and operational support remain separate.' 275 389 585 52 12 $false $Black 'Aptos' 1 1|Out-Null

    # 24 deployment
    $s = Add-Base $presentation 'Deployment and Operational Readiness'
    $deploy=@(
        @('Client',"Vite production build`nHTTPS host + PWA headers"),
        @('API',"FastAPI behind reverse proxy`nsecure cookies + origin controls"),
        @('Database',"SQLite for academic pilot`nPostgreSQL migration path available"),
        @('Providers',"OTP, Meta, routing and AI`nconfigured through secrets"),
        @('Operations',"Backups, restore drills`nmonitoring and incident handling")
    )
    for($i=0;$i -lt 5;$i++){
        $x=34+$i*187
        Add-Node $s $deploy[$i][0] $deploy[$i][1] $x 170 155 120 $(if($i%2){$PaleOlive}else{$PaleBrown}) $(if($i%2){$Olive}else{$Brown2})|Out-Null
        if($i -lt 4){Add-Arrow $s ($x+155) 230 ($x+181) 230 $Red 2|Out-Null}
    }
    Add-Text $s 'Pilot hosting estimate' 100 350 270 26 17 $true $Brown 'Times New Roman' 2 3|Out-Null
    Add-Text $s 'INR 3,500 / month' 100 385 270 34 24 $true $Olive 'Times New Roman' 2 3|Out-Null
    Add-Text $s 'Illustrative host, storage, domain allocation and monitoring only.' 430 365 390 60 14 $false $Black 'Aptos' 1 1|Out-Null

    # 25 limitations
    $s = Add-Base $presentation 'Limitations and Responsible Use'
    $lims=@(
        @('Spatial authority','Analytical reference points are not certified vending boundaries.'),
        @('Outcome evidence','No verified footfall, revenue, safety or displacement outcomes exist.'),
        @('Model meaning','K-Means is descriptive; MCDA sensitivity is scenario-specific.'),
        @('Field validation','Pilot slots lack obstruction survey and physical approval.'),
        @('External services','Production OTP, WhatsApp, routing and AI need live-provider validation.'),
        @('Operational scale','Load, accessibility, backup recovery and long-term monitoring need formal testing.')
    )
    for($i=0;$i -lt 6;$i++){
        $x=52+($i%2)*445; $y=118+[Math]::Floor($i/2)*118
        Add-Node $s $lims[$i][0] $lims[$i][1] $x $y 410 82 $(if($i%2){$PaleOlive}else{$PaleBrown}) $(if($i%2){$Olive}else{$Brown2})|Out-Null
    }
    Add-Text $s 'Final allocation remains a municipal decision supported by evidence, policy and field inspection.' 95 464 770 24 13 $true $Red 'Aptos' 2 3|Out-Null

    # 26 future/conclusion
    $s = Add-Base $presentation 'Future Scope and Conclusion'
    Add-Text $s 'Next validation phase' 58 118 380 26 18 $true $Brown 'Times New Roman' 2 3|Out-Null
    Add-Text $s "- Survey authoritative vending polygons and accessibility constraints`n- Verify capacity, obstructions and pilot slots in the field`n- Collect privacy-reviewed outcome labels for supervised evaluation`n- Run sensitivity across vendor categories and divisions" 70 157 400 190 14 $false $Black 'Aptos' 1 1|Out-Null
    Add-Text $s 'Operational hardening' 520 118 380 26 18 $true $Olive 'Times New Roman' 2 3|Out-Null
    Add-Text $s "- Deploy PostgreSQL, backups and restore drills`n- Complete load, security and accessibility testing`n- Validate OTP, WhatsApp and routing providers over HTTPS`n- Add monitoring, rate limits and incident procedures" 532 157 360 190 14 $false $Black 'Aptos' 1 1|Out-Null
    Add-Box $s 78 375 804 86 $PaleOlive $Olive 5|Out-Null
    Add-Text $s 'Conclusion' 98 387 150 22 16 $true $Brown 'Times New Roman' 1 3|Out-Null
    Add-Text $s 'VendorMap connects GIS evidence, transparent ranking and controlled allocation in one auditable workflow while preserving the limits of the available data.' 248 382 610 60 14 $true $Black 'Aptos' 1 1|Out-Null

    # 27 references/Q&A
    $s = Add-Base $presentation 'References and Discussion'
    Add-Text $s 'Primary project evidence' 55 118 400 26 18 $true $Brown 'Times New Roman' 2 3|Out-Null
    Add-Text $s "1. VendorMap Project Report, final LaTeX/PDF build`n2. Versioned K-Means metrics and comparison artifacts`n3. MCDA sensitivity summary and scenario CSVs`n4. Data-quality audit and feature dictionary`n5. Browser-captured vendor, officer and pilot-slot interfaces`n6. Automated backend/frontend test suites and production build" 72 158 410 230 13 $false $Black 'Aptos' 1 1|Out-Null
    Add-Text $s 'Questions and Discussion' 545 190 330 54 29 $true $Brown 'Times New Roman' 2 3|Out-Null
    Add-Text $s 'VendorMap | Project Final Examination' 575 260 270 22 12 $false $Red 'Aptos' 2 3|Out-Null
    Add-PictureFit $s $nmcLogo 610 318 190 110 $false | Out-Null

    # Save
    if (Test-Path $OutputPptx) { Remove-Item -LiteralPath $OutputPptx -Force }
    if (Test-Path $OutputPdf) { Remove-Item -LiteralPath $OutputPdf -Force }
    $presentation.SaveAs($OutputPptx, 24)
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
