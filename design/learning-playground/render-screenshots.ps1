Add-Type -AssemblyName System.Drawing
$repo = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$script:bitmap = $null
$script:graphics = $null

function To-Color([string]$hex) { [Drawing.ColorTranslator]::FromHtml($hex) }
function Start-Canvas([string]$background) {
  $script:bitmap = [Drawing.Bitmap]::new(1440,1000)
  $script:graphics = [Drawing.Graphics]::FromImage($script:bitmap)
  $script:graphics.SmoothingMode = [Drawing.Drawing2D.SmoothingMode]::AntiAlias
  $script:graphics.TextRenderingHint = [Drawing.Text.TextRenderingHint]::ClearTypeGridFit
  $script:graphics.Clear((To-Color $background))
}
function Box([int]$x,[int]$y,[int]$w,[int]$h,[string]$fill,[int]$radius=0,[string]$border='') {
  $brush = [Drawing.SolidBrush]::new((To-Color $fill))
  if ($radius -le 0) { $script:graphics.FillRectangle($brush,$x,$y,$w,$h) }
  else {
    $path = [Drawing.Drawing2D.GraphicsPath]::new()
    $d = $radius * 2
    $path.AddArc($x,$y,$d,$d,180,90); $path.AddArc($x+$w-$d,$y,$d,$d,270,90)
    $path.AddArc($x+$w-$d,$y+$h-$d,$d,$d,0,90); $path.AddArc($x,$y+$h-$d,$d,$d,90,90)
    $path.CloseFigure(); $script:graphics.FillPath($brush,$path)
    if ($border) { $pen=[Drawing.Pen]::new((To-Color $border),1); $script:graphics.DrawPath($pen,$path); $pen.Dispose() }
    $path.Dispose()
  }
  $brush.Dispose()
}
function Rule([int]$x1,[int]$y1,[int]$x2,[int]$y2,[string]$color,[float]$width=1) {
  $pen=[Drawing.Pen]::new((To-Color $color),$width); $script:graphics.DrawLine($pen,$x1,$y1,$x2,$y2); $pen.Dispose()
}
function Txt([string]$value,[int]$x,[int]$y,[float]$size,[string]$color,[string]$weight='normal',[string]$face='sans') {
  $family=if($face -eq 'mono'){'Consolas'}else{'Segoe UI'}
  $style=if($weight -eq 'bold'){[Drawing.FontStyle]::Bold}else{[Drawing.FontStyle]::Regular}
  $font=[Drawing.Font]::new($family,$size,$style,[Drawing.GraphicsUnit]::Pixel)
  $brush=[Drawing.SolidBrush]::new((To-Color $color))
  $script:graphics.DrawString($value,$font,$brush,[float]$x,[float]$y)
  $font.Dispose();$brush.Dispose()
}
function Btn([int]$x,[int]$y,[int]$w,[int]$h,[string]$label,[string]$fill,[string]$ink,[string]$border='') {
  Box $x $y $w $h $fill 8 $border
  Txt $label ($x+12) ($y+([int](($h-13)/2))) 12 $ink bold
}
function ChapterRail([string]$style) {
  $rail='#FFFFFF';$line='#E8EBE6';$ink='#26332E';$muted='#7A8580';$accent='#26745A';$active='#E8F3ED';$quiet='#606D66'
  if($style -eq 'studio'){$rail='#141A22';$line='#29313B';$ink='#DDE5EC';$muted='#8D99A7';$accent='#70D1A1';$active='#20352F';$quiet='#A5B0BC'}
  if($style -eq 'guided'){$rail='#FFFDFA';$line='#EEE5D9';$ink='#3C3730';$muted='#8C8174';$accent='#A85E40';$active='#F6E9DD';$quiet='#776E62'}
  Box 0 0 238 1000 $rail
  Rule 237 0 237 1000 $line
  Box 23 24 28 28 $accent 8
  Txt 'p' 32 26 20 '#FFFFFF' bold
  Txt 'postgres' 61 26 16 $ink bold
  Txt 'lab' 133 26 16 $muted
  Txt $(if($style -eq 'studio'){'COURSE MAP'}else{'YOUR COURSE'}) 25 84 10 $muted bold
  Box 194 79 23 20 $(if($style -eq 'studio'){'#222A33'}elseif($style -eq 'guided'){'#F7F0E7'}else{'#F1F3F0'}) 6
  Txt '11' 200 81 10 $muted
  $labels=@('Start here','Room to PostgreSQL','Tables, rows & types','Finding data','Changing data','Joins','Aggregates','Indexes & EXPLAIN','Transactions & concurrency','FastAPI + Postgres','Event-driven thinking')
  for($i=0;$i -lt $labels.Count;$i++){
    $y=116+$i*39;$current=$i -eq 8;$done=$i -lt 8
    if($current){Box 12 ($y-3) 214 36 $active 8}
    $badge=if($done){$accent}elseif($current){$accent}else{$muted}
    $badgefill=if($done){if($style -eq 'studio'){'#213A31'}elseif($style -eq 'guided'){'#EDF2E8'}else{'#E8F3ED'}}elseif($current){$accent}else{if($style -eq 'studio'){'#252D36'}else{'#F1F3F0'}}
    Box 23 $y 18 18 $badgefill 9
    Txt $(if($done){'✓'}elseif($current){'•'}else{('{0:D2}' -f ($i+1))}) 27 ($y+2) 9 $(if($current -and $style -eq 'studio'){'#10251A'}elseif($current){'#FFFFFF'}else{$badge}) bold
    Txt ('{0:D2}' -f $i) 49 ($y+2) 9 $muted
    Txt $labels[$i] 73 ($y+1) 10 $(if($current){$accent}elseif($done){$quiet}else{$muted}) $(if($current){'bold'}else{'normal'})
  }
  if($style -eq 'studio'){
    Rule 18 570 220 570 $line
    Txt 'COURSE PROGRESS' 25 589 9 $muted bold
    Txt '8' 25 609 17 $ink bold;Txt '/ 11 lessons' 40 613 10 $muted
    Box 25 638 187 5 '#2C343D' 3;Box 25 638 136 5 $accent 3
    Txt 'Chapter 08 of 11' 25 653 9 $muted
  }
  if($style -eq 'guided'){
    Box 17 584 204 58 '#FFFAF3' 9 '#F0E6D9'
    Txt '+' 28 596 15 '#B27B4C' bold
    Txt 'Eight chapters down.' 50 592 10 '#8D7F70'
    Txt 'You are finding your flow.' 50 610 10 '#655849' bold
  }
  Rule 18 943 220 943 $line
  Box 23 957 28 28 $(if($style -eq 'studio'){'#344D42'}elseif($style -eq 'guided'){'#E5D7C4'}else{'#E5D7C4'}) 14
  Txt 'S' 32 962 12 $(if($style -eq 'studio'){'#B6E9CC'}else{'#725F4C'}) bold
  Txt 'Sam learning space' 60 958 10 $ink bold
  Txt $(if($style -eq 'studio'){'Local progress'}else{'Progress saved on this device'}) 60 975 9 $muted
}
function Header([string]$style) {
  $line='#E8EBE6';$paper='#FFFFFF';$ink='#26332E';$muted='#7A8580';$accent='#25362E';$button='#FFFFFF';$buttonline=$line
  if($style -eq 'studio'){$line='#29313B';$paper='#151B23';$ink='#DDE5EC';$muted='#8D99A7';$accent='#23794F';$button='#1D242D';$buttonline='#303A44'}
  if($style -eq 'guided'){$line='#EEE5D9';$paper='#FFFDFA';$ink='#3C3730';$muted='#8C8174';$accent='#3D4B3E'}
  Box 238 0 1202 65 $paper
  Rule 238 64 1440 64 $line
  Txt $(if($style -eq 'studio'){'●  Playground'}elseif($style -eq 'guided'){'Learning path'}else{'Postgres foundations'}) 270 25 11 $muted
  Txt $(if($style -eq 'studio'){'/  08 · Concurrency'}elseif($style -eq 'guided'){'›  Step 9 of 11'}else{'/  Chapter 08'}) 370 25 11 $ink bold
  Txt '●  4 day streak' 930 27 10 $muted
  Btn 1050 15 $(if($style -eq 'guided'){137}else{125}) 34 $(if($style -eq 'guided'){'Save my progress'}elseif($style -eq 'studio'){'Sign in'}else{'Sign in to sync'}) $button $ink $buttonline
  Btn 1186 15 226 34 $(if($style -eq 'guided'){'AI coach settings'}elseif($style -eq 'studio'){'AI settings'}else{'Connect AI coach'}) $accent '#FFFFFF'
}
function Save-Canvas([string]$filename) {
  $path=Join-Path $repo ('screenshots/'+$filename)
  $script:bitmap.Save($path,[Drawing.Imaging.ImageFormat]::Png)
  $script:graphics.Dispose();$script:bitmap.Dispose()
}
function Draw-Editorial {
  Start-Canvas '#F8F9F6';ChapterRail 'editorial';Header 'editorial'
  Txt '—  CHAPTER 08  ·  12 MIN' 272 91 10 '#7A8580' bold
  Txt 'When two orders arrive' 272 115 34 '#26332E' bold
  Txt 'at the same time' 272 151 34 '#26332E' bold
  Txt 'Make a stock update that stays correct when two customers order together.' 272 199 14 '#64716A'
  Txt 'S  For Android developers    ·    Concept + practice' 272 227 10 '#7A8580'
  Box 272 253 824 79 '#F0F4EF' 11 '#E5EBE3'
  Box 287 270 32 32 '#FFFFFF' 8;Txt '↗' 296 273 17 '#26745A' bold
  Txt 'Let Postgres do the math.' 332 265 12 '#26332E' bold
  Txt 'Read, subtract, then write can lose an order. Update from the current value in one statement' 332 285 11 '#65736A'
  Txt 'and let the row lock keep both requests in line.' 332 301 11 '#65736A'
  Box 272 349 824 463 '#FFFFFF' 13 '#E8EBE6'
  Txt 'YOUR TURN  ·  PRACTICE' 290 365 9 '#7A8580' bold
  Txt 'Protect the last chai' 290 384 19 '#26332E' bold
  Txt '●  chaipoint · products' 895 377 10 '#7A8580'
  Txt 'Two orders of 2 arrive together. Update Masala chai safely and return the new stock count.' 290 416 11 '#6C7972'
  Box 290 445 788 207 '#F6F8F5' 9 '#EDF0EB'
  Rule 290 476 1078 476 '#E8ECE6'
  Txt '●  ●  ●      exercise.sql' 304 454 9 '#8B958E' mono
  Txt 'SQL' 1038 454 9 '#8B958E' mono
  Txt '1' 307 491 11 '#A7B0A9' mono;Txt 'UPDATE' 341 491 11 '#28745A' mono bold;Txt ' products' 395 491 11 '#3C4C43' mono
  Txt '2' 307 519 11 '#A7B0A9' mono;Txt 'SET' 341 519 11 '#28745A' mono bold;Txt ' stock = stock - 2' 370 519 11 '#3C4C43' mono
  Txt '3' 307 547 11 '#A7B0A9' mono;Txt 'WHERE' 341 547 11 '#28745A' mono bold;Txt ' id = 1 AND stock >= 2' 384 547 11 '#3C4C43' mono
  Txt '4' 307 575 11 '#A7B0A9' mono;Txt 'RETURNING' 341 575 11 '#28745A' mono bold;Txt ' stock;' 414 575 11 '#3C4C43' mono
  Txt '⌘ + ↵ to run' 292 672 9 '#89938C'
  Btn 945 661 133 34 '▶  Run query' '#26745A' '#FFFFFF'
  Rule 290 708 1078 708 '#EEF0ED'
  Txt '✓' 292 722 11 '#47865A' bold;Txt 'Result' 310 722 11 '#48574F' bold;Txt 'Ready to run' 970 722 9 '#87928B' mono
  Box 292 747 784 25 '#F5F7F4' 4;Txt 'stock' 303 752 10 '#7B867F' mono;Txt '200' 392 752 10 '#3C4C43' mono
  Txt 'Start with 200 in stock. Run the guarded update to see the result.' 292 782 9 '#8B948D'
  Txt '●  Up next: Lock a row with FOR UPDATE' 272 838 10 '#77827B'
  Btn 902 823 194 35 'Mark lesson complete  →' '#26745A' '#FFFFFF'
  Box 1120 92 292 100 '#FFFFFF' 12 '#E8EBE6'
  Txt 'YOUR PROGRESS' 1135 107 9 '#7A8580' bold;Txt '8 / 11' 1347 103 15 '#26332E' bold
  Box 1135 132 262 5 '#E9EDE8' 3;Box 1135 132 191 5 '#26745A' 3
  Txt 'You are building real backend intuition.' 1135 146 10 '#77827B'
  Txt 'View your learning path  ↗' 1135 169 9 '#26745A' bold
  Box 1120 207 292 590 '#FFFFFF' 12 '#E8EBE6'
  Box 1136 223 30 30 '#EDF3EE' 9;Txt '✳' 1143 226 16 '#26745A' bold
  Txt 'Your learning coach' 1175 222 11 '#26332E' bold;Txt 'Here when you need a nudge' 1175 239 9 '#7A8580'
  Txt 'What would help you move forward?' 1136 276 10 '#7C8881'
  $items=@(@('01','Give me a nudge','A gentle next step'),@('02','Show me a hint','Point me to the pattern'),@('03','Walk me through it','Solution + why it works'))
  for($i=0;$i -lt 3;$i++){$y=302+$i*59;Rule 1136 $y 1396 $y '#EEF0ED';Box 1138 ($y+13) 22 22 '#F3F5F2' 7;Txt $items[$i][0] 1142 ($y+18) 9 '#8D9891' mono;Txt $items[$i][1] 1169 ($y+11) 10 '#26332E' bold;Txt $items[$i][2] 1169 ($y+29) 9 '#909B94';Txt '›' 1381 ($y+12) 16 '#9AA49D'}
  Box 1136 493 260 68 '#F5F7F3' 8;Txt '✳' 1148 505 13 '#26745A' bold;Txt 'Select a step when you are ready.' 1166 504 9 '#6C7970';Txt 'Getting help is part of learning.' 1166 520 9 '#6C7970'
  Box 1136 576 260 37 '#FFFFFF' 7 '#E7EBE5';Txt '✳  Ask the AI coach' 1148 588 10 '#48564D' bold;Txt '↗' 1375 588 10 '#809087'
  Txt '◇  Hints keep your progress.' 1136 635 9 '#8B968E';Txt 'How AI help works' 1153 651 9 '#26745A'
  Save-Canvas 'editorial-learning-lab.png'
}
function Draw-Studio {
  Start-Canvas '#10151C';ChapterRail 'studio';Header 'studio'
  Txt '—  TRANSACTIONS  /  EXERCISE 2 OF 4' 272 92 10 '#9AA7B4' bold
  Txt 'Keep both orders.' 272 115 33 '#E1E7ED' bold
  Txt 'Write the update once. Let Postgres serialize the row changes.' 272 158 12 '#9AA6B3'
  Txt 'LESSON' 1035 111 9 '#85919E' bold;Txt '8 / 11' 1035 130 19 '#E1E7ED' bold
  Box 272 193 824 79 '#171E26' 10 '#29333C';Box 286 216 31 31 '#27362F' 8;Txt '↯' 295 219 17 '#80D7A7' bold
  Txt 'THE CHALLENGE' 329 203 9 '#8D99A7' bold
  Txt 'ChaiPoint has 200 Masala chai. Asha and Ravi each order 2.' 329 221 11 '#AEB9C4'
  Txt 'Add the stock guard so neither order can oversell.' 329 238 11 '#AEB9C4'
  Box 272 285 824 298 '#151B23' 10 '#2B3540'
  Box 272 285 824 40 '#181F28' 10 '#2B3540'
  Box 272 315 824 10 '#181F28'
  Box 288 293 8 8 '#65BF91' 2;Txt 'stock_update.sql' 305 291 10 '#D4DDE5' mono
  Txt '●  chaipoint / products' 878 293 9 '#8E9BA9' mono
  Txt '1' 297 344 11 '#677583' mono;Txt 'UPDATE' 342 344 12 '#8BCFFF' mono;Txt ' products' 397 344 12 '#D1D9E0' mono
  Txt '2' 297 378 11 '#677583' mono;Txt 'SET' 342 378 12 '#8BCFFF' mono;Txt ' stock = stock - 2' 371 378 12 '#D1D9E0' mono
  Txt '3' 297 412 11 '#677583' mono;Txt 'WHERE' 342 412 12 '#8BCFFF' mono;Txt ' id = 1 AND stock >= 2' 389 412 12 '#D1D9E0' mono
  Txt '4' 297 446 11 '#677583' mono;Txt 'RETURNING' 342 446 12 '#8BCFFF' mono;Txt ' stock;' 418 446 12 '#D1D9E0' mono
  Rule 272 510 1096 510 '#29333D'
  Txt '●  PostgreSQL 16   ·   Read Committed' 289 529 9 '#98A5B2' mono
  Btn 961 519 119 30 '▶  Run   ⌘ ↵' '#45B77C' '#082A1B'
  Box 272 598 824 174 '#151B23' 9 '#29333D'
  Txt '●  Results' 289 612 10 '#DDE5EC' bold;Txt 'Data output' 381 611 9 '#B4BFCA'
  Txt 'Ready · 200 in stock' 928 613 9 '#8493A1' mono
  Rule 272 640 1096 640 '#29333D'
  Box 273 641 822 26 '#1A212A'
  Txt '#' 289 647 9 '#8996A3' mono;Txt 'stock' 333 647 9 '#8996A3' mono
  Rule 272 667 1096 667 '#29333D';Txt '1' 289 675 10 '#C9D3DC' mono;Txt '200' 333 675 10 '#C9D3DC' mono
  Rule 272 706 1096 706 '#29333D';Txt 'Waiting for your query.' 289 721 9 '#8C99A6' mono;Txt '0.00s  ·  1 row' 956 721 9 '#8C99A6' mono
  Txt '●  Up next   Lock a row with SELECT FOR UPDATE' 272 800 9 '#96A3AF'
  Btn 911 789 185 34 'Complete exercise  →' '#42AA77' '#082B1A'
  Box 1115 92 297 680 '#171E26' 11 '#2B3540'
  Box 1130 106 30 30 '#25372F' 9;Txt '✳' 1137 109 16 '#8CE0B1' bold
  Txt 'Coach' 1170 107 11 '#E1E7ED' bold;Txt 'Context-aware guidance' 1170 124 9 '#8D99A7'
  Rule 1130 147 1397 147 '#2B3540'
  Box 1130 161 267 108 '#202831' 7;Box 1130 171 2 86 '#55BC83'
  Txt 'ON THIS EXERCISE' 1142 171 8 '#8FA093' bold
  Txt 'Requests cannot see uncommitted writes' 1142 192 10 '#BDC8D1'
  Txt 'uncommitted change. How do we avoid' 1142 209 10 '#BDC8D1'
  Txt 'writing an old value?' 1142 226 10 '#BDC8D1'
  $items=@(@('01','Nudge','Just a small push'),@('02','Hint','Reveal the pattern'),@('03','Full walkthrough','Code + explanation'))
  for($i=0;$i -lt 3;$i++){$y=281+$i*53;Rule 1130 $y 1397 $y '#29333D';Box 1131 ($y+13) 22 22 '#252D36' 6;Txt $items[$i][0] 1135 ($y+18) 8 '#8D9AA7' mono;Txt $items[$i][1] 1163 ($y+10) 10 '#E1E7ED' bold;Txt $items[$i][2] 1163 ($y+27) 9 '#8D99A7';Txt '→' 1380 ($y+14) 11 '#8695A2'}
  Box 1130 459 267 80 '#202831' 8;Txt '✳' 1142 470 13 '#7BD3A1' bold;Txt 'Try a nudge, or ask for the' 1161 469 9 '#B0BDC8';Txt 'full walkthrough when ready.' 1161 485 9 '#B0BDC8'
  Btn 1130 552 267 36 '✳  Ask AI coach   ↗' '#202B29' '#C4EBD4' '#33413C'
  Txt 'AI help is optional. Your SQL stays in this demo.' 1130 603 8 '#82909C'
  Save-Canvas 'developer-studio.png'
}
function Draw-Guided {
  Start-Canvas '#FAF6EF';ChapterRail 'guided';Header 'guided'
  Box 290 91 1020 5 '#EDE4D7' 3;Box 290 91 690 5 '#9AAD87' 3;Box 980 91 52 5 '#B97550' 3
  Txt 'Build your foundation' 290 103 9 '#9A8E7E';Txt 'Make it reliable' 740 103 9 '#9B6248' bold;Txt 'Go event-driven' 1220 103 9 '#9A8E7E'
  Box 280 132 795 686 '#FFFDFA' 15 '#EEE4D7'
  Txt 'YOUR NEXT STEP' 305 154 9 '#9A826D' bold;Txt '~ 12 MIN' 1003 154 9 '#9A826D' bold
  Txt 'Make every order count.' 305 178 34 '#3C3730' bold
  Txt 'Asha and Ravi order chai at the same moment. Help ChaiPoint' 305 225 12 '#786E62'
  Txt 'keep stock accurate.' 305 244 12 '#786E62'
  Box 305 275 744 69 '#F8F1E6' 9
  Box 319 292 25 25 '#FFFAF1' 7;Txt '01' 324 299 9 '#AA754F' mono
  Txt 'One statement. One current value.' 355 288 11 '#55493C' bold
  Txt 'Let the database subtract from the latest stock value. A guard keeps it from going below zero.' 355 309 10 '#7E7162'
  Box 305 364 744 452 '#FFFFFF' 11 '#EFE8DF'
  Txt '2 of 3   ·   TRY IT' 322 380 9 '#A06F4E' bold
  Txt '●  Ready to practice' 906 380 9 '#8C8174'
  Txt 'Can you protect the last chai?' 322 410 16 '#3C3730' bold
  Txt 'Reduce Masala chai by 2. Only update it when at least 2 are still in stock.' 322 437 10 '#81776B'
  Box 322 468 710 204 '#FAF9F5' 8 '#ECE8DF'
  Rule 322 498 1032 498 '#ECE8DF';Txt 'your-query.sql' 336 477 9 '#8B958E' mono;Txt 'SQL' 995 477 9 '#8B958E' mono
  Txt '1' 339 511 10 '#A7B0A9' mono;Txt 'UPDATE' 368 511 10 '#A65F42' mono bold;Txt ' products' 423 511 10 '#3C4C43' mono
  Txt '2' 339 539 10 '#A7B0A9' mono;Txt 'SET' 368 539 10 '#A65F42' mono bold;Txt ' stock = stock - 2' 394 539 10 '#3C4C43' mono
  Txt '3' 339 567 10 '#A7B0A9' mono;Txt 'WHERE' 368 567 10 '#A65F42' mono bold;Txt ' id = 1 AND stock >= 2' 409 567 10 '#3C4C43' mono
  Txt '4' 339 595 10 '#A7B0A9' mono;Txt 'RETURNING' 368 595 10 '#A65F42' mono bold;Txt ' stock;' 434 595 10 '#3C4C43' mono
  Box 322 690 710 54 '#F7F7F1' 7
  Box 334 706 17 17 '#E8F3EB' 9;Txt '✓' 338 707 9 '#47865A' bold
  Txt 'Ready when you are' 362 696 9 '#56614F' bold;Txt 'Masala chai starts with 200 in stock.' 362 714 8 '#8A8C7D'
  Btn 926 702 94 30 'Run it  →' '#A85E40' '#FFFFFF'
  Txt 'Need a hand? Your coach has three gentle steps.' 305 778 9 '#918575'
  Btn 850 769 182 34 'I have it  →' '#A85E40' '#FFFFFF'
  Box 1098 132 314 388 '#FFFDFA' 13 '#EEE4D7'
  Box 1114 148 30 30 '#F7EBDF' 9;Txt '✳' 1121 151 16 '#A95E3F' bold
  Txt 'Need a little help?' 1154 149 11 '#3C3730' bold;Txt 'Choose what feels right' 1154 166 9 '#8C8174'
  $items=@(@('1','A nudge','Point me in a direction'),@('2','A helpful hint','Give me the pattern'),@('3','Show me how','Full solution + why'))
  for($i=0;$i -lt 3;$i++){$y=198+$i*59;Rule 1114 $y 1396 $y '#F0E8DF';Box 1116 ($y+16) 23 23 '#FFF7EE' 12 '#EADFD2';Txt $items[$i][0] 1125 ($y+21) 9 '#A57856' mono;Txt $items[$i][1] 1152 ($y+10) 10 '#3C3730' bold;Txt $items[$i][2] 1152 ($y+28) 9 '#8C8174';Txt '›' 1380 ($y+14) 16 '#AF9C86'}
  Box 1114 386 282 62 '#FAF3E9' 8;Txt '✳' 1125 398 13 '#A96849' bold;Txt 'There is no penalty for asking.' 1145 396 9 '#806F5A';Txt 'We will keep your place while you learn.' 1145 413 8 '#806F5A'
  Btn 1114 462 282 35 'Ask AI coach   ↗' '#F4E8DC' '#925438'
  Box 1098 535 314 95 '#F8F1E6' 10
  Txt 'YOUR MOMENTUM' 1115 550 9 '#A27A5B' bold
  Txt '8 of 11 complete' 1115 568 15 '#574D41' bold
  Box 1115 594 277 5 '#E9DECE' 3;Box 1115 594 201 5 '#A85E40' 3
  Txt 'You are building a reliable foundation.' 1115 605 9 '#8D7F70'
  Save-Canvas 'guided-learning-path.png'
}

New-Item -ItemType Directory -Force -Path (Join-Path $repo 'screenshots') | Out-Null
Draw-Editorial
Draw-Studio
Draw-Guided
Get-ChildItem (Join-Path $repo 'screenshots') -Filter '*.png' | Select-Object FullName,Length
