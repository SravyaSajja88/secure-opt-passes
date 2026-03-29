"""
Enhanced RL Environment for LLVM Optimization
Gymnasium-compatible environment with proper state representation and reward shaping
"""

import gymnasium as gym
import numpy as np
import tempfile
import os
import shutil
from typing import Tuple, Dict, Any, List
from llvm_wrapper import LLVMWrapper, read_ir_file
from security_oracle import SecurityOracle
from feature_extractor import FeatureExtractor
from config import APPROVED_PASSES, SECURITY_THRESHOLD, LAMBDA_PENALTY, MAX_PASSES


class LLVMOptimizationEnv(gym.Env):
    """
    Gymnasium environment for security-aware LLVM optimization
    
    State: IR features + security score
    Action: Select one optimization pass
    Reward: Size reduction - penalty for security violations
    """
    
    def __init__(self, 
                 ir_file: str,
                 baseline_score: float,
                 max_steps: int = MAX_PASSES,
                 lambda_penalty: float = LAMBDA_PENALTY,
                 threshold: float = SECURITY_THRESHOLD,
                 alpha: float = 1.0):
        """
        Args:
            ir_file: Initial LLVM IR file
            baseline_score: Original security score
            max_steps: Maximum optimization passes
            lambda_penalty: Security violation penalty weight
            threshold: Security preservation threshold
            alpha: Performance reward weight
        """
        super().__init__()
        
        self.llvm = LLVMWrapper()
        self.oracle = SecurityOracle()
        self.extractor = FeatureExtractor()
        
        self.baseline_ir_file = ir_file
        self.baseline_score = baseline_score
        self.max_steps = max_steps
        self.lambda_penalty = lambda_penalty
        self.threshold = threshold
        self.alpha = alpha
        
        # Action space: select one pass
        self.action_space = gym.spaces.Discrete(len(APPROVED_PASSES))
        self.pass_names = APPROVED_PASSES
        
        # Enhanced state space: IR features + history + metadata
        ir_feature_dim = self.extractor.get_feature_dim()
        history_dim = len(APPROVED_PASSES) + 8  # Pass counts + episode info + security + reward stats
        self.state_dim = ir_feature_dim + history_dim
        
        self.observation_space = gym.spaces.Box(
            low=-np.inf, high=np.inf, shape=(self.state_dim,), dtype=np.float32
        )
        
        # Episode state
        self.current_ir_file = None
        self.current_size = 0
        self.current_score = 0
        self.baseline_size = 0
        self.step_count = 0
        self.applied_passes = []
        self.pass_application_count = np.zeros(len(APPROVED_PASSES))
        self.recent_rewards = []
        self.cumulative_reward = 0.0
        self.temp_files = []
    
    def reset(self, seed=None, options=None) -> Tuple[np.ndarray, Dict]:
        """Reset environment to initial state"""
        super().reset(seed=seed)
        
        # Clean up old temp files
        self._cleanup_temp_files()
        
        # Copy baseline IR to new temp file
        fd, self.current_ir_file = tempfile.mkstemp(suffix=".ll")
        os.close(fd)
        shutil.copy(self.baseline_ir_file, self.current_ir_file)
        self.temp_files.append(self.current_ir_file)
        
        # Initialize state
        ir_content = read_ir_file(self.current_ir_file)
        self.current_score, _ = self.oracle.analyze(ir_content)
        self.current_size = self.llvm.count_instructions(self.current_ir_file)
        self.baseline_size = self.current_size
        self.step_count = 0
        self.applied_passes = []
        self.pass_application_count = np.zeros(len(APPROVED_PASSES))
        self.recent_rewards = []
        
        # Extract features with enhanced state
        state = self._get_enhanced_state(ir_content)
        
        return state, {}
    
    def step(self, action: int) -> Tuple[np.ndarray, float, bool, bool, Dict]:
        """
        Apply selected optimization pass with improved reward shaping
        
        Args:
            action: Pass index
        
        Returns:
            (next_state, reward, terminated, truncated, info)
        """
        pass_name = self.pass_names[action]
        
        # Save previous state
        prev_size = self.current_size
        prev_score = self.current_score
        
        # Apply pass
        fd, new_ir_file = tempfile.mkstemp(suffix=".ll")
        os.close(fd)
        self.temp_files.append(new_ir_file)
        
        try:
            self.llvm.apply_pass(self.current_ir_file, pass_name, new_ir_file)
            
            # Analyze new state
            new_ir = read_ir_file(new_ir_file)
            new_score, _ = self.oracle.analyze(new_ir)
            new_size = self.llvm.count_instructions(new_ir_file)
            
            # Compute security metrics
            security_ratio = new_score / self.baseline_score if self.baseline_score > 0 else 1.0
            security_delta = new_score - prev_score
            
            # Check security violation
            violation = security_ratio < self.threshold
            
            # IMPROVED REWARD FUNCTION with gradient
            if violation:
                # Severe penalty proportional to violation severity
                violation_severity = self.threshold - security_ratio
                reward = -self.lambda_penalty * (1.0 + violation_severity)
                
                # Reject pass - rollback
                os.remove(new_ir_file)
                self.temp_files.remove(new_ir_file)
                info = {
                    "status": "rejected",
                    "reason": "security_violation",
                    "pass": pass_name,
                    "security_ratio": security_ratio,
                    "violation_severity": violation_severity
                }
            else:
                # Safe optimization - compute performance reward
                size_reduction = (prev_size - new_size) / self.baseline_size if self.baseline_size > 0 else 0.0
                perf_reward = 0.0
                
                if size_reduction > 0:
                    # Positive reduction - good!
                    perf_reward = self.alpha * size_reduction * 10
                    
                    # Bonus for maintaining high security
                    security_bonus = 0.1 if security_ratio >= 0.95 else 0.0
                    
                    reward = perf_reward + security_bonus
                elif size_reduction == 0:
                    # No change - small penalty for wasted effort
                    reward = -0.01
                else:
                    # Size increased (rare) - penalty
                    reward = -0.05
                
                # Update state
                self.current_ir_file = new_ir_file
                self.current_size = new_size
                self.current_score = new_score
                self.applied_passes.append(pass_name)
                self.pass_application_count[action] += 1
                
                info = {
                    "status": "accepted",
                    "pass": pass_name,
                    "size_reduction": size_reduction,
                    "security_ratio": security_ratio,
                    "perf_reward": perf_reward
                }
        
        except Exception as e:
            # Pass failed - moderate penalty
            reward = -0.5
            if os.path.exists(new_ir_file):
                os.remove(new_ir_file)
                if new_ir_file in self.temp_files:
                    self.temp_files.remove(new_ir_file)
            info = {"status": "error", "pass": pass_name, "error": str(e)}
        
        self.step_count += 1
        self.recent_rewards.append(reward)
        if len(self.recent_rewards) > 10:
            self.recent_rewards.pop(0)
        
        # Get new state with enhanced features
        ir_content = read_ir_file(self.current_ir_file)
        state = self._get_enhanced_state(ir_content)
        
        # Check termination
        terminated = False  # Episode doesn't end early (except below)
        truncated = self.step_count >= self.max_steps
        
        # Early termination if no improvement for several steps
        if len(self.recent_rewards) >= 10 and all(r <= 0 for r in self.recent_rewards[-5:]):
            terminated = True
            info["early_stop"] = "no_improvement"
        
        return state, reward, terminated, truncated, info
    
    def _get_enhanced_state(self, ir_content: str) -> np.ndarray:
        """
        Build enhanced state vector including optimization history
        
        State components:
        1. IR features (instruction counts, CFG metrics)
        2. Security features (scores, ratios)
        3. Optimization history (pass counts, progress)
        4. Recent performance (reward trends)
        """
        # Base IR features
        ir_features = self.extractor.extract(ir_content, self.current_score)
        
        # Security features (normalized)
        security_features = np.array([
            self.current_score / max(self.baseline_score, 1.0),  # Security ratio
            float(self.current_score >= self.baseline_score * self.threshold),  # Is safe?
        ], dtype=np.float32)
        
        # Optimization history
        history_features = np.array([
            self.step_count / self.max_steps,  # Progress
            self.current_size / max(self.baseline_size, 1.0),  # Size ratio
            len(self.applied_passes) / max(self.step_count, 1),  # Acceptance rate
        ], dtype=np.float32)
        
        # Pass application counts (normalized)
        pass_counts_normalized = self.pass_application_count / max(self.step_count, 1)
        
        # Recent reward statistics
        if len(self.recent_rewards) > 0:
            recent_reward_stats = np.array([
                np.mean(self.recent_rewards),
                np.std(self.recent_rewards) if len(self.recent_rewards) > 1 else 0.0,
                self.recent_rewards[-1] if len(self.recent_rewards) > 0 else 0.0,
            ], dtype=np.float32)
        else:
            recent_reward_stats = np.zeros(3, dtype=np.float32)
        
        # Concatenate all features
        state = np.concatenate([
            ir_features,
            security_features,
            history_features,
            pass_counts_normalized,
            recent_reward_stats,
        ]).astype(np.float32)
        
        # Pad or truncate to match observation space
        if len(state) < self.state_dim:
            state = np.pad(state, (0, self.state_dim - len(state)))
        elif len(state) > self.state_dim:
            state = state[:self.state_dim]
        
        return state
    
    def _cleanup_temp_files(self):
        """Remove temporary IR files"""
        for f in self.temp_files:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except:
                    pass
        self.temp_files = []
    
    def close(self):
        """Clean up resources"""
        self._cleanup_temp_files()
    
    def get_final_ir(self) -> str:
        """Get path to final optimized IR"""
        return self.current_ir_file
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get optimization metrics"""
        baseline_size = self.llvm.count_instructions(self.baseline_ir_file)
        
        return {
            "baseline_size": baseline_size,
            "final_size": self.current_size,
            "size_reduction": (baseline_size - self.current_size) / baseline_size * 100,
            "baseline_score": self.baseline_score,
            "final_score": self.current_score,
            "security_preservation": self.current_score / max(self.baseline_score, 1e-6) * 100 if self.baseline_score > 0 else 100,
            "num_passes_applied": len(self.applied_passes),
            "num_steps_taken": self.step_count,
            "applied_passes": self.applied_passes,
        }
