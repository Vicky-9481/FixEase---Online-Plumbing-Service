const sidebarToggle = document.querySelector("[data-sidebar-toggle]");
const sidebarScrollKey = "fixease.sidebar.scrollTop";
let sidebarScrollTop = Number(sessionStorage.getItem(sidebarScrollKey) || 0);

if (sidebarToggle) {
  sidebarToggle.addEventListener("click", () => {
    document.body.classList.toggle("sidebar-open");
  });
}

const sidebarScrollArea = document.querySelector("[data-sidebar-scroll]");

if (sidebarScrollArea) {
  sidebarScrollArea.scrollTop = sidebarScrollTop;
  sidebarScrollArea.addEventListener("scroll", () => {
    sidebarScrollTop = sidebarScrollArea.scrollTop;
    sessionStorage.setItem(sidebarScrollKey, String(sidebarScrollTop));
  });
}

const revealItems = document.querySelectorAll(".reveal");

if ("IntersectionObserver" in window && revealItems.length) {
  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add("visible");
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.12 });

  revealItems.forEach((item) => observer.observe(item));
} else {
  revealItems.forEach((item) => item.classList.add("visible"));
}

document.addEventListener("click", (event) => {
  if (window.innerWidth > 768) return;
  const sidebar = document.querySelector("[data-sidebar-shell]");
  const toggle = event.target.closest("[data-sidebar-toggle]");
  if (toggle || !sidebar) return;
  if (!sidebar.contains(event.target) && document.body.classList.contains("sidebar-open")) {
    document.body.classList.remove("sidebar-open");
  }
});

const registerForm = document.querySelector("[data-role-form]");

function setFieldState(field, active) {
  if (!field) return;
  const inputs = field.querySelectorAll("input, select, textarea");
  field.classList.toggle("is-hidden", !active);
  inputs.forEach((input) => {
    input.disabled = !active;
    if (input.dataset.requiredWhenVisible === "true") {
      input.required = active;
    }
  });
}

document.querySelectorAll("[data-photo-input]").forEach((input) => {
  input.addEventListener("change", () => {
    const form = input.closest("form");
    if (form && input.files && input.files.length) {
      form.submit();
    }
  });
});

document.querySelectorAll("[data-request-image-input]").forEach((input) => {
  input.addEventListener("change", () => {
    const zone = input.closest("[data-request-upload-zone]");
    const preview = zone ? zone.querySelector("[data-request-image-preview]") : null;
    const previewImg = zone ? zone.querySelector("[data-request-image-preview-img]") : null;
    const previewName = zone ? zone.querySelector("[data-request-image-name]") : null;
    const file = input.files && input.files[0];

    if (!zone || !preview || !previewImg || !previewName) return;

    if (!file) {
      preview.classList.add("is-hidden");
      previewImg.removeAttribute("src");
      previewName.textContent = "No file selected yet.";
      return;
    }

    const reader = new FileReader();
    reader.onload = () => {
      previewImg.src = reader.result;
      previewName.textContent = file.name;
      preview.classList.remove("is-hidden");
    };
    reader.readAsDataURL(file);
  });
});

if (registerForm) {
  const roleSelect = registerForm.querySelector("[data-role-select]");
  const customerSection = registerForm.querySelector("[data-role-panel='customer']");
  const plumberSection = registerForm.querySelector("[data-role-panel='plumber']");
  const adminSection = registerForm.querySelector("[data-role-panel='admin']");
  const confirmField = registerForm.querySelector("[data-confirm-field]");
  const roleMessage = registerForm.querySelector("[data-role-message]");

  const syncRole = () => {
    const role = roleSelect ? roleSelect.value : "customer";
    setFieldState(customerSection, role === "customer");
    setFieldState(plumberSection, role === "plumber");
    setFieldState(adminSection, role === "admin");

    if (confirmField) {
      const showConfirm = role === "customer" || role === "plumber";
      confirmField.classList.toggle("is-hidden", !showConfirm);
      confirmField.querySelectorAll("input").forEach((input) => {
        input.disabled = !showConfirm;
        if (input.dataset.requiredWhenVisible === "true") {
          input.required = showConfirm;
        }
      });
    }

    if (roleMessage) {
      roleMessage.textContent =
        role === "plumber"
          ? "Plumber registration adds a profile that admins verify before jobs are assigned."
          : role === "admin"
          ? "Admin registration requires the access code."
          : "Customer accounts are used to book and track plumbing services.";
    }
  };

  if (roleSelect) {
    roleSelect.addEventListener("change", syncRole);
    syncRole();
  }
}
