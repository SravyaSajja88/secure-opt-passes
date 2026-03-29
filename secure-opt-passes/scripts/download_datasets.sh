#!/bin/bash
# Download and setup real datasets for secure-opt-passes project

set -e

DATA_DIR="data/datasets"
BENCHMARK_DIR="data/benchmarks"

mkdir -p "$DATA_DIR"
mkdir -p "$BENCHMARK_DIR"

echo "========================================"
echo "Downloading Compiler Benchmarks"
echo "========================================"

# 1. PolyBench/C
echo "[1/3] Setting up PolyBench/C..."
if [ ! -d "$DATA_DIR/PolyBenchC" ]; then
    git clone --depth 1 https://github.com/fjricci/polybench-c "$DATA_DIR/PolyBenchC"
fi

# Note: PolyBench are purely numerical kernels and lack security bounds checks.
# They serve as valid stress tests but initially have a baseline secure score of 0.
# The tool should handle this seamlessly as zero security.
find "$DATA_DIR/PolyBenchC" -name "*.c" -maxdepth 3 -type f -exec cp {} "$BENCHMARK_DIR/" \;

# 2. cBench
echo "[2/3] Downloading cBench subset (approximation)..."
# While cBench isn't purely packaged natively on github in the same way, we can pull some similar components.
# In a real environment we'd extract specific tarballs or use specific repositories. For demonstration, we skip the raw clone and point to Angha.
echo "Skipping full cBench tarball, focusing on AnghaBench and PolyBench..."

# 3. AnghaBench Sample
echo "[3/3] Setting up AnghaBench..."
if [ ! -d "$DATA_DIR/AnghaBench" ]; then
    # Shallow clone to save time
    git clone --depth 1 https://github.com/brenocfg/AnghaBench "$DATA_DIR/AnghaBench"
fi

echo "Sampling 200 random programs from AnghaBench (out of 1 million)..."
# Find all C files, shuffle, and pick 200 to drop into benchmarks
find "$DATA_DIR/AnghaBench" -name "*.c" | shuf -n 200 > "$DATA_DIR/AnghaBench_sample.txt"
while IFS= read -r file; do
    cp "$file" "$BENCHMARK_DIR/"
done < "$DATA_DIR/AnghaBench_sample.txt"

echo "========================================"
echo "Download and Sampling Complete!"
echo "Datasets merged into: $BENCHMARK_DIR"
echo "Total benchmark files: $(ls -1 $BENCHMARK_DIR/*.c | wc -l)"
echo "Note: PolyBench kernels lack explicit security checks but are good for optimization stress tests."
echo "========================================"

