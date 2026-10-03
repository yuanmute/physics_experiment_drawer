# Platform compatibility

This package uses the Agent Skills layout: `SKILL.md` plus `scripts/`, `references/` and optional `agents/openai.yaml`. Install the complete directory under the name `physics-lab-plotter`.

| Client | Conventional directory | Discovery |
| --- | --- | --- |
| Codex | `.agents/skills/physics-lab-plotter/` or `~/.agents/skills/physics-lab-plotter/` | `$physics-lab-plotter`; check your version's documentation for legacy directories |
| Claude Code | `.claude/skills/physics-lab-plotter/` or `~/.claude/skills/physics-lab-plotter/` | `/physics-lab-plotter` or automatic selection |
| Cursor | `.cursor/skills/physics-lab-plotter/` or `~/.cursor/skills/physics-lab-plotter/` | Depends on the installed Agent Skills support |
| WorkBuddy / other clients | The installed version's documented skill directory | Keep the same package; confirm local discovery support |

These are installation conventions, not a claim that every client/version has been tested. `agents/openai.yaml` is optional Codex metadata and can be ignored elsewhere. Do not rename `SKILL.md` or separate the helper from the package. Restart discovery only if your client requires it.

The helper is a local Python 3.10+ program. PDF generation needs XeLaTeX, PGFPlots/TikZ, ctex/Fandol and the packages named in the input schema; another client does not supply these automatically. Run the helper by its installed path from a user workspace and direct outputs there. Check the PDF in the target runtime before claiming compilation or visual success.

The package does not configure any client's cloud processing, retention or telemetry. Consult that client's current settings before supplying sensitive images or documents.

Authoritative references: [Agent Skills specification](https://agentskills.io/specification), [Codex skills](https://developers.openai.com/codex/skills), [Claude Code skills](https://code.claude.com/docs/en/skills), [Cursor skills](https://cursor.com/docs/context/skills), [WorkBuddy documentation](https://docs.work-buddy.ai/).
