const API_BASE = "http://localhost:8000"; // adjust to your backend URL

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
      tr.innerHTML = `
        <td class="py-2 px-4 border-b">${row.Fecha || ""}</td>
        <td class="py-2 px-4 border-b">${row.Causa || ""}</td>
        <td class="py-2 px-4 border-b"><a class="text-blue-500 underline" href="${row.Link || "#"}" target="_blank">Ver</a></td>
      `;
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
