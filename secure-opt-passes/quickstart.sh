#!/bin/bash
# Quick Start Script for Security-Preserving LLVM Optimization

set -e  # Exit on error

echo "==================================="
echo "Security-Preserving LLVM Optimizer"
echo "Quick Start Script"
echo "==================================="
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is required but not found"
    exit 1
fi

echo "✓ Python 3 found"

# Check LLVM/Clang
if command -v clang-14 &> /dev/null; then
    CLANG_CMD="clang-14"
    OPT_CMD="opt-14"
    echo "✓ LLVM 14 found"
elif command -v clang &> /dev/null; then
    CLANG_CMD="clang"
    OPT_CMD="opt"
    echo "✓ LLVM found (using default version)"
else
    echo "⚠ Warning: LLVM/Clang not found"
    echo "  Please install: sudo apt-get install llvm clang"
    echo "  Continuing anyway (will check during execution)..."
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo ""
    echo "Creating Python virtual environment..."
    python3 -m venv venv
    echo "✓ Virtual environment created"
fi

# Activate virtual environment
echo ""
echo "Activating virtual environment..."
source venv/bin/activate
echo "✓ Virtual environment activated"

# Install dependencies
echo ""
echo "Installing dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt
echo "✓ Dependencies installed"

# Generate benchmarks
echo ""
echo "Generating benchmark programs..."
python scripts/generate_benchmarks.py --count 20 --output data/benchmarks
echo "✓ Benchmarks generated"

# Run a quick test
echo ""
echo "Running quick test..."
if [ -f "data/benchmarks/benchmark_000.c" ]; then
    python src/main.py data/benchmarks/benchmark_000.c \
        --selector greedy \
        --output data/results/test_output.ll \
        --report data/results/test_report.txt
    
    echo ""
    echo "✓ Test completed successfully!"
    echo ""
    echo "Results:"
    cat data/results/test_report.txt
else
    echo "⚠ Benchmark file not found, skipping test"
fi

echo ""
echo "==================================="
echo "Setup Complete!"
echo "==================================="
echo ""
echo "Next steps:"
echo "  1. Run optimization: python src/main.py <input.c> --selector greedy"
echo "  2. Full evaluation:  python scripts/evaluate_all.py --benchmark-dir data/benchmarks"
echo "  3. Train RL agent:   python src/train_rl.py --benchmark-dir data/benchmarks --model-output data/models/rl_policy.pt"
echo ""
echo "For help: python src/main.py --help"
echo ""
