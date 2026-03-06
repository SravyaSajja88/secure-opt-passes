"""
Feature Extraction from LLVM IR
Converts IR into numerical feature vectors for ML models
"""

import re
import numpy as np
from typing import Dict, List


class FeatureExtractor:
    """Extract features from LLVM IR for ML models"""
    
    # Common LLVM opcodes to track
    OPCODES = [
        'add', 'sub', 'mul', 'div', 'rem',  # Arithmetic
        'and', 'or', 'xor', 'shl', 'lshr',  # Bitwise
        'icmp', 'fcmp',  # Comparison
        'br', 'switch', 'ret',  # Control flow
        'load', 'store', 'alloca',  # Memory
        'call', 'invoke',  # Function calls
        'phi', 'select',  # SSA
        'getelementptr',  # Pointer arithmetic
    ]
    
    def __init__(self):
        self.feature_names = self._build_feature_names()
    
    def _build_feature_names(self) -> List[str]:
        """Build list of feature names"""
        names = []
        
        # Instruction counts per opcode
        for opcode in self.OPCODES:
            names.append(f"inst_{opcode}")
        
        # CFG metrics
        names.extend([
            "num_basic_blocks",
            "num_functions",
            "num_branches",
            "num_loops_estimated",
        ])
        
        # Memory operations
        names.extend([
            "num_loads",
            "num_stores",
            "num_allocas",
        ])
        
        # Call graph
        names.extend([
            "num_calls",
            "num_intrinsics",
        ])
        
        # Security-related
        names.extend([
            "security_score",
            "num_icmp",
            "num_traps",
        ])
        
        return names
    
    def extract(self, ir_content: str, security_score: float = 0.0) -> np.ndarray:
        """
        Extract feature vector from IR
        
        Args:
            ir_content: LLVM IR text
            security_score: Pre-computed security score
        
        Returns:
            Feature vector (numpy array)
        """
        features = {}
        
        # Count instructions by opcode
        for opcode in self.OPCODES:
            features[f"inst_{opcode}"] = self._count_opcode(ir_content, opcode)
        
        # CFG metrics
        features["num_basic_blocks"] = self._count_basic_blocks(ir_content)
        features["num_functions"] = self._count_functions(ir_content)
        features["num_branches"] = features["inst_br"]
        features["num_loops_estimated"] = self._estimate_loops(ir_content)
        
        # Memory operations
        features["num_loads"] = features["inst_load"]
        features["num_stores"] = features["inst_store"]
        features["num_allocas"] = features["inst_alloca"]
        
        # Call graph
        features["num_calls"] = features["inst_call"]
        features["num_intrinsics"] = self._count_intrinsics(ir_content)
        
        # Security
        features["security_score"] = security_score
        features["num_icmp"] = features["inst_icmp"]
        features["num_traps"] = self._count_pattern(ir_content, r'@llvm\.trap\(')
        
        # Convert to numpy array in consistent order
        vector = np.array([features.get(name, 0.0) for name in self.feature_names], 
                         dtype=np.float32)
        
        return vector
    
    def _count_opcode(self, ir: str, opcode: str) -> int:
        """Count occurrences of an opcode"""
        # Match opcode as whole word (with word boundaries)
        pattern = rf'\b{opcode}\b'
        return len(re.findall(pattern, ir, re.IGNORECASE))
    
    def _count_pattern(self, ir: str, pattern: str) -> int:
        """Count regex pattern matches"""
        return len(re.findall(pattern, ir))
    
    def _count_basic_blocks(self, ir: str) -> int:
        """Count basic blocks (labels)"""
        # Basic blocks are labeled entries
        lines = ir.split('\n')
        count = 0
        for line in lines:
            line = line.strip()
            # Labels end with ':'
            if line and line.endswith(':') and not line.startswith(';'):
                count += 1
        return count
    
    def _count_functions(self, ir: str) -> int:
        """Count function definitions"""
        return self._count_pattern(ir, r'define\s+')
    
    def _estimate_loops(self, ir: str) -> int:
        """Estimate number of loops (heuristic: back edges in CFG)"""
        # Simple heuristic: count branches to earlier labels
        # This is approximate but sufficient for features
        lines = ir.split('\n')
        labels = set()
        branches_back = 0
        
        for line in lines:
            line = line.strip()
            # Track labels
            if line.endswith(':') and not line.startswith(';'):
                label = line[:-1].strip()
                labels.add(label)
            # Check branches
            if 'br ' in line:
                # Extract label names
                parts = line.split()
                for part in parts:
                    if part.startswith('%') and part.rstrip(',') in labels:
                        branches_back += 1
        
        return branches_back // 2  # Approximate (back edges counted multiple times)
    
    def _count_intrinsics(self, ir: str) -> int:
        """Count LLVM intrinsic function calls"""
        return self._count_pattern(ir, r'@llvm\.')
    
    def get_feature_dim(self) -> int:
        """Get feature vector dimensionality"""
        return len(self.feature_names)
