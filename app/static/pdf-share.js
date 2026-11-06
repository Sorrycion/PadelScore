// 📲 Enviar por WhatsApp (the jornada summary card). The link opens WhatsApp with the
// text and the PDF's public link. Phones that can share files (Android Chrome, iPhone
// Safari) send the PDF itself instead: the share sheet, where you pick WhatsApp and the
// chat or group. The PDF is fetched when the page loads, because Safari only shares
// right after the tap. <a href="https://wa.me/?text=..." data-share-pdf="<public PDF url>"
// data-text="...">
document.querySelectorAll("[data-share-pdf]").forEach((link) => {
  if (!navigator.canShare) return;
  const probe = new File(["%PDF"], "resumen.pdf", { type: "application/pdf" });
  if (!navigator.canShare({ files: [probe] })) return;
  let file = null;
  fetch(link.dataset.sharePdf).then(async (response) => {
    if (!response.ok) return;
    const header = response.headers.get("content-disposition") || "";
    const name = (header.match(/filename="([^"]+)"/) || [])[1] || "resumen.pdf";
    file = new File([await response.blob()], name, { type: "application/pdf" });
  }).catch(() => {});
  link.addEventListener("click", (event) => {
    if (!file) return;  // not loaded (yet): WhatsApp with the link
    event.preventDefault();
    navigator.share({ files: [file], text: link.dataset.text }).catch((e) => {
      if (e.name !== "AbortError") window.open(link.href, "_blank");
    });
  });
});
