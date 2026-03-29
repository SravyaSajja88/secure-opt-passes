document.addEventListener("DOMContentLoaded", () => {
    const btnRun = document.getElementById("btn-run");
    const codeEditor = document.getElementById("code-editor");
    const statusLog = document.getElementById("status-log");
    const statusIndicator = document.getElementById("status-indicator");
    
    // Cards
    const cardTrace = document.getElementById("card-trace");
    const cardMetrics = document.getElementById("card-metrics");
    const cardDeepDive = document.getElementById("card-deep-dive");
    const cardDownloads = document.getElementById("card-downloads");
    
    // UI Elements
    const chartSize = document.getElementById("chart-size");
    const chartSecurity = document.getElementById("chart-security");
    const tableRlTraceBody = document.querySelector("#table-rl-trace tbody");
    const contentDeepDive = document.getElementById("content-deep-dive");
    
    // IR Viewer
    const irTabs = document.getElementById("ir-tabs");
    const irCodeDisplay = document.getElementById("ir-code-display");
    const downloadButtons = document.getElementById("download-buttons");

    // State
    let methodsData = {};
    let irData = {};
    
    // Enable run button if there is text
    codeEditor.addEventListener("input", () => {
        btnRun.disabled = codeEditor.value.trim().length === 0;
    });
    // Check initial state
    btnRun.disabled = codeEditor.value.trim().length === 0;

    btnRun.addEventListener("click", () => {
        startDemonstration();
    });

    function logMessage(msg, type="info") {
        const p = document.createElement("p");
        p.className = `log-${type}`;
        p.textContent = `> ${msg}`;
        statusLog.appendChild(p);
        statusLog.scrollTop = statusLog.scrollHeight;
    }

    function resetUI() {
        statusLog.innerHTML = "";
        statusIndicator.className = "status-indicator running";
        
        [cardTrace, cardMetrics, cardDeepDive, cardDownloads].forEach(c => {
            c.classList.remove("visible");
            c.classList.add("hidden");
        });
        
        chartSize.innerHTML = "";
        chartSecurity.innerHTML = "";
        tableRlTraceBody.innerHTML = "";
        contentDeepDive.innerHTML = "";
        irTabs.innerHTML = "";
        downloadButtons.innerHTML = "";
        irCodeDisplay.textContent = "Select a tab above to view IR...";
        
        methodsData = {};
        irData = {};
    }

    async function startDemonstration() {
        btnRun.disabled = true;
        codeEditor.disabled = true;
        resetUI();

        logMessage("Initializing demonstration...", "start");

        try {
            const response = await fetch("/api/run-demo", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ c_code: codeEditor.value })
            });

            if (!response.body) {
                throw new Error("ReadableStream not supported");
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder("utf-8");
            let buffer = "";

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                
                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n\n');
                buffer = lines.pop(); // Keep the last incomplete chunk

                for (const line of lines) {
                    if (line.startsWith("data: ")) {
                        const dataStr = line.substring(6);
                        try {
                            const event = JSON.parse(dataStr);
                            handleEvent(event);
                        } catch (e) {
                            console.error("Error parsing SSE JSON:", e);
                        }
                    }
                }
            }
        } catch (e) {
            logMessage(`Connection failed: ${e.message}`, "error");
            statusIndicator.className = "status-indicator error";
        } finally {
            btnRun.disabled = false;
            codeEditor.disabled = false;
        }
    }

    function handleEvent(event) {
        const { step, data } = event;
        
        if (step === "START") {
            logMessage(data.message, "start");
        } 
        else if (step === "INFO") {
            logMessage(data.message, "info");
        }
        else if (step === "STEP_BASELINE") {
            logMessage(`Baseline compiled. Instructions: ${data.instruction_count}, Sec Score: ${data.security_score.toFixed(1)}`, "info");
            irData["Baseline"] = data.baseline_ir;
            addArtifactTab("Baseline", "baseline.ll");
        }
        else if (step === "STEP_EVAL_UPDATE") {
            const { method, result } = data;
            if (result) {
                methodsData[method] = result;
                logMessage(`[${method}] Done: Size reduced by ${result.size_reduction.toFixed(1)}%, Sec kept ${result.security_preservation.toFixed(1)}%`, 
                    result.security_preservation >= 90 ? "success" : "error");
                
                if (result.ir_content) {
                    const niceName = method === "rl" ? "RL Optimized" : `${method} Optimized`;
                    const fileName = method === "rl" ? "rl_optimized.ll" : `${method.toLowerCase()}_optimized.ll`;
                    irData[niceName] = result.ir_content;
                    addArtifactTab(niceName, fileName);
                }
                
                updateCharts();
            } else {
                logMessage(`[${method}] Failed`, "error");
            }
        }
        else if (step === "STEP_DEEP_DIVE") {
            cardDeepDive.classList.remove("hidden");
            cardDeepDive.classList.add("visible");
            renderDeepDive(data.comparison, data.removed_count);
        }
        else if (step === "STEP_RL_TRACE_STEP") {
            cardTrace.classList.remove("hidden");
            cardTrace.classList.add("visible");
            appendTraceRow(data);
        }
        else if (step === "STEP_RL_SUMMARY") {
            logMessage(`RL Trace Complete. Final Size Red: ${data.metrics.size_reduction.toFixed(1)}%`, "success");
            // Add RL IR to viewer
            irData["RL Optimized"] = data.metrics.ir_content || "RL Optimization completed. Download the file below.";
            addArtifactTab("RL Optimized", "rl_optimized.ll");
        }
        else if (step === "DONE") {
            logMessage(data.message, "done");
            statusIndicator.className = "status-indicator done";
        }
        else if (step === "ERROR") {
            logMessage(`ERROR: ${data.message}`, "error");
            statusIndicator.className = "status-indicator error";
        }
    }

    function updateCharts() {
        cardMetrics.classList.remove("hidden");
        cardMetrics.classList.add("visible");
        
        chartSize.innerHTML = "";
        chartSecurity.innerHTML = "";
        
        const validMethods = Object.keys(methodsData);
        if (validMethods.length === 0) return;
        
        const maxSizeRed = Math.max(...validMethods.map(m => methodsData[m].size_reduction || 0), 1);
        
        validMethods.forEach(m => {
            const res = methodsData[m];
            
            // Size Chart
            const sizeVal = res.size_reduction || 0;
            const sizeColor = m === "rl" ? "var(--success)" : m === "greedy" ? "var(--accent-primary)" : "var(--warning)";
            const sizeWidth = Math.max((sizeVal / maxSizeRed) * 100, 0);
            
            chartSize.appendChild(createBarRow(m, sizeWidth, `${sizeVal.toFixed(1)}%`, sizeColor));
            
            // Security Chart
            const secVal = res.security_preservation || 0;
            const secColor = secVal >= 90 ? "var(--success)" : "var(--danger)";
            
            chartSecurity.appendChild(createBarRow(m, secVal, `${secVal.toFixed(1)}%`, secColor));
        });
    }

    function createBarRow(label, widthPct, valueText, color) {
        const row = document.createElement("div");
        row.className = "bar-row";
        
        const lbl = document.createElement("div");
        lbl.className = "bar-label";
        lbl.textContent = label;
        
        const container = document.createElement("div");
        container.className = "bar-container";
        
        const fill = document.createElement("div");
        fill.className = "bar-fill";
        fill.style.backgroundColor = color;
        // animate
        setTimeout(() => fill.style.width = `${widthPct}%`, 50);
        
        const val = document.createElement("div");
        val.className = "bar-value";
        val.textContent = valueText;
        
        container.appendChild(fill);
        row.appendChild(lbl);
        row.appendChild(container);
        row.appendChild(val);
        return row;
    }

    function renderDeepDive(comp, removedCount) {
        if (removedCount > 0) {
            contentDeepDive.innerHTML = `<p class="text-red mb-2" style="font-weight:600; margin-bottom:1rem;">O3 removed ${removedCount} security check(s)!</p>`;
        } else {
            contentDeepDive.innerHTML = `<p class="text-green mb-2" style="font-weight:600; margin-bottom:1rem;">O3 preserved all checks on this baseline.</p>`;
        }
        
        let html = `<table class="deep-dive-table">
            <thead>
                <tr>
                    <th style="color:var(--text-secondary)">Check Type</th>
                    <th style="color:var(--text-secondary)">Baseline (O0)</th>
                    <th style="color:var(--text-secondary)">After O3</th>
                </tr>
            </thead>
            <tbody>`;
            
        for (const [type, counts] of Object.entries(comp)) {
            const trColor = counts.after < counts.before ? "var(--danger)" : "var(--success)";
            html += `<tr style="color:${trColor}">
                <td>${type}</td>
                <td>${counts.before}</td>
                <td>${counts.after}</td>
            </tr>`;
        }
        html += `</tbody></table>
        <p class="text-dim" style="margin-top:1rem; font-size:0.85rem;">The RL Agent is penalized for these removals and learns to preserve them.</p>`;
        
        contentDeepDive.innerHTML += html;
    }

    function appendTraceRow(data) {
        const tr = document.createElement("tr");
        const deltaStr = data.delta === 0 ? "━" : (data.delta > 0 ? `+${data.delta}` : `${data.delta}`);
        const colorClass = data.delta < 0 ? "text-green" : (data.delta > 0 ? "text-red" : "text-yellow");
        
        tr.innerHTML = `
            <td>${data.step}</td>
            <td class="${colorClass}">${data.pass_name}</td>
            <td>${data.size}</td>
            <td class="${colorClass}">${deltaStr}</td>
            <td>${data.security_pct.toFixed(1)}%</td>
            <td>${data.reward.toFixed(3)}</td>
        `;
        tableRlTraceBody.appendChild(tr);
        
        // auto scroll
        const wrapper = document.querySelector(".terminal-table-wrapper");
        wrapper.scrollTop = wrapper.scrollHeight;
    }

    function escapeHtml(unsafe) {
        return unsafe
             .replace(/&/g, "&amp;")
             .replace(/</g, "&lt;")
             .replace(/>/g, "&gt;")
             .replace(/"/g, "&quot;")
             .replace(/'/g, "&#039;");
    }

    function displayIRCode(text) {
        if (!text) {
            irCodeDisplay.innerHTML = "Loading...";
            return;
        }
        const lines = text.split('\n');
        irCodeDisplay.innerHTML = '';
        lines.forEach((line, index) => {
            const lineDiv = document.createElement('div');
            lineDiv.className = 'code-line';
            lineDiv.innerHTML = `<span class="line-number">${index + 1}</span><span class="line-content">${escapeHtml(line)}</span>`;
            irCodeDisplay.appendChild(lineDiv);
        });
    }

    function addArtifactTab(name, filename) {
        cardDownloads.classList.remove("hidden");
        cardDownloads.classList.add("visible");
        
        // Add Pill
        const pill = document.createElement("button");
        pill.className = "pill";
        pill.textContent = name;
        pill.onclick = () => {
            document.querySelectorAll(".pill").forEach(p => p.classList.remove("active"));
            pill.classList.add("active");
            displayIRCode(irData[name] || "Loading...");
        };
        irTabs.appendChild(pill);
        
        // Add Download Link
        const link = document.createElement("a");
        link.className = "download-link";
        link.href = `/api/download/${filename}`;
        link.download = filename;
        link.innerHTML = `⬇️ ${filename}`;
        downloadButtons.appendChild(link);
    }

});
