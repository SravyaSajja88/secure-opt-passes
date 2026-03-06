# AI for Secure Optimization Passes

A Machine Learning-Based Framework for Security-Aware Compiler Optimization at the LLVM IR Level

## 🎯 Project Overview

This system intelligently selects LLVM optimization passes while preserving security-critical code patterns like bounds checks, sanitizer calls, and assertions.

## 🏗️ Architecture

```
C Source → LLVM IR → Security Oracle → Pass Selector → Optimization → Validation
                          ↓                 ↓              ↓             ↓
                    Detect Checks    Choose Pass    Apply Pass    Check Security
                                                                   (Rollback if unsafe)
```

## 📦 Installation

### Prerequisites
- LLVM/Clang 14+ (install via apt/brew/package manager)
- Python 3.8+
- 8GB RAM recommended

### Quick Setup
```bash
# Install LLVM (Ubuntu)
sudo apt-get update
sudo apt-get install llvm-14 clang-14

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## 🚀 Quick Start

### 1. Generate Test Programs
```bash
python scripts/generate_benchmarks.py --count 50 --output data/benchmarks/
```

### 2. Run Single Optimization
```bash
python src/main.py data/benchmarks/array_bounds_01.c \
    --selector greedy \
    --output results/optimized.ll \
    --report results/security_report.txt
```

### 3. Train RL Agent
```bash
python src/train_rl.py \
    --benchmark-dir data/benchmarks/ \
    --model-output data/models/rl_policy.pt \
    --episodes 1000
```

### 4. Full Evaluation
```bash
python scripts/evaluate_all.py \
    --benchmark-dir data/benchmarks/ \
    --output-dir data/results/ \
    --methods O0,O2,O3,greedy,random,rl
```

## 📊 Output Examples

### Security Report
```
=== Security-Preserving Optimization Report ===
Input: array_bounds_01.c
Selector: greedy
Initial Security Score: 12
Final Security Score: 11
Security Preservation: 91.7%

Applied Passes (8):
  ✓ dce (safe)
  ✓ gvn (safe)
  ✓ licm (safe)

Rejected Passes (2):
  ✗ aggressive-dce (removed 2 bounds checks)

Code Size: 1024 → 856 instructions (-16.4%)
```

### Comparison Results
```
Method      | Code Size Reduction | Security Preservation | Pareto Score
------------|---------------------|----------------------|-------------
O0          | 0.0%               | 100.0%               | N/A
O2          | 32.5%              | 67.3%                | 0.495
O3          | 41.2%              | 52.8%                | 0.470
Greedy      | 28.3%              | 91.7%                | 0.600
RL          | 30.1%              | 93.2%                | 0.617
```

## 🧪 Testing
```bash
pytest tests/ -v
```

## 📚 Project Structure

```
secure-opt-passes/
├── src/
│   ├── main.py                 # Main CLI entry point
│   ├── security_oracle.py      # Pattern detection
│   ├── feature_extractor.py    # IR feature extraction
│   ├── pass_selector.py        # Heuristic selectors
│   ├── rl_environment.py       # Gymnasium environment
│   ├── rl_agent.py             # RL policy wrapper
│   ├── train_rl.py             # RL training script
│   └── llvm_wrapper.py         # LLVM tool interfaces
├── scripts/
│   ├── generate_benchmarks.py  # Create test programs
│   └── evaluate_all.py         # Run full evaluation
├── tests/
│   ├── test_oracle.py
│   └── test_selector.py
└── data/
    ├── benchmarks/             # Generated C programs
    ├── models/                 # Trained RL models
    └── results/                # Evaluation outputs
```

## 🔧 Configuration

Key parameters in `src/config.py`:
- `SECURITY_THRESHOLD`: Minimum security preservation (default: 0.9)
- `LAMBDA_PENALTY`: Security violation penalty weight (default: 10.0)
- `MAX_PASSES`: Maximum optimization passes per program (default: 50)
- `APPROVED_PASSES`: List of allowed LLVM passes

## 📖 Documentation

See `/docs` for:
- System Architecture (Week 4 report)
- Literature Survey (Week 2 report)
- Requirements Specification (Week 3 SRS)

## 🎓 Academic Context

This is a research prototype demonstrating:
- RL for compiler optimization under constraints
- Security-aware compiler design
- Performance-security trade-off analysis

**Limitations:**
- Heuristic pattern matching (not formal verification)
- Single compilation unit only
- IR instruction count as performance proxy
- Limited to 20-30 common optimization passes

## 📝 License

Academic/Research Use Only

## 👤 Author

Sravya Sajja (24CSB0B74)
Department of Computer Science and Engineering
National Institute of Technology Warangal
