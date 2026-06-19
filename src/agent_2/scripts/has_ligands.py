#!/usr/bin/env python3
"""Print 'true' if an Agent 2 metadata JSON reports ligands, else 'false'.

Shared by run_pipeline.ps1 and run_pipeline.sh so the ligand check lives in one
place instead of being duplicated as inline Python in each coordinator. It
decides whether binding_site.py runs. Never raises — any error prints 'false'.

Usage:
    python has_ligands.py <stem>_metadata.json
"""
import json
import sys


def main() -> None:
    try:
        with open(sys.argv[1], encoding="utf-8") as f:
            meta = json.load(f)
    except Exception:
        print("false")
        return
    print("true" if meta.get("has_ligands") else "false")


if __name__ == "__main__":
    main()
