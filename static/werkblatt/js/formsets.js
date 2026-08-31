"use strict";

for (const formset of document.querySelectorAll("[data-formset]")) {
  const prefix = formset.dataset.formset;
  const rows = formset.querySelector("[data-formset-rows]");
  const template = formset.querySelector("template[data-empty-form]");
  const totalForms = formset.querySelector(`#id_${prefix}-TOTAL_FORMS`);
  const addButton = formset.querySelector("[data-add-row]");

  const removeRow = (button) => {
    const row = button.closest(".participant-row, .facilitator-row");
    const deleteInput = row?.querySelector(`input[name$="-DELETE"]`);
    if (!row || !deleteInput) return;
    deleteInput.checked = true;
    row.hidden = true;
  };

  formset.addEventListener("click", (event) => {
    const removeButton = event.target.closest("[data-remove-row]");
    if (removeButton) removeRow(removeButton);
  });

  addButton?.addEventListener("click", () => {
    const index = Number.parseInt(totalForms.value, 10);
    const fragment = template.content.cloneNode(true);
    for (const element of fragment.querySelectorAll("[name], [id], label[for]")) {
      for (const attribute of ["name", "id", "for"]) {
        if (element.hasAttribute(attribute)) {
          element.setAttribute(attribute, element.getAttribute(attribute).replaceAll("__prefix__", index));
        }
      }
    }
    rows.append(fragment);
    totalForms.value = index + 1;
    rows.lastElementChild?.querySelector('input:not([type="hidden"])')?.focus();
  });
}
