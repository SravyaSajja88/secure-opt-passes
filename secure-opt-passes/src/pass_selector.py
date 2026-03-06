"""
Heuristic Pass Selectors
Baseline optimization strategies for comparison with RL
"""

import random
import shutil
from typing import List, Tuple, Optional
from llvm_wrapper import LLVMWrapper, read_ir_file
from security_oracle import SecurityOracle
from config import APPROVED_PASSES, SECURITY_THRESHOLD, MAX_ITERATIONS


class PassSelector:
    """Base class for pass selection strategies"""
    
    def __init__(self, llvm: LLVMWrapper, oracle: SecurityOracle, 
                 threshold: float = SECURITY_THRESHOLD):
        self.llvm = llvm
        self.oracle = oracle
        self.threshold = threshold
        self.applied_passes = []
        self.rejected_passes = []
    
    def select_pass(self, ir_file: str, baseline_score: float) -> Optional[str]:
        """
        Select next pass to apply
        
        Args:
            ir_file: Current IR file
            baseline_score: Original security score
        
        Returns:
            Pass name or None if done
        """
        raise NotImplementedError
    
    def get_report(self) -> dict:
        """Get optimization report"""
        return {
            "applied": self.applied_passes,
            "rejected": self.rejected_passes,
        }


class RandomSafeSelector(PassSelector):
    """Randomly select passes that don't violate security"""
    
    def __init__(self, llvm: LLVMWrapper, oracle: SecurityOracle,
                 threshold: float = SECURITY_THRESHOLD, max_attempts: int = 50):
        super().__init__(llvm, oracle, threshold)
        self.max_attempts = max_attempts
        self.available_passes = APPROVED_PASSES.copy()
        random.shuffle(self.available_passes)
        self.attempt_count = 0
    
    def select_pass(self, ir_file: str, baseline_score: float) -> Optional[str]:
        """Select random pass from remaining options"""
        if not self.available_passes or self.attempt_count >= self.max_attempts:
            return None
        
        # Try passes in random order
        pass_name = self.available_passes.pop(0)
        self.attempt_count += 1
        
        return pass_name


class GreedySelector(PassSelector):
    """Greedily select pass with maximum size reduction while preserving security"""
    
    def __init__(self, llvm: LLVMWrapper, oracle: SecurityOracle,
                 threshold: float = SECURITY_THRESHOLD, max_iterations: int = MAX_ITERATIONS):
        super().__init__(llvm, oracle, threshold)
        self.max_iterations = max_iterations
        self.iteration = 0
        self.available_passes = APPROVED_PASSES.copy()
    
    def select_pass(self, ir_file: str, baseline_score: float) -> Optional[str]:
        """
        Select pass that gives best size reduction without violating security
        
        Returns:
            Best pass name or None
        """
        if self.iteration >= self.max_iterations:
            return None
        
        self.iteration += 1
        
        current_ir = read_ir_file(ir_file)
        current_size = self.llvm.count_instructions(ir_file)
        current_score, _ = self.oracle.analyze(current_ir)
        
        best_pass = None
        best_reduction = 0
        
        # Try each available pass
        for pass_name in self.available_passes:
            try:
                # Apply pass to temporary file
                import tempfile
                import os
                fd, temp_file = tempfile.mkstemp(suffix=".ll")
                os.close(fd)
                
                # Copy current IR
                shutil.copy(ir_file, temp_file)
                
                # Apply pass
                output_file = self.llvm.apply_pass(temp_file, pass_name)
                
                # Check security
                new_ir = read_ir_file(output_file)
                new_score, _ = self.oracle.analyze(new_ir)
                
                # Check if safe
                if not self.oracle.is_violation(baseline_score, new_score, self.threshold):
                    # Calculate size reduction
                    new_size = self.llvm.count_instructions(output_file)
                    reduction = current_size - new_size
                    
                    if reduction > best_reduction:
                        best_reduction = reduction
                        best_pass = pass_name
                
                # Clean up
                os.remove(temp_file)
                if output_file != temp_file:
                    os.remove(output_file)
                    
            except Exception as e:
                # Pass failed, skip it
                continue
        
        if best_pass is None:
            # No beneficial pass found
            return None
        
        return best_pass


def optimize_with_selector(c_file: str, selector_type: str = "greedy",
                           output_ll: Optional[str] = None,
                           max_passes: int = 50,
                           verbose: bool = False) -> Tuple[str, dict]:
    """
    Optimize C file using selected strategy
    
    Args:
        c_file: Input C source file
        selector_type: "random", "greedy"
        output_ll: Output IR file
        max_passes: Maximum passes to apply
        verbose: Print progress
    
    Returns:
        (output_file, optimization_report)
    """
    llvm = LLVMWrapper()
    oracle = SecurityOracle()
    
    # Compile to IR
    import tempfile
    import os
    fd, ir_file = tempfile.mkstemp(suffix=".ll")
    os.close(fd)
    
    if verbose:
        print(f"Compiling {c_file} to IR...")
    llvm.compile_to_ir_stripped(c_file, ir_file, opt_level="0")
    
    # Get baseline security score
    baseline_ir = read_ir_file(ir_file)
    baseline_score, baseline_checks = oracle.analyze(baseline_ir)
    baseline_size = llvm.count_instructions(ir_file)
    
    if verbose:
        print(f"Baseline: {baseline_size} instructions, security score: {baseline_score:.1f}")
    
    # Initialize selector
    if selector_type == "random":
        selector = RandomSafeSelector(llvm, oracle)
    elif selector_type == "greedy":
        selector = GreedySelector(llvm, oracle)
    else:
        raise ValueError(f"Unknown selector type: {selector_type}")
    
    # Optimization loop
    applied_passes = []
    rejected_passes = []
    
    for i in range(max_passes):
        # Select pass
        pass_name = selector.select_pass(ir_file, baseline_score)
        
        if pass_name is None:
            if verbose:
                print("No more beneficial passes")
            break
        
        # Apply pass
        try:
            fd_new, new_ir_file = tempfile.mkstemp(suffix=".ll")
            os.close(fd_new)
            
            llvm.apply_pass(ir_file, pass_name, new_ir_file)
            
            # Check security
            new_ir = read_ir_file(new_ir_file)
            new_score, new_checks = oracle.analyze(new_ir)
            
            if oracle.is_violation(baseline_score, new_score):
                # Violation - reject
                rejected_passes.append({
                    "pass": pass_name,
                    "reason": f"Removed {len(baseline_checks) - len(new_checks)} checks"
                })
                if verbose:
                    print(f"  ✗ {pass_name} (security violation)")
                os.remove(new_ir_file)
            else:
                # Safe - accept
                new_size = llvm.count_instructions(new_ir_file)
                reduction = baseline_size - new_size
                applied_passes.append({
                    "pass": pass_name,
                    "size_before": llvm.count_instructions(ir_file),
                    "size_after": new_size,
                    "reduction": reduction
                })
                if verbose:
                    print(f"  ✓ {pass_name} ({ir_file} → {new_size} inst)")
                
                # Update current IR
                os.remove(ir_file)
                ir_file = new_ir_file
        
        except Exception as e:
            if verbose:
                print(f"  ! {pass_name} failed: {e}")
            rejected_passes.append({
                "pass": pass_name,
                "reason": f"Error: {str(e)}"
            })
    
    # Final metrics
    final_size = llvm.count_instructions(ir_file)
    final_ir = read_ir_file(ir_file)
    final_score, final_checks = oracle.analyze(final_ir)
    
    # Copy to output
    if output_ll:
        shutil.copy(ir_file, output_ll)
    else:
        output_ll = ir_file
    
    report = {
        "selector": selector_type,
        "baseline_size": baseline_size,
        "final_size": final_size,
        "size_reduction": (baseline_size - final_size) / baseline_size * 100,
        "baseline_score": baseline_score,
        "final_score": final_score,
        "security_preservation": final_score / baseline_score * 100 if baseline_score > 0 else 100,
        "applied_passes": applied_passes,
        "rejected_passes": rejected_passes,
        "num_applied": len(applied_passes),
        "num_rejected": len(rejected_passes),
    }
    
    return output_ll, report
