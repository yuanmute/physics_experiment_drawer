# Platform compatibility

This package follows the Agent Skills open format: a directory with a `SKILL.md` containing `name` and `description`, plus optional `scripts/`, `references/`, and `assets/`. Keep the package intact when moving it between clients.

## Client locations

| Client | Recommended location | Notes |
| --- | --- | --- |
| Codex | `.agents/skills/physics-lab-plotter/` or `~/.agents/skills/physics-lab-plotter/` | `agents/openai.yaml` is optional UI metadata. This machine also supports `~/.codex/skills/physics-lab-plotter/`. |
| Claude Code | `.claude/skills/physics-lab-plotter/` or `~/.claude/skills/physics-lab-plotter/` | Invoke as `/physics-lab-plotter`; Claude Code can also select it automatically from its description. |
| Cursor | `.cursor/skills/physics-lab-plotter/` or `~/.cursor/skills/physics-lab-plotter/` | Invoke from Agent chat or let the Agent select it when the description matches. |
| WorkBuddy | The Claude Code skill directory used by the WorkBuddy installation | WorkBuddy is built on Claude Code. If a release exposes another skill directory, use that directory with the same package. |

## Portability rules

1. Do not rename `SKILL.md`, remove its YAML frontmatter, or move `scripts/` and `references/` away from the skill root.
2. Do not depend on `agents/openai.yaml` outside Codex; other clients should ignore it.
3. Run `scripts/make_lab_pdf.py` from any client with Python 3 and `xelatex` available on `PATH`. Use `python3` instead of `python` where required by the host.
4. Keep the confirmation gate: transcribe and show the table first, then fit only after the user confirms it.
5. If a client cannot discover a user-level skill immediately, restart its agent session or use its explicit skill invocation command.

## Invocation forms

- Codex: `$physics-lab-plotter`
- Claude Code: `/physics-lab-plotter`
- Cursor Agent: select or type `/physics-lab-plotter`
- WorkBuddy: `/physics-lab-plotter` through its Claude Code skill surface

References: [Agent Skills specification](https://agentskills.io/specification), [Codex skills](https://developers.openai.com/codex/skills), [Claude Code skills](https://code.claude.com/docs/en/skills), [Cursor Agent Skills](https://cursor.com/docs/context/skills), and [WorkBuddy documentation](https://docs.work-buddy.ai/).
