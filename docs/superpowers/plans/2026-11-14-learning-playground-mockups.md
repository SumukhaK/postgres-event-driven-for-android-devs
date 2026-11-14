# Learning Playground Mockups Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce three clickable, locally viewable learning-playground mockups and matching desktop screenshots for the PostgreSQL course.

**Architecture:** Use three small HTML pages with one shared stylesheet and one shared vanilla JavaScript file. Each page presents the same ChaiPoint concurrency lesson while changing the course navigation, exercise layout, and help-panel hierarchy.

**Tech Stack:** HTML, CSS, vanilla JavaScript, offline PNG preview exports via Windows System.Drawing. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-11-14-learning-playground-design.md`

## Global Constraints

- Primary use is focused desktop learning; layouts adapt to tablet and narrow mobile widths.
- Include a course map, current lesson, SQL exercise, graduated help, progress summary, learner account, and separate AI provider settings.
- Use a conditional “Continue with ChatGPT” label and an email fallback; do not imply unsupported provider access.
- Explain separate API/consumer-plan billing; never request a real provider secret in the browser.
- Use visible keyboard focus, readable contrast, non-color status cues, and reduced-motion support.
- Keep the mockups local and static; no production auth, persistence, SQL execution, or AI calls.

## Review Focus

- At 375px wide, the page stacks panels without horizontal page overflow.
- With keyboard navigation, interactive controls remain reachable and focus remains visible.
- With reduced motion enabled, state changes do not depend on animation.
- Provider screens retain the billing/availability disclosure and never ask for a real API secret.
- The hint-to-solution flow is readable and does not obscure the exercise or progress state.

---

## File Structure

- Create `design/learning-playground/editorial.html` — light editorial lesson layout.
- Create `design/learning-playground/studio.html` — dark, code-first workspace layout.
- Create `design/learning-playground/guided.html` — warm, milestone-led layout.
- Create `design/learning-playground/styles.css` — shared components plus three page themes and responsive rules.
- Create `design/learning-playground/prototype.js` — help-level selection, simulated Run/Complete states, sign-in and provider dialogs.
- Create `design/learning-playground/README.md` — how to open the pages and what is simulated.
- Create `design/learning-playground/render-screenshots.ps1` — offline Windows exporter for the PNG preview comps.
- Create `screenshots/editorial-learning-lab.png`, `screenshots/developer-studio.png`, and `screenshots/guided-learning-path.png` — same 1440×1000 desktop viewport.

## Task 1: Build and capture the three static mockups

**Files:**

- Create all files listed above.

**Interfaces:**

- Each HTML page loads `styles.css` and `prototype.js` by relative path and declares its visual direction with a body theme class.
- Use `.theme-editorial`, `.theme-studio`, and `.theme-guided` for page themes; use `[data-action="run"]`, `[data-action="complete"]`, `[data-help-level="nudge|hint|solution"]`, and `[data-dialog="signin|provider"]` for shared controls.
- Use native `<dialog id="signin-dialog">` and `<dialog id="provider-dialog">` so focus, Escape-to-close, and modal semantics come from the platform.
- All pages show the same course map (11 published lessons), `8/11 complete`, and Chapter 08 in progress.
- The representative exercise starts with stock `200`; the simulated guarded update reduces it to `198`. Marking it complete updates the visible course progress state.

- [x] **Step 1: Create the three page structures** with the same ChaiPoint lesson, course-map labels, 8/11 progress, SQL editor sample, and coach controls; apply each direction’s distinct layout.
- [x] **Step 2: Add shared responsive styling** for the three themes, readable code/results, keyboard focus, non-color states, and `prefers-reduced-motion`.
- [x] **Step 3: Add shared prototype interactions** so Run and Complete show simulated state, help buttons reveal nudge/hint/solution content, and the account/provider controls open and close their dialogs.
- [x] **Step 4: Add sign-in/provider copy** that separates course identity from model usage, marks ChatGPT sign-in as conditional, offers an email fallback, and describes OpenCode, OpenAI, and Anthropic provider access without requesting secrets.
- [x] **Step 5: Write the README** with direct-open instructions and an explicit note that all interactions and progress are local simulation.
- [x] **Step 6: Export three 1440x1000 offline PNG preview comps into screenshots/.**
- [x] **Step 7: Review exported desktop comps and inspect responsive CSS, keyboard focus, reduced-motion support, provider disclosure, and help copy in source.** The installed headless browser renderers could not start their child processes, so mobile and keyboard behavior were not visually exercised in a browser.

**Execution note:** The sandbox allows editing project files but marks .git read-only, so these artifacts remain uncommitted in the local checkout. PNGs are offline visual comps generated with the included PowerShell exporter; they share layout and content with the HTML previews but are not browser captures.
