"""
Security Oracle
Detects and quantifies security-relevant patterns in LLVM IR
"""

import re
from typing import Dict, List, Tuple
from dataclasses import dataclass
from config import PATTERN_WEIGHTS


@dataclass
class SecurityCheck:
    """Represents a detected security check"""
    type: str  # "bounds_check", "null_check", "sanitizer", "assertion"
    location: str  # Line number or label
    pattern: str  # Matched pattern snippet
    weight: float  # Importance weight


class SecurityOracle:
    """
    Analyzes LLVM IR for security-critical patterns
    """
    
    def __init__(self, weights: Dict[str, float] = None):
        self.weights = weights or PATTERN_WEIGHTS
    
    def analyze(self, ir_content: str) -> Tuple[float, List[SecurityCheck]]:
        """
        Analyze IR and compute security score
        
        Args:
            ir_content: LLVM IR text
        
        Returns:
            (security_score, list of detected checks)
        """
        checks = []
        
        # Detect bounds checks
        checks.extend(self._detect_bounds_checks(ir_content))
        
        # Detect null pointer checks
        checks.extend(self._detect_null_checks(ir_content))
        
        # Detect sanitizer calls
        checks.extend(self._detect_sanitizer_calls(ir_content))
        
        # Detect assertions and traps
        checks.extend(self._detect_assertions(ir_content))
        
        # Compute total score
        score = sum(check.weight for check in checks)
        
        return score, checks
    
    def _detect_bounds_checks(self, ir: str) -> List[SecurityCheck]:
        checks = []
        lines = ir.split('\n')
        
        for i, line in enumerate(lines):
            if 'icmp' in line and ('ult' in line or 'slt' in line or 'uge' in line or 'sge' in line):
                # Look further — abort block can be 20+ lines away in real IR
                for j in range(i+1, min(i+30, len(lines))):  # ← was min(i+5)
                    if 'br i1' in lines[j]:
                        for k in range(j+1, min(j+30, len(lines))):  # ← was min(j+10)
                            if 'llvm.trap' in lines[k] or '@abort' in lines[k] or 'unreachable' in lines[k]:
                                checks.append(SecurityCheck(
                                    type="bounds_check",
                                    location=f"line {i}",
                                    pattern=line.strip(),
                                    weight=self.weights.get("bounds_check", 2.0)
                                ))
                                break
                        break
        return checks

    
    def _detect_null_checks(self, ir: str) -> List[SecurityCheck]:
        """
        Detect null pointer checks
        
        Pattern:
          %cmp = icmp eq ptr %ptr, null
          br i1 %cmp, label %error, label %ok
        """
        checks = []
        lines = ir.split('\n')
        
        for i, line in enumerate(lines):
            if 'icmp' in line and 'null' in line:
                checks.append(SecurityCheck(
                    type="null_check",
                    location=f"line {i}",
                    pattern=line.strip(),
                    weight=self.weights.get("null_check", 1.5)
                ))
        
        return checks
    
    def _detect_sanitizer_calls(self, ir: str) -> List[SecurityCheck]:
        """
        Detect runtime sanitizer calls (UBSan, ASan)
        
        Patterns:
          call void @__ubsan_handle_*
          call void @__asan_*
        """
        checks = []
        lines = ir.split('\n')
        
        sanitizer_patterns = [
            r'__ubsan_handle_',
            r'__asan_',
            r'__msan_',
            r'__tsan_'
        ]
        
        for i, line in enumerate(lines):
            for pattern in sanitizer_patterns:
                if re.search(pattern, line):
                    checks.append(SecurityCheck(
                        type="sanitizer_call",
                        location=f"line {i}",
                        pattern=line.strip(),
                        weight=self.weights.get("sanitizer_call", 1.0)
                    ))
                    break
        
        return checks
    
    def _detect_assertions(self, ir: str) -> List[SecurityCheck]:
        checks = []
        lines = ir.split('\n')
        
        assertion_patterns = [
            r'@llvm\.trap\(',
            r'@abort\(',
            r'@__assert_fail\(',
            r'@exit\(',
        ]
        
        for i, line in enumerate(lines):
            for pattern in assertion_patterns:
                if re.search(pattern, line):
                    # REMOVE the is_near_icmp skip — it was discarding all valid abort() calls
                    # Only count assertions NOT already counted as bounds checks
                    # Simple dedup: count standalone aborts (not preceded by icmp within 3 lines)
                    is_standalone = True
                    for j in range(max(0, i-3), i):
                        if 'icmp' in lines[j]:
                            is_standalone = False
                            break
                    
                    if is_standalone:
                        checks.append(SecurityCheck(
                            type="assertion",
                            location=f"line {i}",
                            pattern=line.strip(),
                            weight=self.weights.get("assertion", 1.0)
                        ))
                    break
        return checks
    def is_violation(self, original_score: float, optimized_score: float,
                 threshold: float = 0.9) -> bool:
        if original_score == 0:
            return False  
        ratio = self.compute_preservation_ratio(original_score, optimized_score)
        return ratio < threshold


def format_security_report(original_score: float, 
                           optimized_score: float,
                           original_checks: List[SecurityCheck],
                           optimized_checks: List[SecurityCheck],
                           threshold: float = 0.9) -> str:
    """
    Generate human-readable security report
    """
    oracle = SecurityOracle()
    ratio = oracle.compute_preservation_ratio(original_score, optimized_score)
    violation = oracle.is_violation(original_score, optimized_score, threshold)
    
    report = []
    report.append("=" * 60)
    report.append("SECURITY ANALYSIS REPORT")
    report.append("=" * 60)
    report.append(f"Original Security Score:   {original_score:.1f}")
    report.append(f"Optimized Security Score:  {optimized_score:.1f}")
    report.append(f"Preservation Ratio:        {ratio*100:.1f}%")
    report.append(f"Threshold:                 {threshold*100:.1f}%")
    report.append(f"Violation Detected:        {'YES ⚠' if violation else 'NO ✓'}")
    report.append("")
    
    if len(original_checks) > 0:
        report.append(f"Original Checks Detected: {len(original_checks)}")
        check_types = {}
        for check in original_checks:
            check_types[check.type] = check_types.get(check.type, 0) + 1
        for ctype, count in check_types.items():
            report.append(f"  - {ctype}: {count}")
    
    if violation and len(original_checks) > len(optimized_checks):
        removed = len(original_checks) - len(optimized_checks)
        report.append("")
        report.append(f"⚠ WARNING: {removed} security check(s) removed!")
    
    report.append("=" * 60)
    
    return "\n".join(report)
