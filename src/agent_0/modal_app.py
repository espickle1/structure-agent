"""Fast-path Modal app. CPU only.

Pipeline per record:
    parse → normalize → type-detect → fast-translate → quality-gate

Output verdict is one of:
    FAST_PATH_PASS         — clean AA emitted, ready for Agent 1
    PROTEIN_PASSTHROUGH    — client supplied AA; quality-gated and emitted
    SLOW_PATH_NEEDED       — forward to slow_app for ORF resolution
    REJECTED               — log and drop

Each function is decorated with @app.function and is invocable via .map().
"""

from __future__ import annotations

import modal

from agent0.fast_app.fast_translate import attempt_fast_path
from agent0.fast_app.ingest import normalize_record
from agent0.fast_app.quality_gate import gate_translation
from agent0.fast_app.type_detect import classify_record, has_non_iupac_nucleotide
from agent0.shared.config import (
    FAST_APP_CPU_REQUEST,
    FAST_APP_MEMORY_MB,
    NON_IUPAC_FRACTION_MAX,
)
from agent0.shared.schemas import (
    InputRecord,
    RejectedRecord,
    RejectionReason,
    SequenceType,
    TranslatedRecord,
    Verdict,
)


app = modal.App("agent0-fast")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "biopython>=1.83",
    )
    # Mount the agent0 package into the container.
    .add_local_python_source("agent0")
)


@app.function(
    image=image,
    cpu=FAST_APP_CPU_REQUEST,
    memory=FAST_APP_MEMORY_MB,
    timeout=120,
)
def process_record(input_dict: dict) -> dict:
    """Process one record. Input/output are plain dicts so they serialize.

    Returns a dict with key "kind" in {"translated", "slow_needed", "rejected"}
    and a payload dict of the appropriate dataclass serialization.
    """
    record = InputRecord(**input_dict)

    # 1. Normalize.
    normalized = normalize_record(record)

    # 2. Type detect.
    typed = classify_record(normalized)

    # 3. Validate alphabet on declared nucleotides.
    if typed.sequence_type in (SequenceType.DNA, SequenceType.RNA):
        bad, offenders = has_non_iupac_nucleotide(typed.normalized_sequence)
        # NON_IUPAC_FRACTION_MAX is 0.0; any bad char triggers rejection.
        if bad and NON_IUPAC_FRACTION_MAX == 0.0:
            return _make_rejection(
                record_id=record.record_id,
                parent_id=record.record_id,
                reason=RejectionReason.NON_IUPAC_CHARACTERS,
                stage="fast_app.process_record",
                detail=f"non-IUPAC chars: {sorted(offenders)}",
                original_sequence=record.sequence,
                client_metadata=record.client_metadata,
            )

    # 4. Ambiguous type → reject (cannot proceed without knowing AA vs nucleic).
    if typed.sequence_type == SequenceType.AMBIGUOUS:
        return _make_rejection(
            record_id=record.record_id,
            parent_id=record.record_id,
            reason=RejectionReason.AMBIGUOUS_TYPE,
            stage="fast_app.process_record",
            detail=f"composition did not resolve: {typed.composition}",
            original_sequence=record.sequence,
            client_metadata=record.client_metadata,
        )

    # 5. Protein passthrough.
    if typed.sequence_type == SequenceType.PROTEIN:
        aa = typed.normalized_sequence
        passed, reason, detail = gate_translation(aa)
        if not passed:
            return _make_rejection(
                record_id=record.record_id,
                parent_id=record.record_id,
                reason=reason,
                stage="fast_app.protein_gate",
                detail=detail,
                original_sequence=record.sequence,
                client_metadata=record.client_metadata,
            )
        return _make_translated(
            record_id=record.record_id,
            parent_id=record.record_id,
            aa=aa,
            verdict=Verdict.PROTEIN_PASSTHROUGH,
            sequence_type=SequenceType.PROTEIN,
            transformations=typed.transformations,
            original_sequence=record.sequence,
            client_metadata=record.client_metadata,
            selected_frame=None,
            selected_genetic_code=None,
            nt_coordinates=None,
            perplexity=None,
        )

    # 6. Nucleotide → fast-path attempt.
    success, aa, dna_used = attempt_fast_path(typed)
    if success:
        passed, reason, detail = gate_translation(aa)
        if not passed:
            return _make_rejection(
                record_id=record.record_id,
                parent_id=record.record_id,
                reason=reason,
                stage="fast_app.fast_path_gate",
                detail=detail,
                original_sequence=record.sequence,
                client_metadata=record.client_metadata,
            )
        # Fast-path translation uses frame 1, code 11, full-length CDS.
        return _make_translated(
            record_id=record.record_id,
            parent_id=record.record_id,
            aa=aa,
            verdict=Verdict.FAST_PATH_PASS,
            sequence_type=typed.sequence_type,
            transformations=typed.transformations + ["rna_to_dna"]
                if typed.sequence_type == SequenceType.RNA
                else typed.transformations,
            original_sequence=record.sequence,
            client_metadata=record.client_metadata,
            selected_frame=1,
            selected_genetic_code=11,
            nt_coordinates=(0, len(dna_used)),
            perplexity=None,
        )

    # 7. Forward to slow path.
    return {
        "kind": "slow_needed",
        "payload": {
            "record_id": record.record_id,
            "parent_id": record.record_id,
            "dna_sequence": dna_used,
            "original_sequence": record.sequence,
            "transformations": typed.transformations + (
                ["rna_to_dna"] if typed.sequence_type == SequenceType.RNA else []
            ),
            "sequence_type": typed.sequence_type.value,
            "client_metadata": record.client_metadata,
        },
    }


# -----------------------------------------------------------------------------
# Result-construction helpers (kept here to avoid duplication in branches).
# -----------------------------------------------------------------------------
def _make_translated(**kwargs) -> dict:
    rec = TranslatedRecord(
        aa_sequence=kwargs.pop("aa"),
        **{k: v for k, v in kwargs.items() if k != "aa"},
    )
    return {"kind": "translated", "payload": rec.to_sidecar_dict()}


def _make_rejection(**kwargs) -> dict:
    rec = RejectedRecord(**kwargs)
    return {"kind": "rejected", "payload": rec.to_log_dict()}
