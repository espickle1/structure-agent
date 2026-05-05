---
type: skill
name: pubmed-search
version: 1.6
author: James
created: 2025-12-11
updated: 2025-12-15
description: Generic PubMed literature search and summarization workflow for biomedical research. Uses 5-step intelligent ranking workflow - searches abstracts, ranks all results, selects top articles (5% rule or requested count, whichever greater), retrieves full metadata for selected articles only, then processes. Dynamically retrieves current date at execution time.
scope: biomedical-literature
dependencies:
  - type: mcp
    name: PubMed
    required_tools:
      - PubMed:search_articles
      - PubMed:get_article_metadata
    setup_url: https://pubmed.mcp.claude.com/mcp
used_by:
  - bacteriophage-surveillance-agent
tags: [pubmed, literature-search, biomedical, surveillance]
---

# PubMed Literature Search Skill

## Overview
Generic skill for searching, retrieving, and summarizing biomedical literature from PubMed. Works with topic-specific agents or standalone searches.

## Token Budget Limits

<computational_budget>
**Maximum per execution:**
- Initial search: Up to 500 articles (abstracts only for ranking)
- Articles selected: Dynamic (5% rule: greater of 5% of total OR requested count)
- Articles fully processed: Typically 10-30, maximum 50
- Summary length: 4-5 sentences per article
- Relevance length: 3 sentences per article
- Total target: <6,000 tokens per search execution (~3% weekly quota)

**Automatic termination if:**
- Selected articles exceed 50 (truncate to top 50 and inform user)
- Processing approaches 6,000 token threshold (complete current article, stop, inform user)
- MCP tool calls exceed 4 per search (initial search + ranking + metadata + optional retry)

**User can request reduced scope:**
- "Brief summaries" → 2-3 sentences per article
- "Top 5 articles" → Override 5% rule, process only 5
- "Just titles and relevance" → Skip detailed summaries

**5% Rule Examples:**
- 200 articles found, 10 requested → Process 10 (5% = 10, requested = 10)
- 200 articles found, 15 requested → Process 15 (5% = 10, but requested = 15)
- 60 articles found, 10 requested → Process 10 (5% = 3, but requested = 10)
</computational_budget>

## Prerequisites Check

<dependency_verification>
Before executing:
- Verify PubMed MCP server is connected
- Verify tools available: `PubMed:search_articles`, `PubMed:get_article_metadata`

**If MCP unavailable:**
1. Inform user: "⚠️ PubMed MCP server required"
2. Guide: "Connect in Settings > Connections"
3. Do NOT proceed without tools
</dependency_verification>

## When to Use

<trigger_conditions>
- User requests biomedical literature search
- Agent invokes surveillance workflow
- Monitoring new publications
- One-time or systematic literature queries
</trigger_conditions>

## Parameter Extraction

<parameter_extraction>
Extract from natural language:

**CRITICAL: Current Date Reference**
- Retrieve the current date from system at execution time
- ALWAYS calculate time periods from this retrieved current date
- Example: If today is 2025-12-12, "last month" = 2025/11/12 to 2025/12/12
- Never default to previous years (2024, 2023) unless explicitly requested
- Format: YYYY/MM/DD for PubMed queries

**Topic/Query:** Keywords, compound queries (AND/OR/NOT), PubMed field tags [Title], [Author]

**Time Period Calculation:**
- Relative: "last week", "past month", "last 14 days" → Calculate from **current date retrieved at runtime**
- Absolute: "from November 2025", "between dates" → Use as specified
- Format: YYYY/MM/DD
- **Verification step:** Before executing search, confirm dates are logical (e.g., "last month" should be in current or previous month of current year)

**Number of Results:**
- Extract if specified: "20 articles", "top 10"
- Default: 10
- Note: Initial search may retrieve more for ranking, but final selection follows 5% rule

**Filters:** Publication types, journals, authors if mentioned

**NIH Public Access Policy Note:**
- As of July 2025, 12-month embargo lifted for NIH-funded research
- Recent articles (2025) should be accessible if NIH-funded
- No need to restrict searches to older dates
</parameter_extraction>

## Workflow

<step_by_step_process>

### Step 1: Initial PubMed Search (Abstracts Only)
- **Retrieve current date from system** at execution time
- Extract parameters from user/agent input
- Calculate date ranges using retrieved current date
  - Example: If current date is 2025-12-12, "last month" → 2025/11/12 to 2025/12/12
  - Verify calculated dates are logical for the current year/month
- Validate date ranges and construct query

**Tool:** `PubMed:search_articles`
**Parameters:**
- query, date_from, date_to (YYYY/MM/DD)
- datetype: 'pdat' (publication date)
- max_results: Set high (typically 100-500 to capture broad search)
- sort: 'relevance' default

**Returns:** PMIDs, titles, abstracts, basic publication info
**Output:** Complete list of articles that fit search parameters

### Step 2: Create Ranked List of Results
**Ranking Criteria:**
- **Relevance to research focus** (from agent/user parameters)
- **Abstract quality indicators:**
  - Novel findings mentioned
  - Methodological innovation
  - Priority pathogens/topics
  - Recent important developments
- **Publisher preferences** focus on journals with highest impact factor
- **Citation context clues** in abstract

**Process:**
- Score each article based on abstract content analysis
- Rank all results from highest to lowest relevance
- Create ordered list: [PMID_1, PMID_2, ..., PMID_n]

**Output:** Ranked list of all search results by relevance score

### Step 3: Select Top Articles Using 5% Rule
**Selection Logic:**
- Calculate: `top_count = max(requested_article_count, ceil(0.05 * total_results))`
- **Whichever is GREATER:**
  - 5% of total results found
  - Article number set to be retrieved (from user/agent)

**Examples:**
- Found 200 articles, requested 10 → Select top 10 (200 * 0.05 = 10)
- Found 200 articles, requested 15 → Select top 15 (15 > 10)
- Found 60 articles, requested 10 → Select top 10 (60 * 0.05 = 3, but 10 > 3)

**Output:** List of selected PMIDs for full metadata retrieval

### Step 4: Retrieve Full Metadata for Selected Articles
**Tool:** `PubMed:get_article_metadata`
- Input: Selected PMIDs from Step 3 only
- Retrieve complete metadata: full author lists, keywords, MeSH terms, complete abstracts, DOI, citation details
- **Efficiency gain:** Only processes articles that passed ranking selection

**Output:** Complete article metadata for selected articles only

### Step 5: Full Evaluation and Results Processing
**For each selected article, generate:**

**Basic Info:**
- Full title
- Authors (First Author et al. if >3)
- Journal, publication date
- PMID link: https://pubmed.ncbi.nlm.nih.gov/[PMID]
- DOI if available

**Summary (4-5 sentences):**
- Main objective, methodology, key findings
- Clear, direct language
- Original synthesis (never copy abstract)

**Relevance (3 sentences):**
- Connect to user's research (from memory/agent)
- Explain significance for their work
- Methodological, theoretical, or practical implications

**Token monitoring:** Stop if approaching token budget limits
</step_by_step_process>

## Output Format

<output_structure>
Results formatted as **downloadable markdown**:

```markdown
## Recent Literature: [Topic Name]
**Search Period:** [Date Range or "All dates"]
**Total Found:** [Number] articles matching criteria
**Selected:** [Number] articles (5% rule: [percentage]% of total OR [requested] requested)
**Processed:** [Number] articles with full summaries

---

### Article 1: [Full Title]

**Authors:** [First Author et al.]  
**Journal:** [Journal Name], [Publication Date]  
**PMID:** [PMID] | [PubMed Link]  
**DOI:** [DOI if available]

**Summary:** [4-5 sentences: objective, methods, findings]

**Relevance:** [3 sentences: connection to user's research, significance, implications]

---

[Repeat for each selected article]

---

## Selection Process
**Initial search:** [X] articles found
**Ranking applied:** All articles scored by relevance to research focus
**Selection rule:** Top [Y] articles selected (greater of 5% of total or [Z] requested)
**Processing:** [Y] articles with full metadata retrieved and analyzed
```

**To save output:** Copy entire output to .md file or ask "Can you provide this as a downloadable file?"
</output_structure>

## Relevance Assessment

<relevance_guidance>
**Connect to user's work:**
- Pull from memory or agent configuration
- Consider expertise and ongoing projects
- Make specific connections, avoid generalities

**Connection types:**
- Methodological: applicable techniques
- Theoretical: supporting/challenging findings
- Practical: workflow improvements
- Contextual: interpretive relevance

**Quality standard:** Concrete, specific connections to actual research
</relevance_guidance>

## Agent Integration

<agent_integration>
**Accept from agents:**
- Default topics, time windows, result counts
- Research focus for relevance
- Domain terminology

**Parameter priority:**
1. User's explicit request (highest)
2. Agent defaults
3. Skill defaults (lowest)
</agent_integration>

## Quality Standards

<quality_requirements>
**Summaries:**
- Exactly 4-5 sentences
- Key findings and methods focus
- Clear language, no abstract copying
- Scientifically accurate

**Relevance:**
- Exactly 3 sentences
- Specific to user's work
- Concrete connections
- Practical applications

**Citations:**
- Always: PMID, PubMed link
- Include DOI when available
- Proper author formatting
</quality_requirements>

## Error Handling

<error_handling>
**No results:** Report parameters, suggest modifications

**Incomplete metadata:** Note missing info, provide PMID link

**MCP issues:** State problem, guide reconnection, offer retry

**Ambiguous queries:** Ask clarification before searching

**Token budget exceeded:** Complete current article, stop, inform user how many articles processed vs. requested
</error_handling>

## Critical Guidelines

<critical_guidelines>
- **DATE CALCULATION:** Retrieve current date from system at execution time. Use this date for all time-relative calculations. Verify dates are logical for current year/month.
- **5-STEP WORKFLOW:** Always follow sequence: (1) Initial search abstracts, (2) Rank all results, (3) Select top articles using 5% rule, (4) Retrieve full metadata for selected only, (5) Process and evaluate selected articles
- **5% SELECTION RULE:** Select greater of (5% of total results) OR (requested article count)
- Always cite PubMed source with PMIDs/DOIs
- Never reproduce abstracts verbatim (copyright)
- Respect token budget (≤50 articles selected, ~6,000 tokens total)
- Keep summaries concise and original (4-5 sentences)
- Make relevance assessments specific and personalized (3 sentences)
- Verify MCP connection before executing
- Maintain scientific accuracy
- Format output as downloadable markdown showing selection statistics
- Auto-terminate if exceeding computational limits
</critical_guidelines>
