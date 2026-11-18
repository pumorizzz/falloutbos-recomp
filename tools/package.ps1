# The Steam Deck kit: a clean folder that runs by itself once fobos.exe is
# added to Steam as a non-Steam game (Proton) -- no launcher, no variables.
#
#   powershell -ExecutionPolicy Bypass -File tools\package.ps1 [-Out dist\fbos-deck]
#       [-Build build-dist] [-Scale 1|2] [-Lang ru|en] [-WithSaves] [-Pdb]
#       [-DryRun] [-Force]
#
# The folder:
#   fobos.exe            built with -DFBOS_STATIC_CRT=ON in its own build tree
#                        (-Build, default build-dist): the C runtime linked in,
#                        d3dcompiler_47 and Media Foundation loaded on first use
#   fobos.ini            tools\deck\fobos.ini (1280x800 16:10, GPU, MSAA 2x,
#                        frame skip auto; -Scale sets the internal resolution)
#   README-SteamDeck.txt tools\deck\README-SteamDeck.txt
#   game\                a copy of your game\ (the junction followed), in the
#                        language of -Lang: ru (the default) runs
#                        tools\russian.py apply on the COPY -- text, fonts, XBE
#                        strings and the movie subtitles; your game\ is never
#                        written. en puts the English text and XBE back in the
#                        copy where a Russian set is in place.
#   saves\               empty, or with -WithSaves your saves: only what the game
#                        reads back ($SaveDirs: UDATA\49500008 -- the saves and
#                        settings.dat -- and TDATA\49500008); not the HDD
#                        images Partition*.img (sparse here, 5 GB copied; the
#                        game makes them itself) nor pad recordings
#   fobos.pdb            with -Pdb (for FBOS_PROFILE on the Deck)
# Then the exe's imports, the folder's size and the exe's SHA-256.
#
# This is a personal copy of your own game data for your own device: nothing
# is uploaded, and dist\ is not in git (.gitignore). -DryRun checks and says
# what it would do, writing nothing.

param(
    [string]$Out = 'dist\fbos-deck',
    [string]$Build = 'build-dist',
    [ValidateSet(1, 2)][int]$Scale = 1,
    [ValidateSet('ru', 'en')][string]$Lang = 'ru',
    [switch]$WithSaves,
    [switch]$Pdb,
    [switch]$DryRun,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
function Abs($p) { if ([IO.Path]::IsPathRooted($p)) { $p } else { Join-Path $Root $p } }
$Out = Abs $Out
$Build = Abs $Build
$Game = Join-Path $Root 'game'
$Exe = Join-Path $Build 'dist-bin\fobos.exe'
$Deck = Join-Path $PSScriptRoot 'deck'
# -WithSaves: the folders of saves\ the game reads a save back from, a whitelist.
# UDATA\<title id> holds the saves (one folder each: fobos.sav, fobos.hdr,
# SaveMeta.xbx), settings.dat and the title's images; TDATA\<title id> its title
# data. Everything else in saves\ is the runtime's own (Partition*.img, made at
# start) or development (pad recordings).
$SaveDirs = @('UDATA\49500008', 'TDATA\49500008')

function Say($m) { Write-Host $m }
function Fail($m) { Write-Host "package: $m" -ForegroundColor Red; exit 1 }

# ---- the exe's imports, read from the PE headers ---------------------------
function Get-PeImports([string]$Path) {
    $b = [IO.File]::ReadAllBytes($Path)
    $pe = [BitConverter]::ToInt32($b, 0x3C)
    $nsec = [BitConverter]::ToUInt16($b, $pe + 6)
    $optSize = [BitConverter]::ToUInt16($b, $pe + 20)
    $opt = $pe + 24
    $magic = [BitConverter]::ToUInt16($b, $opt)
    $dd = $opt + $(if ($magic -eq 0x20B) { 112 } else { 96 })
    $sec = $opt + $optSize
    $secs = for ($i = 0; $i -lt $nsec; $i++) {
        $s = $sec + 40 * $i
        [pscustomobject]@{ Va = [BitConverter]::ToUInt32($b, $s + 12)
                           Size = [Math]::Max([BitConverter]::ToUInt32($b, $s + 8),
                                              [BitConverter]::ToUInt32($b, $s + 16))
                           Raw = [BitConverter]::ToUInt32($b, $s + 20) }
    }
    function Off([uint32]$rva) {
        foreach ($s in $secs) {
            if ($rva -ge $s.Va -and $rva -lt $s.Va + $s.Size) { return [int]($rva - $s.Va + $s.Raw) }
        }
        return -1
    }
    function Name([uint32]$rva) {
        $o = Off $rva
        if ($o -lt 0) { return '?' }
        $e = $o
        while ($b[$e] -ne 0) { $e++ }
        [Text.Encoding]::ASCII.GetString($b, $o, $e - $o)
    }
    $normal = @(); $delay = @()
    $imp = [BitConverter]::ToUInt32($b, $dd + 8)          # IMAGE_DIRECTORY_ENTRY_IMPORT
    if ($imp) {
        $o = Off $imp
        while ($o -ge 0) {
            $nameRva = [BitConverter]::ToUInt32($b, $o + 12)
            if (-not $nameRva) { break }
            $normal += Name $nameRva
            $o += 20
        }
    }
    $dl = [BitConverter]::ToUInt32($b, $dd + 13 * 8)      # IMAGE_DIRECTORY_ENTRY_DELAY_IMPORT
    if ($dl) {
        $o = Off $dl
        while ($o -ge 0) {
            $nameRva = [BitConverter]::ToUInt32($b, $o + 4)
            if (-not $nameRva) { break }
            $delay += Name $nameRva
            $o += 32
        }
    }
    [pscustomobject]@{ Normal = $normal; Delay = $delay }
}

function Show-Imports([string]$Path) {
    $i = Get-PeImports $Path
    Say ("  imports:       " + ($i.Normal -join ', '))
    Say ("  delay-loaded:  " + $(if ($i.Delay) { $i.Delay -join ', ' } else { '(none)' }))
    $crt = @($i.Normal | Where-Object { $_ -match '^(vcruntime|msvcp|api-ms-win-crt|ucrtbase)' })
    $eager = @($i.Normal | Where-Object { $_ -match '^(d3dcompiler|mfplat|mfreadwrite|mf\.dll)' })
    if ($crt) { Say "  WARNING: needs the C runtime installed: $($crt -join ', ')" }
    if ($eager) { Say "  WARNING: loaded at start, not on first use: $($eager -join ', ')" }
    return (-not $crt -and -not $eager)
}

# ---- checks ------------------------------------------------------------------
if (-not (Test-Path (Join-Path $Game 'default.xbe'))) { Fail "no $Game\default.xbe: unpack your disc first (Setup.cmd)" }
$full = [IO.Path]::GetFullPath($Out).TrimEnd('\') + '\'
foreach ($p in @($Game, (Join-Path $Root 'saves'), (Join-Path $Root 'bin'))) {
    $pf = [IO.Path]::GetFullPath($p).TrimEnd('\') + '\'
    if ($full.StartsWith($pf, [StringComparison]::OrdinalIgnoreCase)) { Fail "-Out must not be inside $p" }
}
$gameItem = Get-Item $Game -Force
$gameSrc = if ($gameItem.LinkType -eq 'Junction' -or $gameItem.LinkType -eq 'SymbolicLink') { @($gameItem.Target)[0] } else { $Game }
# Never anywhere the copy's russian.py apply could reach your own game\: not
# around game\ or its junction's target, not inside the target, and not where
# <Out>\game already leads somewhere else. -Force does not lift these.
function Under([string]$a, [string]$b) {      # $a is $b or inside it
    $fa = [IO.Path]::GetFullPath($a).TrimEnd('\') + '\'
    $fb = [IO.Path]::GetFullPath($b).TrimEnd('\') + '\'
    return $fa.StartsWith($fb, [StringComparison]::OrdinalIgnoreCase)
}
foreach ($g in @($Game, $gameSrc)) {
    if (Under $g $Out) { Fail "-Out $Out holds ${g}; pick a folder of its own (dist\fbos-deck)" }
    if (Under $Out $g) { Fail "-Out must not be inside ${g}" }
}
$outGame = Join-Path $Out 'game'
if (Test-Path $outGame) {
    $og = Get-Item $outGame -Force
    if ($og.LinkType) { Fail "$outGame is a $($og.LinkType) (to $(@($og.Target)[0])); the kit needs a real copy there" }
}
if ((Test-Path $Out) -and (Get-ChildItem $Out -Force | Select-Object -First 1) -and -not $Force) {
    Fail "$Out is not empty; remove it or pass -Force (files are replaced, nothing deleted)"
}
$bytes = (Get-ChildItem $gameSrc -Recurse -File -Force | Measure-Object Length -Sum).Sum
$py = Get-Command py -ErrorAction SilentlyContinue
if ($Lang -eq 'ru' -and -not $py) { Fail 'the Russian kit needs py -3 (tools\russian.py)' }

Say "package: the Steam Deck kit"
Say "  out:           $Out"
Say "  exe:           $Exe (build tree $Build, -DFBOS_STATIC_CRT=ON)"
Say ("  game:          $gameSrc, {0:N2} GB" -f ($bytes / 1GB))
Say "  language:      $Lang$(if ($Lang -eq 'ru') { ' (tools\russian.py apply on the copy: text, fonts, XBE strings, movie subtitles)' })"
Say "  scale:         ${Scale}x, MSAA 2x, 1280x800 16:10, frame skip auto"
Say "  saves:         $(if ($WithSaves) { 'your saves: ' + (($SaveDirs | ForEach-Object { "saves\$_" }) -join ', ') } else { 'empty' })"
Say "  pdb:           $(if ($Pdb) { 'yes' } else { 'no' })"
Say "  A personal copy of your own game data for your own device; nothing is uploaded."

if ($DryRun) {
    if (Test-Path $Exe) {
        Say "  the kit's exe is built ($((Get-Item $Exe).LastWriteTime)):"
        [void](Show-Imports $Exe)
    } else {
        Say "  the kit's exe is not built yet: it would be (cmake -DFBOS_STATIC_CRT=ON, a full build, 10-20 min)"
    }
    Say "package: dry run, nothing written"
    exit 0
}

# ---- the exe -------------------------------------------------------------------
if (-not (Test-Path (Join-Path $Build 'CMakeCache.txt'))) {
    Say "--> configure $Build"
    & cmake -S $Root -B $Build -A x64 "-DXBOXRECOMP_DIR=deps/xboxrecomp" -DFBOS_STATIC_CRT=ON
    if ($LASTEXITCODE) { Fail "cmake configure failed ($LASTEXITCODE)" }
}
Say "--> build fobos.exe in $Build"
& cmake --build $Build --config Release --target fbos --parallel
if ($LASTEXITCODE) { Fail "the build failed ($LASTEXITCODE)" }
if (-not (Test-Path $Exe)) { Fail "no $Exe after the build" }

# ---- the folder --------------------------------------------------------------
New-Item -ItemType Directory -Force $Out | Out-Null
Copy-Item $Exe (Join-Path $Out 'fobos.exe') -Force
if ($Pdb) { Copy-Item (Join-Path $Build 'dist-bin\fobos.pdb') (Join-Path $Out 'fobos.pdb') -Force }
$ini = (Get-Content (Join-Path $Deck 'fobos.ini')) -replace '^RECOMP_GPU_RASTER_SCALE=.*$', "RECOMP_GPU_RASTER_SCALE=$Scale"
Set-Content (Join-Path $Out 'fobos.ini') $ini -Encoding ascii
Copy-Item (Join-Path $Deck 'README-SteamDeck.txt') (Join-Path $Out 'README-SteamDeck.txt') -Force

Say "--> copy game\ ($('{0:N2}' -f ($bytes / 1GB)) GB)"
# The junction's target as the source: robocopy copies what is in it; /XJ skips
# any junction further down.
& robocopy $gameSrc (Join-Path $Out 'game') /E /XJ /R:1 /W:1 /NFL /NDL /NP /NJH | Out-Host
if ($LASTEXITCODE -ge 8) { Fail "robocopy of game\ failed ($LASTEXITCODE)" }

$resx = Join-Path $Out 'game\resx'
if ($Lang -eq 'ru') {
    Say "--> Russian in the copy (tools\russian.py apply $resx)"
    & py -3 (Join-Path $Root 'tools\russian.py') apply $resx
    if ($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne 3) { Fail "russian.py apply failed ($LASTEXITCODE)" }
} else {
    # As the launcher's English (launcher.c set_language): the .en set in place
    # of the three text files and of every level's own names, and of
    # default.xbe only the bytes where its .en and .ru differ (the strings) --
    # the rest of the XBE stays as it is.
    foreach ($n in 'gtext.sdb', 'global.sdb', 'deftexte.sdb') {
        $en = Join-Path $resx "$n.en"
        if (Test-Path $en) { Copy-Item $en (Join-Path $resx $n) -Force }
    }
    foreach ($c in Get-ChildItem $resx -Directory -Filter 'c?') {
        foreach ($l in Get-ChildItem $c.FullName -Directory) {
            $sdb = Join-Path $l.FullName "$($l.Name).sdb"
            if (Test-Path "$sdb.en") { Copy-Item "$sdb.en" $sdb -Force }
        }
    }
    $xbe = Join-Path $Out 'game\default.xbe'
    if ((Test-Path "$xbe.en") -and (Test-Path "$xbe.ru")) {
        $cur = [IO.File]::ReadAllBytes($xbe)
        $en = [IO.File]::ReadAllBytes("$xbe.en")
        $ru = [IO.File]::ReadAllBytes("$xbe.ru")
        if ($cur.Length -ne $en.Length -or $en.Length -ne $ru.Length) {
            Fail "game\default.xbe is not the image its .en/.ru set was made from"
        }
        $changed = 0
        for ($i = 0; $i -lt $cur.Length; $i++) {
            if ($en[$i] -ne $ru[$i] -and $cur[$i] -ne $en[$i]) {
                if ($cur[$i] -ne $ru[$i]) { Fail "game\default.xbe's strings are neither the English nor the Russian ones" }
                $cur[$i] = $en[$i]; $changed++
            }
        }
        if ($changed) { [IO.File]::WriteAllBytes($xbe, $cur) }
        Say "  default.xbe: $changed bytes of the strings back to English"
    }
}
if ($py) {
    Say "--> the copy's language"
    & py -3 (Join-Path $Root 'tools\russian.py') status $resx
}

$saves = Join-Path $Out 'saves'
New-Item -ItemType Directory -Force $saves | Out-Null
if ($WithSaves) {
    foreach ($d in $SaveDirs) {
        $src = Join-Path (Join-Path $Root 'saves') $d
        if (-not (Test-Path $src)) { continue }
        Say "--> copy saves\$d"
        & robocopy $src (Join-Path $saves $d) /E /XJ /R:1 /W:1 /NFL /NDL /NP /NJH | Out-Host
        if ($LASTEXITCODE -ge 8) { Fail "robocopy of saves\$d failed ($LASTEXITCODE)" }
    }
}

# ---- what came out -----------------------------------------------------------
$kitExe = Join-Path $Out 'fobos.exe'
$total = (Get-ChildItem $Out -Recurse -File -Force | Measure-Object Length -Sum).Sum
Say ""
Say "package: $Out"
$clean = Show-Imports $kitExe
Say ("  size:          {0:N2} GB" -f ($total / 1GB))
Say "  fobos.exe SHA-256: $((Get-FileHash $kitExe -Algorithm SHA256).Hash)"
Say "  Next: copy the folder to the Deck (~/Games/fbos-deck/) and follow README-SteamDeck.txt."
Say "  It is a personal copy of your own game data: keep it to your own device."
if (-not $clean) { exit 2 }
exit 0
