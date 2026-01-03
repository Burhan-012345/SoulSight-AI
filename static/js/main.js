// Additional JavaScript for interactive elements

// Initialize tooltips
document.addEventListener("DOMContentLoaded", function () {
  // Add tooltip functionality to all elements with title attribute
  const tooltipElements = document.querySelectorAll("[title]");

  tooltipElements.forEach((el) => {
    el.addEventListener("mouseenter", function (e) {
      const tooltip = document.createElement("div");
      tooltip.className = "tooltip";
      tooltip.textContent = this.title;
      document.body.appendChild(tooltip);

      const rect = this.getBoundingClientRect();
      tooltip.style.position = "fixed";
      tooltip.style.top = rect.top - tooltip.offsetHeight - 10 + "px";
      tooltip.style.left =
        rect.left + (rect.width - tooltip.offsetWidth) / 2 + "px";
      tooltip.style.zIndex = "10000";

      this._tooltip = tooltip;
    });

    el.addEventListener("mouseleave", function () {
      if (this._tooltip) {
        this._tooltip.remove();
        delete this._tooltip;
      }
    });
  });

  // Add smooth scrolling for anchor links
  document.querySelectorAll('a[href^="#"]').forEach((anchor) => {
    anchor.addEventListener("click", function (e) {
      e.preventDefault();
      const targetId = this.getAttribute("href");
      if (targetId === "#") return;

      const targetElement = document.querySelector(targetId);
      if (targetElement) {
        targetElement.scrollIntoView({
          behavior: "smooth",
          block: "start",
        });
      }
    });
  });

  // Add image preview click handler for changing images
  document.addEventListener("click", function (e) {
    if (e.target.closest(".preview-overlay")) {
      document.getElementById("imageUpload").click();
    }
  });

  // Initialize any required libraries or plugins
  initializeApplication();
});

function initializeApplication() {
  console.log("SoulSight AI initialized");

  // Set current year in footer if needed
  const yearElement = document.querySelector(".current-year");
  if (yearElement) {
    yearElement.textContent = new Date().getFullYear();
  }
}

// Image processing helper functions
function validateImage(file) {
  const validTypes = ["image/jpeg", "image/png", "image/jpg", "image/gif"];
  const maxSize = 16 * 1024 * 1024; // 16MB

  if (!validTypes.includes(file.type)) {
    return {
      valid: false,
      error: "Please upload a valid image file (JPG, PNG, GIF)",
    };
  }

  if (file.size > maxSize) {
    return { valid: false, error: "File size must be less than 16MB" };
  }

  return { valid: true };
}

// File size formatter
function formatFileSize(bytes) {
  if (bytes === 0) return "0 Bytes";
  const k = 1024;
  const sizes = ["Bytes", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
}

// Debounce function for search inputs
function debounce(func, wait) {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
}

// Throttle function for scroll events
function throttle(func, limit) {
  let inThrottle;
  return function () {
    const args = arguments;
    const context = this;
    if (!inThrottle) {
      func.apply(context, args);
      inThrottle = true;
      setTimeout(() => (inThrottle = false), limit);
    }
  };
}

// Copy to clipboard function
function copyToClipboard(text) {
  navigator.clipboard
    .writeText(text)
    .then(() => {
      showNotification("Copied to clipboard!", "success");
    })
    .catch((err) => {
      console.error("Failed to copy:", err);
      showNotification("Failed to copy to clipboard", "error");
    });
}

// Show notification (can be used from anywhere)
window.showNotification = function (message, type = "info") {
  const notification = document.createElement("div");
  notification.className = `notification notification-${type}`;
  notification.innerHTML = `
        <i class="fas fa-${
          type === "success"
            ? "check-circle"
            : type === "error"
            ? "exclamation-circle"
            : type === "warning"
            ? "exclamation-triangle"
            : "info-circle"
        }"></i>
        <span>${message}</span>
    `;
  document.body.appendChild(notification);

  setTimeout(() => {
    notification.classList.add("fade-out");
    setTimeout(() => notification.remove(), 300);
  }, 3000);
};

// Theme toggle (if implementing dark mode)
function toggleTheme() {
  const html = document.documentElement;
  const currentTheme = html.getAttribute("data-theme");
  const newTheme = currentTheme === "dark" ? "light" : "dark";

  html.setAttribute("data-theme", newTheme);
  localStorage.setItem("theme", newTheme);

  showNotification(`Switched to ${newTheme} theme`, "info");
}

// Check for saved theme preference
function loadTheme() {
  const savedTheme = localStorage.getItem("theme");
  if (savedTheme) {
    document.documentElement.setAttribute("data-theme", savedTheme);
  }
}

// Error page specific functionality
function setupErrorPage() {
  // Add smooth scrolling for TOC links
  document.querySelectorAll(".toc a").forEach((link) => {
    link.addEventListener("click", function (e) {
      e.preventDefault();
      const targetId = this.getAttribute("href");
      const targetElement = document.querySelector(targetId);
      if (targetElement) {
        targetElement.scrollIntoView({
          behavior: "smooth",
          block: "start",
        });
      }
    });
  });

  // Highlight current section in TOC
  const observerOptions = {
    root: null,
    rootMargin: "0px 0px -50% 0px",
    threshold: 0.1,
  };

  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      const id = entry.target.getAttribute("id");
      if (entry.isIntersecting) {
        document.querySelectorAll(".toc a").forEach((link) => {
          link.classList.remove("active");
          if (link.getAttribute("href") === `#${id}`) {
            link.classList.add("active");
          }
        });
      }
    });
  }, observerOptions);

  document.querySelectorAll(".info-section").forEach((section) => {
    observer.observe(section);
  });
}

// Initialize error page features if on error page
if (document.querySelector(".error-container")) {
  setupErrorPage();
}

// Mobile Navigation
function initializeMobileNavigation() {
  const mobileToggle = document.querySelector(".mobile-menu-toggle");
  const navLinks = document.getElementById("navLinks");
  const mobileOverlay = document.getElementById("mobileOverlay");
  const userMenuToggle = document.querySelector(".user-menu-toggle");
  const userDropdown = document.querySelector(".user-dropdown");
  const body = document.body;

  if (mobileToggle && navLinks) {
    mobileToggle.addEventListener("click", function () {
      const isExpanded = this.getAttribute("aria-expanded") === "true";
      this.setAttribute("aria-expanded", !isExpanded);
      navLinks.classList.toggle("active");
      mobileOverlay.classList.toggle("active");
      body.classList.toggle("no-scroll");

      // Update hamburger icon
      const icon = this.querySelector("i");
      if (navLinks.classList.contains("active")) {
        icon.className = "fas fa-times";
      } else {
        icon.className = "fas fa-bars";
      }
    });
  }

  // Close mobile menu when clicking overlay
  if (mobileOverlay) {
    mobileOverlay.addEventListener("click", function () {
      mobileToggle.setAttribute("aria-expanded", "false");
      navLinks.classList.remove("active");
      this.classList.remove("active");
      body.classList.remove("no-scroll");

      const icon = mobileToggle.querySelector("i");
      icon.className = "fas fa-bars";
    });
  }

  // User dropdown toggle
  if (userMenuToggle && userDropdown) {
    userMenuToggle.addEventListener("click", function (e) {
      e.stopPropagation();
      const isExpanded = this.getAttribute("aria-expanded") === "true";
      this.setAttribute("aria-expanded", !isExpanded);
      userDropdown.classList.toggle("show");

      // Close other dropdowns
      document.querySelectorAll(".user-dropdown.show").forEach((dropdown) => {
        if (dropdown !== userDropdown) {
          dropdown.classList.remove("show");
        }
      });
    });
  }

  // Close dropdowns when clicking outside
  document.addEventListener("click", function (e) {
    if (
      userDropdown &&
      !userMenuToggle.contains(e.target) &&
      !userDropdown.contains(e.target)
    ) {
      userDropdown.classList.remove("show");
      if (userMenuToggle) {
        userMenuToggle.setAttribute("aria-expanded", "false");
      }
    }

    // Close mobile menu when clicking a link
    if (navLinks && navLinks.classList.contains("active")) {
      const isLink =
        e.target.closest(".nav-link") || e.target.closest(".nav-btn");
      if (isLink) {
        mobileToggle.setAttribute("aria-expanded", "false");
        navLinks.classList.remove("active");
        mobileOverlay.classList.remove("active");
        body.classList.remove("no-scroll");

        const icon = mobileToggle.querySelector("i");
        icon.className = "fas fa-bars";
      }
    }
  });

  // Close dropdown on Escape key
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") {
      if (userDropdown && userDropdown.classList.contains("show")) {
        userDropdown.classList.remove("show");
        if (userMenuToggle) {
          userMenuToggle.setAttribute("aria-expanded", "false");
        }
      }

      if (navLinks && navLinks.classList.contains("active")) {
        mobileToggle.setAttribute("aria-expanded", "false");
        navLinks.classList.remove("active");
        mobileOverlay.classList.remove("active");
        body.classList.remove("no-scroll");

        const icon = mobileToggle.querySelector("i");
        icon.className = "fas fa-bars";
      }
    }
  });
}

// Back to Top Button
function initializeBackToTop() {
  const backToTopBtn = document.querySelector(".back-to-top");

  if (!backToTopBtn) return;

  window.addEventListener("scroll", function () {
    if (window.pageYOffset > 300) {
      backToTopBtn.classList.add("visible");
    } else {
      backToTopBtn.classList.remove("visible");
    }
  });

  backToTopBtn.addEventListener("click", function () {
    window.scrollTo({
      top: 0,
      behavior: "smooth",
    });
  });
}

// Accessibility Panel
function initializeAccessibilityPanel() {
  const accessibilityToggle = document.getElementById("accessibility-toggle");
  const accessibilityPanel = document.getElementById("accessibilityPanel");
  const accessibilityClose = document.querySelector(".accessibility-close");

  if (!accessibilityToggle || !accessibilityPanel) return;

  accessibilityToggle.addEventListener("click", function (e) {
    e.preventDefault();
    accessibilityPanel.classList.toggle("show");
  });

  if (accessibilityClose) {
    accessibilityClose.addEventListener("click", function () {
      accessibilityPanel.classList.remove("show");
    });
  }

  // Close panel when clicking outside
  document.addEventListener("click", function (e) {
    if (
      !accessibilityPanel.contains(e.target) &&
      !accessibilityToggle.contains(e.target)
    ) {
      accessibilityPanel.classList.remove("show");
    }
  });

  // High contrast toggle
  const highContrastToggle = document.getElementById("highContrastToggle");
  if (highContrastToggle) {
    highContrastToggle.addEventListener("change", function () {
      document.body.classList.toggle("high-contrast", this.checked);
      localStorage.setItem("highContrast", this.checked);
    });

    // Load saved preference
    if (localStorage.getItem("highContrast") === "true") {
      highContrastToggle.checked = true;
      document.body.classList.add("high-contrast");
    }
  }

  // Large text toggle
  const largeTextToggle = document.getElementById("largeTextToggle");
  if (largeTextToggle) {
    largeTextToggle.addEventListener("change", function () {
      document.body.classList.toggle("large-text", this.checked);
      localStorage.setItem("largeText", this.checked);
    });

    if (localStorage.getItem("largeText") === "true") {
      largeTextToggle.checked = true;
      document.body.classList.add("large-text");
    }
  }

  // Reduce motion toggle
  const reduceMotionToggle = document.getElementById("reduceMotionToggle");
  if (reduceMotionToggle) {
    reduceMotionToggle.addEventListener("change", function () {
      document.body.classList.toggle("reduce-motion", this.checked);
      localStorage.setItem("reduceMotion", this.checked);
    });

    if (localStorage.getItem("reduceMotion") === "true") {
      reduceMotionToggle.checked = true;
      document.body.classList.add("reduce-motion");
    }
  }

  // Read page aloud
  const readPageBtn = document.getElementById("readPageBtn");
  if (readPageBtn && "speechSynthesis" in window) {
    let isReading = false;
    let speech = null;

    readPageBtn.addEventListener("click", function () {
      if (isReading) {
        window.speechSynthesis.cancel();
        isReading = false;
        this.innerHTML = '<i class="fas fa-volume-up"></i> Read Page Aloud';
        this.classList.remove("reading");
      } else {
        const mainContent =
          document.querySelector(".main-content") ||
          document.querySelector("main");
        const text = mainContent
          ? mainContent.innerText
          : document.body.innerText;

        speech = new SpeechSynthesisUtterance(text);
        speech.lang = "en-US";
        speech.rate = 1;
        speech.pitch = 1;
        speech.volume = 1;

        speech.onstart = () => {
          isReading = true;
          this.innerHTML = '<i class="fas fa-stop"></i> Stop Reading';
          this.classList.add("reading");
        };

        speech.onend = () => {
          isReading = false;
          this.innerHTML = '<i class="fas fa-volume-up"></i> Read Page Aloud';
          this.classList.remove("reading");
        };

        speech.onerror = () => {
          isReading = false;
          this.innerHTML = '<i class="fas fa-volume-up"></i> Read Page Aloud';
          this.classList.remove("reading");
          alert("Error reading page. Please try again.");
        };

        window.speechSynthesis.speak(speech);
      }
    });

    // Stop speech when leaving page
    window.addEventListener("beforeunload", () => {
      if (isReading) {
        window.speechSynthesis.cancel();
      }
    });
  }
}

// Flash Messages
function initializeFlashMessages() {
  const flashMessages = document.querySelector(".flash-messages");

  if (!flashMessages) return;

  const closeButtons = flashMessages.querySelectorAll(".flash-close");

  closeButtons.forEach((button) => {
    button.addEventListener("click", function () {
      const flashMessage = this.closest(".flash-message");
      flashMessage.style.animation = "slideInRight 0.3s ease reverse";
      setTimeout(() => {
        flashMessage.remove();
      }, 300);
    });
  });

  // Auto-remove flash messages after 5 seconds
  setTimeout(() => {
    document.querySelectorAll(".flash-message").forEach((message) => {
      message.style.animation = "slideInRight 0.3s ease reverse";
      setTimeout(() => {
        message.remove();
      }, 300);
    });
  }, 5000);
}

// Update the existing initializeApplication function
function initializeApplication() {
  console.log("SoulSight AI initialized");

  // Initialize all components
  initializeMobileNavigation();
  initializeBackToTop();
  initializeAccessibilityPanel();
  initializeFlashMessages();

  // Set current year in footer
  const yearElement = document.getElementById("current-year");
  if (yearElement) {
    yearElement.textContent = new Date().getFullYear();
  }

  // Add no-scroll class to body
  const style = document.createElement("style");
  style.textContent = `
        body.no-scroll {
            overflow: hidden;
        }
        
        .reading {
            background-color: #48bb78 !important;
        }
    `;
  document.head.appendChild(style);
}

// Initialize when DOM is loaded
document.addEventListener("DOMContentLoaded", initializeApplication);

// Initialize theme on load
loadTheme();
