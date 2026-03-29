# AI for Secure Optimization Passes 🛡️

A Machine Learning-Based Framework for Security-Aware Compiler Optimization at the LLVM IR Level. 
This project features an intelligent Reinforcement Learning agent (Deep Q-Network) that sequentially selects LLVM optimization passes to maximize code-size reduction **without** removing security-critical checks like bounds tests, null pointer checks, and assertions.

![Project Status](https://img.shields.io/badge/Status-Final_Project-success)
![LLVM Version](https://img.shields.io/badge/LLVM-14%2B-blue)
![Python](https://img.shields.io/badge/Python-3.8%2B-blue)

---

## 🎯 Project Highlights
- **Security Oracle**: Accurately detects and scores security constraints built into C programs via analyzing the intermediate LLVM IR representation.
- **Deep Q-Network Agents**: Replaces heuristic-based selection. Learns optimizing trajectories that achieve comparable reductions to `-O3` without sacrificing system guarantees.
- **Interactive Web Dashboard**: A stunning glassmorphism dashboard streaming Live RL Pass Selection Traces, IR views, and Bar Charts built on **FastAPI** and **Server-Sent Events**.

---

## 🏗️ Architecture

```
C Source Code ──► Compile to LLVM IR (clang)
                       │
                       ▼
                 Security Oracle (Detects Checks)
                       │
                       ▼ 
                 Pass Selector (RL Agent DQN)  ◄────── Evaluates Reward Function
                       │
                       ▼
                 Optimized IR Generation
```

---

## 🚀 Quick Start: Web Interactive Dashboard

We have an interactive FastAPI dashboard that walks through the entire AI optimization pipeline step-by-step.

### 1. Prerequisites
- LLVM/Clang 14+ (install via apt/brew/package manager)
- Python 3.8+ (WSL / Ubuntu recommended)

### 2. Setup your Environment
```bash
# Clone the repository
git clone https://github.com/SravyaSajja88/secure-opt-passes.git
cd secure-opt-passes

# Create and activate virtual environment
python3 -m venv .venv_wsl
source .venv_wsl/bin/activate

# Install all baseline and web dependencies
pip install -r requirements.txt
pip install fastapi uvicorn
```

### 3. Run the Demonstration App
```bash
# Start the web backend server
uvicorn app:app --host 0.0.0.0 --port 8000
```
Then, open your browser and navigate to **[http://localhost:8000/](http://localhost:8000/)**.
Paste your secure C application code, hit **Start Demonstration**, and watch the AI optimize the IR in real-time!

---

## 💻 CLI Commands & Training

If you prefer to run the training and processing via the terminal:

### Train the RL Agent
```bash
python scripts/generate_benchmarks.py --count 50 --output data/benchmarks/
python src/train_rl.py --benchmark-dir data/benchmarks/ --model-output models/rl_agent.pt --episodes 1000
```

### Full Data Evaluation Pipeline
```bash
python scripts/evaluate_all.py \
    --benchmark-dir data/benchmarks/ \
    --output-dir data/results/ \
    --methods O0,O2,O3,greedy,random,rl
```

---

## 📊 Evaluation Results

| Method | Code Size Reduction | Security Preservation | Verdict |
|--------|---------------------|-----------------------|---------|
| O0     | 0.0%               | 100.0%                | ✔ SECURE |
| O2     | 32.5%              | 67.3%                 | ✘ VIOLATION |
| **O3** | **41.2%**          | **52.8%**             | **✘ VIOLATION** |
| Greedy | 28.3%              | 91.7%                 | ✔ SECURE |
| **RL Agent** | **39.1%**    | **95.2%**             | **✔ SECURE** |

*(Results averaged over 50 generated C benchmarks)*

---

## 📚 Project Structure

```text
secure-opt-passes/
├── app.py                      # FastAPI Web Server for Interactive Dashboard
├── static/                     # Web Frontend HTML, CSS, JavaScript
├── src/
│   ├── security_oracle.py      # LLVM pattern detection
│   ├── feature_extractor.py    # Generates observation state arrays
│   ├── rl_environment.py       # Stable-Baselines API gym environment
│   ├── rl_agent.py             # Internal DQN architecture
│   └── llvm_wrapper.py         # Clang & Opt internal execution wrappers
├── scripts/
│   ├── generate_benchmarks.py  # Create test programs
│   └── evaluate_all.py         # Run full evaluation & Pareto metrics
├── models/                     # Trained .pt RL weights
└── data/                       # C Benchmarks & CSV evaluation outputs
```

---

## 🎓 Academic Context
This is a research prototype serving as a Final Project in Systems Security demonstrating:
1. Practical Reinforcement Learning for compiler optimization boundaries.
2. Security-aware compilation toolchains.
3. Quantifiable performance/security trade-off analyses on the Pareto-frontier.

**Author:** Sravya Sajja (24CSB0B74)  
**Institution:** Department of Computer Science and Engineering, National Institute of Technology Warangal  
**License:** Academic/Research Use Only
