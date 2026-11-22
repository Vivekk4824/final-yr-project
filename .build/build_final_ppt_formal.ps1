param(
    [string]$OutputPptx = "C:\Users\kalya\vendor-map\.build\formal-preview\VendorMap_Final_Project_Examination.pptx",
    [string]$OutputPdf = "C:\Users\kalya\vendor-map\.build\formal-preview\VendorMap_Final_Project_Examination.pdf"
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing

function C([int]$r,[int]$g,[int]$b){ $r + 256*$g + 65536*$b }
$Cream=C 250 249 238; $Brown=C 78 67 59; $Brown2=C 114 89 70
$Olive=C 102 122 93; $Pale=C 235 237 226; $PaleBrown=C 242 235 226
$Red=C 160 61 49; $Gold=C 151 112 54; $Black=C 32 32 32; $White=C 255 255 255
$Grey=C 95 95 95; $Line=C 205 198 188; $Blue=C 58 92 130

$root='C:\Users\kalya\vendor-map'
$contentBg=Join-Path $root '.build\reference_unpack\ppt\media\image4.jpg'
$coverBg=Join-Path $root '.build\reference_unpack\ppt\media\image2.jpg'
$media=Join-Path $root '.build\review2_unpack\ppt\media'
$archPage=Join-Path $root '.build\architecture-cropped.png'
$diagramDir=Join-Path $root '.build\report-diagrams'
$realWhatsAppDir=Join-Path $root 'report\reportss\figures\whatsapp'
$websiteDir=Join-Path $root 'report\reportss\figures\website_screenshots'
$waMenu=Join-Path $realWhatsAppDir 'WhatsApp Image 2026-11-18 at 10.58.48 AM.jpeg'
$waChoose=Join-Path $realWhatsAppDir 'WhatsApp Image 2026-11-18 at 10.58.49 AM (1).jpeg'
$waRequest=Join-Path $realWhatsAppDir 'WhatsApp Image 2026-11-18 at 10.58.49 AM (2).jpeg'
$waRecommendations=Join-Path $realWhatsAppDir 'WhatsApp Image 2026-11-18 at 10.58.49 AM.jpeg'
$waLanguage=Join-Path $realWhatsAppDir 'WhatsApp Image 2026-11-18 at 10.58.50 AM (1).jpeg'
$waExplainMap=Join-Path $realWhatsAppDir 'WhatsApp Image 2026-11-18 at 10.58.51 AM (1).jpeg'

function Text($s,[string]$t,[double]$x,[double]$y,[double]$w,[double]$h,[double]$size=28,[bool]$bold=$false,[int]$color=$Black,[string]$font='Aptos',[int]$align=1,[int]$valign=1){
    $q=$s.Shapes.AddTextbox(1,$x,$y,$w,$h)
    $q.TextFrame.MarginLeft=3; $q.TextFrame.MarginRight=3; $q.TextFrame.MarginTop=1; $q.TextFrame.MarginBottom=1
    $q.TextFrame.WordWrap=-1; $q.TextFrame.VerticalAnchor=$valign
    $q.TextFrame.TextRange.Text=$t; $q.TextFrame.TextRange.Font.Name=$font; $q.TextFrame.TextRange.Font.Size=$size
    $q.TextFrame.TextRange.Font.Bold=[int]$bold*-1; $q.TextFrame.TextRange.Font.Color.RGB=$color
    $q.TextFrame.TextRange.ParagraphFormat.Alignment=$align; $q.Fill.Visible=0; $q.Line.Visible=0
    $q
}
function Box($s,[double]$x,[double]$y,[double]$w,[double]$h,[int]$fill=$White,[int]$line=$Line,[int]$shape=1){
    $q=$s.Shapes.AddShape($shape,$x,$y,$w,$h); $q.Fill.ForeColor.RGB=$fill; $q.Fill.Solid(); $q.Line.ForeColor.RGB=$line; $q.Line.Weight=1.2; $q
}
function PicFit($s,[string]$path,[double]$x,[double]$y,[double]$w,[double]$h,[bool]$frame=$true){
    if($frame){ Box $s ($x-3) ($y-3) ($w+6) ($h+6) $White $Line 1 | Out-Null }
    $im=[System.Drawing.Image]::FromFile($path)
    try{$sc=[Math]::Min($w/$im.Width,$h/$im.Height);$iw=$im.Width*$sc;$ih=$im.Height*$sc;$ix=$x+($w-$iw)/2;$iy=$y+($h-$ih)/2}finally{$im.Dispose()}
    $s.Shapes.AddPicture($path,0,-1,$ix,$iy,$iw,$ih)
}
function Arrow($s,[double]$x1,[double]$y1,[double]$x2,[double]$y2,[int]$color=$Red){
    $q=$s.Shapes.AddConnector(1,$x1,$y1,$x2,$y2);$q.Line.ForeColor.RGB=$color;$q.Line.Weight=2.2;$q.Line.EndArrowheadStyle=3;$q
}
function Base($p,[string]$title,[string]$section='PROJECT FINAL EXAMINATION'){
    $s=$p.Slides.Add($p.Slides.Count+1,12);$s.Shapes.AddPicture($contentBg,0,-1,0,0,960,540)|Out-Null
    Text $s $title 42 24 800 46 32 $true $Brown 'Times New Roman' 1 3|Out-Null
    Text $s $section 44 72 620 17 10 $true $Grey 'Aptos' 1 3|Out-Null
    Text $s 'Department of Information Technology | A.Y. 2026-27' 42 516 620 14 10 $false $Grey 'Aptos' 1 3|Out-Null
    Text $s ([string]$s.SlideIndex) 910 516 24 14 10 $false $Grey 'Aptos' 3 3|Out-Null
    $s
}
function Bullets($s,[string[]]$items,[double]$x=70,[double]$y=120,[double]$w=820,[double]$h=330,[double]$size=28,[int]$color=$Black){
    $t=($items|ForEach-Object{"- $_"}) -join "`r`n"
    $q=Text $s $t $x $y $w $h $size $false $color 'Aptos' 1 1
    $q.TextFrame.TextRange.ParagraphFormat.SpaceAfter=10
    $q
}
function TwoPics($p,[string]$title,[string]$a,[string]$b,[string]$ca,[string]$cb){
    $s=Base $p $title
    PicFit $s $a 35 112 430 315|Out-Null; PicFit $s $b 495 112 430 315|Out-Null
    Text $s $ca 45 437 410 42 28 $true $Brown 'Times New Roman' 2 3|Out-Null
    Text $s $cb 505 437 410 42 28 $true $Brown 'Times New Roman' 2 3|Out-Null
    $s
}
function FullScreenshot($p,[string]$title,[string]$path){
    $s=Base $p $title
    PicFit $s $path 30 96 900 405|Out-Null
    $s
}
function TwoCols($p,[string]$title,[string]$lt,[string[]]$lb,[string]$rt,[string[]]$rb){
    $s=Base $p $title
    Text $s $lt 65 115 380 40 30 $true $Brown 'Times New Roman' 1 3|Out-Null
    Text $s $rt 515 115 380 40 30 $true $Olive 'Times New Roman' 1 3|Out-Null
    Bullets $s $lb 65 165 380 300 28|Out-Null; Bullets $s $rb 515 165 380 300 28|Out-Null
    $s
}
function MetricRow($s,[object[]]$metrics,[double]$y=170){
    $n=$metrics.Count;$gap=18;$w=(840-($n-1)*$gap)/$n
    for($i=0;$i -lt $n;$i++){$x=60+$i*($w+$gap);Box $s $x $y $w 150 $(if($i%2){$Pale}else{$PaleBrown}) $(if($i%2){$Olive}else{$Brown2}) 5|Out-Null;Text $s $metrics[$i][0] ($x+8) ($y+20) ($w-16) 52 34 $true $Brown 'Times New Roman' 2 3|Out-Null;Text $s $metrics[$i][1] ($x+10) ($y+82) ($w-20) 55 28 $false $Black 'Aptos' 2 3|Out-Null}
}

$pp=$null;$p=$null
try{
    New-Item -ItemType Directory -Force -Path (Split-Path $OutputPptx),(Split-Path $OutputPdf)|Out-Null
    $pp=New-Object -ComObject PowerPoint.Application;$p=$pp.Presentations.Add();$p.PageSetup.SlideWidth=960;$p.PageSetup.SlideHeight=540

    # 1 - formal review-style cover
    $s=$p.Slides.Add(1,12);$s.Shapes.AddPicture($coverBg,0,-1,0,0,960,540)|Out-Null
    Text $s 'K. K. WAGH INSTITUTE OF ENGINEERING EDUCATION AND RESEARCH, NASHIK' 42 18 520 30 18 $true $White 'Times New Roman' 2 3|Out-Null
    Text $s 'Department of Information Technology' 42 52 520 24 16 $true $White 'Times New Roman' 2 3|Out-Null
    Box $s 55 80 500 100 $Cream $Cream 1|Out-Null
    Text $s "Project Final Examination`r`nPresentation On" 55 104 500 64 28 $true $Brown 'Times New Roman' 2 3|Out-Null
    Text $s 'VendorMap' 55 166 500 53 40 $true $Red 'Times New Roman' 2 3|Out-Null
    Text $s "GIS Decision Support for Vendors`r`nZoning, Allocation and Management" 55 218 500 70 28 $true $Black 'Times New Roman' 2 1|Out-Null
    Text $s 'Presented By' 60 286 200 30 28 $true $Brown 'Times New Roman' 1 3|Out-Null
    Text $s "19  Darshan Gavate`r`n48  Vivek Patil" 60 315 235 68 28 $false $Black 'Times New Roman' 1 1|Out-Null
    Text $s "65  Sneha Tingare`r`n66  Kalyani Ugale" 300 315 250 68 28 $false $Black 'Times New Roman' 1 1|Out-Null
    Text $s 'Under the Guidance of' 60 382 300 32 28 $true $Brown 'Times New Roman' 1 3|Out-Null
    Text $s 'Prof. R. M. Bora' 60 414 250 32 28 $true $Black 'Times New Roman' 1 3|Out-Null
    Text $s 'Academic Year 2026-27' 60 474 430 28 28 $true $White 'Times New Roman' 1 3|Out-Null

    # 2
    $s=Base $p 'Project Team'
    $team=@(@('19','Darshan Gavate'),@('48','Vivek Patil'),@('65','Sneha Tingare'),@('66','Kalyani Ugale'))
    for($i=0;$i -lt 4;$i++){$y=125+$i*70;Text $s $team[$i][0] 95 $y 90 42 30 $true $Brown 'Times New Roman' 2 3|Out-Null;Text $s $team[$i][1] 205 $y 360 42 30 $false $Black 'Times New Roman' 1 3|Out-Null}
    Box $s 615 145 260 180 $Pale $Olive 5|Out-Null;Text $s 'Project Guide' 640 175 210 42 30 $true $Brown 'Times New Roman' 2 3|Out-Null;Text $s 'Prof. R. M. Bora' 635 235 220 46 30 $true $Black 'Times New Roman' 2 3|Out-Null

    # 3
    $s=Base $p 'Presentation Sequence'
    Bullets $s @('Problem, objectives and proposed solution','Roles, architecture, UML and data-flow models','Raw data, GeoPackages and GIS preparation','K-Means profiling and MCDA ranking','Real WhatsApp, vendor and officer workflows','Testing, COCOMO, deployment and conclusion') 80 112 810 350 28|Out-Null

    # 4
    $s=Base $p 'Problem Definition'
    Bullets $s @('Municipal vendor records, zones and spatial evidence are fragmented.','Manual allocation is difficult to explain, audit and update.','Zone suitability depends on policy, capacity, access and livelihood factors.','Final decisions require both analytical evidence and officer control.') 75 125 815 320 28|Out-Null

    # 5
    $s=Base $p 'Project Objectives'
    Bullets $s @('Prepare traceable NMC and OpenStreetMap spatial datasets.','Profile vending environments through unsupervised learning.','Rank eligible zones through explainable multi-criteria analysis.','Support vendor requests, officer review, capacity and audit workflows.','Provide multilingual web and WhatsApp access.') 75 112 820 355 28|Out-Null

    # 6
    TwoCols $p 'Existing System and Proposed System' 'Existing System' @('Separate files and manual lists','Limited spatial evidence','No factor-level explanation','Manual follow-up') 'Proposed System' @('Unified operational workflow','GIS-based zone evidence','Explainable ranked options','Auditable allocation lifecycle')|Out-Null

    # 7
    $s=Base $p 'Implemented Solution Story'
    $nodes=@('DATA','PROFILE','RECOMMEND','ALLOCATE')
    $sub=@('NMC + OSM','K-Means','MCDA','Officer approval')
    for($i=0;$i -lt 4;$i++){$x=45+$i*230;Box $s $x 180 185 135 $(if($i%2){$Pale}else{$PaleBrown}) $(if($i%2){$Olive}else{$Brown2}) 5|Out-Null;Text $s $nodes[$i] ($x+8) 197 169 38 30 $true $Brown 'Times New Roman' 2 3|Out-Null;Text $s $sub[$i] ($x+8) 250 169 42 28 $false $Black 'Aptos' 2 3|Out-Null;if($i -lt 3){Arrow $s ($x+185) 247 ($x+222) 247|Out-Null}}
    Text $s 'Evidence remains advisory; municipal authority remains final.' 90 380 780 50 30 $true $Red 'Times New Roman' 2 3|Out-Null

    # 8
    $s=Base $p 'System Architecture - Report Evidence'
    PicFit $s $archPage 70 105 820 375|Out-Null

    # 9
    $s=Base $p 'System Architecture - Layered View'
    $layers=@(@('CLIENT CHANNELS','Vendor PWA  |  Officer Dashboard  |  WhatsApp',$PaleBrown,$Brown2),@('APPLICATION AND DOMAIN','FastAPI  |  Authentication  |  MCDA  |  Allocation',$Pale,$Olive),@('DATA AND PROVIDERS','SQLite/PostgreSQL  |  GIS Assets  |  OSM/Meta',$PaleBrown,$Brown2))
    for($i=0;$i -lt 3;$i++){$y=120+$i*125;Box $s 80 $y 800 88 $layers[$i][2] $layers[$i][3] 5|Out-Null;Text $s $layers[$i][0] 105 ($y+10) 250 32 28 $true $Brown 'Times New Roman' 1 3|Out-Null;Text $s $layers[$i][1] 365 ($y+10) 485 58 28 $false $Black 'Aptos' 1 3|Out-Null;if($i -lt 2){Arrow $s 480 ($y+88) 480 ($y+120)|Out-Null}}

    # 10
    TwoCols $p 'Major Architecture Components' 'Service Layer' @('Session and role validation','Eligibility and MCDA','Requests and allocation','Capacity and audit') 'Data Layer' @('Operational repository','Versioned GIS features','K-Means model assets','External providers')|Out-Null

    # Design models from the final report
    $s=Base $p 'Operational Data Model'
    PicFit $s (Join-Path $diagramDir 'er-model.png') 35 115 585 345|Out-Null
    Text $s 'Context' 655 122 240 38 30 $true $Brown 'Times New Roman' 1 3|Out-Null
    Bullets $s @('Vendor requests connect to reviewed allocations.','Live zone status supports capacity checks.','Audit and slot records preserve administrative history.') 650 170 270 275 28|Out-Null

    $s=Base $p 'Data Flow Diagrams'
    PicFit $s (Join-Path $diagramDir 'dfd-level-0.png') 35 112 430 295|Out-Null
    PicFit $s (Join-Path $diagramDir 'dfd-level-1.png') 495 112 430 295|Out-Null
    Text $s 'Level 0: actors and system boundary' 45 420 410 52 28 $true $Brown 'Times New Roman' 2 3|Out-Null
    Text $s 'Level 1: identity, ranking and allocation processes' 505 420 410 52 28 $true $Brown 'Times New Roman' 2 3|Out-Null

    $s=Base $p 'UML Use-Case Model'
    PicFit $s (Join-Path $diagramDir 'use-case.png') 40 110 560 360|Out-Null
    Text $s 'Context' 640 120 245 38 30 $true $Brown 'Times New Roman' 1 3|Out-Null
    Bullets $s @('Vendors manage profiles and requests.','Officers inspect evidence and decide.','Role separation limits each action to its owner.') 635 170 280 270 28|Out-Null

    $s=Base $p 'Component Dependency Model'
    PicFit $s (Join-Path $diagramDir 'component.png') 50 125 570 285|Out-Null
    Text $s 'Context' 655 125 245 38 30 $true $Brown 'Times New Roman' 1 3|Out-Null
    Bullets $s @('React calls one credentialed API client.','FastAPI routes delegate to domain services.','Repositories control database transactions.') 650 175 270 250 28|Out-Null

    $s=Base $p 'Recommendation Sequence Diagram'
    PicFit $s (Join-Path $diagramDir 'sequence.png') 35 105 600 370|Out-Null
    Text $s 'Context' 665 115 235 38 30 $true $Brown 'Times New Roman' 1 3|Out-Null
    Bullets $s @('The API loads evidence and live state.','MCDA returns scores and contributions.','Only the selected request reaches the database.') 655 165 270 270 28|Out-Null

    $s=Base $p 'Allocation Activity Diagram'
    PicFit $s (Join-Path $diagramDir 'activity.png') 35 105 585 370|Out-Null
    Text $s 'Context' 655 115 245 38 30 $true $Brown 'Times New Roman' 1 3|Out-Null
    Bullets $s @('Eligibility is checked before request creation.','The officer reviews the supporting evidence.','Capacity is checked again before commit.') 650 165 275 270 28|Out-Null

    # 11
    $s=Base $p 'Data Sources'
    Bullets $s @('NMC official zone records: type, division, capacity and description.','Historical vendor registry: 7,259 vendor records.','OpenStreetMap: roads, commercial places, transport and facilities.','Operational database: profiles, requests, allocations and slots.') 70 125 825 310 28|Out-Null

    # 12
    TwoPics $p 'Data Before Processing - Municipal Sources' (Join-Path $media 'image11.png') (Join-Path $media 'image12.png') 'Official NMC source table' 'Raw vendor registry extract'|Out-Null

    # 13
    $s=Base $p 'Prepared GeoPackage Dataset'
    PicFit $s (Join-Path $media 'image14.png') 105 110 750 310|Out-Null
    Text $s 'Cleaned, deduplicated and versioned GIS layers' 120 438 720 38 28 $true $Brown 'Times New Roman' 2 3|Out-Null

    # 14
    $s=Base $p 'GIS Verification in QGIS'
    PicFit $s (Join-Path $media 'image15.png') 85 105 790 335|Out-Null
    Text $s 'Layer alignment, geometry and coverage were visually inspected.' 80 451 800 34 28 $true $Brown 'Times New Roman' 2 3|Out-Null

    # 15
    $s=Base $p 'GeoPackage Layers and Parameters - I'
    $rows=@(@('roads_clean.gpkg','13,988','MultiLineString'),@('commercial_model_points.gpkg','353','Point'),@('landuse_clean.gpkg','401','MultiPolygon'))
    Text $s 'Layer' 65 115 420 35 28 $true $White 'Aptos' 1 3|ForEach-Object{$_.Fill.Visible=-1;$_.Fill.ForeColor.RGB=$Brown}
    Text $s 'Features' 500 115 150 35 28 $true $White 'Aptos' 2 3|ForEach-Object{$_.Fill.Visible=-1;$_.Fill.ForeColor.RGB=$Brown}
    Text $s 'Geometry' 665 115 225 35 28 $true $White 'Aptos' 2 3|ForEach-Object{$_.Fill.Visible=-1;$_.Fill.ForeColor.RGB=$Brown}
    for($i=0;$i -lt 3;$i++){$y=170+$i*85;Text $s $rows[$i][0] 65 $y 420 55 28 $false $Black 'Aptos' 1 3|Out-Null;Text $s $rows[$i][1] 500 $y 150 55 28 $true $Brown 'Aptos' 2 3|Out-Null;Text $s $rows[$i][2] 665 $y 225 55 28 $false $Black 'Aptos' 2 3|Out-Null}

    # 16
    $s=Base $p 'GeoPackage Layers and Parameters - II'
    $rows=@(@('transport_deduplicated.gpkg','61','Point'),@('facilities_deduplicated.gpkg','373','Point'),@('Analysis CRS','EPSG:32643','Metric projection'))
    Text $s 'Layer / Parameter' 65 115 420 35 28 $true $White 'Aptos' 1 3|ForEach-Object{$_.Fill.Visible=-1;$_.Fill.ForeColor.RGB=$Brown}
    Text $s 'Value' 500 115 150 35 28 $true $White 'Aptos' 2 3|ForEach-Object{$_.Fill.Visible=-1;$_.Fill.ForeColor.RGB=$Brown}
    Text $s 'Type' 665 115 225 35 28 $true $White 'Aptos' 2 3|ForEach-Object{$_.Fill.Visible=-1;$_.Fill.ForeColor.RGB=$Brown}
    for($i=0;$i -lt 3;$i++){$y=170+$i*85;Text $s $rows[$i][0] 65 $y 420 55 28 $false $Black 'Aptos' 1 3|Out-Null;Text $s $rows[$i][1] 500 $y 150 55 28 $true $Brown 'Aptos' 2 3|Out-Null;Text $s $rows[$i][2] 665 $y 225 55 28 $false $Black 'Aptos' 2 3|Out-Null}

    # 17
    $s=Base $p 'Data Processing Pipeline'
    $st=@('INGEST','CLEAN','VALIDATE','FEATURES','SERVE')
    $sb=@('NMC + OSM','IDs + CRS','Quality audit','12 features','API + maps')
    for($i=0;$i -lt 5;$i++){$x=30+$i*187;Box $s $x 185 155 120 $(if($i%2){$Pale}else{$PaleBrown}) $(if($i%2){$Olive}else{$Brown2}) 5|Out-Null;Text $s $st[$i] ($x+5) 198 145 34 28 $true $Brown 'Times New Roman' 2 3|Out-Null;Text $s $sb[$i] ($x+6) 249 143 40 28 $false $Black 'Aptos' 2 3|Out-Null;if($i -lt 4){Arrow $s ($x+155) 245 ($x+181) 245|Out-Null}}
    Text $s 'Invalid geometry: 0  |  Ready for feature engineering: Yes' 70 370 820 44 30 $true $Olive 'Times New Roman' 2 3|Out-Null

    # 18
    TwoPics $p 'Data Transformation - Before and After' (Join-Path $media 'image12.png') (Join-Path $media 'image13.png') 'Before: raw registry' 'After: structured analytical table'|Out-Null

    # 19
    $s=Base $p 'K-Means Environmental Profiling'
    Bullets $s @('Input: 258 usable zone references.','Features: 12 scaled environmental variables.','Model selection compared candidate K values.','Selected K = 2 with five-seed stability testing.','Purpose: descriptive typology, not suitability prediction.') 75 112 820 360 28|Out-Null

    # 20
    TwoPics $p 'K-Means - Before and After' (Join-Path $root 'research-paper\figures\kmeans_before.png') (Join-Path $root 'research-paper\figures\kmeans_after.png') 'Before clustering' 'After environmental profiling'|Out-Null

    # 21
    $s=Base $p 'K-Means Evaluation Parameters'
    MetricRow $s @(@('0.3406','Silhouette'),@('1.4645','Davies-Bouldin'),@('102.8891','Calinski-Harabasz')) 135
    Text $s 'Cluster sizes: 83 and 175  |  ARI across five seeds: 1.0000' 70 355 820 55 30 $true $Brown 'Times New Roman' 2 3|Out-Null
    Text $s 'Interpretation: stable environmental groups, not accuracy.' 70 425 820 42 28 $true $Red 'Aptos' 2 3|Out-Null

    # 22
    $s=Base $p 'MCDA Recommendation Method'
    Text $s 'Score(z) = SUM [ weight(i) x normalized factor(i,z) ]' 65 130 830 58 32 $true $Brown 'Times New Roman' 2 3|Out-Null
    Bullets $s @('Eligibility filters are applied before scoring.','Each factor contribution is shown to the user.','Missing values are handled without inventing evidence.','Officer approval is required before allocation.') 85 220 790 245 28|Out-Null

    # 23
    $s=Base $p 'MCDA Parameters and Baseline Weights'
    Bullets $s @('Business compatibility - 25%','Commercial activity - 20%','Access - 20%','Facilities - 15%','Vendor preference - 10%','Historical evidence - 10%') 120 105 720 370 28|Out-Null

    $s=Base $p 'Ranking Eligibility Rules'
    Bullets $s @('Zone type must be FREE and analytically scoreable.','Live status and verified capacity must allow a request.','A selected division becomes a strict candidate filter.','The current zone is excluded during relocation.','Only eligible candidates enter MCDA ranking.') 75 112 820 355 28|Out-Null

    $s=Base $p 'Factor Scoring Parameters'
    Text $s 'Counts use diminishing returns' 55 112 410 40 30 $true $Brown 'Times New Roman' 1 3|Out-Null
    Bullets $s @('Commercial POIs scale: 12','Markets scale: 4','Food POIs scale: 8','Historical evidence scale: 50') 55 165 405 270 28|Out-Null
    Text $s 'Distance and access transforms' 505 112 410 40 30 $true $Olive 'Times New Roman' 1 3|Out-Null
    Bullets $s @('Major-road distance scale: 400 m','Bus-access distance scale: 1,000 m','Pedestrian density scale: 5,000','Closer distances receive higher scores') 505 165 405 270 28|Out-Null

    $s=Base $p 'Facility and Historical Parameters'
    Text $s 'Facility count scales' 70 115 380 40 30 $true $Brown 'Times New Roman' 1 3|Out-Null
    Bullets $s @('Healthcare: 15','Education: 6','Public toilets: 3','Parking: 4') 70 165 350 260 28|Out-Null
    Text $s 'Historical evidence controls' 500 115 400 40 30 $true $Olive 'Times New Roman' 1 3|Out-Null
    Bullets $s @('Business-share shrinkage strength: 20','Evidence-count saturation scale: 50','Small samples move toward the citywide share','Historical evidence does not represent profit or footfall') 500 165 405 280 28|Out-Null

    $s=Base $p 'Vendor Preference Personalization'
    Text $s '40%' 80 130 180 60 40 $true $Brown 'Times New Roman' 2 3|Out-Null
    Text $s 'Baseline policy' 70 195 200 40 28 $true $Black 'Aptos' 2 3|Out-Null
    Text $s '60%' 385 130 180 60 40 $true $Olive 'Times New Roman' 2 3|Out-Null
    Text $s 'Preference distribution' 345 195 260 40 28 $true $Black 'Aptos' 2 3|Out-Null
    Text $s '3x' 700 130 150 60 40 $true $Red 'Times New Roman' 2 3|Out-Null
    Text $s 'Selected priority multiplier' 645 195 260 60 28 $true $Black 'Aptos' 2 3|Out-Null
    Bullets $s @('A selected priority multiplies commercial, access or facilities by 3x.','Final weights blend 40% baseline with 60% preference distribution.','A fixed division removes preference from scoring and redistributes its weight.') 70 285 825 180 28|Out-Null

    $s=Base $p 'Preference-Adjusted Weight Example'
    Text $s 'Balanced profile with market, transport and parking selected' 65 112 830 44 30 $true $Brown 'Times New Roman' 2 3|Out-Null
    Bullets $s @('Business compatibility - 18.4%','Commercial activity - 27.0%','Access - 27.0%','Facilities - 20.2%','Vendor preference - 0.0% after strict division filtering','Historical evidence - 7.4%') 130 175 700 285 28|Out-Null

    $s=Base $p 'Final Score and Rank Order'
    Text $s 'Score = 100 x weighted available-factor sum / available weight' 55 120 850 55 30 $true $Brown 'Times New Roman' 2 3|Out-Null
    Bullets $s @('Each factor is normalized to a value from 0 to 1.','Missing factors are omitted and available weights are renormalized.','Factor contributions add to the final 0-100 score.','Candidates sort by score descending, then zone ID ascending.','The score supports comparison and is not a success probability.') 75 205 820 270 28|Out-Null

    # 24
    $s=Base $p 'Recommendation Sensitivity'
    MetricRow $s @(@('224','Weight scenarios'),@('100%','Top-1 stability'),@('85.57%','Mean top-3 retention')) 140
    Text $s 'Mean rank correlation: 0.9977' 130 355 700 46 30 $true $Brown 'Times New Roman' 2 3|Out-Null
    Text $s 'The interface presents multiple candidates because lower ranks can change.' 70 420 820 52 28 $true $Red 'Aptos' 2 3|Out-Null

    # 25
    $s=Base $p 'End-to-End Recommendation Flow'
    $st=@('ACCESS','RECOMMEND','APPROVE')
    $sb=@('Login + context','Filter + rank + explain','Request + capacity + audit')
    for($i=0;$i -lt 3;$i++){$x=70+$i*300;Box $s $x 175 240 125 $(if($i%2){$Pale}else{$PaleBrown}) $(if($i%2){$Olive}else{$Brown2}) 5|Out-Null;Text $s $st[$i] ($x+8) 190 224 38 28 $true $Brown 'Times New Roman' 2 3|Out-Null;Text $s $sb[$i] ($x+10) 240 220 45 28 $false $Black 'Aptos' 2 3|Out-Null;if($i -lt 2){Arrow $s ($x+240) 237 ($x+290) 237|Out-Null}}
    Text $s 'Capacity, status and audit are verified again at approval.' 80 360 800 48 30 $true $Red 'Times New Roman' 2 3|Out-Null

    TwoPics $p 'WhatsApp Channel - Menu and Current Allocation' $waMenu $waChoose 'Main menu and active allocation' 'Interactive menu selection'|Out-Null

    TwoPics $p 'WhatsApp Channel - Recommendations and Request' $waRecommendations $waRequest 'Top 3 ranked zones' 'Relocation request submission'|Out-Null

    TwoPics $p 'WhatsApp Channel - Language, WHY and MAP' $waLanguage $waExplainMap 'Language and profile preferences' 'Explanation and map reference'|Out-Null

    # Website workflow - real captures from the final report
    TwoPics $p 'Website Access - Bilingual Vendor Login' (Join-Path $websiteDir 'login_english.png') (Join-Path $websiteDir 'login_marathi.png') 'English interface' 'Marathi interface'|Out-Null

    FullScreenshot $p 'Vendor 1 - Dashboard and Entry Point' (Join-Path $websiteDir 'vendor_home1.png')|Out-Null

    FullScreenshot $p 'Vendor 2 - Preference Capture' (Join-Path $websiteDir 'vendor_find_a_place.png')|Out-Null

    FullScreenshot $p 'Vendor 3 - Ranked Recommendations' (Join-Path $websiteDir 'vendor_recommendations.png')|Out-Null

    FullScreenshot $p 'Vendor 4 - Explainable Match Scores' (Join-Path $websiteDir 'vendor_why_this_match.png')|Out-Null

    FullScreenshot $p 'Vendor 5 - Relocation Application' (Join-Path $websiteDir 'vendor_application.png')|Out-Null

    FullScreenshot $p 'Vendor 6 - Allocated Slot Tracking' (Join-Path $websiteDir 'vendor_view_my_slot.png')|Out-Null

    FullScreenshot $p 'Officer 1 - Application Review' (Join-Path $websiteDir 'admin_appliactions_requets.png')|Out-Null

    FullScreenshot $p 'Officer 2 - Vendor Directory' (Join-Path $websiteDir 'admin_login_vendors.png')|Out-Null

    FullScreenshot $p 'Officer 3 - Spatial Slot Creation' (Join-Path $websiteDir 'admin_create slots.png')|Out-Null

    # 30
    $s=Base $p 'Testing and Verified Results'
    MetricRow $s @(@('97 / 97','Focused backend tests'),@('64 / 64','Frontend unit tests'),@('1,690','Build modules')) 130
    Bullets $s @('Role, capacity and relocation workflows verified.','PWA privacy and localization verified.','Pilot slot geometry passed computational checks.') 80 335 800 140 28|Out-Null

    # 31
    $s=Base $p 'COCOMO II - Repository Size'
    MetricRow $s @(@('20.930','Backend KSLOC'),@('5.899','Scripts KSLOC'),@('4.664','Frontend KSLOC')) 135
    Text $s 'Total maintained source size: 31.493 KSLOC' 70 355 820 50 32 $true $Brown 'Times New Roman' 2 3|Out-Null
    Text $s 'Tests, generated files and dependencies are excluded.' 70 420 820 44 28 $false $Grey 'Aptos' 2 3|Out-Null

    # 32
    $s=Base $p 'COCOMO II - Effort and Schedule'
    MetricRow $s @(@('177.37 PM','Professional effort'),@('19.35 months','Estimated schedule'),@('9.17 FTE','Average team')) 125
    Text $s 'PM = 2.94 x 31.493^1.1153 x 1.287' 90 335 780 50 30 $true $Olive 'Times New Roman' 2 3|Out-Null
    Text $s 'Planning estimate only; not recorded student expenditure.' 75 415 810 48 28 $true $Red 'Aptos' 2 3|Out-Null

    # 33
    TwoCols $p 'Deployment and Limitations' 'Deployment' @('Vite production client','FastAPI service','SQLite / PostgreSQL','HTTPS and secrets') 'Limitations' @('Reference points only','No verified outcome labels','Field survey required','Provider validation pending')|Out-Null

    # 34
    TwoCols $p 'Future Scope and Conclusion' 'Future Scope' @('Authoritative polygons','Field-verified capacity','Operational monitoring','Accessibility testing') 'Conclusion' @('Traceable GIS evidence','Explainable ranking','Controlled allocation','Auditable workflow')|Out-Null

    # 35
    $s=Base $p 'References'
    Bullets $s @('VendorMap Project Report and current codebase.','NMC municipal zone and vendor records.','OpenStreetMap GIS layers and prepared GeoPackages.','K-Means metrics and MCDA sensitivity artifacts.','Automated test suites and captured application screens.') 75 115 820 350 28|Out-Null

    # 36
    $s=Base $p 'Questions and Discussion'
    Text $s 'Thank You' 160 170 640 80 44 $true $Brown 'Times New Roman' 2 3|Out-Null
    Text $s 'VendorMap - Project Final Examination' 150 270 660 52 30 $true $Red 'Times New Roman' 2 3|Out-Null

    if(Test-Path $OutputPptx){Remove-Item -LiteralPath $OutputPptx -Force};if(Test-Path $OutputPdf){Remove-Item -LiteralPath $OutputPdf -Force}
    $p.SaveAs($OutputPptx,24);$p.SaveAs($OutputPdf,32)
}
finally{
    if($p){$p.Close()};if($pp){$pp.Quit()};if($p){[Runtime.InteropServices.Marshal]::ReleaseComObject($p)|Out-Null};if($pp){[Runtime.InteropServices.Marshal]::ReleaseComObject($pp)|Out-Null};[GC]::Collect();[GC]::WaitForPendingFinalizers()
}
