#!/usr/bin/env python3
"""Tolerant structure loading shared by the Agent 2 parser-based scripts.

BioPython's ``MMCIFParser`` hard-requires the ``_atom_site.occupancy`` column,
which minimal predicted mmCIFs (e.g. ESMFold2 / AlphaFold output) routinely
omit — they carry coordinates + pLDDT (in the B-factor column) but no
occupancy, so the parser raises ``KeyError: '_atom_site.occupancy'`` before
building anything. ``read_structure`` injects a default occupancy of 1.00 when
the column is absent, then builds the structure exactly as
``MMCIFParser.get_structure`` would. PDB inputs are parsed unchanged.

This is a shared *I/O utility*: it reads files, it does not read any Agent 2
module's output, so it does not couple the measurement modules to one another.
"""
from __future__ import annotations

import warnings

from Bio.PDB import PDBParser
from Bio.PDB.MMCIFParser import MMCIFParser
from Bio.PDB.MMCIF2Dict import MMCIF2Dict
from Bio.PDB.PDBExceptions import PDBConstructionWarning

# Columns BioPython's _build_structure() requires from the _atom_site loop that
# minimal predicted CIFs may omit; each is filled with a constant per-atom value.
_DEFAULTS = {"_atom_site.occupancy": "1.00"}
# Loop columns used to count atoms (first list-valued one present wins).
_COUNT_KEYS = ("_atom_site.id", "_atom_site.Cartn_x", "_atom_site.label_atom_id")


def read_structure(structure_id: str, filepath, fmt: str):
    """Parse a structure into a BioPython ``Structure``.

    Tolerates minimal mmCIFs that omit required ``_atom_site.*`` columns (e.g.
    ``occupancy`` from ESMFold2 / AlphaFold output). ``fmt`` is ``"mmcif"`` or
    ``"pdb"``.
    """
    filepath = str(filepath)
    if fmt != "mmcif":
        return PDBParser(QUIET=True).get_structure(structure_id, filepath)

    d = MMCIF2Dict(filepath)
    n = next((len(d[k]) for k in _COUNT_KEYS if isinstance(d.get(k), list)), 0)
    for col, val in _DEFAULTS.items():
        if col not in d and n:
            d[col] = [val] * n

    # Build exactly as MMCIFParser.get_structure() does, from our patched dict.
    parser = MMCIFParser(QUIET=True)
    parser._mmcif_dict = d
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=PDBConstructionWarning)
        parser._build_structure(structure_id)
        parser._structure_builder.set_header(parser._get_header())
    return parser._structure_builder.get_structure()
