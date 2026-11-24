// Registers the service worker and powers the optional "Install app" button.
(function () {
  const swUrl = document.currentScript && document.currentScript.dataset.sw;
  if ("serviceWorker" in navigator && swUrl) {
    window.addEventListener("load", function () {
      navigator.serviceWorker.register(swUrl, { scope: "/" }).catch(function () { /* the site works fine without it */ });
    });
  }
  const button = document.getElementById("installBtn");
  let promptEvent = null;
  window.addEventListener("beforeinstallprompt", function (event) {
    event.preventDefault();                       // keep the prompt for our own button
    promptEvent = event;
    if (button) button.classList.remove("d-none");
  });
  if (button) {
    button.addEventListener("click", function () {
      if (!promptEvent) return;
      promptEvent.prompt();
      promptEvent.userChoice.finally(function () { promptEvent = null; button.classList.add("d-none"); });
    });
  }
  window.addEventListener("appinstalled", function () { if (button) button.classList.add("d-none"); });
})();
