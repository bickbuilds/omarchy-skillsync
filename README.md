# SkillSync

<p align="center"><img src="assets/skillsync.svg" width="72" alt="SkillSync"></p>

An [Omarchy](https://omarchy.org) bar plugin for AI agent skills.

One shared library at `~/.agents/skills`, a [skills.sh](https://skills.sh) browser, and one-click wiring so Claude Code, Codex, Grok, Cursor, Hermes, and the rest all read the same folder.

Plugins run unsandboxed inside `omarchy-shell`. Read the repo before you enable it.

## Install

```bash
omarchy plugin add https://github.com/tw3akercc/omarchy-skillsync.git --enable
```

Omarchy will clone it to `~/.config/omarchy/plugins/jbicks.skills/`, warn that it is unsandboxed code, and offer to put it on the bar (default: right).

Move it later:

```bash
omarchy bar move jbicks.skills --section right
```

## What it does

- **Library** — skills in `~/.agents/skills`. Installs land here. Removing a skill removes it for every wired harness.
- **Discover** — the skills.sh leaderboard, plus search. Official skills get a verified badge.
- **Harnesses** — each coding agent on the machine. **Use shared library** moves that harness's unique skills into the shared folder and replaces its skills directory with a symlink.

Most harnesses cannot be configured to read `~/.agents/skills` themselves. Wiring is a directory-level symlink, not a per-skill copy.

Remote installs use `npx skills add … --skills-dir ~/.agents/skills`.

## Use

Click the SkillSync mark on the bar.

| Key | Action |
| --- | --- |
| `/` | Focus search |
| `1` `2` `3` | Library / Discover / Harnesses |
| `r` | Refresh |
| `Esc` | Close |

```bash
omarchy-shell jbicks.skills toggle
omarchy-shell jbicks.skills refresh
```

## Requirements

- Omarchy 4.x / Quickshell
- `python3`
- `npx` (to install from skills.sh)
- Network access to `https://skills.sh`

## Remove

```bash
omarchy plugin remove jbicks.skills
```

## Marketplace

After the repo is public, list it at [plugins.omarchy.org/publish.html](https://plugins.omarchy.org/publish.html).

## Tests

```bash
tests/run.sh
```

## License

MIT
