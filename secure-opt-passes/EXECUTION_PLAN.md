# 🚀 TODAY'S EXECUTION PLAN
## Complete the AI for Secure Optimization Passes Project

---

## ⏱️ TIME BUDGET: ~4-6 hours

### Phase 1: Setup (30 minutes)
- [ ] Install LLVM/Clang if not already installed
- [ ] Run quickstart script
- [ ] Verify all dependencies work

### Phase 2: Understanding (1 hour)  
- [ ] Read IMPLEMENTATION_GUIDE.md (Tutorial 1-2)
- [ ] Examine one generated benchmark
- [ ] Run sample optimization with --verbose
- [ ] Understand the output

### Phase 3: Execution (2 hours)
- [ ] Run `./run_complete_project.sh`
- [ ] This will:
  - Generate 30 benchmarks
  - Test each with 5 methods (O0, O2, O3, greedy, random)
  - Create plots and CSV results
  - Takes ~1-2 hours depending on your machine

### Phase 4: Analysis (1-2 hours)
- [ ] Review CSV results
- [ ] Examine plots (Pareto frontier most important)
- [ ] Document findings
- [ ] Prepare presentation materials

### Phase 5: Documentation (1 hour)
- [ ] Update final report with results
- [ ] Add plots to report
- [ ] Write conclusions

---

## 📂 WHAT YOU GET

### Working Code
```
secure-opt-passes/
├── src/                      # All source code
│   ├── main.py              # Main CLI
│   ├── security_oracle.py   # Pattern detection
│   ├── pass_selector.py     # Optimization strategies
│   ├── llvm_wrapper.py      # LLVM interface
│   ├── feature_extractor.py # ML features
│   └── rl_environment.py    # RL environment
├── scripts/
│   ├── generate_benchmarks.py  # Create test programs
│   └── evaluate_all.py         # Run experiments
├── tests/                   # Unit tests
└── data/
    ├── benchmarks/          # Generated C programs
    ├── results/             # Evaluation outputs
    └── models/              # Trained RL models
```

### Results You'll Generate
1. **evaluation_results.csv** - Every program × method combination
2. **summary_statistics.csv** - Averages and std dev
3. **pareto_frontier.png** - Performance vs security trade-off
4. **size_reduction_comparison.png** - Box plots by method
5. **security_preservation_comparison.png** - Box plots by method

---

## 🎯 CORE FUNCTIONALITY EXPLAINED

### What the System Does

1. **Input:** C source code with security checks
   ```c
   if (idx < 0 || idx >= size) abort();  // Bounds check
   ```

2. **Compile to IR:** Converts to LLVM intermediate representation
   ```llvm
   %cmp = icmp ult i64 %idx, %bound
   br i1 %cmp, label %safe, label %error
   ```

3. **Detect Security:** Finds patterns (bounds checks, sanitizers, assertions)
   - Assigns weight to each pattern
   - Computes security score

4. **Select Optimization:** Choose from ~20 LLVM passes
   - **Greedy:** Try all, pick best safe option
   - **Random:** Randomly select safe passes
   - **RL (optional):** Learn optimal sequence

5. **Apply & Validate:**
   - Apply selected pass
   - Re-scan for security checks
   - If score drops > 10% → Reject (rollback)
   - If safe → Accept and continue

6. **Output:** Optimized IR with security preserved

---

## 🔧 HOW IT WORKS (Technical)

### Security Oracle Architecture
```python
class SecurityOracle:
    def analyze(ir_content):
        # 1. Find bounds checks (icmp + br + trap)
        # 2. Find null checks (icmp + null)
        # 3. Find sanitizer calls (__ubsan_*, __asan_*)
        # 4. Find assertions (abort, trap)
        # 5. Sum weighted scores
        return security_score
```

### Optimization Loop
```python
for i in range(max_passes):
    pass = selector.select_pass()  # Greedy/Random/RL
    
    apply_pass(ir_file, pass)
    new_score = oracle.analyze(new_ir)
    
    if new_score / baseline_score < threshold:
        rollback()  # Reject pass
    else:
        accept()    # Keep optimized IR
```

### Evaluation Metrics
- **Code Size Reduction:** `(baseline_size - optimized_size) / baseline_size`
- **Security Preservation:** `optimized_score / baseline_score`
- **Pareto Score:** Balance of both

---

## 🧪 WHAT TO EXPECT (Results)

### Typical Outcomes

| Method | Code Size Reduction | Security Preservation |
|--------|--------------------|-----------------------|
| O0     | 0%                 | 100%                  |
| O2     | 30-35%             | 65-70%                |
| O3     | 40-45%             | 50-60%                |
| **Greedy** | **25-30%**     | **90-95%**            |
| Random | 20-25%             | 90-95%                |

**Key Insight:** Your greedy method should:
- Optimize less aggressively than O2/O3
- But preserve **much more security** (>90% vs 50-70%)
- This is the **trade-off** - you sacrifice 5-10% performance for 20-30% more security

---

## 📊 DELIVERABLES

### For Your Report/Presentation

1. **System Diagram** (copy from Week 4 doc)
2. **Algorithm Pseudocode** (optimization loop)
3. **Results Table** (from summary_statistics.csv)
4. **Pareto Frontier Plot** (key visualization!)
5. **Discussion:**
   - Greedy balances performance and security
   - O2/O3 too aggressive on security
   - Heuristic patterns vs formal verification trade-off

### Sample Conclusion
```
Our security-aware optimization framework achieves 28% code size 
reduction while preserving 92% of security checks, compared to 
LLVM -O2's 33% reduction but only 68% security preservation.

This demonstrates that intelligent pass selection can balance 
performance and security better than fixed optimization levels.

Future work: RL-based selection, formal verification, whole-program 
analysis.
```

---

## ⚡ QUICK START (5 minutes to first result)

```bash
# 1. Clone/navigate to project
cd secure-opt-passes

# 2. Run everything
./run_complete_project.sh

# 3. View results
cat data/results/summary_statistics.csv
open data/results/pareto_frontier.png

# Done! You have all results.
```

---

## 🎓 EXPERTISE NEEDED

### Essential (must have)
- ✅ Python basics (you can read the code)
- ✅ Running scripts from command line
- ✅ Basic understanding of what optimizations do

### Nice to have (but code handles it)
- ⭕ LLVM IR syntax (provided templates work)
- ⭕ Machine learning (libraries do the work)
- ⭕ Compiler theory (high-level understanding sufficient)

### You DON'T need
- ❌ To implement RL from scratch (Stable-Baselines3 handles it)
- ❌ To manually parse IR (wrapper does it)
- ❌ To know every LLVM pass (we provide curated list)

---

## 🐛 TROUBLESHOOTING

### "clang not found"
```bash
sudo apt-get install llvm-14 clang-14
```

### "No checks detected"
- Use provided benchmark generator (already has checks)
- Don't write your own programs unless following templates

### "Everything rejected"
- Lower threshold: `--threshold 0.8`
- Check benchmark has actual security checks with `--verbose`

### Script hangs
- Reduce benchmarks: `--count 10`
- Reduce passes: `--max-passes 20`

---

## 📞 HELP

If stuck at any point:
1. Check IMPLEMENTATION_GUIDE.md for detailed tutorials
2. Run with `--verbose` to see what's happening
3. Check tests: `pytest tests/ -v`
4. Verify LLVM: `clang-14 --version`

---

## ✅ FINAL CHECKLIST

Before submitting:
- [ ] All scripts run without errors
- [ ] Have CSV results with 30+ programs
- [ ] Have 3+ plots generated
- [ ] Understand what the Pareto frontier shows
- [ ] Can explain greedy vs O2/O3 trade-offs
- [ ] Final report includes results and plots
- [ ] Code is on GitHub/submitted properly

---

## 🎯 SUCCESS CRITERIA

You'll know you're done when:
1. ✅ `run_complete_project.sh` completes successfully
2. ✅ You have CSV files and plots in `data/results/`
3. ✅ You can explain the performance-security trade-off
4. ✅ Your report includes experimental results
5. ✅ You understand the system architecture

**Time to complete: 4-6 hours total**

Good luck! 🚀
