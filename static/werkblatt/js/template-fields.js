"use strict";

const documentationForm = document.querySelector("#documentation-form");
const templateSelect = documentationForm?.querySelector("#id_template");
let pendingTemplateFields = null;
let activeTemplate = templateSelect?.value || "";
const valuesByTemplate = new Map();

const currentCustomValues = () => {
  const values = [];
  const region = document.querySelector("#custom-fields-region");
  for (const input of region?.querySelectorAll("[name^=custom_]") || []) {
    if ((input.type === "checkbox" || input.type === "radio") && !input.checked) continue;
    values.push([input.name, input.value]);
  }
  return values;
};

const loadTemplateFields = async () => {
  const region = document.querySelector("#custom-fields-region");
  if (!documentationForm || !templateSelect || !region || !templateSelect.value) return;
  const data = new FormData();
  data.append("csrfmiddlewaretoken", documentationForm.querySelector("[name=csrfmiddlewaretoken]").value);
  data.append("template", templateSelect.value);
  for (const [name, value] of valuesByTemplate.get(templateSelect.value) || []) data.append(name, value);
  region.setAttribute("aria-busy", "true");
  const response = await fetch(region.dataset.customFieldsUrl, {
    method: "POST",
    body: data,
    credentials: "same-origin",
    headers: {"X-Requested-With": "XMLHttpRequest"},
  });
  if (!response.ok) throw new Error("Zusatzfelder konnten nicht geladen werden.");
  region.outerHTML = await response.text();
};

templateSelect?.addEventListener("change", () => {
  valuesByTemplate.set(activeTemplate, currentCustomValues());
  activeTemplate = templateSelect.value;
  pendingTemplateFields = loadTemplateFields().catch(() => {
    const region = document.querySelector("#custom-fields-region");
    region?.removeAttribute("aria-busy");
    const version = region?.querySelector("[name=displayed_template_version_id]");
    if (version) version.value = "";
  }).finally(() => { pendingTemplateFields = null; });
});

documentationForm?.addEventListener("submit", async (event) => {
  if (!pendingTemplateFields) return;
  event.preventDefault();
  const submitter = event.submitter;
  await pendingTemplateFields;
  documentationForm.requestSubmit(submitter);
});
