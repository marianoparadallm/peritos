const API_BASE =
  window.localStorage.getItem("API_BASE") ||
  window.API_BASE ||
  ""; // defaults to relative URLs

async function fetchData() {
  const msg = document.getElementById("message");
  try {
    const response = await fetch(`${API_BASE}/data`);
    if (!response.ok) throw new Error("Network response was not ok");
    const data = await response.json();
    const tbody = document.getElementById("data-body");
    tbody.innerHTML = "";
    data.forEach((row) => {
      const tr = document.createElement("tr");

      const tdFecha = document.createElement("td");
      tdFecha.className = "py-2 px-4 border-b";
      tdFecha.textContent = row.Fecha || "";
      tr.appendChild(tdFecha);

      const tdCausa = document.createElement("td");
      tdCausa.className = "py-2 px-4 border-b";
      tdCausa.textContent = row.Causa || "";
      tr.appendChild(tdCausa);

      const tdLink = document.createElement("td");
      tdLink.className = "py-2 px-4 border-b";
      const link = document.createElement("a");
      link.className = "text-blue-500 underline";
      link.textContent = "Ver";
      link.setAttribute("href", row.Link || "#");
      link.setAttribute("target", "_blank");
      tdLink.appendChild(link);
      tr.appendChild(tdLink);

      tbody.appendChild(tr);
    });
    msg.textContent = "";
  } catch (error) {
    msg.textContent = "Error obteniendo datos.";
  }
}

async function runScraping() {
  const msg = document.getElementById("message");
  msg.textContent = "Ejecutando scraping...";
  try {
    const response = await fetch(`${API_BASE}/scrape`, { method: "POST" });
    if (response.ok) {
      msg.textContent = "Scraping iniciado correctamente.";
      await fetchData();
    } else {
      msg.textContent = "Error al iniciar scraping.";
    }
  } catch (error) {
    msg.textContent = "Error al iniciar scraping.";
  }
}

document.getElementById("run-scraping").addEventListener("click", runScraping);
document.getElementById("refresh-data").addEventListener("click", fetchData);

// Initial load
fetchData();
