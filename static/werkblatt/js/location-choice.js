(() => {
  const choice = document.querySelector("#id_location_choice");
  const customField = document.querySelector("#location-custom-field");
  const customInput = document.querySelector("#id_location");

  if (!choice || !customField || !customInput) return;

  const updateVisibility = () => {
    const needsCustomLocation =
      choice.value === "__other__" || (choice.value === "" && customInput.value.trim() !== "");
    customField.hidden = !needsCustomLocation;
  };

  choice.addEventListener("change", updateVisibility);
  updateVisibility();
})();
