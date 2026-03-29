"""
Comprehensive Evaluation Script
Compare all optimization strategies across benchmarks
"""

import argparse
import os
import sys
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from tqdm import tqdm
import tempfile

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from llvm_wrapper import LLVMWrapper, read_ir_file
from security_oracle import SecurityOracle
from pass_selector import optimize_with_selector
from rl_environment import LLVMOptimizationEnv
from rl_agent import RLPassSelector


def evaluate_method(c_file: str, method: str, llvm: LLVMWrapper, oracle: SecurityOracle, agent: RLPassSelector = None):
    """
    Evaluate a single method on one program
    
    Returns:
        dict with metrics or None if failed
    """
    try:
        if method in ["O0", "O1", "O2", "O3"]:
            # Standard LLVM optimization levels
            fd, ir_file = tempfile.mkstemp(suffix=".ll")
            os.close(fd)
            
            # Compile with optimization level
            opt_level = method[1]  # Extract number from "O2" -> "2"
            llvm.compile_to_ir(c_file, ir_file, opt_level=opt_level)
            
            # Get baseline (O0) for comparison
            fd_baseline, baseline_ir = tempfile.mkstemp(suffix=".ll")
            os.close(fd_baseline)
            llvm.compile_to_ir(c_file, baseline_ir, opt_level="0")
            
            # Analyze both
            baseline_content = read_ir_file(baseline_ir)
            baseline_score, _ = oracle.analyze(baseline_content)
            baseline_size = llvm.count_instructions(baseline_ir)
            
            opt_content = read_ir_file(ir_file)
            opt_score, _ = oracle.analyze(opt_content)
            opt_size = llvm.count_instructions(ir_file)
            
            # Cleanup
            os.remove(ir_file)
            os.remove(baseline_ir)
            
            return {
                "method": method,
                "baseline_size": baseline_size,
                "final_size": opt_size,
                "size_reduction": (baseline_size - opt_size) / baseline_size * 100 if baseline_size > 0 else 0,
                "baseline_score": baseline_score,
                "final_score": opt_score,
                "security_preservation": opt_score / baseline_score * 100 if baseline_score > 0 else 100,
                "num_applied": 0,  # Standard optimization
            }
        
        elif method in ["greedy", "random"]:
            # Our methods
            fd, output_ll = tempfile.mkstemp(suffix=".ll")
            os.close(fd)
            
            _, report = optimize_with_selector(
                c_file=c_file,
                selector_type=method,
                output_ll=output_ll,
                max_passes=50,
                verbose=False
            )
            
            os.remove(output_ll)
            
            report["method"] = method
            return report
        
        elif method == "rl" and agent is not None:
            # RL method using trained agent
            fd, ir_file = tempfile.mkstemp(suffix=".ll")
            os.close(fd)
            
            # Compile to stripped IR so passes run identically to training
            llvm.compile_to_ir_stripped(c_file, ir_file, opt_level="0")
            
            ir_content = read_ir_file(ir_file)
            baseline_score, _ = oracle.analyze(ir_content)
            
            env = LLVMOptimizationEnv(ir_file, baseline_score)
            state, _ = env.reset()
            
            done = False
            steps = 0
            while not done and steps < env.max_steps:
                action = agent.select_action(state, epsilon=0.0)
                state, reward, terminated, truncated, info = env.step(action)
                done = terminated or truncated
                steps += 1
                
            report = env.get_metrics()
            env.close()
            os.remove(ir_file)
            
            report["method"] = method
            return report
            
        else:
            return None
    
    except Exception as e:
        print(f"  Error evaluating {method} on {c_file}: {e}")
        return None


def run_evaluation(benchmark_dir: str, output_dir: str, 
                   methods: list = None,
                   model_path: str = None,
                   verbose: bool = True):
    """
    Run full evaluation across all methods and benchmarks
    """
    if methods is None:
        methods = ["O0", "O2", "O3", "greedy", "random", "rl"]
    
    os.makedirs(output_dir, exist_ok=True)
    
    llvm = LLVMWrapper()
    oracle = SecurityOracle()
    
    # Initialize agent if rl is in methods
    agent = None
    if "rl" in methods:
        if not model_path or not os.path.exists(model_path):
            print(f"Warning: model_path '{model_path}' missing or invalid for RL evaluation. Skipping 'rl' method.")
            methods = [m for m in methods if m != "rl"]
        else:
            # Create dummy env to get state_dim and load weights
            dummy_c = list(Path(benchmark_dir).glob("*.c"))
            if not dummy_c:
                print(f"No C files found in {benchmark_dir}")
                return
            fd, ir_dummy = tempfile.mkstemp(suffix=".ll")
            os.close(fd)
            llvm.compile_to_ir_stripped(str(dummy_c[0]), ir_dummy, opt_level="0")
            dummy_ir = read_ir_file(ir_dummy)
            dummy_score, _ = oracle.analyze(dummy_ir)
            env = LLVMOptimizationEnv(ir_dummy, dummy_score)
            state_dim = env.observation_space.shape[0]
            action_dim = env.action_space.n
            env.close()
            os.remove(ir_dummy)
            
            agent = RLPassSelector(state_dim=state_dim, action_dim=action_dim, device="cpu")
            agent.load(model_path)
            if verbose:
                print(f"Successfully loaded RL agent from {model_path}")
    
    # Get benchmark files
    c_files = list(Path(benchmark_dir).glob("*.c"))
    
    if not c_files:
        print(f"No C files found in {benchmark_dir}")
        return
    
    if verbose:
        print(f"Found {len(c_files)} benchmark programs")
        print(f"Testing methods: {', '.join(methods)}")
    
    # Collect results
    results = []
    
    # Evaluate each program with each method
    for c_file in tqdm(c_files, desc="Benchmarks"):
        program_name = c_file.stem
        
        for method in methods:
            result = evaluate_method(str(c_file), method, llvm, oracle, agent)
            
            if result:
                result["program"] = program_name
                results.append(result)
    
    # Convert to DataFrame
    df = pd.DataFrame(results)
    
    # Save raw results
    csv_path = os.path.join(output_dir, "evaluation_results.csv")
    df.to_csv(csv_path, index=False)
    if verbose:
        print(f"\nResults saved to: {csv_path}")
    
    # Compute summary statistics
    summary = df.groupby("method").agg({
        "size_reduction": ["mean", "std", "min", "max"],
        "security_preservation": ["mean", "std", "min", "max"],
        "num_applied": ["mean", "std"],
    }).round(2)
    
    summary_path = os.path.join(output_dir, "summary_statistics.csv")
    summary.to_csv(summary_path)
    if verbose:
        print(f"Summary statistics saved to: {summary_path}")
    
    # Print summary table
    if verbose:
        print("\n" + "=" * 80)
        print("EVALUATION SUMMARY")
        print("=" * 80)
        print(summary)
    
    # Generate plots
    generate_plots(df, output_dir, verbose)
    
    return df


def generate_plots(df: pd.DataFrame, output_dir: str, verbose: bool = True):
    """Generate comparison plots"""
    
    # Plot 1: Size reduction comparison
    fig, ax = plt.subplots(figsize=(10, 6))
    methods = df["method"].unique()
    size_reductions = [df[df["method"] == m]["size_reduction"].values for m in methods]
    
    ax.boxplot(size_reductions, labels=methods)
    ax.set_ylabel("Code Size Reduction (%)")
    ax.set_title("Code Size Reduction by Method")
    ax.grid(True, alpha=0.3)
    
    plot1_path = os.path.join(output_dir, "size_reduction_comparison.png")
    plt.savefig(plot1_path, dpi=150, bbox_inches='tight')
    plt.close()
    
    if verbose:
        print(f"Plot saved: {plot1_path}")
    
    # Plot 2: Security preservation comparison
    fig, ax = plt.subplots(figsize=(10, 6))
    security_preservations = [df[df["method"] == m]["security_preservation"].values for m in methods]
    
    ax.boxplot(security_preservations, labels=methods)
    ax.set_ylabel("Security Preservation (%)")
    ax.set_title("Security Preservation by Method")
    ax.axhline(y=90, color='r', linestyle='--', label='90% Threshold')
    ax.grid(True, alpha=0.3)
    ax.legend()
    
    plot2_path = os.path.join(output_dir, "security_preservation_comparison.png")
    plt.savefig(plot2_path, dpi=150, bbox_inches='tight')
    plt.close()
    
    if verbose:
        print(f"Plot saved: {plot2_path}")
    
    # Plot 3: Pareto frontier (trade-off)
    fig, ax = plt.subplots(figsize=(10, 8))
    
    for method in methods:
        method_data = df[df["method"] == method]
        ax.scatter(
            method_data["size_reduction"],
            method_data["security_preservation"],
            label=method,
            alpha=0.6,
            s=50
        )
    
    ax.set_xlabel("Code Size Reduction (%)")
    ax.set_ylabel("Security Preservation (%)")
    ax.set_title("Performance-Security Trade-off")
    ax.axhline(y=90, color='r', linestyle='--', alpha=0.5, label='90% Security Threshold')
    ax.grid(True, alpha=0.3)
    ax.legend()
    
    plot3_path = os.path.join(output_dir, "pareto_frontier.png")
    plt.savefig(plot3_path, dpi=150, bbox_inches='tight')
    plt.close()
    
    if verbose:
        print(f"Plot saved: {plot3_path}")


def main():
    parser = argparse.ArgumentParser(description="Evaluate all optimization methods")
    parser.add_argument("--benchmark-dir", required=True,
                       help="Directory with benchmark C files")
    parser.add_argument("--output-dir", default="data/results",
                       help="Output directory for results")
    parser.add_argument("--methods", default="O0,O2,O3,greedy,random,rl",
                       help="Comma-separated list of methods")
    parser.add_argument("--model-path", default=None,
                       help="Path to trained RL model (.pt) if evaluating rl method")
    parser.add_argument("--verbose", action="store_true",
                       help="Verbose output")
    
    args = parser.parse_args()
    
    methods = args.methods.split(',')
    
    run_evaluation(
        benchmark_dir=args.benchmark_dir,
        output_dir=args.output_dir,
        methods=methods,
        model_path=args.model_path,
        verbose=args.verbose
    )


if __name__ == "__main__":
    main()
