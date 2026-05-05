# Agent 4 — Literature search

## Scope

Literature retrieval, ranking, and summarization keyed to structural
anchors. Agent 4's role is to convert a list of resolved anchors into a
ranked, readable, attributed reading list — never to invent anchors of its
own. Anchor production is Agent 3's job.

## Inputs

- Resolved Foldseek anchors (with per-anchor metadata) from Agent 3.
- User-provided context (organism, pathway, function) for query
  refinement.

## Outputs

- Ranked reading list with per-paper anchor attribution: which anchor
  (or anchors) each paper was retrieved against, what makes the paper
  relevant, and why it ranked where it did.
- Summaries appropriate to the consumer (Agent 5+ when one exists; the
  user directly otherwise).

## Status

Not started. Empty directory plus this stub. The `VERB.pubmed-search-skill.md`
generic PubMed search skill currently lives in `../agent_3/` and will move
here when Agent 4 begins implementation; moving it earlier creates a
dangling reference.
