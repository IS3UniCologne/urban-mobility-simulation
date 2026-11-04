// Let long module names in the sidebar wrap after an underscore instead of mid-word
document.addEventListener("DOMContentLoaded", () => {
  const isIndexPage =
    window.location.pathname.endsWith("/") ||
    window.location.pathname.endsWith("/index.html");
  const isApiReferencePage =
    window.location.pathname.includes("/_autosummary/");
  if (isIndexPage) {
    document.querySelector("#pst-secondary-sidebar")?.remove();
    document.querySelector("#pst-secondary-sidebar-modal")?.remove();
  } else if (isApiReferencePage) {
    document
      .querySelector(".editthispage")
      ?.closest(".sidebar-secondary-item")
      ?.remove();
  }

  for (const link of document.querySelectorAll(".bd-sidenav a.reference")) {
    link.innerHTML = link.innerHTML.replaceAll("_", "_<wbr>");
  }
});
