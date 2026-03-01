# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Status

This is a new project workspace with the GSD (Get Shit Done) framework installed. No application code exists yet. Use GSD workflows to initialize and build the project.

## GSD Framework

The `.claude/get-shit-done/` directory contains the GSD project orchestration framework (v1.20.6). It manages planning, execution, and verification of development work through specialized AI agents and structured workflows.

### Key Commands

All GSD commands are invoked as slash commands in Claude Code:

- `/gsd:new-project` — Initialize a new project (creates PROJECT.md, ROADMAP.md, REQUIREMENTS.md)
- `/gsd:plan-phase <N>` — Research and plan a specific phase
- `/gsd:execute-phase <N>` — Execute a planned phase with wave-based parallelization
- `/gsd:verify-work` — Verify completed work against phase goals
- `/gsd:progress` — Check project progress and get routed to next action
- `/gsd:resume-work` — Resume work from a previous session
- `/gsd:debug` — Systematic debugging with persistent state

### CLI Tool

```bash
node ./.claude/get-shit-done/bin/gsd-tools.cjs <command> [args] [--raw]
```

Subcommands: `state`, `phase`, `roadmap`, `config`, `verify-summary`, `verify`, `init`, `commit`, `frontmatter`, `template`, `slug`, `timestamp`, `todo`, `history-digest`.

### Architecture

- **Agents** (`.claude/agents/`): 11 specialized agent definitions (planner, executor, verifier, researcher, debugger, etc.)
- **Workflows** (`.claude/get-shit-done/workflows/`): 30+ markdown workflow definitions that map to slash commands
- **Core lib** (`.claude/get-shit-done/bin/lib/`): CommonJS modules — `core.cjs` (shared utils), `state.cjs`, `roadmap.cjs`, `phase.cjs`, `milestone.cjs`, `template.cjs`, `frontmatter.cjs`, `verify.cjs`, `config.cjs`, `init.cjs`, `commands.cjs`
- **Templates** (`.claude/get-shit-done/templates/`): Document templates for plans, summaries, and project artifacts

### Key Artifacts (created during project lifecycle)

- `PROJECT.md` — Project definition and scope
- `.planning/ROADMAP.md` — Phase breakdown with success criteria
- `.planning/REQUIREMENTS.md` — Requirement traceability matrix
- `.planning/STATE.md` — Current execution state (source of truth for progress)
- `.planning/config.json` — Project-specific configuration (model profile, workflow toggles, git strategy)
- `.planning/phase-N/PLAN.md` — Executable plan for each phase
- `.planning/phase-N/SUMMARY.md` — Completion evidence per phase

### Configuration

Model profiles control which Claude model each agent uses: `quality` (opus-heavy), `balanced` (default), `budget` (haiku-heavy). Set via `/gsd:set-profile` or in `.planning/config.json`.

### Hooks

`.claude/settings.json` configures three hooks:
- **SessionStart**: Background update checker
- **PostToolUse**: Context usage monitor (warns when context is getting large)
- **statusLine**: Terminal status display
