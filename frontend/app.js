const SECTOR_COLORS = { automotive: "var(--automotive)", home_service: "var(--home-service)", medicare: "var(--medicare)" };
const SAMPLES = {
  pet: "Thank you for calling [ORGANIZATION]. This is [PERSON_NAME], how can I help you today? Hi, I would like to book boarding for my two dogs next weekend. Drop off on Friday morning and pick up on Sunday afternoon. Do you have a suite available? We have the classic suite and the luxury suite, and play time is included in both packages. How much is the luxury suite per night? The luxury suite is [MONEY_AMOUNT] a night, and for two dogs sharing the same suite there is a multi pet discount. They are both vaccinated, I can send the records by email. Perfect, I will put the reservation under your name. Do they need to bring their own food? Yes please bring the food they usually eat and any medication with the instructions. Great, thank you so much.",
  glass: "Thank you for calling [ORGANIZATION]. This is [PERSON_NAME]. Hi, I have a crack in my windshield on the driver side and it keeps growing. Can you replace it? Absolutely, can I get the year and model of your vehicle? It is a [DATE] Toyota Tundra, [VEHICLE_ID]. And do you have insurance that covers glass? Yes, I have full coverage. Then in many cases there is no out of pocket cost, we can bill the insurance directly. Do you want us to come to your house or do you prefer to drop it off at the shop? Mobile service would be great, I work from home. We have an opening tomorrow morning between eight and ten. That works. I will send you a confirmation by text with the technician name and the arrival window.",
  car: "Thank you for calling [ORGANIZATION], new car sales, this is [PERSON_NAME]. Hi, I am interested in leasing a new SUV and I would like to know what the monthly payment would be. Sure, do you have a trade in? Yes, I own a [DATE] sedan with about forty thousand miles, and I still owe some money on it. We can appraise it and put the equity toward the deal. What about my credit, I had a late payment last year. Our finance team works with many lenders, so we can usually find a program. What down payment would you be comfortable with? Maybe [MONEY_AMOUNT]. I can have a manager call you with a number today, what is the best phone number to reach you?",
};

const byId = (id) => document.getElementById(id);

function extractTranscript(fileContent, fileName) {
  if (!fileName.toLowerCase().endsWith(".json")) return fileContent;
  const document = JSON.parse(fileContent);
  if (typeof document.text !== "string") throw new Error("o arquivo JSON não tem o campo text");
  return document.text;
}

async function loadFile(file) {
  try {
    byId("transcript").value = extractTranscript(await file.text(), file.name);
    byId("error").hidden = true;
  } catch (error) {
    showError(error.message);
  }
}

function showError(message) {
  byId("error-text").textContent = message;
  byId("error").hidden = false;
  byId("result").hidden = true;
}

function renderSectorBars(scores) {
  byId("sector-bars").innerHTML = Object.entries(scores).sort((a, b) => b[1] - a[1]).map(([sector, probability]) =>
    `<div class="bar"><span class="label">${sector}</span>
       <span class="track"><span class="fill" style="width:${probability * 100}%;background:${SECTOR_COLORS[sector]}"></span></span>
       <span class="percent">${(probability * 100).toFixed(1)}%</span></div>`).join("");
}

function renderSubgroup(subgroup) {
  byId("subgroup-name").innerHTML = subgroup.name + (subgroup.ambiguous ? '<span class="pill">atribuição frágil</span>' : "");
  byId("subgroup-detail").textContent = `Segundo mais próximo: ${subgroup.runner_up} (margem ${subgroup.margin.toFixed(2)})`;
}

function renderEvidence(evidence) {
  const chips = (label, terms) => terms.map((term) => `<span class="chip" title="${label}">${term}</span>`).join("");
  byId("evidence").innerHTML = evidence ? chips("termo que sustenta o setor", evidence.sector_terms) + chips("termo do subgrupo", evidence.subgroup_terms) : "";
}

function renderMeta(result) {
  const warnings = [];
  if (result.low_confidence) warnings.push("baixa confiança no setor");
  if (result.warnings.includes("transcricao_curta")) warnings.push("transcrição curta");
  byId("meta").textContent = `${result.latency_ms.toFixed(1)} ms · modelo ${result.model_version}` + (warnings.length ? ` · aviso: ${warnings.join(", ")}` : "");
}

async function segment() {
  const text = byId("transcript").value.trim();
  if (!text) return;
  byId("segment-button").disabled = true;
  byId("error").hidden = true;
  try {
    const response = await fetch("../segment?explain=true", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text }),
    });
    if (!response.ok) throw new Error((await response.json()).detail?.[0]?.msg || `erro ${response.status}`);
    const result = await response.json();
    renderSectorBars(result.sector_scores);
    renderSubgroup(result.subgroup);
    renderEvidence(result.evidence);
    renderMeta(result);
    byId("result").hidden = false;
    setTimeout(loadRecent, 400);
  } catch (error) {
    showError(error.message);
  } finally {
    byId("segment-button").disabled = false;
  }
}

async function loadRecent() {
  try {
    const response = await fetch("../recent?limit=8");
    if (!response.ok) return;
    const rows = await response.json();
    if (!rows.length) return;
    byId("recent-card").hidden = false;
    byId("recent-rows").innerHTML = rows.map((row) =>
      `<tr><td>${new Date(row.ts).toLocaleTimeString()}</td><td>${row.sector}</td>
       <td>${row.subgroup}${row.ambiguous ? '<span class="pill">ambíguo</span>' : ""}</td>
       <td>${(row.sector_probability * 100).toFixed(0)}%</td></tr>`).join("");
  } catch (error) {
    /* o histórico é opcional */
  }
}

function setUpDropzone() {
  const zone = byId("dropzone");
  zone.addEventListener("dragover", (event) => { event.preventDefault(); zone.classList.add("dragging"); });
  zone.addEventListener("dragleave", () => zone.classList.remove("dragging"));
  zone.addEventListener("drop", (event) => {
    event.preventDefault();
    zone.classList.remove("dragging");
    if (event.dataTransfer.files[0]) loadFile(event.dataTransfer.files[0]);
  });
  byId("file-input").addEventListener("change", (event) => event.target.files[0] && loadFile(event.target.files[0]));
}

document.querySelectorAll("button[data-sample]").forEach((button) =>
  button.addEventListener("click", () => { byId("transcript").value = SAMPLES[button.dataset.sample]; }));
byId("segment-button").addEventListener("click", segment);
setUpDropzone();
loadRecent();
