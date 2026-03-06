"""
LLVM Tool Wrappers
Provides clean interfaces to clang, opt, and other LLVM utilities
"""

import subprocess
import os
import tempfile
from typing import Optional, List, Tuple
from config import CLANG_PATH, OPT_PATH


class LLVMWrapper:
    """Wrapper for LLVM command-line tools"""
    
    def __init__(self, clang_path: str = CLANG_PATH, opt_path: str = OPT_PATH):
        self.clang = clang_path
        self.opt = opt_path
        self._verify_tools()
    
    def _verify_tools(self):
        """Check that LLVM tools are available"""
        try:
            subprocess.run([self.clang, "--version"], 
                         capture_output=True, check=True, timeout=5)
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            # Try without version suffix
            try:
                self.clang = "clang"
                subprocess.run([self.clang, "--version"], 
                             capture_output=True, check=True, timeout=5)
            except:
                raise RuntimeError(
                    f"Could not find clang. Please install LLVM/Clang 14+ or set CLANG_PATH in config.py"
                )
        
        try:
            subprocess.run([self.opt, "--version"], 
                         capture_output=True, check=True, timeout=5)
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            try:
                self.opt = "opt"
                subprocess.run([self.opt, "--version"], 
                             capture_output=True, check=True, timeout=5)
            except:
                raise RuntimeError(
                    f"Could not find opt. Please install LLVM/Clang 14+ or set OPT_PATH in config.py"
                )
    
    def compile_to_ir(self, c_file: str, output_ll: Optional[str] = None, 
                      opt_level: str = "0") -> str:
        """
        Compile C source to LLVM IR
        
        Args:
            c_file: Path to C source file
            output_ll: Output .ll file (if None, creates temp file)
            opt_level: Optimization level ("0", "1", "2", "3")
        
        Returns:
            Path to generated .ll file
        """
        if not os.path.exists(c_file):
            raise FileNotFoundError(f"Source file not found: {c_file}")
        
        if output_ll is None:
            fd, output_ll = tempfile.mkstemp(suffix=".ll")
            os.close(fd)
        
        cmd = [
            self.clang,
            f"-O{opt_level}",
            "-S",               # Output assembly (IR)
            "-emit-llvm",       # Emit LLVM IR
            "-o", output_ll,
            c_file
        ]
        
        try:
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=30,
                check=True
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                f"Compilation failed:\n{e.stderr}"
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"Compilation timeout for {c_file}")
        
        return output_ll
    
    def compile_to_ir_stripped(self, c_file: str, output_ll: str, opt_level: str = "0") -> str:
        """Compile C to IR and strip optnone so passes can actually run"""
        self.compile_to_ir(c_file, output_ll, opt_level)
        with open(output_ll, 'r') as f:
            content = f.read()
        content = content.replace('optnone ', '')
        with open(output_ll, 'w') as f:
            f.write(content)
        return output_ll
    
    def apply_pass(self, input_ll: str, pass_name: str, 
                   output_ll: Optional[str] = None) -> str:
        """
        Apply a single LLVM optimization pass
        
        Args:
            input_ll: Input LLVM IR file
            pass_name: Name of pass (e.g., "dce", "gvn")
            output_ll: Output file (if None, overwrites input)
        
        Returns:
            Path to output file
        """
        if not os.path.exists(input_ll):
            raise FileNotFoundError(f"IR file not found: {input_ll}")
        
        if output_ll is None:
            fd, output_ll = tempfile.mkstemp(suffix=".ll")
            os.close(fd)
        
        # Modern LLVM uses -passes= syntax
        cmd = [
            self.opt,
            f"-passes={pass_name}",
            "-S",  # Output textual IR
            "-o", output_ll,
            input_ll
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                check=True
            )
        except subprocess.CalledProcessError as e:
            # Try legacy syntax for older LLVM versions
            cmd_legacy = [
                self.opt,
                f"-{pass_name}",
                "-S",
                "-o", output_ll,
                input_ll
            ]
            try:
                result = subprocess.run(
                    cmd_legacy,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    check=True
                )
            except subprocess.CalledProcessError as e2:
                raise RuntimeError(
                    f"Pass application failed:\nNew syntax: {e.stderr}\nLegacy syntax: {e2.stderr}"
                )
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"Pass {pass_name} timeout")
        
        return output_ll
    
    def verify_ir(self, ll_file: str) -> bool:
        """
        Verify that IR is well-formed
        
        Args:
            ll_file: Path to .ll file
        
        Returns:
            True if valid, False otherwise
        """
        cmd = [self.opt, "-verify", "-S", "-o", "/dev/null", ll_file]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10,
                check=True
            )
            return True
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return False
    
    def count_instructions(self, ll_file: str) -> int:
        """
        Count total instructions in IR file
        
        Args:
            ll_file: Path to .ll file
        
        Returns:
            Instruction count
        """
        with open(ll_file, 'r') as f:
            content = f.read()
        
        # Count lines that look like instructions (simple heuristic)
        lines = content.split('\n')
        count = 0
        for line in lines:
            line = line.strip()
            # Skip empty, comments, labels, metadata
            if not line or line.startswith(';') or line.startswith('!') or line.endswith(':'):
                continue
            # Skip declarations and definitions
            if line.startswith('define ') or line.startswith('declare ') or line.startswith('attributes'):
                continue
            if line.startswith('}') or line.startswith('{'):
                continue
            # Count as instruction
            if any(op in line for op in ['=', 'ret', 'br', 'call', 'store', 'load']):
                count += 1
        
        return count


def read_ir_file(ll_file: str) -> str:
    """Read LLVM IR file content"""
    with open(ll_file, 'r') as f:
        return f.read()


def write_ir_file(content: str, ll_file: str):
    """Write LLVM IR file"""
    with open(ll_file, 'w') as f:
        f.write(content)
