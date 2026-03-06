"""
Main CLI for Security-Preserving LLVM Optimization
"""

import argparse
import sys
import os
from pathlib import Path
from pass_selector import optimize_with_selector
from llvm_wrapper import LLVMWrapper, read_ir_file
from security_oracle import SecurityOracle, format_security_report
from config import SECURITY_THRESHOLD, MAX_PASSES


def print_report(report: dict, output_file: str = None):
    """Print optimization report"""
    print("\n" + "=" * 70)
    print("SECURITY-PRESERVING OPTIMIZATION REPORT")
    print("=" * 70)
    print(f"Selector:              {report['selector']}")
    print(f"Baseline Size:         {report['baseline_size']} instructions")
    print(f"Final Size:            {report['final_size']} instructions")
    print(f"Size Reduction:        {report['size_reduction']:.1f}%")
    print(f"Baseline Security:     {report['baseline_score']:.1f}")
    print(f"Final Security:        {report['final_score']:.1f}")
    print(f"Security Preservation: {report['security_preservation']:.1f}%")
    print(f"\nPasses Applied:        {report['num_applied']}")
    print(f"Passes Rejected:       {report['num_rejected']}")
    
    if report['applied_passes']:
        print("\nApplied Passes:")
        for i, p in enumerate(report['applied_passes'][:10], 1):
            print(f"  {i}. {p['pass']} (-{p['reduction']} inst)")
        if len(report['applied_passes']) > 10:
            print(f"  ... and {len(report['applied_passes']) - 10} more")
    
    if report['rejected_passes']:
        print("\nRejected Passes:")
        for i, p in enumerate(report['rejected_passes'][:5], 1):
            print(f"  {i}. {p['pass']}: {p['reason']}")
        if len(report['rejected_passes']) > 5:
            print(f"  ... and {len(report['rejected_passes']) - 5} more")
    
    print("=" * 70)
    
    # Save to file if requested
    if output_file:
        with open(output_file, 'w') as f:
            f.write("SECURITY-PRESERVING OPTIMIZATION REPORT\n")
            f.write("=" * 70 + "\n")
            f.write(f"Selector: {report['selector']}\n")
            f.write(f"Baseline Size: {report['baseline_size']} instructions\n")
            f.write(f"Final Size: {report['final_size']} instructions\n")
            f.write(f"Size Reduction: {report['size_reduction']:.1f}%\n")
            f.write(f"Baseline Security: {report['baseline_score']:.1f}\n")
            f.write(f"Final Security: {report['final_score']:.1f}\n")
            f.write(f"Security Preservation: {report['security_preservation']:.1f}%\n")
            f.write(f"\nPasses Applied: {report['num_applied']}\n")
            f.write(f"Passes Rejected: {report['num_rejected']}\n")
            
            if report['applied_passes']:
                f.write("\nApplied Passes:\n")
                for p in report['applied_passes']:
                    f.write(f"  - {p['pass']}\n")
            
            if report['rejected_passes']:
                f.write("\nRejected Passes:\n")
                for p in report['rejected_passes']:
                    f.write(f"  - {p['pass']}: {p['reason']}\n")
        
        print(f"\nReport saved to: {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Security-Preserving LLVM Optimization Framework",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Greedy optimization
  python main.py input.c --selector greedy --output optimized.ll
  
  # Random-safe optimization
  python main.py input.c --selector random --max-passes 30
  
  # Save detailed report
  python main.py input.c --selector greedy --report report.txt
        """
    )
    
    parser.add_argument("input", help="Input C source file")
    parser.add_argument("--selector", choices=["greedy", "random", "rl"], default="greedy",
                       help="Pass selection strategy (default: greedy)")
    parser.add_argument("--model", help="Path to trained RL model (required for --selector rl)")
    parser.add_argument("--output", help="Output optimized IR file (.ll)")
    parser.add_argument("--report", help="Save security report to file")
    parser.add_argument("--threshold", type=float, default=SECURITY_THRESHOLD,
                       help=f"Security preservation threshold (default: {SECURITY_THRESHOLD})")
    parser.add_argument("--max-passes", type=int, default=MAX_PASSES,
                       help=f"Maximum passes to apply (default: {MAX_PASSES})")
    parser.add_argument("--verbose", action="store_true",
                       help="Show detailed progress")
    parser.add_argument("--quiet", action="store_true",
                       help="Minimal output")
    
    args = parser.parse_args()
    
    # Validate input
    if not os.path.exists(args.input):
        print(f"Error: Input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)
    
    if not args.input.endswith('.c'):
        print(f"Warning: Input file should be a C source file (.c)", file=sys.stderr)
    
    # Check RL model if needed
    if args.selector == "rl" and not args.model:
        print(f"Error: --model is required when using RL selector", file=sys.stderr)
        sys.exit(1)
    
    if args.selector == "rl" and not os.path.exists(args.model):
        print(f"Error: Model file not found: {args.model}", file=sys.stderr)
        sys.exit(1)
    
    # Set output file
    if args.output is None:
        base = Path(args.input).stem
        args.output = f"{base}_optimized.ll"
    
    # Run optimization
    try:
        if not args.quiet:
            print(f"Optimizing {args.input} using {args.selector} selector...")
        
        output_file, report = optimize_with_selector(
            c_file=args.input,
            selector_type=args.selector,
            output_ll=args.output,
            max_passes=args.max_passes,
            verbose=args.verbose
        )
        
        # Print report
        if not args.quiet:
            print_report(report, args.report)
        
        if not args.quiet:
            print(f"\nOptimized IR saved to: {output_file}")
        
    except Exception as e:
        print(f"Error during optimization: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
