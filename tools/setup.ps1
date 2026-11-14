# Quick start for falloutbos-recomp: from a plain download to a playable build.
# Run by Setup.cmd. Every step below is the same command README's
# "Step by step" documents, so the two routes cannot drift apart.
#
# - Checks prerequisites and ASKS before installing anything (winget).
# - Asks for your own disc image, finding it first when it can.
# - Skips steps already done, so a rerun after a failure resumes.
# - On failure, one sentence on what to do; details in setup.log.
#
# Nothing here downloads or bundles game data: you supply the disc.

$ErrorActionPreference = 'Stop'
$Root    = Split-Path -Parent $PSScriptRoot
$Log     = Join-Path $Root 'setup.log'
$Toolkit = Join-Path $Root 'deps\xboxrecomp'
# The toolkit fork and branch with this port's fixes: work/falloutbos plus the
# D3D11 back end and the movsx lifter fix (Bink blocks), none of them upstream.
$ToolkitUrl = 'https://github.com/pumorizzz/xboxrecomp'
$ToolkitRef = 'gpu-rastr'
# Tips the branch once had before its history was rewritten (e458191 did not
# build). A clean checkout on one of them has nothing of its own to lose.
$ToolkitRewritten = @(
    'e458191d6492d7e5449646155c8378dd7773b5e9',
    '539403e6e7243a52e36e0c8b90f029d3b3c4e71e',
    'cbbf98c506cc372e58665f4e7cd5e96ede7a855a'
)
$ToolkitUpdated = $false
Set-Location $Root
"=== setup $(Get-Date -Format s) ===" | Out-File $Log -Append -Encoding utf8

function Say($m)  { Write-Host $m; $m | Out-File $Log -Append -Encoding utf8 }
function Fail($m) { Write-Host ""; Write-Host "Setup stopped: $m" -ForegroundColor Red
                    Write-Host "Details are in $Log"; Read-Host "Press Enter to close"; exit 1 }
function Ask($q)  { (Read-Host "$q [y/N]") -match '^[Yy]' }
function Run($what, [scriptblock]$cmd) {
    Say "--> $what"
    # Windows PowerShell turns a native program's stderr into an error record
    # once it is redirected, and under 'Stop' that ends the script -- on git's
    # "Cloning into ..." progress line. The exit code is the real verdict.
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $global:LASTEXITCODE = 0
    # Out-File, not >>: Windows PowerShell's >> appends UTF-16 to this UTF-8 log.
    & $cmd 2>&1 | ForEach-Object { "$_" } | Out-File $Log -Append -Encoding utf8
    $code = $LASTEXITCODE
    $ErrorActionPreference = $prev
    if ($code -ne 0) { Fail "$what failed." }
}
function Have($exe) { [bool](Get-Command $exe -ErrorAction SilentlyContinue) }
function Install($id, $why, $size) {
    if (-not (Have 'winget')) { Fail "$why is missing and winget is not available; install it by hand (see README)." }
    if (-not (Ask "$why is not installed. Install $id with winget (about $size)?")) { Fail "$why is required." }
    Run "installing $id" { winget install --id $id -e --accept-package-agreements --accept-source-agreements }
    Say "Installed. If the next check still fails, close this window and run Setup.cmd again (PATH changes need a new window)."
}

# ---- 1. prerequisites --------------------------------------------------------
Say "Checking prerequisites..."
if (-not (Have 'py')) { Install 'Python.Python.3.12' 'Python 3' '30 MB' }
if (-not (Have 'py')) { Fail "Python is installed but 'py' is not on PATH yet; open a new window and run Setup.cmd again." }
# Asked without a traceback: Windows PowerShell turns a native program's
# redirected stderr into an error record, and under 'Stop' that ended the
# script right here, before the question below (see Run).
& py -3 -c "import importlib.util, sys; sys.exit(importlib.util.find_spec('capstone') is None)"
if ($LASTEXITCODE -ne 0) {
    if (-not (Ask "The Python package 'capstone' (disassembler, about 3 MB) is missing. Install it with pip?")) { Fail "capstone is required." }
    Run 'pip install capstone' { py -3 -m pip install --user capstone }
}
if (-not (Have 'git')) { Install 'Git.Git' 'Git (also provides bash)' '60 MB' }
if (-not (Have 'cmake')) { Install 'Kitware.CMake' 'CMake' '40 MB' }
$vswhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
$vc = if (Test-Path $vswhere) { & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath } else { $null }
if (-not $vc) {
    if (-not (Ask "The Visual Studio 2022 C++ build tools are not installed. Install them with winget (about 6 GB)?")) { Fail "a C compiler is required." }
    Run 'installing VS 2022 Build Tools' { winget install --id Microsoft.VisualStudio.2022.BuildTools -e --accept-package-agreements --accept-source-agreements --override "--quiet --wait --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended" }
}
$bash = Join-Path (Split-Path (Split-Path (Get-Command git).Source)) 'bin\bash.exe'
if (-not (Test-Path $bash)) { Fail "Git's bash.exe was not found next to git; reinstall Git for Windows." }

# ---- 2. toolkit ----------------------------------------------------------------
if (-not (Test-Path (Join-Path $Toolkit '.git'))) {
    Run "fetching the xboxrecomp toolkit ($ToolkitRef)" { git clone --branch $ToolkitRef $ToolkitUrl $Toolkit }
} else {
    # An older checkout (sp00nznet's work/falloutbos, or this branch from
    # before a fix) is moved up to the fork's branch -- but only by a
    # fast-forward, so local commits and edits are never thrown away.
    # Not through Run: with no network the toolkit already here is still
    # good enough to build, so a failed fetch is said and set aside.
    Say "--> checking the toolkit against $ToolkitRef"
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $fetchOut = @(git -C $Toolkit fetch $ToolkitUrl $ToolkitRef 2>&1 | ForEach-Object { "$_" })
    $fetched = $LASTEXITCODE -eq 0
    $fetchOut | Out-File $Log -Append -Encoding utf8
    $ErrorActionPreference = $prev
    if ($fetched) {
        $tip = (git -C $Toolkit rev-parse FETCH_HEAD).Trim()
        git -C $Toolkit merge-base --is-ancestor $tip HEAD
    }
    if (-not $fetched) {
        # git's own words: no network, no such branch and a refused login all
        # end up here, and only the first is fine to shrug off.
        $why = ($fetchOut | Where-Object { $_ -match '^(fatal|error):' } | Select-Object -Last 1)
        if (-not $why) { $why = ($fetchOut | Select-Object -Last 1) }
        Say "Could not fetch $ToolkitRef from ${ToolkitUrl}: $why"
        Say "Using the toolkit already in $Toolkit as it is; if the build fails, fix the above and run Setup again."
    }
    elseif ($LASTEXITCODE -eq 0) { Say "Toolkit already present and up to date: $Toolkit" }
    else {
        git -C $Toolkit merge-base --is-ancestor HEAD $tip
        $ff = $LASTEXITCODE -eq 0
        $head = (git -C $Toolkit rev-parse HEAD).Trim()
        if ($ToolkitRewritten -contains $head) { $ff = $true }
        if ($ff -and -not (git -C $Toolkit status --porcelain --untracked-files=no)) {
            Run "updating the toolkit to $ToolkitRef" { git -C $Toolkit checkout -B $ToolkitRef $tip }
            $ToolkitUpdated = $true
        } else {
            Say "Toolkit in $Toolkit has local changes; left as it is. To take the fixes: git -C deps\xboxrecomp pull $ToolkitUrl $ToolkitRef"
        }
    }
}

# ---- 3. your disc --------------------------------------------------------------
if (-not (Test-Path (Join-Path $Root 'game\default.xbe'))) {
    $iso = Get-ChildItem -Path $Root, "$env:USERPROFILE\Downloads" -Filter '*.iso' -ErrorAction SilentlyContinue |
           Where-Object { $_.Name -match 'Fallout' -and $_.Name -match 'Brotherhood' } | Select-Object -First 1
    if ($iso -and (Ask "Use this disc image: $($iso.FullName)?")) { $path = $iso.FullName }
    else { $path = (Read-Host "Path to your Fallout: Brotherhood of Steel (USA) .iso").Trim('"') }
    if (-not (Test-Path $path)) { Fail "no disc image at '$path'." }
    Run 'unpacking your disc into game\' { Push-Location $Toolkit; py -3 -m tools.xiso unpack $path -o (Join-Path $Root 'game'); $c = $LASTEXITCODE; Pop-Location; $global:LASTEXITCODE = $c }
} else { Say "Disc already unpacked into game\" }

# No widescreen step: 16:9, 16:10 or 4:3 is picked at start (FBOS_ASPECT, the
# launcher's Aspect), and the C is generated the same from a patched or an
# unpatched disc (tools\aspect.py), so the disc is left as it is.

# ---- 4. generate the C ---------------------------------------------------------
if (-not (Test-Path (Join-Path $Root 'src\game\recomp\gen\recomp_funcs.h'))) {
    $env:RECOMP = $Toolkit
    Run 'generating C from your disc (about 3 minutes)' { & $bash ./regen.sh --disasm }
} else { Say "Generated C already present (delete src\game\recomp\gen to redo)" }

# ---- 5. build ------------------------------------------------------------------
# A toolkit update needs a rebuild; the build itself regenerates gen/ when the
# toolkit's codegen changed (src/game/CMakeLists.txt).
if ($ToolkitUpdated -or -not (Test-Path (Join-Path $Root 'bin\fobos.exe'))) {
    Run 'configuring the build' { cmake -S . -B build-msvc -A x64 "-DXBOXRECOMP_DIR=$Toolkit" }
    Run 'building (several minutes; your machine will be busy)' { cmake --build build-msvc --config Release }
} else { Say "Already built: bin\fobos.exe" }

Say ""
Say "Done. Double-click bin\FalloutLauncher.exe (resolution, anti-aliasing) or Play.cmd in $Root to start the game."
Read-Host "Press Enter to close"
