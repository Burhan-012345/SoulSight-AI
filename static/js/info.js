// Info Pages JavaScript
document.addEventListener("DOMContentLoaded", function () {
  // Initialize table of contents highlighting
  if (document.querySelector(".info-toc")) {
    initTableOfContents();
  }

  // Initialize smooth scrolling for anchor links
  initSmoothScrolling();

  // Initialize animations
  initAnimations();
});

function initTableOfContents() {
  const sections = document.querySelectorAll(".info-section");
  const tocLinks = document.querySelectorAll(".toc-link");
  const headerOffset = 100;

  // Highlight TOC link on scroll
  window.addEventListener("scroll", () => {
    let current = "";

    sections.forEach((section) => {
      const sectionTop = section.offsetTop;
      const sectionHeight = section.clientHeight;

      if (pageYOffset >= sectionTop - headerOffset) {
        current = section.getAttribute("id");
      }
    });

    tocLinks.forEach((link) => {
      link.classList.remove("active");
      if (link.getAttribute("href") === `#${current}`) {
        link.classList.add("active");
      }
    });
  });
}

function initSmoothScrolling() {
  document.querySelectorAll('a[href^="#"]').forEach((anchor) => {
    anchor.addEventListener("click", function (e) {
      e.preventDefault();

      const targetId = this.getAttribute("href");
      if (targetId === "#") return;

      const targetElement = document.querySelector(targetId);
      if (targetElement) {
        window.scrollTo({
          top: targetElement.offsetTop - 100,
          behavior: "smooth",
        });

        // Update URL without page reload
        history.pushState(null, null, targetId);
      }
    });
  });
}

function initAnimations() {
  // Add animation to stat cards
  const statCards = document.querySelectorAll(".stat-card");
  statCards.forEach((card) => {
    card.addEventListener("mouseenter", () => {
      card.style.transform = "translateY(-5px)";
    });

    card.addEventListener("mouseleave", () => {
      card.style.transform = "translateY(0)";
    });
  });

  // Add animation to team members
  const teamMembers = document.querySelectorAll(".team-member");
  teamMembers.forEach((member) => {
    member.addEventListener("mouseenter", () => {
      member.style.transform = "translateY(-5px)";
    });

    member.addEventListener("mouseleave", () => {
      member.style.transform = "translateY(0)";
    });
  });
}
