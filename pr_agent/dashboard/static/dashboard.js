// PR-Agent Dashboard Dynamic Interactivity & Enhanced Multi-Chart Analytics

document.addEventListener("DOMContentLoaded", () => {
  const path = window.location.pathname;
  if (path.startsWith("/runs/")) {
    initRunDetailPage();
  } else {
    initOverviewPage();
  }
});

// Format numbers with commas (e.g. 12,450)
function formatNumber(num) {
  if (num === null || num === undefined) return "0";
  return num.toLocaleString();
}

// Format duration
function formatDuration(sec) {
  if (!sec) return "0s";
  return `${Number(sec).toFixed(1)}s`;
}

// Format relative date
function formatDate(isoStr) {
  if (!isoStr) return "-";
  try {
    const d = new Date(isoStr);
    return d.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch (e) {
    return isoStr;
  }
}

/* =========================================================================
   OVERVIEW PAGE LOGIC & MULTI-CHART RENDERING
   ========================================================================= */

let allRunsCache = [];
let chartInstances = {};

async function initOverviewPage() {
  const refreshBtn = document.getElementById("refreshBtn");
  if (refreshBtn) {
    refreshBtn.addEventListener("click", () => {
      loadOverviewData();
    });
  }

  // Setup search and filter listeners
  const searchInput = document.getElementById("runSearchInput");
  if (searchInput) {
    searchInput.addEventListener("input", (e) => {
      filterRunsTable(e.target.value);
    });
  }

  const filterBtns = document.querySelectorAll(".filter-btn");
  filterBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      filterBtns.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      const engineFilter = btn.dataset.engine;
      filterRunsByEngine(engineFilter);
    });
  });

  await loadOverviewData();
}

async function loadOverviewData() {
  try {
    // 1. Fetch Stats
    const statsRes = await fetch("/api/stats");
    let stats = {};
    if (statsRes.ok) {
      stats = await statsRes.json();
      renderStatsCards(stats);
      renderDistributionChart(stats);
      renderComponentsChart(stats);
    }

    // 2. Fetch Runs
    const runsRes = await fetch("/api/runs");
    if (runsRes.ok) {
      allRunsCache = await runsRes.json();
      renderRunsTable(allRunsCache);
      renderTokenChart(allRunsCache);
      renderTestsChart(allRunsCache);
      renderDurationChart(allRunsCache);
      renderSpeedChart(allRunsCache);
    }
  } catch (err) {
    console.error("Failed to load dashboard data:", err);
  }
}

function renderStatsCards(stats) {
  const totalTokensEl = document.getElementById("kpiTotalTokens");
  const promptTokensEl = document.getElementById("kpiPromptTokens");
  const compTokensEl = document.getElementById("kpiCompTokens");
  const totalRunsEl = document.getElementById("kpiTotalRuns");
  const passRateEl = document.getElementById("kpiPassRate");
  const testsPassedEl = document.getElementById("kpiTestsPassed");
  const primaryModelEl = document.getElementById("kpiPrimaryModel");
  const aiCallsEl = document.getElementById("kpiAiCalls");
  const fixRateEl = document.getElementById("kpiFixRate");
  const speedEl = document.getElementById("kpiSpeed");

  if (totalTokensEl) totalTokensEl.textContent = formatNumber(stats.total_tokens);
  if (promptTokensEl) promptTokensEl.textContent = `${formatNumber(stats.prompt_tokens)} in`;
  if (compTokensEl) compTokensEl.textContent = `${formatNumber(stats.completion_tokens)} out`;
  if (totalRunsEl) totalRunsEl.textContent = formatNumber(stats.total_runs);
  if (passRateEl) passRateEl.textContent = `${stats.test_pass_rate}%`;
  if (testsPassedEl) testsPassedEl.textContent = `${stats.passed_tests} / ${stats.total_tests} tests`;
  if (aiCallsEl) aiCallsEl.textContent = `${formatNumber(stats.total_ai_calls)} AI calls`;
  if (fixRateEl) fixRateEl.textContent = `${stats.self_healing_rate || 100}%`;
  if (speedEl) speedEl.textContent = `${stats.avg_speed_tokens_per_sec || 0} t/s`;

  if (primaryModelEl) {
    const models = Object.keys(stats.models_breakdown || {});
    primaryModelEl.textContent = models.length > 0 ? `Primary: ${models[0]}` : "Primary: ollama/qwen2.5:7b";
  }
}

function renderRunsTable(runs) {
  const tbody = document.getElementById("runsTableBody");
  if (!tbody) return;

  if (runs.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="8" style="text-align: center; padding: 36px; color: var(--text-muted);">
          No PR runs recorded yet. Execute <code>test_and_fix</code> or <code>review</code> to see telemetry here!
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = runs
    .map((r) => {
      const isUnreal = r.engine === "unreal";
      const isUnity = r.engine === "unity";
      const engineBadge = isUnreal
        ? `<span class="badge badge-unreal">🎮 Unreal C++</span>`
        : isUnity
        ? `<span class="badge badge-unity">🎮 Unity C#</span>`
        : `<span class="badge" style="background: rgba(255,255,255,0.06); color: var(--text-secondary);">General</span>`;

      const statusBadge =
        r.status === "success"
          ? `<span class="badge badge-success">✅ Passed (${r.passed_tests}/${r.total_tests})</span>`
          : `<span class="badge badge-failed">❌ ${r.failed_tests} Fail (${r.passed_tests}/${r.total_tests} pass)</span>`;

      const title = r.pr_title || r.repo || "PR Run";
      const shortTitle = title.length > 38 ? title.substring(0, 35) + "..." : title;
      const speed = r.duration_seconds > 0 ? (r.total_tokens / r.duration_seconds).toFixed(1) : "0.0";

      return `
        <tr>
          <td>
            <a href="/runs/${r.run_id}" style="color: var(--accent-primary); font-weight: 500; text-decoration: none;">
              <code>${r.run_id}</code>
            </a>
          </td>
          <td>
            <div style="font-weight: 500;">${shortTitle}</div>
            <div style="font-size: 11px; color: var(--text-muted);">${r.repo || r.pr_url || ""}</div>
          </td>
          <td>${engineBadge}</td>
          <td>${statusBadge}</td>
          <td>
            <strong>${formatNumber(r.total_tokens)}</strong>
            <span style="font-size: 11px; color: var(--text-muted);">(${formatNumber(r.prompt_tokens)} in / ${formatNumber(r.completion_tokens)} out)</span>
          </td>
          <td>
            <span style="color: var(--accent-amber); font-weight: 500;">${speed}</span>
            <span style="font-size: 11px; color: var(--text-muted);">tok/s</span>
          </td>
          <td>${formatDuration(r.duration_seconds)}</td>
          <td>
            <a href="/runs/${r.run_id}" class="btn btn-secondary btn-sm">
              Inspect →
            </a>
          </td>
        </tr>
      `;
    })
    .join("");
}

function filterRunsTable(query) {
  const q = query.toLowerCase().trim();
  const filtered = allRunsCache.filter((r) => {
    return (
      (r.run_id && r.run_id.toLowerCase().includes(q)) ||
      (r.pr_title && r.pr_title.toLowerCase().includes(q)) ||
      (r.repo && r.repo.toLowerCase().includes(q)) ||
      (r.engine && r.engine.toLowerCase().includes(q)) ||
      (r.model_used && r.model_used.toLowerCase().includes(q))
    );
  });
  renderRunsTable(filtered);
}

function filterRunsByEngine(engine) {
  if (!engine || engine === "all") {
    renderRunsTable(allRunsCache);
  } else {
    const filtered = allRunsCache.filter((r) => (r.engine || "").toLowerCase() === engine.toLowerCase());
    renderRunsTable(filtered);
  }
}

// Helper to destroy and rebuild chart cleanly
function updateChart(key, canvasId, config) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  if (chartInstances[key]) {
    chartInstances[key].destroy();
  }
  chartInstances[key] = new Chart(canvas, config);
}

/* --- CHART 1: Token Usage by Run --- */
function renderTokenChart(runs) {
  const recent = [...runs].reverse().slice(-10);
  const labels = recent.map((r, i) => {
    const short = (r.repo ? r.repo.split("/")[1] : "") || r.run_id.split("_").slice(-2).join("_");
    return short || `Run ${i + 1}`;
  });

  const promptData = recent.map((r) => r.prompt_tokens || 0);
  const completionData = recent.map((r) => r.completion_tokens || 0);

  updateChart("tokenChart", "tokenChart", {
    type: "bar",
    data: {
      labels: labels,
      datasets: [
        {
          label: "Prompt Tokens (Input)",
          data: promptData,
          backgroundColor: "rgba(99, 102, 241, 0.75)",
          borderColor: "#6366f1",
          borderWidth: 1,
          borderRadius: 6,
        },
        {
          label: "Completion Tokens (Output)",
          data: completionData,
          backgroundColor: "rgba(6, 182, 212, 0.75)",
          borderColor: "#06b6d4",
          borderWidth: 1,
          borderRadius: 6,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: "top", labels: { color: "#94a3b8", font: { family: "Inter", size: 12 } } },
      },
      scales: {
        x: { stacked: true, grid: { color: "rgba(255, 255, 255, 0.04)" }, ticks: { color: "#64748b" } },
        y: { stacked: true, grid: { color: "rgba(255, 255, 255, 0.04)" }, ticks: { color: "#64748b" } },
      },
    },
  });
}

/* --- CHART 2: Engine & Platform Distribution --- */
function renderDistributionChart(stats) {
  const engines = stats.engines_breakdown || {};
  const labels = Object.keys(engines).map((k) => (k === "unreal" ? "Unreal Engine" : k === "unity" ? "Unity" : k));
  const data = Object.values(engines);

  if (labels.length === 0) {
    labels.push("Unreal Engine", "Unity");
    data.push(1, 1);
  }

  updateChart("distChart", "distChart", {
    type: "doughnut",
    data: {
      labels: labels,
      datasets: [
        {
          data: data,
          backgroundColor: ["rgba(6, 182, 212, 0.8)", "rgba(139, 92, 246, 0.8)", "rgba(99, 102, 241, 0.8)"],
          borderColor: "rgba(20, 29, 47, 0.9)",
          borderWidth: 2,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: "bottom", labels: { color: "#94a3b8", font: { family: "Inter", size: 12 } } },
      },
      cutout: "68%",
    },
  });
}

/* --- CHART 3: Test Pass vs Failure Breakdown per Run --- */
function renderTestsChart(runs) {
  const recent = [...runs].reverse().slice(-10);
  const labels = recent.map((r, i) => {
    const short = (r.repo ? r.repo.split("/")[1] : "") || r.run_id.split("_").slice(-2).join("_");
    return short || `Run ${i + 1}`;
  });

  const passedData = recent.map((r) => r.passed_tests || 0);
  const failedData = recent.map((r) => r.failed_tests || 0);

  updateChart("testsChart", "testsChart", {
    type: "bar",
    data: {
      labels: labels,
      datasets: [
        {
          label: "Passed Tests",
          data: passedData,
          backgroundColor: "rgba(16, 185, 129, 0.75)",
          borderColor: "#10b981",
          borderWidth: 1,
          borderRadius: 6,
        },
        {
          label: "Failed Tests",
          data: failedData,
          backgroundColor: "rgba(244, 63, 94, 0.75)",
          borderColor: "#f43f5e",
          borderWidth: 1,
          borderRadius: 6,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: "top", labels: { color: "#94a3b8", font: { family: "Inter", size: 12 } } },
      },
      scales: {
        x: { grid: { color: "rgba(255, 255, 255, 0.04)" }, ticks: { color: "#64748b" } },
        y: { grid: { color: "rgba(255, 255, 255, 0.04)" }, ticks: { color: "#64748b", stepSize: 1 } },
      },
    },
  });
}

/* --- CHART 4: Top Fragile Components / Risk Frequency --- */
function renderComponentsChart(stats) {
  const components = stats.top_components_risk || {};
  let labels = Object.keys(components);
  let data = Object.values(components);

  if (labels.length === 0) {
    labels = ["AMovingPlatform", "AECRCharacter", "Coin.cs"];
    data = [2, 1, 1];
  }

  updateChart("componentsChart", "componentsChart", {
    type: "bar",
    data: {
      labels: labels,
      datasets: [
        {
          label: "Identified Regression Risks",
          data: data,
          backgroundColor: "rgba(245, 158, 11, 0.75)",
          borderColor: "#f59e0b",
          borderWidth: 1,
          borderRadius: 6,
        },
      ],
    },
    options: {
      indexAxis: "y",
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
      },
      scales: {
        x: { grid: { color: "rgba(255, 255, 255, 0.04)" }, ticks: { color: "#64748b", stepSize: 1 } },
        y: { grid: { display: false }, ticks: { color: "#e2e8f0" } },
      },
    },
  });
}

/* --- CHART 5: Run Duration & Latency Trend --- */
function renderDurationChart(runs) {
  const recent = [...runs].reverse().slice(-10);
  const labels = recent.map((r, i) => {
    const short = (r.repo ? r.repo.split("/")[1] : "") || r.run_id.split("_").slice(-2).join("_");
    return short || `Run ${i + 1}`;
  });

  const durationData = recent.map((r) => Number((r.duration_seconds || 0).toFixed(1)));

  updateChart("durationChart", "durationChart", {
    type: "line",
    data: {
      labels: labels,
      datasets: [
        {
          label: "Execution Duration (Seconds)",
          data: durationData,
          fill: true,
          backgroundColor: "rgba(139, 92, 246, 0.15)",
          borderColor: "#8b5cf6",
          pointBackgroundColor: "#8b5cf6",
          pointRadius: 4,
          tension: 0.35,
          borderWidth: 2,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: "top", labels: { color: "#94a3b8", font: { family: "Inter", size: 12 } } },
      },
      scales: {
        x: { grid: { color: "rgba(255, 255, 255, 0.04)" }, ticks: { color: "#64748b" } },
        y: { grid: { color: "rgba(255, 255, 255, 0.04)" }, ticks: { color: "#64748b" } },
      },
    },
  });
}

/* --- CHART 6: Inference Throughput (Tokens / Sec) --- */
function renderSpeedChart(runs) {
  const recent = [...runs].reverse().slice(-10);
  const labels = recent.map((r, i) => {
    const short = (r.repo ? r.repo.split("/")[1] : "") || r.run_id.split("_").slice(-2).join("_");
    return short || `Run ${i + 1}`;
  });

  const speedData = recent.map((r) => {
    return r.duration_seconds > 0 ? Number((r.total_tokens / r.duration_seconds).toFixed(1)) : 0;
  });

  updateChart("speedChart", "speedChart", {
    type: "bar",
    data: {
      labels: labels,
      datasets: [
        {
          label: "Throughput (Tokens / Sec)",
          data: speedData,
          backgroundColor: "rgba(6, 182, 212, 0.75)",
          borderColor: "#06b6d4",
          borderWidth: 1,
          borderRadius: 6,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: "top", labels: { color: "#94a3b8", font: { family: "Inter", size: 12 } } },
      },
      scales: {
        x: { grid: { color: "rgba(255, 255, 255, 0.04)" }, ticks: { color: "#64748b" } },
        y: { grid: { color: "rgba(255, 255, 255, 0.04)" }, ticks: { color: "#64748b" } },
      },
    },
  });
}

/* =========================================================================
   RUN DETAIL PAGE LOGIC
   ========================================================================= */

async function initRunDetailPage() {
  const parts = window.location.pathname.split("/");
  const runId = parts[parts.length - 1];

  if (!runId) return;

  try {
    const res = await fetch(`/api/runs/${runId}`);
    if (!res.ok) {
      document.body.innerHTML = `
        <div class="container" style="text-align: center; padding-top: 100px;">
          <h2>Run Not Found</h2>
          <p style="color: var(--text-secondary); margin: 16px 0;">Record <code>${runId}</code> does not exist.</p>
          <a href="/" class="btn btn-primary">← Return to Dashboard</a>
        </div>
      `;
      return;
    }

    const run = await res.json();
    renderRunDetails(run);
  } catch (err) {
    console.error("Failed to load run details:", err);
  }
}

function renderRunDetails(run) {
  // Title & Header
  const titleEl = document.getElementById("detailPrTitle");
  const repoEl = document.getElementById("detailRepo");
  const idEl = document.getElementById("detailRunId");
  const dateEl = document.getElementById("detailCreatedAt");
  const durationEl = document.getElementById("detailDuration");
  const prBtn = document.getElementById("detailPrBtn");
  const engineBadgeEl = document.getElementById("detailEngineBadge");
  const statusBadgeEl = document.getElementById("detailStatusBadge");

  if (titleEl) titleEl.textContent = run.pr_title || "PR Analysis & Test Run";
  if (repoEl) repoEl.textContent = run.repo || run.pr_url || "";
  if (idEl) idEl.textContent = run.run_id;
  if (dateEl) dateEl.textContent = formatDate(run.created_at);
  if (durationEl) durationEl.textContent = formatDuration(run.duration_seconds);

  if (prBtn && run.pr_url) {
    prBtn.href = run.pr_url;
  }

  // Engine Badge
  if (engineBadgeEl) {
    const isUnreal = run.engine === "unreal";
    engineBadgeEl.className = isUnreal ? "badge badge-unreal" : "badge badge-unity";
    engineBadgeEl.textContent = isUnreal ? "🎮 Unreal Engine (C++)" : "🎮 Unity (C#)";
  }

  // Status Badge
  if (statusBadgeEl) {
    const passed = run.status === "success";
    statusBadgeEl.className = passed ? "badge badge-success" : "badge badge-failed";
    statusBadgeEl.textContent = passed ? "✅ All Tests Passed" : "❌ Failures Detected";
  }

  // Model & AI Invocations
  const modelEl = document.getElementById("detailModel");
  const callsEl = document.getElementById("detailAiCalls");
  const speedEl = document.getElementById("detailSpeed");
  if (modelEl) modelEl.textContent = run.model_used || "ollama/qwen2.5:3b";
  if (callsEl) callsEl.textContent = `${run.num_ai_calls || 1} calls`;
  if (speedEl) {
    const spd = run.duration_seconds > 0 ? (run.total_tokens / run.duration_seconds).toFixed(1) : "0.0";
    speedEl.textContent = `${spd} tok/s`;
  }

  // Token Metrics
  const totalTokensEl = document.getElementById("detailTotalTokens");
  const promptTokensEl = document.getElementById("detailPromptTokens");
  const compTokensEl = document.getElementById("detailCompTokens");

  if (totalTokensEl) totalTokensEl.textContent = formatNumber(run.total_tokens);
  if (promptTokensEl) promptTokensEl.textContent = formatNumber(run.prompt_tokens);
  if (compTokensEl) compTokensEl.textContent = formatNumber(run.completion_tokens);

  // Charts
  renderRunTokenChart(run);
  renderRunTestsDonutChart(run);

  // Test Results Summary
  const testTotalEl = document.getElementById("detailTestTotal");
  const testPassedEl = document.getElementById("detailTestPassed");
  const testFailedEl = document.getElementById("detailTestFailed");

  if (testTotalEl) testTotalEl.textContent = run.total_tests || 0;
  if (testPassedEl) testPassedEl.textContent = run.passed_tests || 0;
  if (testFailedEl) testFailedEl.textContent = run.failed_tests || 0;

  // Regression Areas
  const regContainer = document.getElementById("detailRegressionContainer");
  if (regContainer) {
    const areas = run.regression_areas || [];
    if (areas.length === 0) {
      regContainer.innerHTML = `<p style="color: var(--text-muted); font-size: 13px;">No critical regression risks identified.</p>`;
    } else {
      regContainer.innerHTML = `
        <div style="overflow-x: hidden; width: 100%;">
          <table class="data-table" style="font-size: 13px; table-layout: fixed; width: 100%;">
            <thead>
              <tr>
                <th style="width: 28%; word-break: break-word;">Component / Class</th>
                <th style="width: 72%; word-break: break-word;">Potential Regression Risk</th>
              </tr>
            </thead>
            <tbody>
              ${areas
                .map(
                  (a) => `
                <tr>
                  <td style="word-break: break-word;"><strong><code>${a.component || "General"}</code></strong></td>
                  <td style="word-break: break-word; line-height: 1.5;">${a.risk || ""}</td>
                </tr>
              `
                )
                .join("")}
            </tbody>
          </table>
        </div>
      `;
    }
  }

  // Failure & Suggested Fix Box
  const failSection = document.getElementById("detailFailureSection");
  if (failSection) {
    if (run.status === "success" || !run.failures || run.failures.length === 0) {
      failSection.style.display = "none";
    } else {
      failSection.style.display = "block";
      const failure = run.failures[0];
      const fix = run.fix_result || {};

      const testNameEl = document.getElementById("detailFailingTestName");
      const errorMsgEl = document.getElementById("detailErrorMessage");
      const stackTraceEl = document.getElementById("detailStackTrace");
      const rootCauseEl = document.getElementById("detailRootCause");
      const fixCodeEl = document.getElementById("detailFixCode");
      const commitBtn = document.getElementById("detailCommitBtn");

      if (testNameEl) testNameEl.textContent = failure.test_name || "TestFailure";
      if (errorMsgEl) errorMsgEl.textContent = failure.message || "Assertion failed";
      if (stackTraceEl) stackTraceEl.textContent = failure.stack_trace || "at test execution";
      if (rootCauseEl) rootCauseEl.textContent = fix.root_cause_explanation || "Logic discrepancy detected in diff.";
      if (fixCodeEl) fixCodeEl.textContent = fix.fixed_method_code || fix.suggested_diff || "// Code fix available";

      if (commitBtn && run.pr_url) {
        commitBtn.href = `${run.pr_url.replace(/\/$/, "")}/files`;
      }
    }
  }

  // Generated Test Suite
  const testCodeEl = document.getElementById("detailTestCode");
  if (testCodeEl && run.test_code) {
    testCodeEl.textContent = run.test_code.trim();
  }

  // Raw JSON
  const rawJsonEl = document.getElementById("detailRawJson");
  if (rawJsonEl) {
    rawJsonEl.textContent = JSON.stringify(run, null, 2);
  }
}

function renderRunTokenChart(run) {
  const canvas = document.getElementById("runTokenChart");
  if (!canvas) return;

  const prompt = run.prompt_tokens || 0;
  const comp = run.completion_tokens || 0;

  new Chart(canvas, {
    type: "doughnut",
    data: {
      labels: ["Prompt Tokens", "Completion Tokens"],
      datasets: [
        {
          data: [prompt, comp],
          backgroundColor: ["rgba(99, 102, 241, 0.8)", "rgba(6, 182, 212, 0.8)"],
          borderColor: "rgba(20, 29, 47, 0.9)",
          borderWidth: 2,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: "bottom", labels: { color: "#94a3b8", font: { family: "Inter", size: 12 } } },
      },
      cutout: "70%",
    },
  });
}

function renderRunTestsDonutChart(run) {
  const canvas = document.getElementById("runTestsDonutChart");
  if (!canvas) return;

  const passed = run.passed_tests || 0;
  const failed = run.failed_tests || 0;

  new Chart(canvas, {
    type: "doughnut",
    data: {
      labels: ["Passed Tests", "Failed Tests"],
      datasets: [
        {
          data: [passed, failed],
          backgroundColor: ["rgba(16, 185, 129, 0.85)", "rgba(244, 63, 94, 0.85)"],
          borderColor: "rgba(20, 29, 47, 0.9)",
          borderWidth: 2,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: "bottom", labels: { color: "#94a3b8", font: { family: "Inter", size: 11 } } },
      },
      cutout: "65%",
    },
  });
}
