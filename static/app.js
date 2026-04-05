const navToggle = document.querySelector("[data-nav-toggle]");
const nav = document.querySelector("[data-nav]");

if (navToggle && nav) {
  navToggle.addEventListener("click", () => {
    nav.classList.toggle("open");
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
  }, { threshold: 0.14 });

  revealItems.forEach((item) => observer.observe(item));
} else {
  revealItems.forEach((item) => item.classList.add("visible"));
}

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
