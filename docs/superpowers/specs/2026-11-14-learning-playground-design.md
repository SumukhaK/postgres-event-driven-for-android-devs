# PostgreSQL learning playground: UI design brief

## Goal

Create three desktop-first, responsive wireframe mockups for an interactive PostgreSQL and backend course aimed at experienced Android developers. Each mockup should show the same core lesson experience with a different visual hierarchy so the user can compare and choose a direction.

The mockups are design artifacts, not a working learning platform. They should make the intended lesson, practice, progress, account, and AI-help flows understandable at a glance.

## Audience and context

- Android developers who know Kotlin, Room, coroutines, and app architecture, but are learning PostgreSQL and backend concepts.
- Primary use is focused desktop learning; layouts should still adapt cleanly to tablet and narrow mobile widths.
- The running example is ChaiPoint. The representative lesson is the guarded stock update from the concurrency/order API chapters.

## Shared learning flow

All three concepts include:

1. A predictable course map with chapter names and completed/current/next states.
2. A current lesson with a short objective and clear explanation.
3. An interactive SQL exercise area with a sample query, Run action, and visible result/feedback state.
4. A graduated help path: nudge, hint, then complete solution with an explanation. Asking for help should not erase progress or shame the learner.
5. A persistent progress summary showing course completion and current lesson position.
6. A learner sign-in screen/account area and a separate AI provider connection/settings area.

## Three visual directions

### A. Editorial learning lab

- Light, quiet surface and strong typographic hierarchy.
- Narrow course rail on the left, readable lesson and exercise in the center, persistent coach on the right.
- Best for reading-first learners and a low-friction transition from tutorial text to practice.

### B. Developer studio

- Dark, code-first workspace with restrained color and high-contrast editor states.
- Compact course rail, lesson brief above or beside the SQL editor/results, coach in a collapsible side panel.
- Best for longer practice sessions where running and inspecting SQL is the main activity.

### C. Guided learning path

- Warm, progress-led surface with explicit milestones and one primary action per step.
- A lightweight journey/progress rail, focused lesson card, exercise, and expandable help drawer.
- Best for learners who want clear momentum and small, guided steps.

## Account and AI usage language

Treat course identity and model access as separate concepts in every mockup. Include a course account sign-in screen with a conditional “Continue with ChatGPT” option and a standard email fallback. ChatGPT identity sign-in is currently available through participating apps, so the label is illustrative until this product is eligible to integrate it. Do not present Claude consumer login as a generic third-party OAuth option without validating that capability.

Show AI access as a separate settings flow. Include OpenCode as a connector for models already configured there, plus OpenAI and Anthropic provider options. Provide permission review, usage/billing disclosure, a spend limit control, and disconnect. Explain that API usage may be billed separately from consumer plans; ChatGPT usage sharing requires a separately supported authorization and eligibility, while a Claude subscription does not include API usage through the Console. OpenCode manages its provider connection; usage follows provider terms. A provider connection in a wireframe is illustrative only and must not request a real secret in the browser.

## Accessibility and interaction

- Use readable body text, strong text and control contrast, visible keyboard focus, clear labels, and non-color status cues.
- Make primary controls comfortable to click and ensure help, progress, and run states are understandable without motion.
- Use motion only to clarify state changes; respect reduced-motion preferences in any interactive prototype behavior.
- Avoid emoji as functional icons.

## Deliverables after spec approval

- Three self-contained, clickable HTML/CSS/JS mockups under `design/learning-playground/`, one per direction.
- One screenshot per direction under `screenshots/` with consistent desktop dimensions and a descriptive filename.
- Each mockup includes a sign-in view and an AI provider settings view reachable from the main lesson screen.
- A small `design/learning-playground/README.md` explaining how to open the mockups and what the interactions simulate.
- No changes to the course lessons, sample backend, authentication, database schema, AI calls, or provider credentials.

## Review criteria

- The three variants are visibly distinct, yet show the same representative lesson and core learning flow.
- It is obvious how a learner moves through lessons, runs an exercise, asks for progressively stronger help, and sees saved progress.
- Account sign-in and AI access are clearly separate.
- The files can be opened locally without installing dependencies or starting a service.
- Screenshots clearly show the main learning screen at the same desktop viewport for direct comparison.

## Scope limits

- No production implementation, backend persistence, OAuth, provider billing, real AI assistant, SQL execution, or progress syncing.
- No mobile screenshots in this first review set; the mockups should still have responsive layouts.
- No branding or logo work beyond a simple course/product wordmark.

## References

- [OpenAI: Sign in with ChatGPT](https://help.openai.com/en/articles/20001410-sign-in-with-chatgpt)
- [OpenAI: ChatGPT and API billing](https://help.openai.com/en/articles/9039756-managing-your-work-in-the-api-platform-with-projects)
- [Anthropic: Claude subscription and API billing](https://support.anthropic.com/en/articles/9876003-i-subscribe-to-a-paid-claude-ai-plan-why-do-i-have-to-pay-separately-for-api-usage-on-console)
- [OpenCode: provider sign-in and connections](https://opencode.ai/docs/providers/)
- [W3C: Web Content Accessibility Guidelines 2.2](https://www.w3.org/TR/WCAG22/)
