// The editable score boxes of a set card (jornada page): once both boxes have games,
// or both are emptied, the set is saved (POST /matches/{id}/score, back to the card).
document.querySelectorAll("form[data-score-inline]").forEach((form) => {
  const boxes = [...form.querySelectorAll("input")];
  const start = boxes.map((b) => b.value).join("-");
  const save = () => {
    const filled = boxes.filter((b) => b.value !== "").length;
    if ((filled === 2 || filled === 0) && boxes.map((b) => b.value).join("-") !== start) {
      form.requestSubmit ? form.requestSubmit() : form.submit();
    }
  };
  boxes.forEach((b) => b.addEventListener("change", save));
  form.addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); save(); }
  });
});
