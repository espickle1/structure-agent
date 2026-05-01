---
type: object
name: foldseek_results
query_id: [Query structure identifier]
foldseek_version: [e.g., 9-427df8a]
database: [PDB | AFDB | ESMAtlas | mixed]
hit_count: [Number of rows]
run_date: [YYYY-MM-DD]
version: 1.0
created: [YYYY-MM-DD]
---

# OBJECT.foldseek_results.md — [Query ID]

## Run Metadata

- **Query structure:** [filename or accession]
- **Database searched:** [PDB | AFDB | ESMAtlas | other]
- **Foldseek version:** [version]
- **Search command:** [`foldseek easy-search ...` if useful for reproducibility]
- **Run date:** [YYYY-MM-DD]

---

## Hits

| query | target | alntmscore | evalue | qtmscore | ttmscore | prob | theader |
|-------|--------|------------|--------|----------|----------|------|---------|
| [query_id] | 1abc_A | 0.87 | 1.2e-25 | 0.85 | 0.89 | 0.99 | [PDB title] |
| [query_id] | AF-Q12345-F1 | 0.74 | 3.4e-18 | 0.72 | 0.76 | 0.95 | [UniProt name] |
| ... |

*(Embedded TSV is also acceptable in place of a markdown table — paste the m8 output directly under this heading.)*

---

## Preparation Notes

**Recommended Foldseek command:**

```bash
foldseek easy-search query.pdb /path/to/db results.m8 tmpfolder \
  --format-output "query,target,alntmscore,evalue,qtmscore,ttmscore,prob,theader,taxname"
```

**Required columns (any order, any name; agent auto-detects):**

| Column | Purpose |
|--------|---------|
| `query` | query structure identifier |
| `target` | Foldseek hit identifier |
| `evalue` | significance value |
| at least one of `alntmscore`, `qtmscore`, `ttmscore`, `prob` | TM-score or proxy used for ranking |

**Optional columns (used when present):**

| Column | Purpose |
|--------|---------|
| `theader` | target header text from PDB/UniProt; bolsters per-paper relevance summary |
| `taxname`, `taxlineage` | taxonomic disambiguation when target IDs are ambiguous |
| `lddt`, `fident`, `alnlen` | informational only at v0; preserved in metadata |

**Target ID conventions handled by agent:**

| Source | Example | Resolved as | PubMed coverage |
|--------|---------|-------------|-----------------|
| PDB chain | `1abc_A`, `1abc.A` | `1ABC` (PDB code) | yes |
| AlphaFold DB | `AF-Q12345-F1-model_v4` | `Q12345` (UniProt accession) | yes |
| ESMAtlas | `MGYP000...` | — | no — agent skips and reports |
| Other / custom | any | verbatim | flagged for review |

**File preparation options:**

1. **Quickest:** save raw m8/TSV from `--format-output` and pass directly to the agent. The OBJECT wrapper is optional.
2. **Provenance-preserving:** prepend the YAML frontmatter and Run Metadata block above to the m8/TSV (or convert to a markdown table). Recommended when the Foldseek run is one you'll want to reproduce or cite later.

**Self-hits:**

The agent automatically drops self-hits (`query == target` or near-identical IDs). No manual filtering needed.

**Preparing for the agent:**

1. Run Foldseek with the required (and any optional) columns.
2. Save raw m8/TSV, or wrap into this OBJECT format.
3. Hand the file (or pasted contents) to AGENT.foldseek-literature-retrieval. No further preprocessing required.
