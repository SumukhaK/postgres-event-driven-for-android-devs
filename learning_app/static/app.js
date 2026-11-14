import { PGliteWorker } from "@electric-sql/pglite/worker";
import PGWorker from "./db-worker.js?worker";
import seedSql from "./seed.sql?raw";
import exercises from "./exercises.json";
import "../../site/assets/viz.js";

const nav = document.querySelector("#course-nav");
const content = document.querySelector("#lesson-content");
const lessonStatus = document.querySelector("#lesson-status");
const databaseCard = document.querySelector(".database-card");
const courseMenu = document.querySelector(".course-menu");
const compactViewport = window.matchMedia("(max-width: 720px)");
const sqlEditor = document.querySelector("#sql-editor");
const runQueryButton = document.querySelector("#run-query");
const resetDatabaseButton = document.querySelector("#reset-database");
const queryStatus = document.querySelector("#query-status");
const resultSummary = document.querySelector("#result-summary");
const queryResults = document.querySelector("#query-results");
const exerciseCard = document.querySelector("#exercise-card");
const exerciseChoices = document.querySelector("#exercise-choices");
const exerciseInstruction = document.querySelector("#exercise-instruction");
const exerciseStatus = document.querySelector("#exercise-status");
const helpOutput = document.querySelector("#help-output");
const accountStatus = document.querySelector("#account-status");
const accountForm = document.querySelector("#account-form");
const providerCard = document.querySelector("#provider-card");
const providerNotice = document.querySelector("#provider-notice");
const localProviderForm = document.querySelector("#local-provider-form");
const assistantProvider = document.querySelector("#assistant-provider");
const assistantModel = document.querySelector("#assistant-model");
const assistantForm = document.querySelector("#assistant-form");
const assistantQuestion = document.querySelector("#assistant-question");
const assistantLog = document.querySelector("#assistant-log");
const assistantStatus = document.querySelector("#assistant-status");
const completed = new Set(readCompleted());
let database;
let lessons = [];
let currentLesson;
let currentExercise;
let lastQueryResult;
let currentUser;
let csrfToken;
let assistantHistory = [];
let assistantBusy = false;
let assistantRequestId = 0;
let assistantSessionId = `ses_${crypto.randomUUID().replaceAll("-", "")}`;
let copilotFlowId = 0;
let copilotState;

function readCompleted() {
  try {
    const value = JSON.parse(localStorage.getItem("postgres-lab-completed") ?? "[]");
    return Array.isArray(value) ? value.filter(slug => exercises.some(exercise => exercise.slug === slug)) : [];
  } catch {
    return [];
  }
}

function updateProgress() {
  const count = completed.size;
  document.querySelector("#progress-summary").textContent = `${count} / ${exercises.length} activities`;
  document.querySelector("#progress-detail").textContent = `${count} of ${exercises.length} complete`;
  document.querySelector("#progress-meter").value = count;
  nav.querySelectorAll(".lesson-link").forEach(link => {
    const done = completed.has(link.dataset.slug);
    link.classList.toggle("is-complete", done);
    link.querySelector(".lesson-check").textContent = done ? "✓" : "";
    link.setAttribute("aria-label", done ? `${link.dataset.title}, activity complete` : link.dataset.title);
  });
}

function finishActivity() {
  completed.add(currentExercise.slug);
  try { localStorage.setItem("postgres-lab-completed", JSON.stringify([...completed])); } catch {}
  document.querySelector("#exercise-complete").textContent = "Completed";
  exerciseStatus.textContent = "Activity complete. Nice work.";
  updateProgress();
}

function setAccountStatus(message, kind = "") {
  accountStatus.textContent = message;
  accountStatus.dataset.kind = kind;
}

function renderAccount() {
  document.querySelector("#signed-out-view").hidden = Boolean(currentUser);
  document.querySelector("#signed-in-view").hidden = !currentUser;
  providerCard.hidden = !currentUser;
  if (!currentUser) providerCard.querySelector("details").open = false;
  if (currentUser) document.querySelector("#account-email-display").textContent = currentUser.email;
  if (!currentUser) {
    clearAssistantConversation();
    assistantQuestion.value = "";
    setAssistantProviders([]);
  }
}

async function sendProgress(slug, isComplete) {
  const response = await fetch(`/api/progress/${encodeURIComponent(slug)}`, {
    method: "POST",
    headers: { "content-type": "application/json", "x-csrf-token": csrfToken },
    body: JSON.stringify({ completed: isComplete }),
  });
  if (!response.ok) throw new Error("Progress could not be saved to your account.");
  return response.json();
}

async function syncAccountProgress() {
  const response = await fetch("/api/progress");
  if (!response.ok) throw new Error("Account progress could not be loaded.");
  const serverActivities = (await response.json()).activities;
  const serverCompleted = new Set(serverActivities.filter(activity => activity.completed).map(activity => activity.slug));
  for (const slug of serverCompleted) completed.add(slug);
  try { localStorage.setItem("postgres-lab-completed", JSON.stringify([...completed])); } catch {}
  updateProgress();
  for (const slug of completed) {
    if (!serverCompleted.has(slug)) await sendProgress(slug, true);
  }
  setAccountStatus(`Progress synced · ${completed.size} of ${exercises.length} activities complete.`, "success");
}

async function loadProviders() {
  if (!currentUser) return;
  const response = await fetch("/api/providers");
  if (!response.ok) throw new Error("AI connection status could not be loaded.");
  const data = await response.json();
  setAssistantProviders(data.connections, data.catalog);
  const catalog = Object.fromEntries(data.catalog.map(item => [item.id, item]));
  providerCard.hidden = false;
  if (!data.credential_storage_ready) providerNotice.textContent = "Secure provider storage is not configured. Static hints are always available.";
  else if (!data.chatgpt_local_available) providerNotice.textContent = "API-key connections are available here. ChatGPT plan sign-in requires the local app.";
  else providerNotice.textContent = "Connect a provider for optional AI help. Static hints always work without one.";

  for (const connection of data.connections) {
    const state = document.querySelector(`#${connection.provider}-state`);
    const disconnect = document.querySelector(`[data-disconnect="${connection.provider}"]`);
    if (connection.provider === "chatgpt") {
      state.textContent = connection.connected
        ? connection.plan_enabled ? `Connected · ${connection.email ?? "ChatGPT account"} · plan use enabled` : `Connected · ${connection.email ?? "ChatGPT account"} · plan use not enabled`
        : "Not connected";
      document.querySelector("#connect-chatgpt").disabled = !data.chatgpt_local_available;
      document.querySelector("#connect-chatgpt").textContent = connection.connected
        ? connection.plan_enabled ? "Reconnect ChatGPT" : "Enable ChatGPT plan use"
        : "Continue with ChatGPT";
      document.querySelector("#chatgpt-usage").hidden = !connection.plan_enabled;
    } else if (connection.provider === "copilot") {
      state.textContent = connection.connected ? `Connected · GitHub @${connection.login}` : "Not connected";
      document.querySelector("#connect-copilot").disabled = !data.copilot_local_available;
      document.querySelector("#connect-copilot").textContent = connection.connected ? "Reconnect GitHub Copilot" : "Sign in with GitHub";
      if (!data.copilot_local_available) state.textContent = "Unavailable · configure local GitHub sign-in";
    } else if (connection.provider === "local") {
      state.textContent = connection.connected ? "Connected" : "Not connected";
      const endpoint = document.querySelector("#local-endpoint-detail");
      endpoint.textContent = connection.connected ? `Endpoint · ${connection.api_base}` : "";
      endpoint.hidden = !connection.connected;
      localProviderForm.elements.base_url.value = connection.api_base ?? "";
      localProviderForm.querySelector("button[type=submit]").textContent = connection.connected ? "Replace endpoint" : catalog.local.auth_methods[0].label;
    } else {
      state.textContent = connection.connected ? "Connected · encrypted on this server" : "Not connected";
      const form = document.querySelector(`.provider-key-form[data-provider="${connection.provider}"]`);
      form.querySelector("button[type=submit]").textContent = connection.connected ? "Replace connection" : catalog[connection.provider].auth_methods[0].label;
    }
    disconnect.hidden = !connection.connected;
    state.dataset.kind = connection.connected ? "success" : "";
  }

  const callbackResult = new URLSearchParams(location.search).get("chatgpt");
  if (callbackResult) {
    providerCard.querySelector("details").open = true;
    providerNotice.textContent = callbackResult === "connected"
      ? "ChatGPT connection updated. Check the status above to confirm plan use is enabled."
      : "ChatGPT sign-in did not complete. Your course progress is unchanged; try again when ready.";
    history.replaceState(null, "", `${location.pathname}${location.hash}`);
  }
}

function setAssistantProviders(connections, catalog = []) {
  const available = currentUser ? connections.filter(item => item.connected && (item.provider !== "chatgpt" || item.plan_enabled)) : [];
  const selected = available.some(item => item.provider === assistantProvider.value) ? assistantProvider.value : "";
  const names = Object.fromEntries(catalog.map(item => [item.id, item.name]));
  assistantProvider.replaceChildren(new Option("Choose a connected provider", ""));
  for (const item of available) assistantProvider.add(new Option(
    item.provider === "chatgpt" ? "ChatGPT plan" : (names[item.provider] ?? item.provider), item.provider,
  ));
  assistantProvider.value = selected;
  assistantProvider.disabled = available.length === 0;
  if (!currentUser) assistantStatus.textContent = "Sign in and connect an AI provider to ask about this lesson. Static hints always work without AI.";
  else if (!available.length) assistantStatus.textContent = "Connect an AI provider in your account panel. Static hints always work without AI.";
  else assistantStatus.textContent = "Choose a provider to load its models. Lesson context is sent only when you ask for help.";
  if (!selected) {
    assistantModel.replaceChildren(new Option("Choose a provider first", ""));
    assistantModel.disabled = true;
  }
  updateAssistantControls();
}

function updateAssistantControls() {
  const enabled = Boolean(currentUser && assistantProvider.value && assistantModel.value && !assistantBusy);
  assistantModel.disabled = !assistantProvider.value || assistantBusy;
  assistantQuestion.disabled = !enabled;
  assistantForm.querySelector("button[type=submit]").disabled = !enabled;
  document.querySelectorAll("[data-assistant-action]").forEach(button => { button.disabled = !enabled; });
}

function clearAssistantConversation() {
  assistantRequestId += 1;
  assistantBusy = false;
  assistantSessionId = `ses_${crypto.randomUUID().replaceAll("-", "")}`;
  assistantHistory = [];
  assistantLog.replaceChildren();
  assistantLog.hidden = true;
  updateAssistantControls();
}

async function loadAssistantModels() {
  assistantModel.replaceChildren(new Option("Loading models…", ""));
  assistantModel.disabled = true;
  updateAssistantControls();
  clearAssistantConversation();
  if (!assistantProvider.value) {
    assistantModel.replaceChildren(new Option("Choose a provider first", ""));
    updateAssistantControls();
    return;
  }
  assistantStatus.textContent = "Loading the provider’s available models…";
  try {
    const response = await fetch(`/api/assistant/models?provider=${encodeURIComponent(assistantProvider.value)}`);
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail ?? "The model list could not be loaded.");
    assistantModel.replaceChildren(new Option(data.models.length ? "Choose a model" : "No models available", ""));
    for (const item of data.models) assistantModel.add(new Option(item.name, item.id));
    assistantStatus.textContent = data.models.length
      ? "Select the model you want to use. Each request is sent to this provider."
      : "This provider did not return any available models.";
    assistantModel.disabled = data.models.length === 0;
  } catch (error) {
    assistantModel.replaceChildren(new Option("Model list unavailable", ""));
    assistantStatus.textContent = error.message;
  }
  updateAssistantControls();
}

function showAssistantTurn(role, content, kind = "") {
  const turn = document.createElement("p");
  turn.className = "assistant-turn";
  turn.dataset.role = role;
  if (kind) turn.dataset.kind = kind;
  turn.textContent = `${role === "user" ? "You" : "Tutor"} · ${content}`;
  assistantLog.append(turn);
  assistantLog.hidden = false;
  assistantLog.scrollTop = assistantLog.scrollHeight;
  return turn;
}

async function askAssistant(action, message = "") {
  if (assistantBusy || !currentUser || !assistantProvider.value || !assistantModel.value || !currentLesson) return;
  const labels = {nudge: "Give me a nudge.", hint: "Give me a hint.", explanation: "Explain the key idea.", solution: "Show me a complete solution."};
  const displayMessage = action === "ask" ? message.trim() : labels[action];
  if (!displayMessage) return;
  const requestId = ++assistantRequestId;
  const userTurn = showAssistantTurn("user", displayMessage);
  const pendingTurn = showAssistantTurn("assistant", "Thinking…");
  assistantBusy = true;
  updateAssistantControls();
  assistantStatus.textContent = "Sending your question to the selected provider…";
  try {
    const response = await fetch("/api/assistant/respond", {
      method: "POST",
      headers: {"content-type": "application/json", "x-csrf-token": csrfToken},
      body: JSON.stringify({provider: assistantProvider.value, model: assistantModel.value,
        lesson_slug: currentLesson.slug, exercise_slug: currentExercise?.slug ?? null,
        action, message, history: assistantHistory.slice(-6), session_id: assistantSessionId}),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail ?? "The assistant could not answer this request.");
    if (requestId !== assistantRequestId) return;
    assistantHistory.push({role: "user", content: displayMessage}, {role: "assistant", content: data.answer});
    assistantHistory = assistantHistory.slice(-6);
    pendingTurn.textContent = `Tutor · ${data.answer}`;
    assistantStatus.textContent = "Answer ready. Ask a follow-up or use a static hint above.";
    if (action === "ask") assistantQuestion.value = "";
  } catch (error) {
    if (requestId !== assistantRequestId) return;
    userTurn.remove();
    pendingTurn.dataset.kind = "error";
    pendingTurn.textContent = `Tutor · ${error.message}`;
    assistantStatus.textContent = "The AI request did not complete. Your progress is safe; use a static hint above or retry after checking the provider.";
  } finally {
    if (requestId === assistantRequestId) {
      assistantBusy = false;
      updateAssistantControls();
    }
  }
}

assistantProvider.addEventListener("change", loadAssistantModels);
assistantModel.addEventListener("change", () => {
  clearAssistantConversation();
  updateAssistantControls();
});
assistantForm.addEventListener("submit", event => {
  event.preventDefault();
  void askAssistant("ask", assistantQuestion.value);
});
document.querySelectorAll("[data-assistant-action]").forEach(button => button.addEventListener("click", () => {
  void askAssistant(button.dataset.assistantAction);
}));

document.querySelectorAll(".provider-key-form").forEach(form => form.addEventListener("submit", async event => {
  event.preventDefault();
  const provider = form.dataset.provider;
  const state = document.querySelector(`#${provider}-state`);
  const button = form.querySelector("button[type=submit]");
  button.disabled = true;
  state.textContent = "Checking key with the provider…";
  state.dataset.kind = "";
  try {
    const apiKey = new FormData(form).get("api_key");
    const response = await fetch(`/api/providers/${provider}/key`, {
      method: "POST",
      headers: { "content-type": "application/json", "x-csrf-token": csrfToken },
      body: JSON.stringify({ api_key: apiKey }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail ?? "The provider key could not be connected.");
    form.reset();
    state.textContent = "Connected · encrypted on this server";
    state.dataset.kind = "success";
    await loadProviders();
    providerCard.querySelector("details").open = true;
  } catch (error) {
    state.textContent = error.message;
    state.dataset.kind = "error";
  } finally {
    button.disabled = false;
  }
}));

localProviderForm.addEventListener("submit", async event => {
  event.preventDefault();
  const state = document.querySelector("#local-state");
  const button = localProviderForm.querySelector("button[type=submit]");
  button.disabled = true;
  state.textContent = "Checking local model server…";
  state.dataset.kind = "";
  try {
    const values = new FormData(localProviderForm);
    const response = await fetch("/api/providers/local", {
      method: "POST",
      headers: {"content-type": "application/json", "x-csrf-token": csrfToken},
      body: JSON.stringify({base_url: values.get("base_url"), api_key: values.get("api_key")}),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail ?? "The local model server could not be connected.");
    localProviderForm.elements.api_key.value = "";
    state.textContent = "Connected · model server ready";
    state.dataset.kind = "success";
    await loadProviders();
    providerCard.querySelector("details").open = true;
  } catch (error) {
    state.textContent = error.message;
    state.dataset.kind = "error";
  } finally {
    button.disabled = false;
  }
});

document.querySelector("#connect-chatgpt").addEventListener("click", async event => {
  const button = event.currentTarget;
  button.disabled = true;
  try {
    const response = await fetch("/api/providers/chatgpt/start", {
      method: "POST", headers: { "x-csrf-token": csrfToken },
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail ?? "ChatGPT sign-in could not start.");
    location.assign(data.authorization_url);
  } catch (error) {
    const state = document.querySelector("#chatgpt-state");
    state.textContent = error.message;
    state.dataset.kind = "error";
    button.disabled = false;
  }
});

document.querySelector("#connect-copilot").addEventListener("click", async event => {
  const button = event.currentTarget;
  const state = document.querySelector("#copilot-state");
  button.disabled = true;
  state.textContent = "Starting GitHub sign-in…";
  state.dataset.kind = "";
  try {
    const response = await fetch("/api/providers/copilot/start", {
      method: "POST", headers: { "x-csrf-token": csrfToken },
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail ?? "GitHub sign-in could not start.");
    const verification = new URL(data.verification_uri);
    if (verification.origin !== "https://github.com" || verification.pathname !== "/login/device") throw new Error("GitHub returned an invalid verification address.");
    const flow = ++copilotFlowId;
    copilotState = data.state;
    document.querySelector("#copilot-code").textContent = data.user_code;
    document.querySelector("#copilot-verification-link").href = verification.href;
    document.querySelector("#copilot-flow-status").textContent = "Waiting for GitHub approval…";
    document.querySelector("#copilot-flow").hidden = false;
    document.querySelector("#cancel-copilot").hidden = false;
    button.hidden = true;
    providerCard.querySelector("details").open = true;
    void pollCopilot(flow, data.state, data.interval, data.expires_in);
  } catch (error) {
    state.textContent = error.message;
    state.dataset.kind = "error";
    button.disabled = false;
  }
});

async function pollCopilot(flow, state, interval, expiresIn) {
  const status = document.querySelector("#copilot-flow-status");
  const wait = milliseconds => new Promise(resolve => setTimeout(resolve, milliseconds));
  const finish = () => {
    document.querySelector("#copilot-flow").hidden = true;
    document.querySelector("#cancel-copilot").hidden = true;
    const button = document.querySelector("#connect-copilot");
    button.hidden = false;
    button.disabled = false;
  };
  const started = Date.now();
  while (flow === copilotFlowId && Date.now() - started < expiresIn * 1000) {
    await wait(interval * 1000);
    if (flow !== copilotFlowId) return;
    try {
      const response = await fetch("/api/providers/copilot/poll", {
        method: "POST", headers: { "content-type": "application/json", "x-csrf-token": csrfToken },
        body: JSON.stringify({ state }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? "GitHub sign-in could not be checked.");
      if (data.status === "pending") { interval = Math.max(interval, data.retry_after ?? interval); continue; }
      if (data.status === "connected") {
        status.textContent = `Connected as @${data.login}.`;
        await loadProviders();
        providerCard.querySelector("details").open = true;
        finish();
        return;
      }
      status.textContent = data.status === "denied" ? "GitHub sign-in was declined." :
        data.status === "expired" ? "The sign-in code expired. Start again." : (data.message ?? "GitHub sign-in could not be completed.");
      finish();
      return;
    } catch (error) {
      status.textContent = error.message;
      finish();
      return;
    }
  }
  if (flow === copilotFlowId) { status.textContent = "The sign-in code expired. Start again."; finish(); }
}

document.querySelector("#cancel-copilot").addEventListener("click", async () => {
  copilotFlowId++;
  if (copilotState) {
    void fetch("/api/providers/copilot/cancel", {
      method: "POST", headers: { "content-type": "application/json", "x-csrf-token": csrfToken },
      body: JSON.stringify({ state: copilotState }),
    }).catch(() => {});
    copilotState = undefined;
  }
  document.querySelector("#copilot-flow").hidden = true;
  document.querySelector("#cancel-copilot").hidden = true;
  const button = document.querySelector("#connect-copilot");
  button.hidden = false;
  button.disabled = false;
  document.querySelector("#copilot-state").textContent = "Sign-in cancelled.";
});

document.querySelectorAll("[data-disconnect]").forEach(button => button.addEventListener("click", async () => {
  const provider = button.dataset.disconnect;
  const state = document.querySelector(`#${provider}-state`);
  button.disabled = true;
  try {
    const response = await fetch(`/api/providers/${provider}`, {
      method: "DELETE", headers: { "x-csrf-token": csrfToken },
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail ?? "The provider could not be disconnected.");
    await loadProviders();
    if (provider === "chatgpt" && !data.remote_revocation_confirmed) {
      state.textContent = "Local connection removed. Remote revocation was not confirmed; review ChatGPT settings.";
      state.dataset.kind = "error";
    }
  } catch (error) {
    state.textContent = error.message;
    state.dataset.kind = "error";
  } finally {
    button.disabled = false;
  }
}));

async function loadAccount() {
  try {
    const response = await fetch("/api/auth/me");
    if (!response.ok) throw new Error("Account status could not be loaded.");
    const data = await response.json();
    if (!data.user) return;
    currentUser = data.user;
    csrfToken = data.csrf_token;
    renderAccount();
    await syncAccountProgress();
    try { await loadProviders(); } catch (error) { providerNotice.textContent = error.message; }
  } catch (error) {
    setAccountStatus(`${error.message} Your browser progress is still available.`, "error");
  }
}

async function authenticate(mode) {
  setAccountStatus(mode === "register" ? "Creating your account…" : "Signing in…");
  try {
    const response = await fetch(`/api/auth/${mode}`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(Object.fromEntries(new FormData(accountForm))),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail ?? "Account request failed.");
    currentUser = data.user;
    csrfToken = data.csrf_token;
    accountForm.reset();
    document.querySelector("#account-password").autocomplete = "current-password";
    renderAccount();
    await syncAccountProgress();
    try { await loadProviders(); } catch (error) { providerNotice.textContent = error.message; }
  } catch (error) {
    setAccountStatus(error.message, "error");
  }
}

accountForm.addEventListener("submit", event => {
  event.preventDefault();
  document.querySelector("#account-password").autocomplete = "new-password";
  authenticate("register");
});
document.querySelector("#sign-in").addEventListener("click", () => {
  document.querySelector("#account-password").autocomplete = "current-password";
  authenticate("login");
});
document.querySelector("#sign-out").addEventListener("click", async () => {
  try {
    const response = await fetch("/api/auth/logout", { method: "POST", headers: { "x-csrf-token": csrfToken } });
    if (!response.ok) throw new Error("Sign out could not be completed.");
    currentUser = undefined;
    csrfToken = undefined;
    renderAccount();
    setAccountStatus("Signed out. Progress in this browser is still available.");
  } catch (error) {
    setAccountStatus(error.message, "error");
  }
});

function renderExercise(lesson) {
  currentExercise = exercises.find(item => item.slug === lesson.slug);
  clearAssistantConversation();
  exerciseCard.hidden = !currentExercise;
  if (!currentExercise) return;
  lastQueryResult = undefined;
  document.querySelector("#exercise-title").textContent = currentExercise.title;
  document.querySelector("#exercise-prompt").textContent = currentExercise.prompt;
  const done = completed.has(currentExercise.slug);
  document.querySelector("#exercise-complete").textContent = done ? "Completed" : "";
  exerciseStatus.textContent = done ? "You’ve completed this activity. You can practise it again any time." : "Your progress stays in this browser until you sign in.";
  helpOutput.hidden = true;
  helpOutput.textContent = "";
  exerciseChoices.replaceChildren();
  exerciseChoices.hidden = currentExercise.kind !== "choice";
  exerciseInstruction.hidden = currentExercise.kind !== "sql";
  if (currentExercise.kind === "choice") {
    for (const choice of currentExercise.choices) {
      const label = document.createElement("label");
      const input = document.createElement("input");
      input.type = "radio";
      input.name = "exercise-answer";
      input.value = choice.value;
      const text = document.createElement("span");
      text.textContent = choice.label;
      label.append(input, text);
      exerciseChoices.append(label);
    }
  }
}

function checkSqlActivity() {
  if (!lastQueryResult) {
    exerciseStatus.textContent = "Run your query below first. The result will stay here while you check it.";
    return false;
  }
  const rows = lastQueryResult.rows ?? [];
  if (currentExercise.check === "names") {
    const names = rows.map(row => row.name).filter(Boolean).sort();
    return JSON.stringify(names) === JSON.stringify([...currentExercise.expected].sort());
  }
  if (currentExercise.check === "updated-samosa") return rows.some(row => row.name === "Samosa" && Number(row.stock) > 32);
  if (currentExercise.check === "joined-customers") {
    const names = rows.map(row => row.name).filter(Boolean).sort();
    return JSON.stringify(names) === JSON.stringify([...currentExercise.expected].sort()) && rows.every(row => Number(Object.entries(row).find(([key]) => key !== "name")?.[1]) > 0);
  }
  if (currentExercise.check === "category-counts") {
    const actual = Object.fromEntries(rows.map(row => [row.category, Number(row.product_count)]));
    const expected = { Coffee: 1, Snacks: 1, Tea: 2 };
    return Object.keys(actual).length === 3 && Object.entries(expected).every(([category, count]) => actual[category] === count);
  }
  if (currentExercise.check === "explain-products") return rows.some(row => Object.values(row).some(value => /scan on products/i.test(String(value))));
  if (currentExercise.check === "guarded-stock") return rows.some(row => Number(row.stock) >= 0 && Number(row.stock) < 200);
  return false;
}

document.querySelector("#check-exercise").addEventListener("click", async () => {
  if (!currentExercise) return;
  const correct = currentExercise.kind === "choice"
    ? exerciseChoices.querySelector("input:checked")?.value === currentExercise.answer
    : checkSqlActivity();
  if (correct) finishActivity();
  else if (currentExercise.kind === "choice") exerciseStatus.textContent = "Not quite. Think it through, then try another answer.";
  else if (lastQueryResult) exerciseStatus.textContent = "That result does not match the check yet. Adjust the query and try again.";
  if (currentUser) {
    try {
      await sendProgress(currentExercise.slug, correct);
      setAccountStatus("Activity attempt saved to your account.", "success");
    } catch (error) {
      setAccountStatus(`${error.message} Your browser progress is still available.`, "error");
    }
  }
});

document.querySelector(".help-controls").addEventListener("click", event => {
  const level = event.target.closest("[data-help]")?.dataset.help;
  if (!currentExercise || !level) return;
  helpOutput.textContent = currentExercise.help[level];
  helpOutput.hidden = false;
});

function syncCourseMenu() {
  courseMenu.open = !compactViewport.matches;
}

syncCourseMenu();
compactViewport.addEventListener("change", syncCourseMenu);

const chapterNumber = slug => slug.split("-")[0];

function renderNav() {
  const groups = [];
  for (const lesson of lessons) {
    let group = groups.at(-1);
    if (!group || group.part !== lesson.part) {
      group = { part: lesson.part, lessons: [] };
      groups.push(group);
    }
    group.lessons.push(lesson);
  }
  nav.replaceChildren(...groups.map(group => {
    const section = document.createElement("section");
    section.className = "nav-group";
    const heading = document.createElement("h2");
    heading.textContent = group.part;
    const list = document.createElement("ol");
    for (const lesson of group.lessons) {
      const item = document.createElement("li");
      const link = document.createElement("a");
      link.className = "lesson-link";
      link.href = `/playground#${encodeURIComponent(lesson.slug)}`;
      link.dataset.slug = lesson.slug;
      link.dataset.title = lesson.title;
      const number = document.createElement("span");
      number.className = "lesson-number";
      number.textContent = chapterNumber(lesson.slug);
      const title = document.createElement("span");
      title.textContent = lesson.title;
      const check = document.createElement("span");
      check.className = "lesson-check";
      check.setAttribute("aria-hidden", "true");
      link.append(number, title, check);
      item.append(link);
      list.append(item);
    }
    section.append(heading, list);
    return section;
  }));
  document.querySelector("#lesson-count").textContent = `${lessons.length} lessons`;
  updateProgress();
}

async function openLesson(slug, { announce = true } = {}) {
  const lesson = lessons.find(item => item.slug === slug);
  if (!lesson) return;
  currentLesson = lesson;
  content.setAttribute("aria-busy", "true");
  lessonStatus.textContent = `Loading ${lesson.title}`;
  try {
    const response = await fetch(`/course/${encodeURIComponent(slug)}.html`);
    if (!response.ok) throw new Error(`The lesson returned ${response.status}.`);
    const page = new DOMParser().parseFromString(await response.text(), "text/html");
    const article = page.querySelector("article.lesson");
    if (!article) throw new Error("The lesson content is missing.");
    content.innerHTML = article.innerHTML;
    document.querySelector("#current-part").textContent = lesson.part;
    document.querySelector("#workspace-title").textContent = lesson.title;
    document.querySelector("#lesson-position").textContent = `${chapterNumber(slug)} · LESSON`;
    document.querySelector("#lesson-tag").textContent = `${lessons.indexOf(lesson) + 1} of ${lessons.length}`;
    document.querySelector("#brief-title").textContent = lesson.title;
    document.querySelector("#brief-summary").textContent = lesson.summary;
    document.querySelector("#reading-link").href = `/course/${encodeURIComponent(slug)}.html`;
    document.title = `${lesson.title} · Postgres Lab`;
    renderExercise(lesson);
    nav.querySelectorAll(".lesson-link").forEach(link => {
      if (link.dataset.slug === slug) link.setAttribute("aria-current", "page");
      else link.removeAttribute("aria-current");
    });
    window.bootCourseVisualizations?.();
    if (announce) lessonStatus.textContent = `Loaded ${lesson.title}`;
  } catch (error) {
    content.replaceChildren(Object.assign(document.createElement("p"), { textContent: `We couldn’t load this lesson. ${error.message}` }));
    lessonStatus.textContent = `Could not load ${lesson.title}`;
  } finally {
    content.removeAttribute("aria-busy");
  }
}

async function start() {
  try {
    const response = await fetch("/api/course");
    if (!response.ok) throw new Error("Course catalog is unavailable.");
    lessons = (await response.json()).lessons;
    if (!lessons.length) throw new Error("No lessons were found.");
    renderNav();
    const requested = decodeURIComponent(location.hash.slice(1));
    await openLesson(lessons.some(item => item.slug === requested) ? requested : lessons[0].slug, { announce: false });
    initializeDatabase();
    void loadAccount();
  } catch (error) {
    content.replaceChildren(Object.assign(document.createElement("p"), { textContent: error.message }));
    lessonStatus.textContent = error.message;
  }
}

async function initializeDatabase() {
  const status = databaseCard.querySelector("small");
  try {
    database = await PGliteWorker.create(new PGWorker({ type: "module" }), { dataDir: "idb://postgres-lab-sandbox" });
    await database.waitReady;
    const existing = await database.query("SELECT to_regclass('public.products') AS products");
    if (!existing.rows[0].products) await database.exec(seedSql);
    databaseCard.dataset.ready = "true";
    status.textContent = "Ready · stored in this browser";
    runQueryButton.disabled = false;
    queryStatus.textContent = "Ready · run a query to see its results.";
  } catch (error) {
    status.textContent = `Unavailable · ${error.message}`;
    queryStatus.textContent = "The local database could not start. Reload the workspace to retry.";
    queryStatus.dataset.kind = "error";
  }
}

function cellText(value) {
  if (value === null) return "NULL";
  return typeof value === "object" ? JSON.stringify(value) : String(value);
}

function renderResults(result, elapsedMs) {
  queryResults.replaceChildren();
  const rows = result.rows ?? [];
  const count = result.rowCount ?? rows.length;
  const command = result.command ?? "Query";
  resultSummary.textContent = `${command} · ${count} row${count === 1 ? "" : "s"} · ${elapsedMs} ms`;

  if (!rows.length) return;
  const fields = result.fields?.map(field => field.name) ?? Object.keys(rows[0]);
  const table = document.createElement("table");
  table.setAttribute("aria-label", "SQL query results");
  const head = table.createTHead().insertRow();
  for (const field of fields) {
    const cell = document.createElement("th");
    cell.scope = "col";
    cell.textContent = field;
    head.append(cell);
  }
  const body = table.createTBody();
  for (const row of rows.slice(0, 100)) {
    const line = body.insertRow();
    for (const field of fields) {
      const cell = line.insertCell();
      const value = row[field];
      cell.textContent = cellText(value);
      if (value === null) cell.className = "is-null";
      cell.title = cell.textContent;
    }
  }
  queryResults.append(table);
  if (rows.length > 100) resultSummary.textContent += " · showing first 100";
}

async function runQuery() {
  const sql = sqlEditor.value.trim();
  if (!database || !sql || runQueryButton.disabled) {
    if (!sql) {
      queryStatus.textContent = "Enter a query before running it.";
      queryStatus.dataset.kind = "error";
    }
    return;
  }
  runQueryButton.disabled = true;
  resetDatabaseButton.disabled = true;
  queryResults.replaceChildren();
  queryResults.setAttribute("aria-busy", "true");
  queryStatus.textContent = "Running query…";
  queryStatus.dataset.kind = "";
  resultSummary.textContent = "Working in your local PostgreSQL sandbox";
  lastQueryResult = undefined;
  const startTime = performance.now();
  try {
    const result = await database.query(sql);
    lastQueryResult = result;
    const elapsedMs = Math.round(performance.now() - startTime);
    renderResults(result, elapsedMs);
    queryStatus.textContent = `${result.command ?? "Query"} completed.`;
    queryStatus.dataset.kind = "success";
  } catch (error) {
    resultSummary.textContent = "Check the query and try again.";
    queryStatus.textContent = `Query error: ${error.message}`;
    queryStatus.dataset.kind = "error";
  } finally {
    queryResults.removeAttribute("aria-busy");
    runQueryButton.disabled = false;
    resetDatabaseButton.disabled = false;
  }
}

async function resetDatabase() {
  if (!database || resetDatabaseButton.disabled) return;
  if (!window.confirm("Reset the local ChaiPoint database to its starter data?")) return;
  runQueryButton.disabled = true;
  resetDatabaseButton.disabled = true;
  queryResults.setAttribute("aria-busy", "true");
  queryStatus.textContent = "Restoring starter data…";
  queryStatus.dataset.kind = "";
  try {
    await database.exec("DROP SCHEMA public CASCADE; CREATE SCHEMA public;");
    await database.exec(seedSql);
    queryResults.replaceChildren();
    resultSummary.textContent = "Starter data restored.";
    queryStatus.textContent = "Database reset complete.";
    queryStatus.dataset.kind = "success";
    sqlEditor.value = "SELECT name, stock\nFROM products\nORDER BY name;";
  } catch (error) {
    queryStatus.textContent = `Reset error: ${error.message}`;
    queryStatus.dataset.kind = "error";
  } finally {
    queryResults.removeAttribute("aria-busy");
    runQueryButton.disabled = false;
    resetDatabaseButton.disabled = false;
  }
}

runQueryButton.addEventListener("click", runQuery);
resetDatabaseButton.addEventListener("click", resetDatabase);
sqlEditor.addEventListener("keydown", event => {
  if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
    event.preventDefault();
    runQuery();
  }
});

nav.addEventListener("click", event => {
  const link = event.target.closest("a[data-slug]");
  if (!link) return;
  event.preventDefault();
  history.pushState(null, "", link.href);
  openLesson(link.dataset.slug);
  if (compactViewport.matches) courseMenu.open = false;
});

window.addEventListener("popstate", () => {
  const slug = decodeURIComponent(location.hash.slice(1));
  openLesson(lessons.some(item => item.slug === slug) ? slug : lessons[0]?.slug);
});

start();
