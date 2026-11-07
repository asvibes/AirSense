(() => {
  "use strict";
  const sidebar = document.getElementById("sidebar");
  const main = document.querySelector(".main");
  const backdrop = document.getElementById("navBackdrop");
  const toggle = document.getElementById("sidebarToggle");
  const menu = document.getElementById("menuBtn");
  const accountToggle = document.getElementById("homeAccountToggle");
  const accountDetails = document.getElementById("accountDetails");

  function closeMobileNavigation() {
    sidebar.classList.remove("open");
    backdrop.classList.remove("open");
  }

  toggle.addEventListener("click", () => {
    const expanded = sidebar.classList.toggle("expanded");
    main.classList.toggle("sidebar-expanded", expanded);
    toggle.setAttribute("aria-expanded", String(expanded));
    const label = expanded ? "Collapse sidebar" : "Expand sidebar";
    toggle.setAttribute("aria-label", label);
    toggle.title = label;
    toggle.querySelector("span").textContent = label;
  });
  menu.addEventListener("click", () => {
    sidebar.classList.add("open");
    backdrop.classList.add("open");
  });
  backdrop.addEventListener("click", closeMobileNavigation);
  sidebar.querySelectorAll("a").forEach(link => link.addEventListener("click", closeMobileNavigation));
  accountToggle.addEventListener("click", () => {
    const expanded = accountToggle.getAttribute("aria-expanded") !== "true";
    accountToggle.setAttribute("aria-expanded", String(expanded));
    accountDetails.hidden = !expanded;
  });
  document.addEventListener("keydown", event => {
    if (event.key === "Escape") closeMobileNavigation();
  });
})();
