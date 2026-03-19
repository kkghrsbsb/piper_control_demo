# CLAUDE.md

## Documentation Entry

- Default to using `docs/src/README.md` as the first entry point for understanding this project.
- Before making assumptions about project structure, script purpose, workflows, or safety notes, read `docs/src/README.md` first.
- When a task changes project structure, script usage, run commands, environment setup, or risk/safety guidance, update `docs/src/README.md` to keep it in sync with the repository.
- When creating, deleting, renaming, or moving Markdown documents under `docs/src/`, always update `docs/src/SUMMARY.md` in the same task so the mdBook table of contents stays accurate.
- When the user explicitly asks for a change, decision, convention, or detail to be documented, record it in `docs/src/README.md`.
- When making a change that seems important for future understanding of the repository, or when a detail is likely to matter in later work, proactively update `docs/src/README.md` even if the user did not separately remind you.
- When citing project background or giving repository-level explanations, prefer `docs/src/README.md` unless newer source files clearly supersede it.
- For future socket streaming work under `src/piper_socket_bridge/`, treat the current `scripts/move_debug.py` as the control baseline. Do not use legacy control flow under `tests/socket_old/` as the reference implementation for new code.
- For real robot scripts that control joints inside `with piper_control.BuiltinJointPositionController(...)`, default to evaluating and reusing the shared software-layer keyboard e-stop capability unless there is a clear reason not to.
- For real robot scripts that include an operator-confirmed return-to-safe-pose and disable sequence, default to evaluating and reusing the shared shutdown flow capability unless there is a clear reason not to.

## Feature request workflow
- When the user proposes a new feature, do not change code immediately.
- First, clarify the intended behavior, affected modules, expected inputs and outputs, and possible risks or tradeoffs.
- Before making any code changes, create a plan document under `docs/src/plan/`.
- The plan document should be a Markdown file with a clear, descriptive filename in kebab-case.
- Creating a new plan document under `docs/src/plan/` also requires updating `docs/src/SUMMARY.md`.
- The plan document should explain:
  - feature goal
  - current problem or motivation
  - proposed design
  - files or modules likely to be affected
  - possible risks, edge cases, or compatibility concerns
  - implementation steps
- After writing the plan document, stop and wait for user confirmation before editing code.
- Do not modify source code until the user explicitly approves the plan.

## Code review and proposal workflow
- When the user asks for a code review, do not change code immediately.
- First, inspect the relevant code, related modules, and existing behavior.
- Identify problems such as logic bugs, fragile assumptions, missing validation, poor structure, unclear naming, dead code, performance issues, and maintainability risks.
- Before making any code changes, create a review document under `docs/src/review/`.
- The review document must be a Markdown file with a clear, descriptive kebab-case filename.
- Creating a new review document under `docs/src/review/` also requires updating `docs/src/SUMMARY.md`.
- The review document should explain:
  - review scope
  - files reviewed
  - current behavior summary
  - findings and issues
  - severity and impact of each issue
  - root cause analysis
  - recommended design or fix direction
  - affected files or modules
  - risks, edge cases, and compatibility concerns
  - suggested implementation order
- Prefer concrete and actionable findings over vague comments.
- After writing the review document, stop and wait for user confirmation.
- Do not modify source code until the user explicitly approves the proposed changes.

## Code explanation and change summary workflow
- When the user asks to explain code, summarize changes, or analyze an existing implementation, do not change code immediately.
- First, inspect the relevant files, related modules, call paths, and current behavior.
- Focus on explaining what the code does, how the pieces connect, what assumptions it relies on, and what important side effects or limitations exist.
- If the request involves a recent change, commit, diff, or a group of edited files, summarize what changed, why it likely changed, and what impact the change may have.
- Before making any code changes, create an explanation document under `docs/src/explain/`.
- The explanation document must be a Markdown file with a clear, descriptive kebab-case filename.
- Creating a new explanation document under `docs/src/explain/` also requires updating `docs/src/SUMMARY.md`.
- The explanation document should explain:
  - explanation scope
  - files reviewed
  - purpose of the code or change
  - current behavior summary
  - key control flow or execution path
  - important functions, classes, or modules involved
  - inputs, outputs, and data flow
  - dependencies, assumptions, and side effects
  - summary of changes if applicable
  - risks, limitations, edge cases, or unclear areas
  - follow-up questions or suggested next steps if needed
- Prefer concrete, code-based explanation over vague high-level commentary.
- After writing the explanation document, stop and wait for user confirmation.
- Do not modify source code unless the user explicitly asks for implementation changes.

## Commit message format
- When the user asks for commit text, generate a Git commit message instead of committing.
- Use Conventional Commits format:
  - feat:
  - fix:
  - refactor:
  - docs:
  - chore:
  - test:
- Preferred subject format:
  - `<type>(<scope>): <summary>`
- The subject must be concise, specific, and written in Chinese.
- Do not use vague subjects such as:
  - `update`
  - `fix bugs`
  - `misc changes`

## Commit body rules
- For non-trivial changes, also generate a commit body.
- The body should be written in Chinese.
- The body should explain:
  - what changed
  - why it changed
  - any important notes about usage, compatibility, hardware behavior, or risks
- Do not invent tests, results, or effects that are not supported by the diff or user instructions.
- If the change is trivial, the body may be omitted.
- Output should be easy for the user to copy directly into a Git GUI or terminal.

## Accuracy requirements for commit text
- Do not claim that robotic arm hardware tests, motion verification, CAN validation, calibration checks, or safety checks were completed unless the user explicitly said so.

## Python dependency source lookup
- When you need to inspect the implementation of an installed Python dependency, prefer the project virtualenv interpreter at `.venv/bin/python` instead of assuming `python` is available on `PATH`.
- A fast default pattern is:
  - use `.venv/bin/python` with `inspect.getfile(...)` to locate the installed module file
  - use `.venv/bin/python` with `inspect.getsource(...)` to read the relevant class or function
  - use `rg` on the located file to quickly find related constants, helper methods, or control-rate definitions
- Avoid using `uv run` for simple source inspection if it is blocked by sandbox or cache-permission issues; prefer the already-created `.venv` when available.
