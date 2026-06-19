# run_pipeline.ps1 - structure-agent pipeline coordinator (PowerShell)
#
# Full pipeline:  .\run_pipeline.ps1 -Input sequences.fasta -Prompt prompts\report.md
# BYO structure:  .\run_pipeline.ps1 -Input structure.cif   -Prompt prompts\report.md
# BYO batch:      .\run_pipeline.ps1 -Input structures_dir\ -Prompt prompts\report.md
#
# BYO mode is auto-detected from a .cif / .pdb / .mmcif extension or a directory input,
# or forced with -Byo. A directory input analyzes every .cif/.pdb/.mmcif file it
# directly contains (non-recursive).
#
# Synthesis runs non-interactively by default (`claude -p --permission-mode
# acceptEdits` - no prompts; for most users, CI, and batch). Pass -Interactive to
# drive it as a supervised `claude` session instead (handy during development).
# The synthesis model is pinned with -Model (default claude-opus-4-8[1m]) and the
# non-interactive agent loop is bounded with -MaxTurns (default 50) for reproducible,
# self-terminating batch runs. Web search/fetch are disabled in the synthesis call
# (--disallowedTools WebSearch,WebFetch), so a PDB ID or protein name in the metadata
# cannot trigger an external lookup - the report stays identity-agnostic. `claude` is
# preflighted before any work runs, so a missing CLI fails fast rather than after the
# (slow, metered) Modal folds.
# Run from a plain PowerShell prompt, NOT from inside an interactive Claude Code
# session (avoids nesting a second `claude` process).
#
# Prerequisites (one-time):
#   pip install modal biopython numpy scipy pandas matplotlib seaborn gemmi
#   modal token set --token-id <id> --token-secret <secret>
#   (no `modal deploy` needed - the Modal apps run ephemerally and tear down per run)
#   the `claude` CLI installed and authenticated (used for the synthesis step)

param(
    [Parameter(Mandatory = $true)]
    [Alias('Input')]
    [string]$InputPath,

    [string]$OutputDir = "",

    [Parameter(Mandatory = $true)]
    [string]$Prompt,

    [Alias('Profile')]
    [string[]]$ProfilePath = @(),

    [string]$Metadata = "",

    [switch]$Byo,

    [switch]$Interactive,

    [string]$Model = "claude-opus-4-8[1m]",

    [int]$MaxTurns = 50
)

$ErrorActionPreference = "Stop"

# Force UTF-8 mode so the Modal client's progress glyphs (checkmark, emoji) and the
# Agent 2 scripts' Unicode output don't crash under the Windows cp1252 console.
$env:PYTHONUTF8 = "1"

# PowerShell pipes strings to native commands using $OutputEncoding, which defaults
# to US-ASCII on 5.1 and would mangle the synthesis prompt's Unicode (em-dashes,
# etc.) when piped to `claude`. Force UTF-8 so the prompt reaches it intact.
$OutputEncoding = [System.Text.UTF8Encoding]::new()

$repoRoot  = $PSScriptRoot
$srcDir    = Join-Path $repoRoot "src"
$scriptsDir = Join-Path $srcDir "agent_2\scripts"

# --------------------------------------------------------------------------- #
# Resolve and validate inputs
# --------------------------------------------------------------------------- #
if (-not [System.IO.Path]::IsPathRooted($InputPath))  { $InputPath  = (Resolve-Path $InputPath).Path }
if (-not [System.IO.Path]::IsPathRooted($Prompt)) { $Prompt = (Resolve-Path $Prompt).Path }

if (-not (Test-Path $InputPath))  { Write-Error "Input not found: $InputPath";  exit 1 }
if (-not (Test-Path $Prompt)) { Write-Error "Prompt file not found: $Prompt"; exit 1 }

# Preflight the synthesis CLI now. It is the last step, but the Modal folds before it
# are slow and metered - fail fast if `claude` is missing rather than after all that.
if (-not (Get-Command claude -ErrorAction SilentlyContinue)) {
    Write-Error "claude CLI not found on PATH. Install and authenticate it (it runs the synthesis step)."
    exit 1
}

# Default output directory
if ([string]::IsNullOrEmpty($OutputDir)) {
    $ts = Get-Date -Format "yyyyMMdd_HHmmss"
    $OutputDir = Join-Path $repoRoot "results\run_$ts"
}
if (-not [System.IO.Path]::IsPathRooted($OutputDir)) {
    $OutputDir = [System.IO.Path]::GetFullPath($OutputDir)
}

# Resolve profile paths before changing directory
$profileArgs = @()
foreach ($p in $ProfilePath) {
    $rp = if ([System.IO.Path]::IsPathRooted($p)) { $p } else { (Resolve-Path $p).Path }
    $profileArgs += "--profile", $rp
}

# Auto-detect BYO from a structure-file extension or a directory of structures
$inputIsDir = Test-Path -Path $InputPath -PathType Container
$ext = [System.IO.Path]::GetExtension($InputPath).ToLower().TrimStart('.')
if ($inputIsDir -or $ext -in @('cif', 'pdb', 'mmcif')) { $Byo = $true }

# --------------------------------------------------------------------------- #
# Directory setup
# --------------------------------------------------------------------------- #
New-Item -ItemType Directory -Force -Path "$OutputDir\agent_0"           | Out-Null
New-Item -ItemType Directory -Force -Path "$OutputDir\agent_1\structures" | Out-Null
New-Item -ItemType Directory -Force -Path "$OutputDir\agent_2"           | Out-Null

$modeLabel = if ($Byo) { "BYO structure (Agents 0/1 skipped)" } else { "full pipeline" }
Write-Host "=========================================="
Write-Host " structure-agent pipeline"
Write-Host " Input:   $InputPath"
Write-Host " Output:  $OutputDir"
Write-Host " Mode:    $modeLabel"
Write-Host " Prompt:  $Prompt"
Write-Host "=========================================="

# --------------------------------------------------------------------------- #
# Agent 0 - sequence preprocessing
# --------------------------------------------------------------------------- #
if (-not $Byo) {
    Write-Host ""
    Write-Host "[Agent 0] Preprocessing sequences..."

    $a0Args = @("--input", $InputPath, "--output-dir", "$OutputDir\agent_0")
    if ($Metadata) { $a0Args += "--client-metadata", $Metadata }

    Push-Location $srcDir
    try {
        python -m agent_0.orchestrator @a0Args
        if ($LASTEXITCODE -ne 0) { throw "[Agent 0] exited with code $LASTEXITCODE" }
    } finally { Pop-Location }
}

# --------------------------------------------------------------------------- #
# Agent 1 - structure prediction (Modal)
# --------------------------------------------------------------------------- #
if (-not $Byo) {
    Write-Host ""
    Write-Host "[Agent 1] Predicting structures (dispatching to Modal)..."

    Push-Location $srcDir
    try {
        python -m agent_1.orchestrator `
            --input-fasta "$OutputDir\agent_0\cleaned.faa" `
            --sidecar     "$OutputDir\agent_0\sidecar.jsonl" `
            --output-dir  "$OutputDir\agent_1"
        if ($LASTEXITCODE -ne 0) { throw "[Agent 1] exited with code $LASTEXITCODE" }
    } finally { Pop-Location }
}

# --------------------------------------------------------------------------- #
# Collect structure files
# --------------------------------------------------------------------------- #
if ($Byo) {
    if ($inputIsDir) {
        # Directory BYO: analyze every structure file directly inside (non-recursive)
        $structures = @(
            Get-ChildItem -Path $InputPath -File |
                Where-Object { $_.Extension.ToLower() -in @('.cif', '.pdb', '.mmcif') } |
                Sort-Object Name |
                ForEach-Object { $_.FullName }
        )
        if ($structures.Count -eq 0) {
            Write-Error "No .cif/.pdb/.mmcif files found in directory: $InputPath"
            exit 1
        }
    } else {
        $structures = @($InputPath)
    }
} else {
    $structures = @(
        Get-ChildItem -Path "$OutputDir\agent_1\structures" -Recurse |
            Where-Object { $_.Extension -in @('.cif', '.pdb') } |
            Sort-Object Name |
            ForEach-Object { $_.FullName }
    )
}

if ($structures.Count -eq 0) {
    Write-Error "No structure files found after Agent 1"
    exit 1
}

# Agent 2 keys every output on the file stem, so inputs that share a basename
# (e.g. foo.cif + foo.pdb) would overwrite each other. Warn rather than clobber.
$dupStems = $structures |
    ForEach-Object { [System.IO.Path]::GetFileNameWithoutExtension($_) } |
    Group-Object | Where-Object { $_.Count -gt 1 } | ForEach-Object { $_.Name }
if ($dupStems) {
    Write-Warning "Duplicate structure basenames ($($dupStems -join ', ')) - their Agent 2 outputs will overwrite each other. Rename inputs to keep them distinct."
}

Write-Host ""
Write-Host "[Agent 2] Analyzing $($structures.Count) structure(s)..."

# --------------------------------------------------------------------------- #
# Agent 2 - per-structure deterministic analysis
# --------------------------------------------------------------------------- #
foreach ($struct in $structures) {
    $stem = [System.IO.Path]::GetFileNameWithoutExtension($struct)
    Write-Host ""
    Write-Host "  ---- $stem ----"

    Push-Location $scriptsDir
    try {
        python parse_structure.py $struct --output-dir "$OutputDir\agent_2"
        if ($LASTEXITCODE -ne 0) { throw "parse_structure failed for $stem" }

        python surface_analysis.py $struct --output-dir "$OutputDir\agent_2"
        if ($LASTEXITCODE -ne 0) { throw "surface_analysis failed for $stem" }

        python render_trace.py $struct --output-dir "$OutputDir\agent_2" --color pLDDT
        if ($LASTEXITCODE -ne 0) { throw "render_trace failed for $stem" }
    } finally { Pop-Location }

    # Binding site - only if ligands present
    $metaPath = "$OutputDir\agent_2\${stem}_metadata.json"
    $hasLigands = python -c "
import json, sys
try:
    m = json.load(open(r'$metaPath'))
    print('true' if m.get('has_ligands') else 'false')
except:
    print('false')
" 2>$null
    if ($hasLigands -eq 'true') {
        Write-Host "  Ligands present - running binding site analysis..."
        Push-Location $scriptsDir
        try {
            python binding_site.py $struct --output-dir "$OutputDir\agent_2"
            if ($LASTEXITCODE -ne 0) { throw "binding_site failed for $stem" }
        } finally { Pop-Location }
    }

    # Assemble report skeleton
    Push-Location $scriptsDir
    try {
        python assemble_report.py $stem --results-dir "$OutputDir\agent_2" $profileArgs
        if ($LASTEXITCODE -ne 0) { throw "assemble_report failed for $stem" }
    } finally { Pop-Location }
}

# --------------------------------------------------------------------------- #
# Comparative analysis - multiple structures only
# --------------------------------------------------------------------------- #
if ($structures.Count -gt 1) {
    Write-Host ""
    Write-Host "[Agent 2] Comparative analysis ($($structures.Count) structures)..."
    $ref     = $structures[0]
    $queries = $structures[1..($structures.Count - 1)]

    Push-Location $scriptsDir
    try {
        python compare_structures.py $ref $queries --output-dir "$OutputDir\agent_2"
        if ($LASTEXITCODE -ne 0) { throw "compare_structures failed" }
    } finally { Pop-Location }
}

# --------------------------------------------------------------------------- #
# Synthesis - Claude fills SYNTHESIS placeholders
# --------------------------------------------------------------------------- #
Write-Host ""
if ($Interactive) {
    Write-Host "[Synthesis] Invoking Claude (interactive session)..."
} else {
    Write-Host "[Synthesis] Invoking Claude (non-interactive)..."
}

$provenanceNote = if ($Byo) {
    "BYO: structure was not predicted by Agents 0/1. Do not reason about pLDDT or prediction confidence."
} else {
    "Pipeline-predicted by Agents 0/1 using ESMFold2-Fast. pLDDT is in the B-factor column."
}

$structuresList = $structures -join ", "
$promptContent  = Get-Content -Path $Prompt -Raw

$task = @"
$promptContent

---
Context for this run:
- Output directory: $OutputDir/agent_2
- Repo root: $repoRoot
- Provenance: $provenanceNote
- Structures analyzed: $structuresList
"@

# Pipe the prompt via stdin, never as a positional arg: Windows PowerShell 5.1
# mangles multi-line, quote-containing arguments to native executables (it splits
# the prompt at the first embedded double-quote), silently truncating the prompt
# and dropping the context block appended at its end. Stdin avoids that entirely.
if ($Interactive) {
    $task | & claude --disallowedTools "WebSearch,WebFetch" --model $Model
} else {
    $task | & claude -p --disallowedTools "WebSearch,WebFetch" --permission-mode acceptEdits --add-dir $OutputDir --model $Model --max-turns $MaxTurns
    if ($LASTEXITCODE -ne 0) {
        Write-Error "[Synthesis] claude exited with code $LASTEXITCODE - the report skeleton was written but SYNTHESIS placeholders may be unfilled. Re-run synthesis or inspect $OutputDir\agent_2."
        exit 1
    }
}

# --------------------------------------------------------------------------- #
# Package outputs - one zip per protein, plus a separate comparative.zip for the
# cross-protein comparison files. Runs after synthesis so the report is bundled.
# Files are stored flat (by basename) so the report's relative image links stay
# valid on extraction; loose copies are removed once their zip is written.
# Packaging is best-effort: a failure warns and leaves that protein's files loose
# rather than discarding outputs synthesis already produced.
# --------------------------------------------------------------------------- #
Write-Host ""
Write-Host "[Agent 2] Packaging outputs (one zip per protein)..."
$a2 = "$OutputDir\agent_2"

foreach ($struct in $structures) {
    $stem = [System.IO.Path]::GetFileNameWithoutExtension($struct)
    $files = @(
        Get-ChildItem -Path $a2 -File | Where-Object {
            $_.Name.StartsWith("${stem}_") -and
            $_.Name -notmatch '_vs_' -and $_.Name -notlike '*_comparisons.json'
        }
    )
    if ($files.Count -eq 0) {
        Write-Warning "No output files found for '$stem' - skipping its package."
        continue
    }
    $zipPath = Join-Path $a2 "$stem.zip"
    if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
    try {
        Compress-Archive -LiteralPath $files.FullName -DestinationPath $zipPath -ErrorAction Stop
        $files | Remove-Item -Force
        Write-Host "  $stem.zip ($($files.Count) files)"
    } catch {
        Write-Warning "Failed to package '$stem' - leaving its files loose. $($_.Exception.Message)"
    }
}

# Cross-protein comparison files -> comparative.zip (only when >1 structure)
if ($structures.Count -gt 1) {
    $compFiles = @(
        Get-ChildItem -Path $a2 -File | Where-Object {
            $_.Name -match '_vs_' -or $_.Name -like '*_comparisons.json'
        }
    )
    if ($compFiles.Count -gt 0) {
        $compZip = Join-Path $a2 "comparative.zip"
        if (Test-Path $compZip) { Remove-Item $compZip -Force }
        try {
            Compress-Archive -LiteralPath $compFiles.FullName -DestinationPath $compZip -ErrorAction Stop
            $compFiles | Remove-Item -Force
            Write-Host "  comparative.zip ($($compFiles.Count) files)"
        } catch {
            Write-Warning "Failed to package comparative files - leaving them loose. $($_.Exception.Message)"
        }
    }
}

# --------------------------------------------------------------------------- #
Write-Host ""
Write-Host "=========================================="
Write-Host " Done. Results in $OutputDir\agent_2"
Write-Host "=========================================="
