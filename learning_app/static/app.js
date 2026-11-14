import { PGliteWorker } from "@electric-sql/pglite/worker";
import PGWorker from "./db-worker.js?worker";
import seedSql from "./seed.sql?raw";
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
let database;
let lessons = [];

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
      const number = document.createElement("span");
      number.className = "lesson-number";
      number.textContent = chapterNumber(lesson.slug);
      const title = document.createElement("span");
      title.textContent = lesson.title;
      link.append(number, title);
      item.append(link);
      list.append(item);
    }
    section.append(heading, list);
    return section;
  }));
  document.querySelector("#lesson-count").textContent = `${lessons.length} lessons`;
}

async function openLesson(slug, { announce = true } = {}) {
  const lesson = lessons.find(item => item.slug === slug);
  if (!lesson) return;
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
  queryStatus.textContent = "Running query…";
  queryStatus.dataset.kind = "";
  resultSummary.textContent = "Working in your local PostgreSQL sandbox";
  const startTime = performance.now();
  try {
    const result = await database.query(sql);
    const elapsedMs = Math.round(performance.now() - startTime);
    renderResults(result, elapsedMs);
    queryStatus.textContent = `${result.command ?? "Query"} completed.`;
    queryStatus.dataset.kind = "success";
  } catch (error) {
    resultSummary.textContent = "Check the query and try again.";
    queryStatus.textContent = `Query error: ${error.message}`;
    queryStatus.dataset.kind = "error";
  } finally {
    runQueryButton.disabled = false;
    resetDatabaseButton.disabled = false;
  }
}

async function resetDatabase() {
  if (!database || resetDatabaseButton.disabled) return;
  if (!window.confirm("Reset the local ChaiPoint database to its starter data?")) return;
  runQueryButton.disabled = true;
  resetDatabaseButton.disabled = true;
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
