import sys
import os
import time
import json
import asyncio
import tempfile
import shutil
from typing import AsyncGenerator
from collections import Counter

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ── Fix import paths ──────────────────────────────────────────────────────────
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
SRC_DIR      = os.path.join(PROJECT_ROOT, "src")
SCRIPTS_DIR  = os.path.join(PROJECT_ROOT, "scripts")
sys.path.insert(0, SRC_DIR)
sys.path.insert(0, SCRIPTS_DIR)

try:
    from llvm_wrapper   import LLVMWrapper
    from security_oracle import SecurityOracle
    from rl_agent       import RLPassSelector
    from rl_environment import LLVMOptimizationEnv
    from evaluate_all   import evaluate_method
    from pass_selector  import optimize_with_selector
    from config         import APPROVED_PASSES
except ImportError as e:
    print(f"Error importing internal modules: {e}")
    print("Ensure you are running this from the correct environment.")

app = FastAPI(title="Secure Optimizer Demo")

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure static directory exists
STATIC_DIR = os.path.join(PROJECT_ROOT, "static")
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Ensure a directory for downloads
DOWNLOADS_DIR = os.path.join(PROJECT_ROOT, "downloads")
os.makedirs(DOWNLOADS_DIR, exist_ok=True)

class RunDemoRequest(BaseModel):
    c_code: str


def save_c_code(code: str) -> str:
    fd, path = tempfile.mkstemp(suffix=".c")
    with os.fdopen(fd, 'w') as f:
        f.write(code)
    return path


def event_fmt(step: str, data: dict):
    """Format data as Server-Sent Event."""
    msg = json.dumps({"step": step, "data": data})
    return f"data: {msg}\n\n"


async def demo_generator(c_file: str) -> AsyncGenerator[str, None]:
    """Generates SSE messages corresponding to the steps of the demo."""
    try:
        llvm = LLVMWrapper()
        oracle = SecurityOracle()
        
        # ── Step 1: Input
        yield event_fmt("START", {"message": "Starting demonstration pipeline..."})
        await asyncio.sleep(0.5)

        # ── Step 2: Compile to LLVM IR + Security Oracle
        yield event_fmt("INFO", {"message": "Compiling to LLVM IR (O0 baseline)..."})
        fd, ir_path = tempfile.mkstemp(suffix=".ll")
        os.close(fd)
        
        llvm.compile_to_ir(c_file, ir_path, opt_level="0")
        with open(ir_path) as f:
            ir_content = f.read()
            ir_lines = ir_content.splitlines()
        
        instr_count = llvm.count_instructions(ir_path)
        score, checks = oracle.analyze(ir_content)
        
        check_counts = dict(Counter(c.type for c in checks))
        
        out_base = os.path.join(DOWNLOADS_DIR, "baseline.ll")
        shutil.copy2(ir_path, out_base)

        yield event_fmt("STEP_BASELINE", {
            "instruction_count": instr_count,
            "security_score": score,
            "checks": check_counts,
            "baseline_ir": ir_content,
            "ir_snippet": "\\n".join(ir_lines[:15])
        })
        os.remove(ir_path)
        await asyncio.sleep(1.0)

        # ── Step 3: Load RL Agent
        yield event_fmt("INFO", {"message": "Loading trained RL Agent..."})
        model_dir = os.path.join(PROJECT_ROOT, "models")
        wsl_model = "/home/sravya/secure-opt-passes/data/models/rl_dqn_v3.pt"
        candidates = [
            os.path.join(model_dir, "rl_agent_ep1900.pt"),
            os.path.join(model_dir, "rl_agent.pt"),
            os.path.join(model_dir, "best_model.pt"),
            os.path.join(model_dir, "rl_agent_final.pt"),
            wsl_model,
        ]
        model_path = next((p for p in candidates if os.path.exists(p)), None)
        
        agent = None
        if model_path:
            agent = RLPassSelector(state_dim=1, action_dim=1, device="cpu")
            agent.load(model_path)
            yield event_fmt("INFO", {"message": f"Successfully loaded RL Agent from {os.path.basename(model_path)}"})
        else:
            yield event_fmt("INFO", {"message": "No trained model found. RL steps will be skipped."})
        await asyncio.sleep(1.0)

        # ── Step 4: Methods Comparison
        methods = ["O0", "O2", "O3", "greedy"]
        if agent:
            methods.append("rl")
        
        results_summary = {}
        for m in methods:
            yield event_fmt("INFO", {"message": f"Evaluating method: {m}..."})
            await asyncio.sleep(0.2)
            res = evaluate_method(c_file, m, llvm, oracle, agent)
            if res:
                res["method"] = m
                results_summary[m] = res
                
                # Try saving the IR file for download if possible
                if m in ["O2", "O3"]:
                    out_ll = os.path.join(DOWNLOADS_DIR, f"{m.lower()}_optimized.ll")
                    llvm.compile_to_ir(c_file, out_ll, opt_level=m.replace("O", ""))
                    with open(out_ll) as f:
                        res["ir_content"] = f.read()
                elif m == "greedy":
                    out_ll = os.path.join(DOWNLOADS_DIR, f"{m.lower()}_optimized.ll")
                    # Try to generate greedy IR to offer as download
                    try:
                        optimize_with_selector(c_file, m, out_ll, 50, False)
                        with open(out_ll) as f:
                            res["ir_content"] = f.read()
                    except Exception as e:
                        print(f"Failed to generate greedy IR: {e}")
                        
            yield event_fmt("STEP_EVAL_UPDATE", {"method": m, "result": res})
        
        yield event_fmt("INFO", {"message": "Completed baseline comparisons."})
        await asyncio.sleep(1.0)

        # ── Step 6: Security Deep Dive
        yield event_fmt("INFO", {"message": "Performing Security Deep Dive (Baseline vs O3)..."})
        
        def get_checks(opt_level):
            fd, ir = tempfile.mkstemp(suffix=".ll")
            os.close(fd)
            llvm.compile_to_ir(c_file, ir, opt_level=opt_level)
            with open(ir) as f:
                content = f.read()
            score, chks = oracle.analyze(content)
            os.remove(ir)
            return chks

        base_chks = get_checks("0")
        o3_chks = get_checks("3")
        base_types = dict(Counter(c.type for c in base_chks))
        o3_types   = dict(Counter(c.type for c in o3_chks))
        
        deep_dive_data = {}
        for t in set(base_types.keys()).union(set(o3_types.keys())):
            deep_dive_data[t] = {"before": base_types.get(t, 0), "after": o3_types.get(t, 0)}

        yield event_fmt("STEP_DEEP_DIVE", {"comparison": deep_dive_data, "removed_count": len(base_chks) - len(o3_chks)})
        await asyncio.sleep(1.0)

        # ── Step 7: RL Walkthrough
        if agent:
            yield event_fmt("INFO", {"message": "Tracing live RL Agent pass selection..."})
            fd, ir_file = tempfile.mkstemp(suffix=".ll")
            os.close(fd)
            llvm.compile_to_ir_stripped(c_file, ir_file, opt_level="0")
            with open(ir_file) as f:
                ir_content = f.read()
            b_score, _ = oracle.analyze(ir_content)
            
            env = LLVMOptimizationEnv(ir_file, b_score)
            state, _ = env.reset()
            
            done = False
            steps = 0
            prev_size = env.baseline_size
            pass_names = getattr(env, "pass_names", APPROVED_PASSES)
            
            rl_passes = []
            
            while not done and steps < min(env.max_steps, 15):
                action = agent.select_action(state, epsilon=0.0)
                state, reward, terminated, truncated, _ = env.step(action)
                done = terminated or truncated
                steps += 1
                
                cur_size = env.current_size
                sec_ratio = env.current_score / max(env.baseline_score, 1e-6)
                sec_pct   = min(sec_ratio * 100, 100.0)
                p_name   = pass_names[action] if action < len(pass_names) else f"pass_{action}"
                delta    = cur_size - prev_size
                
                step_data = {
                    "step": steps,
                    "pass_name": p_name,
                    "size": cur_size,
                    "delta": delta,
                    "security_pct": sec_pct,
                    "reward": reward
                }
                rl_passes.append(step_data)
                
                yield event_fmt("STEP_RL_TRACE_STEP", step_data)
                prev_size = cur_size
                await asyncio.sleep(0.3) # small delay for visual effect
            
            final_rl_ir = env.get_final_ir()
            out_rl = os.path.join(DOWNLOADS_DIR, "rl_optimized.ll")
            shutil.copy2(final_rl_ir, out_rl)
            
            with open(out_rl) as f:
                 rl_ir_content = f.read()
            
            if "rl" in results_summary and results_summary["rl"] is not None:
                results_summary["rl"]["ir_content"] = rl_ir_content
                
            metrics = env.get_metrics()
            metrics["ir_content"] = rl_ir_content  # Pipe it back to the UI
            env.close()
            os.remove(ir_file)
            
            yield event_fmt("STEP_RL_SUMMARY", {"metrics": metrics})

        yield event_fmt("DONE", {"message": "Demonstration completed successfully.", "summary": results_summary})

    except Exception as e:
        import traceback
        trace = traceback.format_exc()
        yield event_fmt("ERROR", {"message": str(e), "trace": trace})
    finally:
        if os.path.exists(c_file):
            os.remove(c_file)


@app.get("/", response_class=HTMLResponse)
async def read_index():
    with open(os.path.join(STATIC_DIR, "index.html"), "r") as f:
         return f.read()

@app.post("/api/run-demo")
async def run_demo(req: RunDemoRequest):
    c_file = save_c_code(req.c_code)
    return StreamingResponse(demo_generator(c_file), media_type="text/event-stream")

@app.get("/api/download/{filename}")
async def download_file(filename: str):
    file_path = os.path.join(DOWNLOADS_DIR, filename)
    if os.path.exists(file_path):
        return FileResponse(file_path, filename=filename)
    return {"error": "File not found"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
