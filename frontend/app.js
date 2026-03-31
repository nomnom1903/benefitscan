/**
 * BenefitScan — Frontend Application
 *
 * Vanilla JavaScript, no frameworks, no build step.
 * The app does four things:
 *   1. Accept PDF file uploads (drag-drop or click-to-browse)
 *   2. Call the API to extract fields from each PDF via Claude
 *   3. Render extracted data in an editable review table
 *   4. Trigger Excel export download
 *
 * State management: simple module-level variables (no Redux, no React state).
 * For V1 with ~20 plans max, this is completely sufficient.
 */

// ─── API base URL ─────────────────────────────────────────────────────────────
// When deployed: set BENEFITSCAN_API_URL to your backend URL (e.g. Render).
// Locally: falls back to same origin (FastAPI serves both).
const API = window.BENEFITSCAN_API_URL || window.location.origin;

// ─── Column definitions ───────────────────────────────────────────────────────
// Ordered list of field keys and their display labels.
// Must match the SBC_FIELD_KEYS / SBC_FIELD_LABELS in app/models/sbc.py
const FIELDS = [
  { key: "plan_name",                              label: "Plan Name" },
  { key: "carrier_name",                           label: "Carrier" },
  { key: "plan_type",                              label: "Plan Type" },
  { key: "deductible_individual_in_network",       label: "Deductible — Ind. (In-Net)" },
  { key: "deductible_family_in_network",           label: "Deductible — Fam. (In-Net)" },
  { key: "deductible_individual_out_of_network",   label: "Deductible — Ind. (OON)" },
  { key: "deductible_family_out_of_network",       label: "Deductible — Fam. (OON)" },
  { key: "oop_max_individual_in_network",          label: "OOP Max — Ind. (In-Net)" },
  { key: "oop_max_family_in_network",              label: "OOP Max — Fam. (In-Net)" },
  { key: "copay_pcp",                              label: "PCP Copay" },
  { key: "copay_specialist",                       label: "Specialist Copay" },
  { key: "copay_emergency_room",                   label: "ER Copay" },
  { key: "copay_urgent_care",                      label: "Urgent Care Copay" },
  { key: "coinsurance_in_network",                 label: "Coinsurance (In-Net)" },
  { key: "rx_tier1_generic",                       label: "Rx Tier 1 — Generic" },
  { key: "rx_tier2_preferred_brand",               label: "Rx Tier 2 — Pref. Brand" },
  { key: "rx_tier3_nonpreferred_brand",            label: "Rx Tier 3 — Non-Pref. Brand" },
  { key: "rx_tier4_specialty",                     label: "Rx Tier 4 — Specialty" },
  { key: "hsa_eligible",                           label: "HSA Eligible" },
  { key: "separate_drug_deductible",               label: "Separate Drug Deductible" },
  { key: "preventive_care",                        label: "Preventive Care" },
  { key: "inpatient_hospital",                     label: "Inpatient Hospital" },
  { key: "outpatient_surgery",                     label: "Outpatient Surgery" },
  { key: "mental_health_copay",                    label: "Mental Health Copay" },
  { key: "telehealth_copay",                       label: "Telehealth Copay" },
  { key: "premium_employee_only",                  label: "Premium — Ee Only" },
  { key: "premium_employee_spouse",                label: "Premium — Ee + Spouse" },
  { key: "premium_employee_children",             label: "Premium — Ee + Children" },
  { key: "premium_family",                         label: "Premium — Family" },
  { key: "effective_date",                         label: "Effective Date" },
  { key: "network_name",                           label: "Network Name" },
];

// ─── App state ────────────────────────────────────────────────────────────────
let pendingFiles = [];   // Files the user has selected, not yet uploaded
let plans = [];          // Extracted plan objects from the API

// ─────────────────────────────────────────────────────────────────────────────
// INITIALIZATION
// ─────────────────────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  setupDropzone();
  setupExtractButton();
  setupExportButton();
  setupRefreshButton();
  setupClearAllButton();
  checkApiHealth();
  loadPlans();
});

// ─────────────────────────────────────────────────────────────────────────────
// API HEALTH CHECK
// ─────────────────────────────────────────────────────────────────────────────
async function checkApiHealth() {
  const indicator = document.getElementById("api-status");
  try {
    const res = await fetch(`${API}/health`);
    if (res.ok) {
      const data = await res.json();
      indicator.textContent = `● API Connected (${data.model})`;
      indicator.className = "status-indicator ok";
    } else {
      throw new Error(`HTTP ${res.status}`);
    }
  } catch (e) {
    indicator.textContent = "● API Unreachable";
    indicator.className = "status-indicator error";
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// DROPZONE SETUP
// ─────────────────────────────────────────────────────────────────────────────
function setupDropzone() {
  const dropzone = document.getElementById("dropzone");
  const fileInput = document.getElementById("file-input");

  // Click on dropzone → open file picker
  dropzone.addEventListener("click", () => fileInput.click());
  dropzone.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") fileInput.click();
  });

  // File input change (user picked files via browser dialog)
  fileInput.addEventListener("change", () => {
    addFilesToQueue([...fileInput.files]);
    fileInput.value = ""; // Reset so same file can be re-added if needed
  });

  // Drag and drop events
  dropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropzone.classList.add("drag-over");
  });
  dropzone.addEventListener("dragleave", () => dropzone.classList.remove("drag-over"));
  dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.classList.remove("drag-over");
    const files = [...e.dataTransfer.files].filter(f => f.name.toLowerCase().endsWith(".pdf"));
    if (files.length === 0) {
      showToast("Only PDF files are supported.", "error");
      return;
    }
    addFilesToQueue(files);
  });

  // Clear queue button
  document.getElementById("clear-queue-btn").addEventListener("click", () => {
    pendingFiles = [];
    renderFileQueue();
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// FILE QUEUE RENDERING
// ─────────────────────────────────────────────────────────────────────────────
function addFilesToQueue(files) {
  // Deduplicate by name (don't add the same file twice)
  const existingNames = new Set(pendingFiles.map(f => f.file.name));
  const newFiles = files.filter(f => !existingNames.has(f.name));
  newFiles.forEach(f => pendingFiles.push({ file: f, status: "pending" }));
  renderFileQueue();
}

function renderFileQueue() {
  const queue = document.getElementById("file-queue");
  const countEl = document.getElementById("file-queue-count");
  const list = document.getElementById("file-list");

  if (pendingFiles.length === 0) {
    queue.hidden = true;
    return;
  }

  queue.hidden = false;
  countEl.textContent = `${pendingFiles.length} file${pendingFiles.length !== 1 ? "s" : ""} selected`;

  list.innerHTML = "";
  pendingFiles.forEach((item, idx) => {
    const li = document.createElement("li");
    li.className = "file-item";
    li.innerHTML = `
      <span class="file-item-icon">📄</span>
      <span class="file-item-name" title="${esc(item.file.name)}">${esc(item.file.name)}</span>
      <span class="file-item-size">${formatSize(item.file.size)}</span>
      <span class="file-item-status status-${item.status}" id="file-status-${idx}">
        ${statusLabel(item.status)}
      </span>
    `;
    list.appendChild(li);
  });
}

function updateFileStatus(idx, status) {
  pendingFiles[idx].status = status;
  const el = document.getElementById(`file-status-${idx}`);
  if (el) {
    el.className = `file-item-status status-${status}`;
    el.innerHTML = statusLabel(status);
  }
}

function statusLabel(status) {
  const labels = {
    pending:    "Queued",
    uploading:  '<span class="file-spinner"></span>Uploading…',
    processing: '<span class="file-spinner"></span>Extracting…',
    complete:   "✓ Done",
    failed:     "✗ Failed",
  };
  return labels[status] || status;
}

// ─────────────────────────────────────────────────────────────────────────────
// EXTRACT BUTTON — upload + extract all queued files
// ─────────────────────────────────────────────────────────────────────────────
function setupExtractButton() {
  document.getElementById("extract-btn").addEventListener("click", extractAll);
}

async function extractAll() {
  if (pendingFiles.length === 0) return;

  const btn = document.getElementById("extract-btn");
  btn.disabled = true;
  btn.innerHTML = '<span class="file-spinner"></span>Processing…';

  let successCount = 0;
  let failCount = 0;

  // Process files sequentially to avoid overwhelming the API
  // (V2: could parallelize with a concurrency limit of 2-3)
  for (let i = 0; i < pendingFiles.length; i++) {
    const item = pendingFiles[i];

    try {
      // ── Step 1: Upload the PDF ──────────────────────────────────────────
      updateFileStatus(i, "uploading");
      const uploadId = await uploadFile(item.file);

      // ── Step 2: Run extraction ──────────────────────────────────────────
      updateFileStatus(i, "processing");
      await extractPlan(uploadId);

      updateFileStatus(i, "complete");
      successCount++;

    } catch (err) {
      updateFileStatus(i, "failed");
      failCount++;
      console.error(`Failed to process ${item.file.name}:`, err);
    }
  }

  // Clear the queue on completion
  pendingFiles = [];
  renderFileQueue();

  // Reload the plans table
  await loadPlans();

  btn.disabled = false;
  btn.innerHTML = '<span class="btn-icon">⚡</span>Extract All Plans';

  if (failCount === 0) {
    showToast(`✓ ${successCount} plan${successCount !== 1 ? "s" : ""} extracted successfully.`, "success");
  } else {
    showToast(
      `${successCount} extracted, ${failCount} failed. Check the console for error details.`,
      "warning"
    );
  }
}

async function uploadFile(file) {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${API}/upload`, { method: "POST", body: formData });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Upload failed (HTTP ${res.status})`);
  }
  const data = await res.json();
  return data.upload_id;
}

async function extractPlan(uploadId) {
  const res = await fetch(`${API}/extract/${uploadId}`, { method: "POST" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Extraction failed (HTTP ${res.status})`);
  }
  return res.json();
}

// ─────────────────────────────────────────────────────────────────────────────
// LOAD & RENDER PLANS TABLE
// ─────────────────────────────────────────────────────────────────────────────
async function loadPlans() {
  try {
    const res = await fetch(`${API}/plans`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    plans = await res.json();
    renderTable();
  } catch (e) {
    showToast("Could not load plans from API.", "error");
    console.error(e);
  }
}

function setupRefreshButton() {
  document.getElementById("refresh-btn").addEventListener("click", () => {
    loadPlans();
    showToast("Plans refreshed.", "info");
  });
}

function renderTable() {
  const emptyState   = document.getElementById("empty-state");
  const tableWrapper = document.getElementById("table-wrapper");
  const exportBtn    = document.getElementById("export-btn");
  const clearAllBtn  = document.getElementById("clear-all-btn");
  const legend       = document.getElementById("legend");
  const subtitle     = document.getElementById("review-subtitle");

  const completePlans = plans.filter(p => p.status === "complete");

  if (completePlans.length === 0) {
    emptyState.hidden = false;
    tableWrapper.hidden = true;
    exportBtn.hidden = true;
    clearAllBtn.hidden = true;
    legend.hidden = true;
    return;
  }

  emptyState.hidden = true;
  tableWrapper.hidden = false;
  exportBtn.hidden = false;
  clearAllBtn.hidden = false;
  legend.hidden = false;
  subtitle.textContent = `${completePlans.length} plan${completePlans.length !== 1 ? "s" : ""} extracted — click any cell to edit.`;

  buildTableHeader();
  buildTableBody(completePlans);
}

function buildTableHeader() {
  const thead = document.getElementById("table-head");
  const tr = document.createElement("tr");

  // First column: Plan Name (sticky)
  const th0 = document.createElement("th");
  th0.textContent = "Plan Name";
  tr.appendChild(th0);

  // Remaining fields
  FIELDS.filter(f => f.key !== "plan_name").forEach(field => {
    const th = document.createElement("th");
    th.textContent = field.label;
    tr.appendChild(th);
  });

  // Action column (delete)
  const thDel = document.createElement("th");
  thDel.textContent = "";
  thDel.style.minWidth = "40px";
  thDel.style.maxWidth = "40px";
  tr.appendChild(thDel);

  thead.innerHTML = "";
  thead.appendChild(tr);
}

function buildTableBody(completePlans) {
  const tbody = document.getElementById("table-body");
  tbody.innerHTML = "";

  completePlans.forEach(plan => {
    const tr = document.createElement("tr");
    const fieldResults = plan.validation_report?.field_results || {};

    // Build all columns in FIELDS order (plan_name first, then the rest)
    const orderedFields = [
      FIELDS.find(f => f.key === "plan_name"),
      ...FIELDS.filter(f => f.key !== "plan_name"),
    ];

    orderedFields.forEach(field => {
      const td = document.createElement("td");
      const value = plan[field.key] || "";
      const validation = fieldResults[field.key] || { status: "OK", note: "" };

      // Color code by validation status
      const statusClass = {
        "OK":            "cell-ok",
        "Missing":       "cell-missing",
        "Review":        "cell-review",
        "Non-Compliant": "cell-noncompliant",
      }[validation.status] || "cell-ok";

      td.className = statusClass;

      // Make the cell editable via a contenteditable div
      const editable = document.createElement("div");
      editable.className = "editable-cell";
      editable.contentEditable = "true";
      editable.textContent = value;
      editable.setAttribute("data-plan-id", plan.id);
      editable.setAttribute("data-field", field.key);
      editable.setAttribute("data-original", value);

      // Show validation note in tooltip on hover (if there's a note)
      if (validation.note) {
        editable.title = `${validation.status}: ${validation.note}`;
      }

      // Save on blur (when user clicks away or tabs out)
      editable.addEventListener("blur", onCellBlur);

      // Prevent multi-line entry with Enter (single-line values only)
      editable.addEventListener("keydown", (e) => {
        if (e.key === "Enter") { e.preventDefault(); editable.blur(); }
        if (e.key === "Escape") {
          editable.textContent = editable.getAttribute("data-original");
          editable.blur();
        }
      });

      td.appendChild(editable);
      tr.appendChild(td);
    });

    // Delete button column
    const tdDel = document.createElement("td");
    tdDel.style.textAlign = "center";
    tdDel.style.minWidth = "40px";
    const delBtn = document.createElement("button");
    delBtn.className = "delete-btn";
    delBtn.title = "Remove this plan";
    delBtn.textContent = "✕";
    delBtn.addEventListener("click", () => deletePlan(plan.id));
    tdDel.appendChild(delBtn);
    tr.appendChild(tdDel);

    tbody.appendChild(tr);
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// CELL EDIT — save correction to backend
// ─────────────────────────────────────────────────────────────────────────────
async function onCellBlur(e) {
  const el = e.target;
  const planId = el.getAttribute("data-plan-id");
  const field = el.getAttribute("data-field");
  const original = el.getAttribute("data-original");
  const newValue = el.textContent.trim();

  // No change — skip the API call
  if (newValue === original) return;

  try {
    const res = await fetch(`${API}/plans/${planId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ field, value: newValue || null }),
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);

    // Update the original data attribute so subsequent blurs don't re-save
    el.setAttribute("data-original", newValue);

    // Remove the validation color since the user has manually set the value
    const td = el.closest("td");
    td.className = "cell-ok";

    showToast(`✓ Saved: ${field.replace(/_/g, " ")}`, "success");

  } catch (err) {
    showToast("Failed to save change. Check your connection.", "error");
    el.textContent = original; // Revert the cell
    console.error("Save failed:", err);
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// DELETE PLAN
// ─────────────────────────────────────────────────────────────────────────────
async function deletePlan(planId) {
  if (!confirm("Remove this plan from the comparison? This cannot be undone.")) return;

  try {
    const res = await fetch(`${API}/plans/${planId}`, { method: "DELETE" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    await loadPlans();
    showToast("Plan removed.", "info");
  } catch (err) {
    showToast("Failed to delete plan.", "error");
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// CLEAR ALL PLANS
// ─────────────────────────────────────────────────────────────────────────────
function setupClearAllButton() {
  document.getElementById("clear-all-btn").addEventListener("click", async () => {
    if (!confirm(`Delete all ${plans.filter(p => p.status === "complete").length} plans? This cannot be undone.`)) return;

    const completePlans = plans.filter(p => p.status === "complete");
    for (const plan of completePlans) {
      await fetch(`${API}/plans/${plan.id}`, { method: "DELETE" }).catch(() => {});
    }
    await loadPlans();
    showToast("All plans cleared.", "info");
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// EXPORT TO EXCEL
// ─────────────────────────────────────────────────────────────────────────────
function setupExportButton() {
  document.getElementById("export-btn").addEventListener("click", exportToExcel);
}

async function exportToExcel() {
  const btn = document.getElementById("export-btn");
  btn.disabled = true;
  btn.innerHTML = '<span class="file-spinner"></span>Generating…';

  try {
    const res = await fetch(`${API}/export`);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Export failed (HTTP ${res.status})`);
    }

    // Get the filename from the Content-Disposition header (set by FastAPI)
    const disposition = res.headers.get("Content-Disposition") || "";
    const filenameMatch = disposition.match(/filename="?([^";\n]+)"?/);
    const filename = filenameMatch ? filenameMatch[1] : "BenefitScan_Comparison.xlsx";

    // Trigger browser file download
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);

    showToast(`✓ Downloaded: ${filename}`, "success");

  } catch (err) {
    showToast(`Export failed: ${err.message}`, "error");
    console.error("Export error:", err);
  } finally {
    btn.disabled = false;
    btn.innerHTML = "⬇ Export to Excel";
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// TOAST NOTIFICATIONS
// ─────────────────────────────────────────────────────────────────────────────
function showToast(message, type = "info") {
  const container = document.getElementById("toast-container");
  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.textContent = message;
  container.appendChild(toast);

  // Auto-remove after 4 seconds
  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transition = "opacity 0.3s";
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

// ─────────────────────────────────────────────────────────────────────────────
// UTILITIES
// ─────────────────────────────────────────────────────────────────────────────

/** Escape HTML to prevent XSS when rendering user-provided filenames */
function esc(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

/** Format file size as human-readable string */
function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
