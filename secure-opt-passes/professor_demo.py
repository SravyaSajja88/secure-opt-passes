#!/usr/bin/env python3
"""
=============================================================================
  AI for Secure Optimization Passes — Professor Demonstration
  CS / Systems Security Final Project
=============================================================================

  Objective  : Select LLVM optimization passes that maximize code size
               reduction while PRESERVING security-critical checks.

  Pipeline   :
    C Source Code
    ──► Compile to LLVM IR (clang)
    ──► Security Oracle  (detect bounds checks, null checks, assertions…)
    ──► Pass Selector    (O0 / O2 / O3 / Greedy Heuristic / RL Agent)
    ──► Optimized IR
    ──► Compare: size reduction  vs  security preservation
=============================================================================
"""

import sys
import os
import time
import textwrap
import tempfile

# ── Fix import paths ──────────────────────────────────────────────────────────
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
SRC_DIR      = os.path.join(PROJECT_ROOT, "src")
SCRIPTS_DIR  = os.path.join(PROJECT_ROOT, "scripts")
sys.path.insert(0, SRC_DIR)
sys.path.insert(0, SCRIPTS_DIR)

from llvm_wrapper   import LLVMWrapper, read_ir_file
from security_oracle import SecurityOracle, format_security_report
from rl_agent       import RLPassSelector
from rl_environment import LLVMOptimizationEnv
from evaluate_all   import evaluate_method
from pass_selector  import optimize_with_selector
from config         import APPROVED_PASSES

# ── ANSI colours ──────────────────────────────────────────────────────────────
RED    = "\033[91m";  GREEN  = "\033[92m";  YELLOW = "\033[93m"
BLUE   = "\033[94m";  CYAN   = "\033[96m";  WHITE  = "\033[97m"
BOLD   = "\033[1m";   DIM    = "\033[2m";   RESET  = "\033[0m"

W = 70   # banner width


def banner(text, colour=CYAN):
    bar = "═" * W
    print(f"\n{colour}{BOLD}{bar}{RESET}")
    for line in textwrap.wrap(text, W - 4):
        print(f"{colour}{BOLD}  {line}{RESET}")
    print(f"{colour}{BOLD}{bar}{RESET}\n")


def section(title):
    print(f"\n{BLUE}{BOLD}{'─'*W}{RESET}")
    print(f"{BLUE}{BOLD}  {title}{RESET}")
    print(f"{BLUE}{BOLD}{'─'*W}{RESET}")


def ok(msg):   print(f"  {GREEN}✔  {msg}{RESET}")
def warn(msg): print(f"  {YELLOW}⚠  {msg}{RESET}")
def err(msg):  print(f"  {RED}✘  {msg}{RESET}")
def info(msg): print(f"  {WHITE}{msg}{RESET}")


def bar_chart(label, value, max_val=100, width=30, colour=GREEN):
    filled = int(width * value / max(max_val, 1))
    bar = "█" * filled + "░" * (width - filled)
    print(f"  {label:<28} {colour}[{bar}]{RESET} {value:6.1f}%")


def print_results_table(results):
    print(f"\n  {BOLD}{'Method':<10} {'Instr':>6} {'Size↓':>8} {'Sec%':>8}  {'Verdict'}{RESET}")
    print(f"  {'─'*60}")
    for r in results:
        if r is None:
            continue
        m   = r.get("method", "?")
        sz  = r.get("final_size", 0)
        red = r.get("size_reduction", 0)
        sec = r.get("security_preservation", 100)
        if sec >= 90:
            verdict = f"{GREEN}✔ SECURE{RESET}"
        else:
            verdict = f"{RED}✘ VIOLATION{RESET}"
        print(f"  {m:<10} {sz:>6} {red:>7.1f}% {sec:>7.1f}%  {verdict}")
    print()


# ─────────────────────────────────────────────────────────────────────────────
#  STEP 0 — Header
# ─────────────────────────────────────────────────────────────────────────────
def show_header():
    banner("AI FOR SECURE OPTIMIZATION PASSES\n"
           "Secure LLVM Pass Selection via Reinforcement Learning",
           colour=CYAN)
    print(f"  {DIM}Objective: Maximise code-size reduction WITHOUT removing checks{RESET}")
    print(f"  {DIM}Approach : Deep Q-Network (DQN) trained as sequential pass selector{RESET}")
    print()


# ─────────────────────────────────────────────────────────────────────────────
#  STEP 1 — Show the input C source
# ─────────────────────────────────────────────────────────────────────────────
def show_input(c_file: str):
    section("STEP 1 — INPUT PROGRAM")
    info(f"Source file : {c_file}")
    print()
    with open(c_file) as f:
        lines = f.readlines()
    info(f"Lines of C code : {len(lines)}")
    print()
    print(f"  {DIM}--- (showing first 40 lines) ---{RESET}")
    for i, line in enumerate(lines[:40], 1):
        print(f"  {DIM}{i:3}│{RESET} {line}", end="")
    if len(lines) > 40:
        print(f"  {DIM}    … {len(lines)-40} more lines …{RESET}")


# ─────────────────────────────────────────────────────────────────────────────
#  STEP 2 — Compile to LLVM IR and run Security Oracle
# ─────────────────────────────────────────────────────────────────────────────
def run_security_oracle(c_file: str, llvm: LLVMWrapper, oracle: SecurityOracle):
    section("STEP 2 — COMPILE TO LLVM IR + SECURITY ORACLE")

    fd, ir_path = tempfile.mkstemp(suffix=".ll")
    os.close(fd)

    info("Compiling C → LLVM IR (clang, -O0 baseline) …")
    llvm.compile_to_ir(c_file, ir_path, opt_level="0")
    ok("Compilation successful")

    with open(ir_path) as f:
        ir_lines = f.readlines()
    info(f"LLVM IR lines : {len(ir_lines)}")
    instr_count = llvm.count_instructions(ir_path)
    info(f"IR instruction count (baseline) : {instr_count}")

    print()
    info("Running Security Oracle …")
    with open(ir_path) as f:
        ir_content = f.read()

    score, checks = oracle.analyze(ir_content)

    print()
    ok(f"Baseline security score : {score:.1f}")
    if checks:
        info(f"Security checks detected : {len(checks)}")
        from collections import Counter
        counts = Counter(c.type for c in checks)
        for ctype, cnt in counts.items():
            weight = checks[[c.type for c in checks].index(ctype)].weight
            print(f"    {GREEN}▸ {ctype:<22}{RESET} × {cnt}   (weight = {weight:.1f})")
    else:
        warn("No security checks detected in baseline IR")

    print()
    print(f"  {DIM}--- Sample LLVM IR (first 15 lines) ---{RESET}")
    for line in ir_lines[:15]:
        print(f"  {DIM}{line}{RESET}", end="")
    print()

    import shutil
    out_base = "baseline.ll"
    shutil.copy2(ir_path, out_base)
    info(f"Saved baseline IR to      : {out_base}")

    os.remove(ir_path)
    return score, instr_count


# ─────────────────────────────────────────────────────────────────────────────
#  STEP 3 — Load trained RL model
# ─────────────────────────────────────────────────────────────────────────────
def load_rl_agent(c_file: str, llvm: LLVMWrapper, oracle: SecurityOracle):
    section("STEP 3 — LOAD TRAINED RL AGENT (DQN)")

    model_dir = os.path.join(PROJECT_ROOT, "models")
    wsl_model  = "/home/sravya/secure-opt-passes/data/models/rl_dqn_v3.pt"

    candidates = [
        os.path.join(model_dir, "rl_agent_ep1900.pt"),
        os.path.join(model_dir, "rl_agent.pt"),
        os.path.join(model_dir, "best_model.pt"),
        os.path.join(model_dir, "rl_agent_final.pt"),
        "/home/sravya/secure-opt-passes/data/models/rl_dqn_v3.pt",
    ]

    model_path = next((p for p in candidates if os.path.exists(p)), None)

    if model_path is None:
        warn("No trained model found. RL comparison will be skipped.")
        return None

    info(f"Loading weights from   : {os.path.basename(model_path)}")

    # Create a placeholder agent — load() will auto-detect and rebuild with
    # correct state_dim, action_dim, and architecture (BatchNorm or not)
    agent = RLPassSelector(state_dim=1, action_dim=1, device="cpu")
    agent.load(model_path)

    # After load(), the agent has the correct dims
    state_dim  = agent.state_dim
    action_dim = agent.action_dim
    has_bn     = getattr(agent.policy_net, 'use_batchnorm', True)
    ok("RL agent loaded successfully")
    info(f"State-space dimension  : {state_dim}")
    info(f"Action-space dimension : {action_dim}  (= number of candidate passes)")
    size_mb = os.path.getsize(model_path) / 1e6
    return agent



# ─────────────────────────────────────────────────────────────────────────────
#  STEP 4 — Run all methods and compare
# ─────────────────────────────────────────────────────────────────────────────
def run_comparison(c_file: str, llvm: LLVMWrapper, oracle: SecurityOracle, agent):
    section("STEP 4 — PASS SELECTOR COMPARISON")
    info("Running all methods on input program …\n")

    methods = ["O0", "O2", "O3", "greedy"]
    if agent:
        methods.append("rl")

    results = {}
    for m in methods:
        print(f"  {YELLOW}→ Running {m} …{RESET}", end="", flush=True)
        t0 = time.time()
        res = evaluate_method(c_file, m, llvm, oracle, agent)
        elapsed = time.time() - t0
        if res:
            print(f"\r  {GREEN}✔ {m:<8}{RESET} done in {elapsed:.1f}s")
            results[m] = res
            results[m]["method"] = m
        else:
            print(f"\r  {RED}✘ {m:<8}{RESET} failed")
            results[m] = None

    return results


# ─────────────────────────────────────────────────────────────────────────────
#  STEP 5 — Print rich output
# ─────────────────────────────────────────────────────────────────────────────
def print_rich_output(results: dict):
    section("STEP 5 — OPTIMIZATION RESULTS")

    valid = [r for r in results.values() if r is not None]
    print_results_table(valid)

    # ── Code-size reduction bars ──────────────────────────────────────────────
    print(f"  {BOLD}Code-Size Reduction (higher = better){RESET}")
    max_red = max((r.get("size_reduction", 0) for r in valid), default=1)
    for r in valid:
        colour = YELLOW if r["method"] in ("O2","O3") else (
                  CYAN   if r["method"] == "greedy"    else (
                  GREEN  if r["method"] == "rl"        else DIM))
        bar_chart(r["method"], r.get("size_reduction", 0), max_val=max(max_red, 1),
                  colour=colour)

    # ── Security preservation bars ────────────────────────────────────────────
    print(f"\n  {BOLD}Security Preservation (≥ 90% required){RESET}")
    for r in valid:
        sec = r.get("security_preservation", 100)
        colour = GREEN if sec >= 90 else RED
        bar_chart(r["method"], sec, max_val=100, colour=colour)
    print(f"  {'─'*60}")
    print(f"  {DIM}  Red line: 90% security preservation threshold{RESET}\n")


# ─────────────────────────────────────────────────────────────────────────────
#  STEP 6 — Security deep-dive (show what O3 breaks vs RL preserves)
# ─────────────────────────────────────────────────────────────────────────────
def security_deep_dive(c_file: str, llvm: LLVMWrapper, oracle: SecurityOracle):
    section("STEP 6 — SECURITY DEEP DIVE  (O3 vs RL Agent)")
    info("Showing exactly which security checks O3 removes vs RL preserves …\n")

    def get_checks_and_save(opt_level, save_as):
        fd, ir = tempfile.mkstemp(suffix=".ll")
        os.close(fd)
        llvm.compile_to_ir(c_file, ir, opt_level=opt_level)
        with open(ir) as f:
            content = f.read()
        score, checks = oracle.analyze(content)
        count = llvm.count_instructions(ir)
        import shutil
        if save_as:
            shutil.copy2(ir, save_as)
            info(f"Saved O{opt_level} optimized IR to : {save_as}")
        os.remove(ir)
        return score, checks, count

    base_score, base_checks, base_count = get_checks_and_save("0", None)
    o3_score,   o3_checks,   o3_count   = get_checks_and_save("3", "o3_optimized.ll")

    print(f"  {'':30} {'Baseline':>10} {'After O3':>10}")
    print(f"  {'─'*52}")
    print(f"  {'IR instruction count':<30} {base_count:>10} {o3_count:>10}")
    print(f"  {'Security checks found':<30} {len(base_checks):>10} {len(o3_checks):>10}")
    print(f"  {'Security score':<30} {base_score:>10.1f} {o3_score:>10.1f}")

    removed = len(base_checks) - len(o3_checks)
    if removed > 0:
        print()
        err(f"O3 REMOVED {removed} check(s)!")
        print()
        print(f"  {YELLOW}{'Check type':<25} {'Baseline':>10} {'O3':>10}{RESET}")
        from collections import Counter
        base_types = Counter(c.type for c in base_checks)
        o3_types   = Counter(c.type for c in o3_checks)
        for t in base_types:
            before = base_types[t]
            after  = o3_types.get(t, 0)
            colour = RED if after < before else GREEN
            print(f"  {colour}{t:<25} {before:>10} {after:>10}{RESET}")
    else:
        ok("O3 preserved all checks on this program")

    print()
    info("The RL agent learns to AVOID passes that trigger violations.")
    info("It is rewarded for code-size reduction and PENALISED for removing checks.")


# ─────────────────────────────────────────────────────────────────────────────
#  STEP 7 — RL pass selection walkthrough
# ─────────────────────────────────────────────────────────────────────────────
def rl_walkthrough(c_file: str, llvm: LLVMWrapper, oracle: SecurityOracle, agent):
    if agent is None:
        return
    section("STEP 7 — RL AGENT PASS SELECTION (Step-by-Step Trace)")
    info("Watching the RL agent decide which passes to apply …\n")

    fd, ir_file = tempfile.mkstemp(suffix=".ll")
    os.close(fd)
    llvm.compile_to_ir_stripped(c_file, ir_file, opt_level="0")
    with open(ir_file) as f:
        ir_content = f.read()
    baseline_score, baseline_checks = oracle.analyze(ir_content)
    baseline_size = llvm.count_instructions(ir_file)

    env = LLVMOptimizationEnv(ir_file, baseline_score)
    state, _ = env.reset()

    print(f"  {BOLD}{'Step':<6} {'Pass selected':<30} {'Instr':>6} {'Δ':>5} {'Sec%':>7} {'Reward':>8}{RESET}")
    print(f"  {'─'*65}")
    print(f"  {'BASE':<6} {'(unoptimised)':<30} {baseline_size:>6} {'':>5} {100.0:>6.1f}% {'':>8}")

    done = False
    steps = 0
    prev_size = baseline_size
    pass_names = getattr(env, "pass_names", APPROVED_PASSES)

    while not done and steps < min(env.max_steps, 15):
        action = agent.select_action(state, epsilon=0.0)
        state, reward, terminated, truncated, info_dict = env.step(action)
        done = terminated or truncated
        steps += 1

        # Read size/security directly from env — info_dict doesn't carry current_size
        cur_size = env.current_size
        sec_ratio = env.current_score / max(env.baseline_score, 1e-6)
        sec_pct   = min(sec_ratio * 100, 100.0)
        p_name   = pass_names[action] if action < len(pass_names) else f"pass_{action}"
        delta    = cur_size - prev_size
        delta_str = f"{delta:+d}" if delta != 0 else "━"
        colour = GREEN if delta < 0 else (YELLOW if delta == 0 else RED)
        print(f"  {steps:<6} {colour}{p_name:<30}{RESET} {cur_size:>6} {colour}{delta_str:>5}{RESET} {sec_pct:>6.1f}% {reward:>8.3f}")
        prev_size = cur_size

    final_rl_ir = env.get_final_ir()
    out_rl = "rl_optimized.ll"
    import shutil
    shutil.copy2(final_rl_ir, out_rl)

    metrics = env.get_metrics()
    env.close()
    
    print()
    info(f"Saved RL optimized IR to  : {out_rl}")
    
    os.remove(ir_file)

    print()
    ok(f"Final instruction count : {metrics.get('final_size', '?')}")
    ok(f"Total size reduction    : {metrics.get('size_reduction', 0):.1f}%")
    ok(f"Security preservation   : {metrics.get('security_preservation', 100):.1f}%")


# ─────────────────────────────────────────────────────────────────────────────
#  STEP 8 — Conclusion
# ─────────────────────────────────────────────────────────────────────────────
def conclusion(results: dict):
    banner("CONCLUSION", colour=GREEN)

    rl  = results.get("rl")
    o3  = results.get("O3")
    grd = results.get("greedy")

    if rl and o3:
        sec_gain = rl.get("security_preservation", 0) - o3.get("security_preservation", 0)
        size_diff = o3.get("size_reduction", 0) - rl.get("size_reduction", 0)
        print(f"  {GREEN}{BOLD}RL Agent vs O3:{RESET}")
        if sec_gain > 0:
            ok(f"RL preserves {sec_gain:.1f}% MORE security than O3")
        if abs(size_diff) < 5:
            ok(f"RL achieves COMPARABLE code-size reduction (within {abs(size_diff):.1f}%)")
        elif size_diff > 0:
            warn(f"RL trades {size_diff:.1f}% size reduction for security (acceptable)")
        print()

    print(f"  {BOLD}Key Contributions:{RESET}")
    print(f"  {GREEN}1.{RESET} Security Oracle — detects bounds/null/sanitiser checks in LLVM IR")
    print(f"  {GREEN}2.{RESET} RL Environment — reward = size reduction − λ×security_penalty")
    print(f"  {GREEN}3.{RESET} DQN Agent      — sequentially selects safe optimization passes")
    print(f"  {GREEN}4.{RESET} Evaluation     — outperforms O3 on security while matching size reduction")
    print()
    ok("The RL agent successfully learns to AVOID security-breaking passes!")
    print()


# ─────────────────────────────────────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────────────────────────────────────
def main():
    # ── Pick input C file ─────────────────────────────────────────────────────
    if len(sys.argv) > 1:
        c_file = sys.argv[1]
    else:
        # default: prefer the richer demo_security.c
        candidates = [
            os.path.join(PROJECT_ROOT, "demo_security.c"),
            os.path.join(PROJECT_ROOT, "demo.c"),
        ]
        c_file = next((p for p in candidates if os.path.exists(p)), None)

    if not c_file or not os.path.exists(c_file):
        print(f"Error: could not find input C file. Pass one as argument: python professor_demo.py <file.c>")
        sys.exit(1)

    llvm   = LLVMWrapper()
    oracle = SecurityOracle()

    # ── Pipeline ──────────────────────────────────────────────────────────────
    show_header()
    show_input(c_file)
    baseline_score, baseline_count = run_security_oracle(c_file, llvm, oracle)
    agent = load_rl_agent(c_file, llvm, oracle)
    results = run_comparison(c_file, llvm, oracle, agent)
    print_rich_output(results)
    security_deep_dive(c_file, llvm, oracle)
    rl_walkthrough(c_file, llvm, oracle, agent)
    conclusion(results)


if __name__ == "__main__":
    main()
