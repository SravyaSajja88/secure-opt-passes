#!/usr/bin/env python3
"""Quick script to find the benchmark where RL reduces code size the most."""
import sys, os, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "scripts"))

from llvm_wrapper import LLVMWrapper
from security_oracle import SecurityOracle
from rl_agent import RLPassSelector
from evaluate_all import evaluate_method

MODEL_PATH = os.path.join(os.path.dirname(__file__), "models", "rl_agent_ep1900.pt")

llvm   = LLVMWrapper()
oracle = SecurityOracle()

# Load agent
agent = RLPassSelector(state_dim=1, action_dim=1, device="cpu")
agent.load(MODEL_PATH)
print(f"Loaded: {os.path.basename(MODEL_PATH)}  state_dim={agent.state_dim}  action_dim={agent.action_dim}\n")

bench_dir = os.path.join(os.path.dirname(__file__), "data", "benchmarks")
files = sorted(os.listdir(bench_dir))[:30]   # check first 30

results = []
print(f"{'File':<25} {'Base':>5} {'RL':>5} {'Δ':>7} {'Sec%':>7}")
print("-" * 55)
for fname in files:
    if not fname.endswith(".c"):
        continue
    c_file = os.path.join(bench_dir, fname)
    res = evaluate_method(c_file, "rl", llvm, oracle, agent)
    if res:
        red = res.get("size_reduction", 0)
        sec = res.get("security_preservation", 100)
        base = res.get("baseline_size", "?")
        final = res.get("final_size", "?")
        marker = " <-- GOOD" if red > 0 and sec >= 90 else ""
        print(f"{fname:<25} {base:>5} {final:>5} {red:>6.1f}% {sec:>6.1f}%{marker}")
        if red > 0 and sec >= 90:
            results.append((red, sec, fname))

print()
if results:
    results.sort(reverse=True)
    best_red, best_sec, best_file = results[0]
    print(f"BEST for demo: {best_file}  ({best_red:.1f}% reduction, {best_sec:.1f}% security)")
else:
    print("No benchmark showed positive RL reduction with secure output.")
