# CLAUDE.md — Full Skills Template

> Copy this file as `CLAUDE.md` in any project root to enable all Claude Code skills.

---

## Project Overview

<!-- Describe your project here -->

---

## Claude Code Skills Reference

### /update-config
Configure Claude Code behavior via `settings.json`.
Use for:
- Setting up automated hooks ("before every commit, run tests")
- Changing model, timeout, or other harness settings
- Triggering shell commands on Claude Code events

Example prompts:
```
/update-config add a pre-tool-use hook that runs eslint before any Edit
/update-config set default model to claude-opus-4-6
```

---

### /keybindings-help
Customize keyboard shortcuts in `~/.claude/keybindings.json`.
Use for:
- Rebinding keys (e.g., change submit key)
- Adding chord shortcuts
- Modifying or listing current keybindings

Example prompts:
```
/keybindings-help rebind ctrl+s to submit
/keybindings-help add a chord shortcut for /commit
```

---

### /simplify
Review recently changed code for quality, reuse, and efficiency — then fix issues found.
Use after writing or editing code to:
- Remove duplication
- Improve readability
- Apply best practices

Example prompts:
```
/simplify
/simplify the last function I wrote
```

---

### /loop [interval] [command]
Run a prompt or slash command repeatedly on a fixed interval.
Default interval: 10 minutes.

Example prompts:
```
/loop 5m /simplify
/loop 1m check if the server is still running and report status
/loop 30s run the test suite and report failures
```

---

### /schedule
Create, list, update, or delete scheduled remote agents that run on a cron schedule.
Use for:
- Automating recurring tasks (daily reports, nightly builds)
- Setting up cron-style AI agents
- Managing existing scheduled triggers

Example prompts:
```
/schedule create a daily agent at 9am that summarizes yesterday's git commits
/schedule list all my scheduled agents
/schedule delete the nightly-build agent
```

---

### /claude-api
Build applications using the Claude API or Anthropic SDK.
Triggered automatically when your code imports `anthropic` or `@anthropic-ai/sdk`.
Use for:
- Writing scripts that call Claude programmatically
- Building multi-agent pipelines with the Agent SDK
- Tool use, streaming, and structured output patterns

Example prompts:
```
/claude-api write a script that summarizes a file using claude-haiku-4-5
/claude-api build a multi-turn chat loop with tool use
```

Recommended models:
| Use case | Model ID |
|----------|----------|
| Best quality | `claude-opus-4-6` |
| Balanced | `claude-sonnet-4-6` |
| Fast / cheap | `claude-haiku-4-5-20251001` |

---

### /web-artifacts-builder
Build elaborate, multi-component HTML artifacts using React, Tailwind CSS, and shadcn/ui.
Use for:
- Interactive dashboards or data visualizations
- Multi-page single-page apps (with routing)
- Artifacts with complex state management

Example prompts:
```
/web-artifacts-builder create a kanban board with drag-and-drop
/web-artifacts-builder build a budget tracker dashboard with charts
```

---

## Automated Behaviors (Hooks via /update-config)

> Use `/update-config` to wire these up in `settings.json`.

| Trigger | Example action |
|---------|---------------|
| Before any `Edit` | Run linter |
| After any `Write` | Run formatter |
| Before `/commit` | Run test suite |
| After task completes | Send desktop notification |

---

## Key Conventions

- Skills are invoked with `/skill-name` in the chat prompt
- `/loop` and `/schedule` are for recurring automation; `/loop` is in-session, `/schedule` is persistent
- `/claude-api` activates automatically on Anthropic SDK imports
- `/update-config` is the entry point for all settings and hook changes
