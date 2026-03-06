"""
Configuration for Security-Preserving LLVM Optimization Framework
"""

# Security Oracle Configuration
SECURITY_THRESHOLD = 0.9  # Minimum security preservation (90%)
LAMBDA_PENALTY = 2.0      # Security violation penalty weight

# Optimization Configuration
MAX_PASSES = 50           # Maximum passes per optimization run
MAX_ITERATIONS = 100      # Maximum iterations for greedy selector

# LLVM Configuration
CLANG_PATH = "clang-18"   # Path to clang (or just "clang")
OPT_PATH = "opt-18"       # Path to opt (or just "opt")
LLVM_AS_PATH = "llvm-as-14"
LLVM_DIS_PATH = "llvm-dis-14"

# Approved LLVM Optimization Passes
APPROVED_PASSES = [
    "dce",                      # Dead Code Elimination
    "adce",                     # Aggressive DCE
    "gvn",                      # Global Value Numbering
    "licm",                     # Loop-Invariant Code Motion
    "inline",                   # Function Inlining
    "simplifycfg",              # Simplify Control Flow Graph
    "mem2reg",                  # Promote Memory to Register
    "sccp",                     # Sparse Conditional Constant Propagation
    "loop-unroll",              # Loop Unrolling
    "loop-rotate",              # Loop Rotation
    "indvars",                  # Induction Variable Simplification
    "reassociate",              # Reassociate expressions
    "instcombine",              # Instruction Combining
    "tailcallelim",             # Tail Call Elimination
    "sroa",                     # Scalar Replacement of Aggregates
    "early-cse",                # Early Common Subexpression Elimination
    "jump-threading",           # Jump Threading
    "correlated-propagation",   # Correlated Value Propagation
    "loop-deletion",            # Delete dead loops
    "aggressive-instcombine",   # More aggressive instruction combining
]

# Security Pattern Weights
PATTERN_WEIGHTS = {
    "bounds_check": 2.0,
    "null_check": 1.5,
    "sanitizer_call": 1.0,
    "assertion": 1.0,
    "trap": 0.5,
}

# RL Training Configuration
RL_EPISODES = 500
RL_LEARNING_RATE = 0.0003
RL_BATCH_SIZE = 64
RL_GAMMA = 0.99
RL_BUFFER_SIZE = 100000

# Feature Extraction
FEATURE_DIM = 50  # Dimension of state vector

# Evaluation Configuration
BENCHMARK_TIMEOUT = 60  # seconds per program
RANDOM_SEED = 42

# Logging
VERBOSE = True
LOG_FILE = "optimization.log"
