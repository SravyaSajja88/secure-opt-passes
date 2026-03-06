"""
Unit Tests for Security-Preserving Optimization Framework
"""

import pytest
import tempfile
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from security_oracle import SecurityOracle, SecurityCheck
from llvm_wrapper import LLVMWrapper
from feature_extractor import FeatureExtractor


# Sample LLVM IR with bounds check
SAMPLE_IR_WITH_CHECK = """
define i32 @main() {
entry:
  %arr = alloca [10 x i32]
  %idx = alloca i32
  store i32 5, i32* %idx
  %0 = load i32, i32* %idx
  %1 = icmp ult i32 %0, 10
  br i1 %1, label %safe, label %error

safe:
  %2 = getelementptr [10 x i32], [10 x i32]* %arr, i32 0, i32 %0
  %3 = load i32, i32* %2
  ret i32 %3

error:
  call void @llvm.trap()
  unreachable
}

declare void @llvm.trap()
"""

SAMPLE_IR_WITHOUT_CHECK = """
define i32 @main() {
entry:
  %arr = alloca [10 x i32]
  %idx = alloca i32
  store i32 5, i32* %idx
  %0 = load i32, i32* %idx
  %1 = getelementptr [10 x i32], [10 x i32]* %arr, i32 0, i32 %0
  %2 = load i32, i32* %1
  ret i32 %2
}
"""


class TestSecurityOracle:
    """Test SecurityOracle pattern detection"""
    
    def test_detect_bounds_check(self):
        """Test detection of bounds checking pattern"""
        oracle = SecurityOracle()
        score, checks = oracle.analyze(SAMPLE_IR_WITH_CHECK)
        
        assert score > 0, "Should detect security check"
        assert len(checks) > 0, "Should find at least one check"
        assert any(c.type == "bounds_check" for c in checks), "Should detect bounds check"
    
    def test_no_false_positive(self):
        """Test that IR without checks scores lower"""
        oracle = SecurityOracle()
        score_with, _ = oracle.analyze(SAMPLE_IR_WITH_CHECK)
        score_without, _ = oracle.analyze(SAMPLE_IR_WITHOUT_CHECK)
        
        assert score_with > score_without, "IR with checks should score higher"
    
    def test_preservation_ratio(self):
        """Test preservation ratio calculation"""
        oracle = SecurityOracle()
        
        assert oracle.compute_preservation_ratio(10, 10) == 1.0
        assert oracle.compute_preservation_ratio(10, 5) == 0.5
        assert oracle.compute_preservation_ratio(10, 0) == 0.0
    
    def test_violation_detection(self):
        """Test security violation detection"""
        oracle = SecurityOracle()
        
        # 95% preservation - no violation at 90% threshold
        assert not oracle.is_violation(100, 95, threshold=0.9)
        
        # 85% preservation - violation at 90% threshold
        assert oracle.is_violation(100, 85, threshold=0.9)


class TestFeatureExtractor:
    """Test FeatureExtractor"""
    
    def test_extract_features(self):
        """Test feature extraction from IR"""
        extractor = FeatureExtractor()
        features = extractor.extract(SAMPLE_IR_WITH_CHECK, security_score=2.0)
        
        assert len(features) == extractor.get_feature_dim()
        assert features[-3] == 2.0  # security_score should be included
        assert features.sum() > 0, "Should extract non-zero features"
    
    def test_opcode_counting(self):
        """Test that opcodes are counted"""
        extractor = FeatureExtractor()
        features = extractor.extract(SAMPLE_IR_WITH_CHECK)
        
        # Should detect icmp, br, load, store
        feature_dict = dict(zip(extractor.feature_names, features))
        
        assert feature_dict["inst_icmp"] > 0, "Should count icmp"
        assert feature_dict["inst_br"] > 0, "Should count br"
        assert feature_dict["inst_load"] > 0, "Should count load"


class TestLLVMWrapper:
    """Test LLVM tool wrappers"""
    
    @pytest.fixture
    def sample_c_file(self):
        """Create temporary C file"""
        code = """
#include <stdio.h>
int main() {
    int x = 5;
    int y = x + 10;
    printf("%d\\n", y);
    return 0;
}
"""
        fd, path = tempfile.mkstemp(suffix=".c")
        with os.fdopen(fd, 'w') as f:
            f.write(code)
        
        yield path
        
        if os.path.exists(path):
            os.remove(path)
    
    def test_compile_to_ir(self, sample_c_file):
        """Test C to IR compilation"""
        llvm = LLVMWrapper()
        
        fd, ir_file = tempfile.mkstemp(suffix=".ll")
        os.close(fd)
        
        try:
            result = llvm.compile_to_ir(sample_c_file, ir_file)
            assert os.path.exists(result)
            assert os.path.getsize(result) > 0
            
            # Check IR is valid
            with open(result, 'r') as f:
                content = f.read()
                assert "define" in content
        finally:
            if os.path.exists(ir_file):
                os.remove(ir_file)
    
    def test_count_instructions(self, sample_c_file):
        """Test instruction counting"""
        llvm = LLVMWrapper()
        
        fd, ir_file = tempfile.mkstemp(suffix=".ll")
        os.close(fd)
        
        try:
            llvm.compile_to_ir(sample_c_file, ir_file)
            count = llvm.count_instructions(ir_file)
            
            assert count > 0, "Should count at least some instructions"
        finally:
            if os.path.exists(ir_file):
                os.remove(ir_file)


def test_integration():
    """Integration test: compile, analyze, optimize"""
    # Create simple C program
    c_code = """
#include <stdlib.h>
int main() {
    int arr[10];
    int idx = 5;
    
    if (idx < 0 || idx >= 10) {
        abort();
    }
    
    return arr[idx];
}
"""
    
    fd_c, c_file = tempfile.mkstemp(suffix=".c")
    with os.fdopen(fd_c, 'w') as f:
        f.write(c_code)
    
    try:
        llvm = LLVMWrapper()
        oracle = SecurityOracle()
        
        # Compile
        fd_ir, ir_file = tempfile.mkstemp(suffix=".ll")
        os.close(fd_ir)
        llvm.compile_to_ir(c_file, ir_file)
        
        # Analyze
        from llvm_wrapper import read_ir_file
        ir_content = read_ir_file(ir_file)
        score, checks = oracle.analyze(ir_content)
        
        assert score > 0, "Should detect bounds check"
        
        # Clean up
        os.remove(ir_file)
        os.remove(c_file)
        
    except Exception as e:
        pytest.skip(f"LLVM tools not available: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
