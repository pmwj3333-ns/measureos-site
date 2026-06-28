/**
 * MEASURE OS Brand Site — experience layer
 */
(function () {
  "use strict";

  const header = document.querySelector(".site-header");
  const progressBar = document.querySelector(".scroll-progress");
  const navToggle = document.querySelector(".site-nav-toggle");
  const mobileNav = document.querySelector(".mobile-nav");
  const navLinks = document.querySelectorAll("[data-nav]");
  const themedSections = document.querySelectorAll("[data-theme]");

  /* ── Scroll progress ── */
  function updateProgress() {
    if (!progressBar) return;
    const scrollTop = window.scrollY;
    const docHeight = document.documentElement.scrollHeight - window.innerHeight;
    const progress = docHeight > 0 ? scrollTop / docHeight : 0;
    progressBar.style.transform = `scaleX(${progress})`;
  }

  /* ── Header theme (light / dark) ── */
  function updateHeaderTheme() {
    if (!header) return;
    const mid = window.innerHeight * 0.35;
    let activeTheme = "light";

    themedSections.forEach((section) => {
      const rect = section.getBoundingClientRect();
      if (rect.top <= mid && rect.bottom >= mid) {
        activeTheme = section.dataset.theme || "light";
      }
    });

    header.classList.toggle("is-dark", activeTheme === "dark");
    header.classList.toggle("is-scrolled", window.scrollY > 32);
  }

  function onScroll() {
    updateProgress();
    updateHeaderTheme();
  }

  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();

  /* ── Mobile nav ── */
  if (navToggle && mobileNav) {
    navToggle.addEventListener("click", () => {
      const open = mobileNav.classList.toggle("is-open");
      navToggle.setAttribute("aria-expanded", String(open));
      navToggle.setAttribute("aria-label", open ? "メニューを閉じる" : "メニューを開く");
    });

    mobileNav.querySelectorAll("a").forEach((link) => {
      link.addEventListener("click", () => {
        mobileNav.classList.remove("is-open");
        navToggle.setAttribute("aria-expanded", "false");
      });
    });
  }

  /* ── Active nav ── */
  const sectionIds = [];
  navLinks.forEach((link) => {
    const id = link.getAttribute("href")?.slice(1);
    if (!id) return;
    const el = document.getElementById(id);
    if (el) sectionIds.push({ id, el });
  });

  const navObserver = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        const id = entry.target.id;
        navLinks.forEach((link) => {
          link.classList.toggle("is-active", link.getAttribute("href") === `#${id}`);
        });
      });
    },
    { rootMargin: "-45% 0px -45% 0px", threshold: 0 }
  );

  sectionIds.forEach(({ el }) => navObserver.observe(el));

  /* ── Reveal ── */
  const revealEls = document.querySelectorAll(".reveal");
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  if (revealEls.length && !reducedMotion) {
    const revealObserver = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          entry.target.classList.add("is-visible");
          revealObserver.unobserve(entry.target);
        });
      },
      { threshold: 0.08, rootMargin: "0px 0px -8% 0px" }
    );
    revealEls.forEach((el) => revealObserver.observe(el));
  } else {
    revealEls.forEach((el) => el.classList.add("is-visible"));
  }
})();
