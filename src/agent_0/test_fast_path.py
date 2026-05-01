"""Local smoke tests for fast-path components. No Modal, no GPU.

Run with:  pytest agent0/tests/
"""

from __future__ import annotations

from agent0.fast_app.fast_translate import is_clean_cds, attempt_fast_path
from agent0.fast_app.ingest import normalize_record
from agent0.fast_app.quality_gate import (
    gate_length, gate_translation, gate_x_fraction, gate_x_run, gate_x_terminal,
)
from agent0.fast_app.type_detect import detect_type
from agent0.shared.schemas import InputRecord, SequenceType


# ----- type detection ---------------------------------------------------------
def test_detect_dna():
    assert detect_type("ATGCATGCATGCATGC" * 10) == SequenceType.DNA


def test_detect_rna():
    assert detect_type("AUGCAUGCAUGCAUGC" * 10) == SequenceType.RNA


def test_detect_protein():
    assert detect_type("MKTAYIAKQRQISFVKSHFSRQLEERLGLIEVQ") == SequenceType.PROTEIN


def test_detect_ambiguous_unknown_letters():
    # A sequence dominated by 'X' (unknown / gap) is in neither the canonical
    # AA set nor the nucleotide alphabet → ambiguous.
    # NOTE: heavy IUPAC ambiguity codes (R, Y, W, S, K, M, B, D, H, V, N) cannot
    # be distinguished from protein by alphabet alone — they're also valid AA
    # codes. Such inputs will classify as protein and need to be caught by the
    # downstream X-fraction gate. Document for clients.
    seq = "X" * 100
    assert detect_type(seq) == SequenceType.AMBIGUOUS


# ----- fast-path eligibility --------------------------------------------------
def test_clean_cds_passes():
    # M-S-A-* with proper start/stop, code 11. Length divisible by 3.
    seq = "ATG" + "TCT" + "GCT" + "TAA"
    ok, _ = is_clean_cds(seq)
    assert ok


def test_internal_stop_fails():
    seq = "ATG" + "TAA" + "GCT" + "TAA"  # internal stop
    ok, reason = is_clean_cds(seq)
    assert not ok and "internal_stop" in reason


def test_missing_start_fails():
    seq = "GCT" + "TCT" + "GCT" + "TAA"
    ok, reason = is_clean_cds(seq)
    assert not ok and "start" in reason


def test_n_in_sequence_fails():
    seq = "ATG" + "TCN" + "GCT" + "TAA"
    ok, reason = is_clean_cds(seq)
    assert not ok and "non_canonical" in reason


# ----- normalization ----------------------------------------------------------
def test_normalize_uppercase_and_strip():
    rec = InputRecord(record_id="r1", sequence="atg-cat\ngc--at")
    n = normalize_record(rec)
    assert n.normalized_sequence == "ATGCATGCAT"
    assert "uppercase" in n.transformations
    assert "strip_gaps" in n.transformations


# ----- gates ------------------------------------------------------------------
def test_gate_length_min():
    ok, _ = gate_length("M" * 10)
    assert not ok


def test_gate_length_ok():
    ok, _ = gate_length("M" * 100)
    assert ok


def test_gate_x_terminal_rejects_n_term():
    seq = "X" + "M" * 100
    ok, _ = gate_x_terminal(seq)
    assert not ok


def test_gate_x_run_rejects_long_run():
    seq = "M" * 50 + "XXXX" + "M" * 50
    ok, _ = gate_x_run(seq)
    assert not ok


def test_gate_x_run_accepts_short_run():
    seq = "M" * 50 + "XX" + "M" * 50
    ok, _ = gate_x_run(seq)
    assert ok


def test_gate_x_fraction_rejects_high():
    seq = "M" * 90 + "X" * 10  # 10% X
    ok, _ = gate_x_fraction(seq)
    assert not ok


def test_gate_translation_full_pass():
    seq = "M" * 200
    ok, reason, _ = gate_translation(seq)
    assert ok and reason is None


# ----- fast-path attempt end-to-end ------------------------------------------
def test_attempt_fast_path_succeeds_on_clean_input():
    # Build a clean 60-aa protein-coding CDS.
    cds = "ATG" + "GCT" * 60 + "TAA"  # M + 60×A + *
    rec = InputRecord(record_id="r1", sequence=cds)
    norm = normalize_record(rec)
    from agent0.fast_app.type_detect import classify_record
    typed = classify_record(norm)
    ok, aa, _ = attempt_fast_path(typed)
    assert ok
    assert aa.startswith("M")
    assert "*" not in aa
