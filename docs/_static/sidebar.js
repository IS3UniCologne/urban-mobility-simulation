// Let long module names in the sidebar wrap after an underscore instead of mid-word
document.addEventListener("DOMContentLoaded", () => {
  for (const link of document.querySelectorAll(".bd-sidenav a.reference")) {
    link.innerHTML = link.innerHTML.replaceAll("_", "_<wbr>");
  }
});
