"""Agent 1 orchestration config. Single source of truth for orchestrator-side
knobs. All thresholds tunable; calibrate on real structures, not synthetic data.

Model / fold / GPU constants live in ``fold_app/modal_app.py`` (they execute
inside the Modal container, so they are defined there to keep the app
self-contained). This file holds only what the local orchestrator needs.
"""

# ----- Confidence annotation (advisory — Agent 1 never rejects on confidence) -
# Per design decision: Agent 1 emits every fold and annotates a mean-pLDDT tier
# in the sidecar so Agent 2/3 can decide. These bands are TUNABLE — calibrate on
# a batch of real structures before relying on them.
PLDDT_HIGH = 0.70      # >= HIGH
PLDDT_MEDIUM = 0.50    # >= MEDIUM; below this = LOW

# ----- Output layout ----------------------------------------------------------
OUTPUT_STRUCTURES_NAME = "structures.jsonl"   # one StructureRecord per fold
OUTPUT_REJECTIONS_NAME = "rejections.jsonl"   # one FoldFailure per errored fold
OUTPUT_CIF_SUBDIR = "structures"              # <output_dir>/structures/<record_id>.cif
