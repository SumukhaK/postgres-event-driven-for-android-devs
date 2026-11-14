const helpCopy = {
  nudge: "Think about where the subtraction happens. Can the database use its current value directly?",
  hint: "Use one UPDATE statement: subtract from stock and add a WHERE guard that checks stock >= 2. RETURNING shows the changed value.",
  solution: "UPDATE products SET stock = stock - 2 WHERE id = 1 AND stock >= 2 RETURNING stock; The database subtracts from the current row value and locks that row while updating it. The guard makes a second order wait, then match only if enough stock remains. Check whether a row was returned: zero rows means the order could not be fulfilled."
};

document.addEventListener("click", event => {
  const trigger = event.target.closest("[data-dialog]");
  if (trigger) document.getElementById(trigger.dataset.dialog + "-dialog")?.showModal();

  const help = event.target.closest("[data-help-level]");
  if (help) {
    const response = document.querySelector("[data-help-response]");
    response.textContent = helpCopy[help.dataset.helpLevel];
    response.dataset.level = help.dataset.helpLevel;
  }

  if (event.target.closest('[data-action="run"]')) {
    document.querySelectorAll("[data-stock]").forEach(node => node.textContent = "198");
    document.querySelectorAll("[data-run-label]").forEach(node => node.textContent = "Query ran · simulated");
    document.querySelectorAll("[data-run-feedback]").forEach(node => node.textContent = "Success. 1 row updated; stock is now 198. This is a local simulation.");
  }

  if (event.target.closest('[data-action="complete"]')) {
    document.querySelectorAll("[data-progress]").forEach(node => node.textContent = node.classList.contains("path-count") ? "9 of 11 complete" : "9 / 11");
    document.querySelectorAll('[data-action="complete"]').forEach(button => {
      button.textContent = "Lesson complete ✓";
      button.disabled = true;
    });
  }

  if (event.target.closest('[data-action="demo-signin"]')) {
    document.querySelectorAll("[data-account-note]").forEach(node => node.textContent = "Preview only: no account or progress was sent. Sign-in needs a real service.");
  }

  if (event.target.closest('[data-action="provider-preview"]')) {
    document.querySelectorAll("[data-provider-note]").forEach(node => node.textContent = "Preview only: no provider was connected and no usage was shared. A real connection needs supported authorization and a clear billing review; OpenCode handles its own connected-provider flow.");
  }
});

document.addEventListener("input", event => {
  if (event.target.matches(".spend-slider")) {
    const value = event.target.closest("dialog").querySelector("[data-spend-value]");
    value.textContent = "$" + event.target.value;
  }
});
