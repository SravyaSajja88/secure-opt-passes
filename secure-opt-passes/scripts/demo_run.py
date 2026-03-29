import sys
import os
import tempfile
from pathlib import Path

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from llvm_wrapper import LLVMWrapper
from security_oracle import SecurityOracle
from rl_agent import RLPassSelector
from evaluate_all import evaluate_method
from rl_environment import LLVMOptimizationEnv

def get_env_dims(c_file, llvm, oracle):
    fd, ir_dummy = tempfile.mkstemp(suffix=".ll")
    os.close(fd)
    llvm.compile_to_ir_stripped(c_file, ir_dummy, opt_level="0")
    
    with open(ir_dummy, 'r') as f:
        dummy_ir = f.read()
        
    dummy_score, _ = oracle.analyze(dummy_ir)
    env = LLVMOptimizationEnv(ir_dummy, dummy_score)
    state_dim = env.observation_space.shape[0]
    action_dim = env.action_space.n
    env.close()
    os.remove(ir_dummy)
    return state_dim, action_dim

def run_prof_demo():
    print("==================================================")
    print("🤖 SECURE AI OPTIMIZATION: FINAL PROJECT DEMO 🤖")
    print("==================================================\n")
    
    llvm = LLVMWrapper()
    oracle = SecurityOracle()
    
    c_file = "demo.c"
    print(f"[*] Analyzing input source code: {c_file}\n")
    
    current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    c_file_path = os.path.join(current_dir, c_file)
    
    if not os.path.exists(c_file_path):
        print(f"Error: Could not find {c_file_path}. Please create the demo.c file.")
        sys.exit(1)
    
    # Check for a model to load - checking local and WSL home directory
    model_dir = os.path.join(current_dir, "models")
    wsl_model_dir = "/home/sravya/secure-opt-passes/data/models"
    
    best_model_path = os.path.join(model_dir, "best_model.pt")
    final_model_path = os.path.join(model_dir, "rl_agent_final.pt")
    wsl_model_path = os.path.join(wsl_model_dir, "rl_dqn_v3.pt")
    
    model_to_use = None
    if os.path.exists(wsl_model_path):
        model_to_use = wsl_model_path
    elif os.path.exists(best_model_path):
        model_to_use = best_model_path
    elif os.path.exists(final_model_path):
        model_to_use = final_model_path
        
    if model_to_use is None:
        print(f"Error: Could not find a trained model ('best_model.pt' or 'rl_agent_final.pt') in {model_dir}")
        print("Please train the model first by running the rl training script.")
        agent = None
    else:
        # Load the RL Agent
        print(f"[*] Loading trained RL optimization policy from: {os.path.basename(model_to_use)}...")
        
        state_dim, action_dim = get_env_dims(c_file_path, llvm, oracle)
        
        agent = RLPassSelector(state_dim=state_dim, action_dim=action_dim, device="cpu") 
        agent.load(model_to_use) 
    
    # 2. Run Evaluations
    print("--- 1. BASELINE (Unoptimized O0) ---")
    res_o0 = evaluate_method(c_file_path, "O0", llvm, oracle, None)
    if res_o0:
        print(f"Instruction Count: {res_o0['final_size']}")
        print(f"Security Score:    {res_o0['final_score']:.1f} (100% Reference)\n")
    else:
        print("Failed to evaluate O0 baseline")
    
    print("--- 2. TRADITIONAL COMPILER (O3) ---")
    res_o3 = evaluate_method(c_file_path, "O3", llvm, oracle, None)
    if res_o3:
        print(f"Instruction Count: {res_o3['final_size']} (Reduced by {res_o3['size_reduction']:.1f}%)")
        print(f"Security Score:    {res_o3['final_score']:.1f} (Security degraded to {res_o3['security_preservation']:.1f}%)\n")
    else:
        print("Failed to evaluate O3 optimization")
    
    if agent is not None:
        print("--- 3. AI REINFORCEMENT LEARNING AGENT ---")
        res_rl = evaluate_method(c_file_path, "rl", llvm, oracle, agent)
        if res_rl:
            print(f"Instruction Count: {res_rl['final_size']} (Reduced by {res_rl['size_reduction']:.1f}%)")
            print(f"Security Score:    {res_rl['final_score']:.1f} (Security maintained at {res_rl['security_preservation']:.1f}%)\n")
        else:
            print("Failed to evaluate RL optimization")
    
    print("==================================================")
    print("✅ CONCLUSION: ")
    print("The Demo shows the difference between traditional compiler")
    print("optimization vs RL Agent secure optimization strategy!")
    print("==================================================")

if __name__ == "__main__":
    run_prof_demo()
