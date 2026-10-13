(() => {
  const form = document.querySelector('#upload-form');
  const input = document.querySelector('#project-zip');
  const button = document.querySelector('#analyze-button');
  const status = document.querySelector('#status');
  const workspace = document.querySelector('#workspace');
  const fileTree = document.querySelector('#file-tree');
  const relationships = document.querySelector('#relationships');
  const impactResults = document.querySelector('#impact-results');
  const selectedName = document.querySelector('#selected-name');
  const warnings = document.querySelector('#warnings');
  const API_BASE = window.REPOPILOT_API_BASE || '';
  let sessionId = null;
  let currentAnalysis = null;

  function el(tag, text, className) {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (className) node.className = className;
    return node;
  }
  function message(text, error = false) {
    status.textContent = text;
    status.classList.toggle('error', error);
  }
  async function api(path, options) {
    const response = await fetch(`${API_BASE}${path}`, options);
    let payload;
    try { payload = await response.json(); } catch { payload = {}; }
    if (!response.ok) throw new Error(payload.detail || `Request failed (${response.status}).`);
    return payload;
  }
  function renderFiles(data) {
    fileTree.replaceChildren();
    const folders = new Map();
    for (const file of data.files) {
      const parts = file.path.split('/');
      let parent = fileTree;
      let prefix = '';
      for (const folder of parts.slice(0, -1)) {
        prefix = prefix ? `${prefix}/${folder}` : folder;
        if (!folders.has(prefix)) {
          const group = el('div', undefined, 'tree-folder');
          const label = el('div', `â–¸ ${folder}`, 'folder-label');
          group.append(label);
          const children = el('div', undefined, 'folder-children');
          group.append(children);
          parent.append(group);
          folders.set(prefix, children);
        }
        parent = folders.get(prefix);
      }
      const isPython = file.type === 'python';
      const item = el(isPython ? 'button' : 'div', isPython ? `PY  ${parts[parts.length - 1]}` : `Â·  ${parts[parts.length - 1]}`, isPython ? 'tree-file python-file' : 'tree-file');
      if (isPython) {
        item.type = 'button';
        item.title = file.path;
        item.addEventListener('click', () => selectFile(file.path));
        item.dataset.path = file.path;
      } else item.title = file.path;
      parent.append(item);
    }
    document.querySelector('#file-count').textContent = `${data.files.length} files`;
  }
  function renderRelationships(data) {
    relationships.replaceChildren();
    document.querySelector('#edge-count').textContent = `${data.edges.length} imports`;
    if (!data.edges.length) {
      relationships.append(el('p', 'No internal Python import relationships were resolved.', 'muted'));
      return;
    }
    for (const edge of data.edges) {
      const row = el('div', undefined, 'relationship-row');
      row.append(el('code', edge.from));
      row.append(el('span', 'â†’', 'arrow'));
      row.append(el('code', edge.to));
      relationships.append(row);
    }
  }
  function renderWarnings(data) {
    warnings.replaceChildren();
    const all = [];
    for (const warning of data.warnings || []) all.push(`Parser warning â€” ${warning.file}: ${warning.message}`);
    for (const item of data.unresolved_imports || []) all.push(`Unresolved import â€” ${item.file}: ${item.import}${item.line ? ` (line ${item.line})` : ''}`);
    if (!all.length) warnings.append(el('p', 'No parser warnings or unresolved imports were reported.', 'muted'));
    else for (const text of all) warnings.append(el('p', text, 'warning-item'));
    if (!(data.python_files || []).length) warnings.append(el('p', 'No Python files were detected in this archive.', 'warning-item'));
  }
  async function selectFile(path) {
    if (!sessionId) return;
    document.querySelectorAll('.python-file').forEach(node => node.classList.toggle('active', node.dataset.path === path));
    selectedName.textContent = path;
    impactResults.replaceChildren(el('p', 'Calculating dependentsâ€¦', 'muted'));
    try {
      const result = await api('/api/impact', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ session_id: sessionId, selected_file: path }) });
      impactResults.replaceChildren();
      const direct = el('section', undefined, 'impact-group');
      direct.append(el('h3', `Direct dependents (${result.direct_dependents.length})`));
      appendPaths(direct, result.direct_dependents);
      const indirect = el('section', undefined, 'impact-group');
      indirect.append(el('h3', `Indirect dependents (${result.indirect_dependents.length})`));
      appendPaths(indirect, result.indirect_dependents);
      impactResults.append(direct, indirect, el('p', result.note, 'muted small'));
    } catch (error) {
      impactResults.replaceChildren(el('p', error.message, 'error'));
    }
  }
  function appendPaths(container, items) {
    if (!items.length) { container.append(el('p', 'None found.', 'muted')); return; }
    const list = el('ul', undefined, 'path-list');
    for (const item of items) {
      const li = el('li');
      li.append(el('code', item.file));
      li.append(el('p', item.path.join('  â†  '), 'path-detail'));
      list.append(li);
    }
    container.append(list);
  }
  form.addEventListener('submit', async event => {
    event.preventDefault();
    const file = input.files && input.files[0];
    if (!file) { message('Choose a ZIP archive first.', true); return; }
    if (!file.name.toLowerCase().endsWith('.zip')) { message('Only .zip archives are supported.', true); return; }
    button.disabled = true;
    button.textContent = 'Analyzingâ€¦';
    workspace.classList.add('hidden');
    message('Uploading and parsing the actual project filesâ€¦');
    try {
      const body = new FormData();
      body.append('file', file);
      const data = await api('/api/analyze', { method: 'POST', body });
      sessionId = data.session_id;
      currentAnalysis = data; window.repoPilotAnalysis = data; window.repoPilotSessionId = sessionId; if (window.updateRepoPilotDashboard) window.updateRepoPilotDashboard(data); if (window.renderRepoPilotGraph) window.renderRepoPilotGraph(data); window.repoPilotAnalysis = data; window.repoPilotSessionId = sessionId; if (window.renderRepoPilotGraph) window.renderRepoPilotGraph(data); window.repoPilotAnalysis = data; window.repoPilotSessionId = sessionId; if (window.renderRepoPilotGraph) window.renderRepoPilotGraph(data); window.repoPilotAnalysis = data; window.repoPilotSessionId = sessionId; if (window.renderRepoPilotGraph) window.renderRepoPilotGraph(data);
      renderFiles(data);
      renderRelationships(data);
      renderWarnings(data);
      workspace.classList.remove('hidden');
      message(`Analysis complete: ${data.files.length} files scanned, ${data.python_files.length} Python files detected.`);
      if (data.python_files.length) await selectFile(data.python_files[0]);
      else { selectedName.textContent = 'No Python file'; impactResults.replaceChildren(el('p', 'Upload a project containing at least one .py file to run impact analysis.', 'muted')); }
    } catch (error) {
      message(error.message || 'Could not analyze this archive.', true);
    } finally {
      button.disabled = false;
      button.textContent = 'Analyze project';
    }
  });
})();






function renderMetricsDashboard(analysis) {
    const section = document.getElementById("metrics-dashboard");
    const summary = document.getElementById("metrics-summary");
    const table = document.getElementById("metrics-table");
    if (!section || !summary || !table) return;

    const metrics = analysis && Array.isArray(analysis.metrics) ? analysis.metrics : [];
    section.style.display = "block";

    if (!metrics.length) {
        summary.textContent = "No Python metrics found.";
        table.innerHTML = "";
        return;
    }

    const totalLines = metrics.reduce((sum, m) => sum + (m.lines || 0), 0);
    const totalLoc = metrics.reduce((sum, m) => sum + (m.loc || 0), 0);
    const totalFunctions = metrics.reduce((sum, m) => sum + (m.functions || 0), 0);
    const totalClasses = metrics.reduce((sum, m) => sum + (m.classes || 0), 0);

    summary.innerHTML = `
        <div style="display:flex;flex-wrap:wrap;gap:12px;margin:16px 0">
            ${metricCard("Python Files", metrics.length)}
            ${metricCard("Total Lines", totalLines)}
            ${metricCard("Code Lines", totalLoc)}
            ${metricCard("Functions", totalFunctions)}
            ${metricCard("Classes", totalClasses)}
        </div>`;

    table.innerHTML = `
        <div style="overflow-x:auto">
        <table style="width:100%;border-collapse:collapse;color:inherit">
        <thead><tr>
            <th style="text-align:left;padding:10px;border-bottom:1px solid #374151">File</th>
            <th style="padding:10px;border-bottom:1px solid #374151">Lines</th>
            <th style="padding:10px;border-bottom:1px solid #374151">LOC</th>
            <th style="padding:10px;border-bottom:1px solid #374151">Functions</th>
            <th style="padding:10px;border-bottom:1px solid #374151">Classes</th>
            <th style="padding:10px;border-bottom:1px solid #374151">Complexity</th>
            <th style="padding:10px;border-bottom:1px solid #374151">Long Functions</th>
        </tr></thead>
        <tbody>${metrics.map(m => `
            <tr>
                <td style="padding:10px;border-bottom:1px solid #374151;word-break:break-word">${escapeMetricText(m.file)}</td>
                <td style="text-align:center;padding:10px;border-bottom:1px solid #374151">${m.lines ?? "?"}</td>
                <td style="text-align:center;padding:10px;border-bottom:1px solid #374151">${m.loc ?? "?"}</td>
                <td style="text-align:center;padding:10px;border-bottom:1px solid #374151">${m.functions ?? "?"}</td>
                <td style="text-align:center;padding:10px;border-bottom:1px solid #374151">${m.classes ?? "?"}</td>
                <td style="text-align:center;padding:10px;border-bottom:1px solid #374151">${m.complexity ?? "?"}</td>
                <td style="text-align:center;padding:10px;border-bottom:1px solid #374151">${Array.isArray(m.long_functions) ? m.long_functions.length : 0}</td>
            </tr>`).join("")}
        </tbody></table></div>`;

    const longFunctions = metrics.flatMap(m =>
        (m.long_functions || []).map(f => `${m.file}: ${f.name} (${f.lines} lines)`)
    );
    if (longFunctions.length) {
        table.insertAdjacentHTML("beforeend",
            `<h3>Long Functions (&gt;30 lines)</h3><ul>${longFunctions.map(f => `<li>${escapeMetricText(f)}</li>`).join("")}</ul>`
        );
    }
}

function metricCard(label, value) {
    return `<div style="flex:1;min-width:120px;padding:16px;background:#1f2937;border-radius:10px">
        <div style="font-size:13px;color:#9ca3af">${label}</div>
        <div style="font-size:26px;font-weight:700;margin-top:6px">${value}</div>
    </div>`;
}

function escapeMetricText(value) {
    return String(value ?? "").replace(/[&<>"']/g, ch => ({
        "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"
    })[ch]);
}

if (typeof window !== "undefined") window.updateRepoPilotDashboard = renderMetricsDashboard;


/* REPOPILOT_REPORT_DOWNLOAD_BUTTONS */
(function () {
    function addReportButtons() {
        const section = document.getElementById("metrics-dashboard");
        if (!section || document.getElementById("report-download-buttons")) return;

        const box = document.createElement("div");
        box.id = "report-download-buttons";
        box.style.cssText = "display:flex;gap:12px;flex-wrap:wrap;margin:18px 0";

        const buttonStyle = "display:inline-block;padding:11px 16px;border-radius:8px;background:#2563eb;color:white;text-decoration:none;font-weight:600";

        [
            { label: "Download JSON Report", type: "json" },
            { label: "Download HTML Report", type: "html" }
        ].forEach(function (item) {
            const link = document.createElement("a");
            link.textContent = item.label;
            link.href = "#";
            link.style.cssText = buttonStyle;
            link.addEventListener("click", function (event) {
                event.preventDefault();
                const id = window.repoPilotSessionId;
                if (!id) {
                    alert("Please upload and analyze a ZIP file first.");
                    return;
                }
                window.location.href = "/api/report/" + encodeURIComponent(id) + "/" + item.type;
            });
            box.appendChild(link);
        });

        section.insertBefore(box, section.firstChild);
    }

    const previous = window.updateRepoPilotDashboard;
    window.updateRepoPilotDashboard = function (analysis) {
        if (typeof previous === "function") previous(analysis);
        addReportButtons();
    };

    document.addEventListener("DOMContentLoaded", addReportButtons);
})();
