#!/usr/bin/env bash
# run_pipeline.sh — structure-agent pipeline coordinator
#
# Full pipeline:  ./run_pipeline.sh --input sequences.fasta --output-dir results/ --prompt prompts/report.md
# BYO structure:  ./run_pipeline.sh --input structure.cif  --output-dir results/ --prompt prompts/report.md
#
# BYO mode is auto-detected from .cif / .pdb / .mmcif extension, or forced with --byo.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="$REPO_ROOT/src"
SCRIPTS_DIR="$SRC_DIR/agent_2/scripts"

# --------------------------------------------------------------------------- #
# Argument parsing
# --------------------------------------------------------------------------- #
INPUT=""
OUTPUT_DIR=""
PROMPT_FILE=""
PROFILE_FLAGS=""
CLIENT_METADATA=""
BYO=false

usage() {
    cat <<EOF
Usage: $(basename "$0") --input <file> --prompt <markdown>
                        [--output-dir <dir>] [--profile <path>] [--metadata <json>] [--byo]

  --input        Input FASTA (full pipeline) or CIF/PDB (BYO structure)
  --output-dir   Root output directory; subdirs agent_0/, agent_1/, agent_2/ created automatically
                 (default: results/run_YYYYMMDD_HHMMSS/)
  --prompt       Markdown prompt file passed to Claude for the synthesis step
  --profile      Expected-parameter profile for Agent 2 (repeatable)
  --metadata     Client metadata JSON for Agent 0 (optional)
  --byo          Skip Agents 0/1; treat --input as a structure file directly
EOF
    exit 1
}

while [[ $# -gt 0 ]]; do
    case $1 in
        --input)      INPUT="$(realpath "$2")";       shift 2 ;;
        --output-dir) OUTPUT_DIR="$(realpath "$2")";  shift 2 ;;
        --prompt)     PROMPT_FILE="$(realpath "$2")"; shift 2 ;;
        --profile)    PROFILE_FLAGS="$PROFILE_FLAGS --profile $(realpath "$2")"; shift 2 ;;
        --metadata)   CLIENT_METADATA="$(realpath "$2")"; shift 2 ;;
        --byo)        BYO=true; shift ;;
        -h|--help)    usage ;;
        *)            echo "Unknown argument: $1"; usage ;;
    esac
done

[[ -z "$INPUT" || -z "$PROMPT_FILE" ]] && usage
[[ -z "$OUTPUT_DIR" ]] && OUTPUT_DIR="${REPO_ROOT}/results/run_$(date +%Y%m%d_%H%M%S)"
[[ ! -f "$INPUT"       ]] && { echo "ERROR: input file not found: $INPUT";       exit 1; }
[[ ! -f "$PROMPT_FILE" ]] && { echo "ERROR: prompt file not found: $PROMPT_FILE"; exit 1; }

# Auto-detect BYO from extension
EXT="${INPUT##*.}"
if [[ "$EXT" =~ ^(cif|pdb|mmcif)$ ]]; then
    BYO=true
fi

# --------------------------------------------------------------------------- #
# Directory setup
# --------------------------------------------------------------------------- #
mkdir -p "$OUTPUT_DIR/agent_0" \
         "$OUTPUT_DIR/agent_1/structures" \
         "$OUTPUT_DIR/agent_2"

echo "=========================================="
echo " structure-agent pipeline"
echo " Input:   $INPUT"
echo " Output:  $OUTPUT_DIR"
echo " Mode:    $(if $BYO; then echo 'BYO structure (Agents 0/1 skipped)'; else echo 'full pipeline'; fi)"
echo " Prompt:  $PROMPT_FILE"
echo "=========================================="

# --------------------------------------------------------------------------- #
# Agent 0 — sequence preprocessing
# --------------------------------------------------------------------------- #
if ! $BYO; then
    echo ""
    echo "[Agent 0] Preprocessing sequences..."

    META_FLAG=""
    [[ -n "$CLIENT_METADATA" ]] && META_FLAG="--client-metadata $CLIENT_METADATA"

    (cd "$SRC_DIR" && python -m agent_0.orchestrator \
        --input "$INPUT" \
        --output-dir "$OUTPUT_DIR/agent_0" \
        $META_FLAG)
fi

# --------------------------------------------------------------------------- #
# Agent 1 — structure prediction
# --------------------------------------------------------------------------- #
if ! $BYO; then
    echo ""
    echo "[Agent 1] Predicting structures (dispatching to Modal)..."

    (cd "$SRC_DIR" && python -m agent_1.orchestrator \
        --input-fasta "$OUTPUT_DIR/agent_0/cleaned.faa" \
        --sidecar     "$OUTPUT_DIR/agent_0/sidecar.jsonl" \
        --output-dir  "$OUTPUT_DIR/agent_1")
fi

# --------------------------------------------------------------------------- #
# Collect structure files
# --------------------------------------------------------------------------- #
if $BYO; then
    STRUCTURES=("$INPUT")
else
    mapfile -t STRUCTURES < <(find "$OUTPUT_DIR/agent_1/structures" \
        \( -name "*.cif" -o -name "*.pdb" \) | sort)
fi

if [[ ${#STRUCTURES[@]} -eq 0 ]]; then
    echo "ERROR: no structure files found after Agent 1"
    exit 1
fi

echo ""
echo "[Agent 2] Analyzing ${#STRUCTURES[@]} structure(s)..."

# --------------------------------------------------------------------------- #
# Agent 2 — per-structure deterministic analysis
# --------------------------------------------------------------------------- #
for STRUCT in "${STRUCTURES[@]}"; do
    STEM="$(basename "${STRUCT%.*}")"
    echo ""
    echo "  ---- $STEM ----"

    # Step 2: parse
    (cd "$SCRIPTS_DIR" && python parse_structure.py \
        "$STRUCT" --output-dir "$OUTPUT_DIR/agent_2")

    # Step 4: surface + fold
    (cd "$SCRIPTS_DIR" && python surface_analysis.py \
        "$STRUCT" --output-dir "$OUTPUT_DIR/agent_2")

    # Step 4c: Cα-trace renders
    (cd "$SCRIPTS_DIR" && python render_trace.py \
        "$STRUCT" --output-dir "$OUTPUT_DIR/agent_2" --color pLDDT)

    # Step 5: binding site — only if ligands present
    HAS_LIGANDS=$(python3 -c "
import json, sys
try:
    m = json.load(open('$OUTPUT_DIR/agent_2/${STEM}_metadata.json'))
    print('true' if m.get('has_ligands') else 'false')
except:
    print('false')
")
    if [[ "$HAS_LIGANDS" == "true" ]]; then
        echo "  Ligands present — running binding site analysis..."
        (cd "$SCRIPTS_DIR" && python binding_site.py \
            "$STRUCT" --output-dir "$OUTPUT_DIR/agent_2")
    fi

    # Step 9a: assemble report skeleton (deterministic facts + SYNTHESIS placeholders)
    (cd "$SCRIPTS_DIR" && python assemble_report.py "$STEM" \
        --results-dir "$OUTPUT_DIR/agent_2" \
        $PROFILE_FLAGS)
done

# --------------------------------------------------------------------------- #
# Step 6: comparative analysis — multiple structures only
# --------------------------------------------------------------------------- #
if [[ ${#STRUCTURES[@]} -gt 1 ]]; then
    echo ""
    echo "[Agent 2] Comparative analysis (${#STRUCTURES[@]} structures)..."
    REF="${STRUCTURES[0]}"
    QUERIES=("${STRUCTURES[@]:1}")
    (cd "$SCRIPTS_DIR" && python compare_structures.py \
        "$REF" "${QUERIES[@]}" --output-dir "$OUTPUT_DIR/agent_2")
fi

# --------------------------------------------------------------------------- #
# Step 9b: Claude synthesis — fill SYNTHESIS placeholders
# --------------------------------------------------------------------------- #
echo ""
echo "[Synthesis] Invoking Claude..."

PROVENANCE_NOTE="$(if $BYO; then
    echo 'BYO: structure was not predicted by Agents 0/1. Do not reason about pLDDT or prediction confidence.'
else
    echo 'Pipeline-predicted by Agents 0/1 using ESMFold2-Fast. pLDDT is in the B-factor column.'
fi)"

TASK="$(cat "$PROMPT_FILE")

---
Context for this run:
- Output directory: $OUTPUT_DIR/agent_2
- Repo root: $REPO_ROOT
- Provenance: $PROVENANCE_NOTE
- Structures analyzed: $(IFS=', '; echo "${STRUCTURES[*]}")"

claude "$TASK"

# --------------------------------------------------------------------------- #
echo ""
echo "=========================================="
echo " Done. Results in $OUTPUT_DIR/agent_2"
echo "=========================================="
