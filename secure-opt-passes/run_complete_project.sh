#!/bin/bash
# ONE-DAY EXECUTION SCRIPT
# Complete all project tasks in one go

echo "=================================================="
echo "AI for Secure Optimization Passes"
echo "Complete Project Execution"
echo "=================================================="
echo ""

# Activate environment
if [ -d "venv" ]; then
    source venv/bin/activate
else
    echo "Creating virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    echo "Installing dependencies..."
    pip install -q -r requirements.txt
fi

echo "✓ Environment ready"
echo ""

# Step 1: Generate benchmarks
echo "[1/4] Generating 30 benchmark programs..."
python scripts/generate_benchmarks.py --count 30 --output data/benchmarks
echo "✓ Benchmarks generated"
echo ""

# Step 2: Test single optimization
echo "[2/4] Testing single program optimization..."
python src/main.py data/benchmarks/benchmark_000.c \
    --selector greedy \
    --output data/results/sample_output.ll \
    --report data/results/sample_report.txt \
    --verbose

echo ""
echo "Sample Report:"
cat data/results/sample_report.txt
echo ""

# Step 3: Run full evaluation
echo "[3/4] Running comprehensive evaluation..."
echo "This compares: O0, O2, O3, Greedy, Random"
echo "Testing all 30 benchmarks..."
python scripts/evaluate_all.py \
    --benchmark-dir data/benchmarks \
    --output-dir data/results \
    --methods O0,O2,O3,greedy,random \
    --verbose

echo ""
echo "✓ Evaluation complete"
echo ""

# Step 4: Display results
echo "[4/4] Summary of Results"
echo "=================================================="
echo ""

if [ -f "data/results/summary_statistics.csv" ]; then
    echo "Summary Statistics:"
    cat data/results/summary_statistics.csv
    echo ""
fi

echo "Files generated:"
ls -lh data/results/
echo ""

echo "=================================================="
echo "PROJECT COMPLETE!"
echo "=================================================="
echo ""
echo "Results available in: data/results/"
echo ""
echo "Key files:"
echo "  - evaluation_results.csv      (detailed metrics)"
echo "  - summary_statistics.csv      (averages by method)"
echo "  - pareto_frontier.png         (performance vs security plot)"
echo "  - size_reduction_comparison.png"
echo "  - security_preservation_comparison.png"
echo ""
echo "Next steps:"
echo "  1. Review the plots and CSV files"
echo "  2. Copy findings to your final report"
echo "  3. Optionally: Train RL agent with"
echo "     python src/train_rl.py --benchmark-dir data/benchmarks --model-output data/models/rl_policy.pt"
echo ""
