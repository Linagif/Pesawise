// Prevent duplicate submissions: disable submit buttons right after a POST form is sent.
document.addEventListener("submit", function (e) {
  const form = e.target;
  if (form.method && form.method.toLowerCase() === "post") {
    setTimeout(function () { form.querySelectorAll("button[type=submit]").forEach(b => { b.disabled = true; }); }, 0);
  }
});
window.addEventListener("pageshow", function () {
  document.querySelectorAll("button[type=submit]").forEach(b => { b.disabled = false; });
});
// Focus the amount field when the quick-add modal opens.
const qe = document.getElementById("quickExpense");
if (qe) qe.addEventListener("shown.bs.modal", () => document.getElementById("qe_amount").focus());
