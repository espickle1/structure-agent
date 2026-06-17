# run_pipeline.ps1 — structure-agent pipeline coordinator (PowerShell)
#
# Full pipeline:  .\run_pipeline.ps1 -Input sequences.fasta -Prompt prompts\report.md
# BYO structure:  .\run_pipeline.ps1 -Input structure.cif   -Prompt prompts\report.md
#
# BYO mode is auto-detected from .cif / .pdb / .mmcif extension, or forced with -Byo.
#
# Prerequisites (one-time):
#   pip install modal biopython numpy scipy pandas matplotlib seaborn gemmi
#   modal token set --token-id <id> --token-secret <secret>
#   modal deploy src/agent_1/fold_app/modal_app.py

param(
    [Parameter(Mandatory = $true)]
    [string]$Input,

    [string]$OutputDir = "",

    [Parameter(Mandatory = $true)]
    [string]$Prompt,

    [string[]]$Profile = @(),

    [string]$Metadata = "",

    [switch]$Byo
)

$ErrorActionPreference = "Stop"

# Force UTF-8 mode so the Modal client's progress glyphs (✓, emoji) and the
# Agent 2 scripts' Unicode output don't crash under the Windows cp1252 console.
$env:PYTHONUTF8 = "1"

$repoRoot  = $PSScriptRoot
$srcDir    = Join-Path $repoRoot "src"
$scriptsDir = Join-Path $srcDir "agent_2\scripts"

# --------------------------------------------------------------------------- #
# Resolve and validate inputs
# --------------------------------------------------------------------------- #
if (-not [System.IO.Path]::IsPathRooted($Input))  { $Input  = (Resolve-Path $Input).Path }
if (-not [System.IO.Path]::IsPathRooted($Prompt)) { $Prompt = (Resolve-Path $Prompt).Path }

if (-not (Test-Path $Input))  { Write-Error "Input file not found: $Input";  exit 1 }
if (-not (Test-Path $Prompt)) { Write-Error "Prompt file not found: $Prompt"; exit 1 }

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
foreach ($p in $Profile) {
    $rp = if ([System.IO.Path]::IsPathRooted($p)) { $p } else { (Resolve-Path $p).Path }
    $profileArgs += "--profile", $rp
}

# Auto-detect BYO from extension
$ext = [System.IO.Path]::GetExtension($Input).ToLower().TrimStart('.')
if ($ext -in @('cif', 'pdb', 'mmcif')) { $Byo = $true }

# --------------------------------------------------------------------------- #
# Directory setup
# --------------------------------------------------------------------------- #
New-Item -ItemType Directory -Force -Path "$OutputDir\agent_0"           | Out-Null
New-Item -ItemType Directory -Force -Path "$OutputDir\agent_1\structures" | Out-Null
New-Item -ItemType Directory -Force -Path "$OutputDir\agent_2"           | Out-Null

$modeLabel = if ($Byo) { "BYO structure (Agents 0/1 skipped)" } else { "full pipeline" }
Write-Host "=========================================="
Write-Host " structure-agent pipeline"
Write-Host " Input:   $Input"
Write-Host " Output:  $OutputDir"
Write-Host " Mode:    $modeLabel"
Write-Host " Prompt:  $Prompt"
Write-Host "=========================================="

# --------------------------------------------------------------------------- #
# Agent 0 — sequence preprocessing
# --------------------------------------------------------------------------- #
if (-not $Byo) {
    Write-Host ""
    Write-Host "[Agent 0] Preprocessing sequences..."

    $a0Args = @("--input", $Input, "--output-dir", "$OutputDir\agent_0")
    if ($Metadata) { $a0Args += "--client-metadata", $Metadata }

    Push-Location $srcDir
    try {
        python -m agent_0.orchestrator @a0Args
        if ($LASTEXITCODE -ne 0) { throw "[Agent 0] exited with code $LASTEXITCODE" }
    } finally { Pop-Location }
}

# --------------------------------------------------------------------------- #
# Agent 1 — structure prediction (Modal)
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
    $structures = @($Input)
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

Write-Host ""
Write-Host "[Agent 2] Analyzing $($structures.Count) structure(s)..."

# --------------------------------------------------------------------------- #
# Agent 2 — per-structure deterministic analysis
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

    # Binding site — only if ligands present
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
        Write-Host "  Ligands present — running binding site analysis..."
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
# Comparative analysis — multiple structures only
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
# Synthesis — Claude fills SYNTHESIS placeholders
# --------------------------------------------------------------------------- #
Write-Host ""
Write-Host "[Synthesis] Invoking Claude..."

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

& claude $task

# --------------------------------------------------------------------------- #
Write-Host ""
Write-Host "=========================================="
Write-Host " Done. Results in $OutputDir\agent_2"
Write-Host "=========================================="
