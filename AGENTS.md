# AGENTS.md

## Documentation Entry

- Default to using `docs/src/README.md` as the first entry point for understanding this project.
- Before making assumptions about project structure, script purpose, workflows, or safety notes, read `docs/src/README.md` first.
- When a task changes project structure, script usage, run commands, environment setup, or risk/safety guidance, update `docs/src/README.md` to keep it in sync with the repository.
- When the user explicitly asks for a change, decision, convention, or detail to be documented, record it in `docs/src/README.md`.
- When making a change that seems important for future understanding of the repository, or when a detail is likely to matter in later work, proactively update `docs/src/README.md` even if the user did not separately remind you.
- When citing project background or giving repository-level explanations, prefer `docs/src/README.md` unless newer source files clearly supersede it.

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