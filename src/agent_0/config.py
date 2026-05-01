"""Agent 0 configuration. Single source of truth for all thresholds.

All values are tunable. Defer numeric calibration to real-data testing,
not synthetic data. Update only after observing a calibration batch.
"""

# ----- Length bounds (AA output) ----------------------------------------------
LENGTH_MIN_AA = 50      # Below this, structure prediction is unreliable.
LENGTH_MAX_AA = 2000    # Above this, Boltz-2 / ESMFold throughput collapses.

# ----- Minimum nucleotide ORF length (gates orfipy enumeration) --------------
# 50 aa * 3 nt/codon = 150 nt; allows just-above-minimum ORFs through
# enumeration. Stop codon adds 3 nt but orfipy includes it in the span.
MIN_ORF_LENGTH_NT = 150
MAX_ORF_LENGTH_NT = LENGTH_MAX_AA * 3 + 3

# ----- Ambiguity (X / B / Z / J) handling -------------------------------------
# U (selenocysteine) and O (pyrrolysine) are real residues; not counted.
AMBIGUITY_RESIDUES = frozenset("XBZJ")

X_FRACTION_MAX = 0.02       # >2% total ambiguity → reject.
X_RUN_MAX = 3               # Consecutive X run > 3 → reject (gap signal).
X_TERMINAL_BUFFER = 10      # Any X in first/last 10 residues → reject.

# ----- Genetic code cascade ---------------------------------------------------
DEFAULT_GENETIC_CODE = 11           # Bacterial / archaeal / phage standard.
FALLBACK_GENETIC_CODES = (1, 4, 6, 15, 25)
# 1: standard eukaryotic
# 4: mold/protozoan/coelenterate mitochondrial; mycoplasma/spiroplasma
# 6: ciliate / dasycladacean / hexamita nuclear
# 15: blepharisma macronuclear
# 25: candidate division SR1 and Gracilibacteria

# ----- IUPAC nucleotide alphabet (validation only) ----------------------------
IUPAC_NUCLEOTIDE_ALPHABET = frozenset("ACGTUNRYWSKMBDHV-")
NON_IUPAC_FRACTION_MAX = 0.0  # Zero tolerance; reject sequences with junk.

# ----- Type detection thresholds ----------------------------------------------
# Fraction of ACGT(U) needed to call a sequence a nucleotide.
NUCLEOTIDE_PURITY_MIN = 0.90
# Fraction of canonical AA needed to call a sequence a protein.
PROTEIN_PURITY_MIN = 0.90

# ----- ESM-2 perplexity filter ------------------------------------------------
ESM_MODEL_NAME = "facebook/esm2_t33_650M_UR50D"
ESM_BATCH_SIZE = 16  # On A10G; tune for VRAM headroom.

# Perplexity thresholds — TUNABLE, calibrate on real data.
# Lower perplexity = more plausible. Real proteins typically score < 10
# under ESM-2 650M; random sequences score > 20. These are placeholders.
PERPLEXITY_REJECT_ABOVE = 15.0      # Above this, no candidate is viable.
PERPLEXITY_TIE_FRACTION = 0.15      # Candidates within 15% of best are
                                    # all "plausible" → emit as multi-ORF.

# ----- Modal infrastructure ---------------------------------------------------
SLOW_APP_GPU = "A10G"               # Cheaper than A100 for ESM-2 650M.
SLOW_APP_MIN_CONTAINERS = 0         # Set to 1 during active batches if
                                    # cold-start latency becomes an issue.
FAST_APP_CPU_REQUEST = 1.0
FAST_APP_MEMORY_MB = 1024

# ----- Output / volume layout -------------------------------------------------
VOLUME_NAME = "agent0-shared"
OUTPUT_FASTA_NAME = "cleaned.faa"
OUTPUT_SIDECAR_NAME = "sidecar.jsonl"
OUTPUT_REJECTIONS_NAME = "rejections.jsonl"
