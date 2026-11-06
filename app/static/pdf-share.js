// The jornada summary card (_jornada_pdf.html).
//
// 📲 Enviar por WhatsApp: the link opens WhatsApp with the text and the PDF's public
// link. On a phone that can share files (Android Chrome, iPhone Safari) it sends the PDF
// itself instead: the share sheet, where you pick WhatsApp and the chat or group. Only
// on phones: Chrome on a computer can "share" files too, but its share window (e.g.
// Windows') doesn't copy or send them anywhere useful. The PDF is fetched when the page
// loads, because Safari only shares right after the tap.
// <a href="https://wa.me/?text=..." data-share-pdf="<public PDF url>" data-text="...">
//
// 📋 Copiar mensaje: copies data-copy (the text and the link) to the clipboard; if the
// browser won't, shows it in a box to copy by hand.
// <button data-copy="..." data-done="✅ Copiado" data-ask="Copia este mensaje:">
const phone = (navigator.userAgentData && navigator.userAgentData.mobile) ||
  /Android|iPhone|iPad|iPod/i.test(navigator.userAgent) ||
  (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);  // iPadOS

document.querySelectorAll("[data-share-pdf]").forEach((link) => {
  if (!phone || !navigator.canShare) return;
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

function copyByHand(text) {
  // The old way, for browsers without navigator.clipboard (e.g. http, old WebViews).
  const box = document.createElement("textarea");
  box.value = text;
  box.setAttribute("readonly", "");
  box.style.position = "fixed";
  box.style.opacity = "0";
  document.body.appendChild(box);
  box.select();
  box.setSelectionRange(0, text.length);
  let ok = false;
  try { ok = document.execCommand("copy"); } catch (e) { ok = false; }
  box.remove();
  return ok;
}

document.querySelectorAll("[data-copy]").forEach((button) => {
  const label = button.textContent;
  button.addEventListener("click", async () => {
    const text = button.dataset.copy;
    let ok = false;
    try {
      await navigator.clipboard.writeText(text);
      ok = true;
    } catch (e) {
      ok = copyByHand(text);
    }
    if (!ok) {
      window.prompt(button.dataset.ask, text);
      return;
    }
    button.textContent = button.dataset.done;
    setTimeout(() => { button.textContent = label; }, 2500);
  });
});
