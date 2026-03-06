#!/bin/bash
# Complete Project Setup Script
# Run this to set up the entire project

set -e  # Exit on error

echo "=========================================="
echo "AI for Secure Optimization Passes"
echo "Complete Project Setup"
echo "=========================================="
echo ""

# Check if running in correct directory
if [ ! -f "requirements.txt" ]; then
    echo "Error: Please run this script from the project root directory"
    exit 1
fi

# Step 1: Check Python
echo "[1/7] Checking Python..."
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is required"
    exit 1
fi
PYTHON_VERSION=$(python3 --version)
echo "✓ Found $PYTHON_VERSION"

# Step 2: Create virtual environment
echo ""
echo "[2/7] Creating virtual environment..."
if [ -d "venv" ]; then
    echo "Virtual environment already exists, skipping..."
else
    python3 -m venv venv
    echo "✓ Virtual environment created"
fi

# Step 3: Activate and install dependencies
echo ""
echo "[3/7] Installing dependencies..."
source venv/bin/activate
pip install -q --upgrade pip
pip install -q torch numpy pandas matplotlib gymnasium tqdm pytest
echo "✓ Dependencies installed"

# Step 4: Create directories
echo ""
echo "[4/7] Creating project directories..."
mkdir -p data/benchmarks
mkdir -p data/models
mkdir -p data/results
echo "✓ Directories created"

# Step 5: Generate benchmarks
echo ""
echo "[5/7] Generating benchmark programs..."
python scripts/generate_benchmarks.py --count 50 --output data/benchmarks --seed 42
echo "✓ Generated 50 benchmark programs"

# Step 6: Run tests
echo ""
echo "[6/7] Running tests..."
if pytest tests/ -v --tb=short; then
    echo "✓ All tests passed"
else
    echo "⚠ Some tests failed (this is OK if LLVM is not installed)"
fi

# Step 7: Quick functionality test
echo ""
echo "[7/7] Testing single program optimization..."
if [ -f "data/benchmarks/benchmark_000.c" ]; then
    python src/main.py data/benchmarks/benchmark_000.c \
        --selector greedy \
        --output data/results/test_output.ll \
        --report data/results/test_report.txt
    
    echo ""
    echo "✓ Test completed! Sample report:"
    echo "----------------------------------------"
    cat data/results/test_report.txt
    echo "----------------------------------------"
fi

echo ""
echo "=========================================="
echo "SETUP COMPLETE!"
echo "=========================================="
echo ""
echo "Next steps:"
echo ""
echo "1. Train RL agent (1-2 hours):"
echo "   python src/train_rl.py \\"
echo "       --benchmark-dir data/benchmarks \\"
echo "       --model-output data/models/rl_dqn.pt \\"
echo "       --episodes 1000 \\"
echo "       --verbose"
echo ""
echo "2. Run full evaluation:"
echo "   python scripts/evaluate_all.py \\"
echo "       --benchmark-dir data/benchmarks \\"
echo "       --output-dir data/results \\"
echo "       --methods O0,O2,O3,random,greedy,rl \\"
echo "       --rl-model data/models/rl_dqn.pt"
echo ""
echo "3. View results:"
echo "   cat data/results/summary_statistics.csv"
echo "   open data/results/pareto_frontier.png"
echo ""
echo "For help: python src/main.py --help"
echo ""
