## What changes
<!-- What the user sees, and why. -->

## Database
<!-- New sql/predeployment files, or "No schema changes". -->

## Tests
<!-- How many pass, what's new; phone screenshots checked (light/dark)? -->

## Docs and memory
<!-- Every PR documents itself (CLAUDE.md). Tick each, or say why it doesn't apply. -->
- [ ] **Process docs:** the `docs/processes/` page of each area touched, with its Mermaid
      diagram redrawn if the flow, the data or the screens changed. A new area gets a
      new page, linked from `docs/processes/README.md`.
- [ ] **Architecture:** `docs/processes/ARCHITECTURE.md` if a module, route group,
      table or the navigation changed. `README.md` if setup or the project layout changed.
- [ ] **Skills:** `.claude/skills/` updated if a procedure changed, or a new skill if
      it's a task that will repeat. New skills go in the table in `CLAUDE.md`.
- [ ] **Memory:** the area's memory file (live state, decisions and why, open items)
      and its line in `MEMORY.md`.
- [ ] **PR body:** a "Docs and memory" section that lists the above.
