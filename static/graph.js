
(() => {
  let cy = null;

  window.renderRepoPilotGraph = function (analysis) {
    const graph = document.querySelector("#dependency-graph");
    if (!graph || !window.cytoscape) {
      if (graph) graph.textContent = "Graph library unavailable. Check your internet connection.";
      return;
    }

    if (cy) cy.destroy();

    const nodes = (analysis.python_files || []).map(path => ({
      data: { id: path, label: path.split("/").pop() }
    }));

    const nodeIds = new Set(nodes.map(node => node.data.id));

    const edges = (analysis.edges || [])
      .filter(edge => nodeIds.has(edge.from) && nodeIds.has(edge.to))
      .map((edge, index) => ({
        data: {
          id: "edge" + index,
          source: edge.from,
          target: edge.to
        }
      }));

    cy = window.cytoscape({
      container: graph,
      elements: [...nodes, ...edges],
      style: [
        {
          selector: "node",
          style: {
            "label": "data(label)",
            "background-color": "#2563eb",
            "color": "#e5e7eb",
            "font-size": 12,
            "text-wrap": "wrap",
            "text-max-width": 130,
            "width": 42,
            "height": 42,
            "text-valign": "bottom",
            "text-margin-y": 9,
            "border-width": 2,
            "border-color": "#60a5fa"
          }
        },
        {
          selector: "edge",
          style: {
            "width": 2,
            "line-color": "#64748b",
            "target-arrow-color": "#94a3b8",
            "target-arrow-shape": "triangle",
            "curve-style": "bezier"
          }
        },
        {
          selector: ".selected",
          style: {
            "background-color": "#f59e0b",
            "border-width": 4,
            "border-color": "#fde68a"
          }
        },
        {
          selector: ".direct",
          style: { "background-color": "#10b981" }
        },
        {
          selector: ".indirect",
          style: { "background-color": "#a78bfa" }
        }
      ],
      layout: {
        name: "cose",
        animate: true,
        padding: 35
      }
    });

    cy.on("tap", "node", async event => {
      const id = event.target.id();

      cy.nodes().removeClass("selected direct indirect");
      event.target.addClass("selected");

      try {
        const response = await fetch(
          (window.REPOPILOT_API_BASE || "") + "/api/impact",
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              session_id: window.repoPilotSessionId,
              selected_file: id
            })
          }
        );

        if (!response.ok) throw new Error("Impact request failed.");

        const result = await response.json();

        for (const item of result.direct_dependents || []) {
          cy.getElementById(item.file).addClass("direct");
        }

        for (const item of result.indirect_dependents || []) {
          cy.getElementById(item.file).addClass("indirect");
        }

        const name = document.querySelector("#selected-name");
        if (name) name.textContent = id;

        if (window.repoPilotSelectFile) {
          await window.repoPilotSelectFile(id);
        }
      } catch (error) {
        console.error("Graph impact error:", error);
      }
    });

    window.repoPilotCy = cy;
    cy.fit(undefined, 35);
  };
})();

document.addEventListener("DOMContentLoaded", () => {
  const fit = document.querySelector("#graph-fit");
  const reset = document.querySelector("#graph-reset");

  if (fit) fit.addEventListener("click", () => {
    if (window.repoPilotCy) window.repoPilotCy.fit(undefined, 35);
  });

  if (reset) reset.addEventListener("click", () => {
    if (window.repoPilotCy) {
      window.repoPilotCy.layout({
        name: "cose",
        animate: true,
        padding: 35
      }).run();
    }
  });
});
