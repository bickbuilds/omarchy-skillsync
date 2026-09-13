#!/usr/bin/env python3
"""Scan, search, install, and point harnesses at one shared skills library."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

VERSION = "0.1.0"
USER_AGENT = f"skillkit/{VERSION} (omarchy-plugin)"
SEARCH_URL = "https://skills.sh/api/search"
SKILLS_SH = "https://skills.sh"
LEADERBOARD_URL = "https://skills.sh/"
NPX_INSTALL_TIMEOUT = 180
SEARCH_TIMEOUT = 20
INITIAL_SKILLS_MARK = '"initialSkills":'
INITIAL_SKILLS_ESCAPED = 'initialSkills\\":'

VERIFIED_OWNERS = frozenset(
    {
        "anthropics",
        "vercel-labs",
        "microsoft",
        "google-gemini",
        "supabase",
        "expo",
        "omacom",
        "basecamp",
        "xai-org",
        "github",
        "openai",
    }
)

# id, display name, skills dir, detect path, shares the canonical ~/.agents/skills store
HARNESSES = (
    ("universal", "Universal", "{home}/.agents/skills", "{home}/.agents", True),
    ("claude-code", "Claude Code", "{claude}/skills", "{claude}", False),
    ("codex", "Codex", "{codex}/skills", "{codex}", False),
    ("cursor", "Cursor", "{home}/.cursor/skills", "{home}/.cursor", False),
    ("grok", "Grok Build", "{grok}/skills", "{grok}", False),
    ("hermes-agent", "Hermes", "{hermes}/skills", "{hermes}", False),
    ("opencode", "OpenCode", "{config}/opencode/skills", "{config}/opencode", False),
    ("gemini-cli", "Gemini CLI", "{home}/.gemini/skills", "{home}/.gemini", False),
    ("github-copilot", "GitHub Copilot", "{home}/.copilot/skills", "{home}/.copilot", False),
    ("pi", "Pi", "{home}/.pi/agent/skills", "{home}/.pi/agent", False),
    ("windsurf", "Windsurf", "{home}/.codeium/windsurf/skills", "{home}/.codeium/windsurf", False),
    ("amp", "Amp", "{config}/agents/skills", "{config}/amp", False),
    ("cline", "Cline", "{home}/.agents/skills", "{home}/.cline", True),
    ("goose", "Goose", "{config}/goose/skills", "{config}/goose", False),
    ("crush", "Crush", "{config}/crush/skills", "{config}/crush", False),
    ("roo", "Roo Code", "{home}/.roo/skills", "{home}/.roo", False),
    ("continue", "Continue", "{home}/.continue/skills", "{home}/.continue", False),
    ("zed", "Zed", "{home}/.agents/skills", "{config}/zed", True),
    ("openclaw", "OpenClaw", "{home}/.openclaw/skills", "{home}/.openclaw", False),
    ("kilo", "Kilo Code", "{home}/.kilo/skills", "{home}/.kilo", False),
    ("droid", "Droid", "{home}/.factory/skills", "{home}/.factory", False),
    ("warp", "Warp", "{home}/.agents/skills", "{home}/.warp", True),
    ("kimi-code-cli", "Kimi Code", "{home}/.agents/skills", "{home}/.kimi", True),
    ("antigravity", "Antigravity", "{home}/.gemini/antigravity/skills", "{home}/.gemini/antigravity", False),
    ("mistral-vibe", "Mistral Vibe", "{vibe}/skills", "{vibe}", False),
    ("qwen-code", "Qwen Code", "{home}/.qwen/skills", "{home}/.qwen", False),
    ("trae", "Trae", "{home}/.trae/skills", "{home}/.trae", False),
    ("kiro-cli", "Kiro CLI", "{home}/.kiro/skills", "{home}/.kiro", False),
    ("junie", "Junie", "{home}/.junie/skills", "{home}/.junie", False),
    ("aider-desk", "AiderDesk", "{home}/.aider-desk/skills", "{home}/.aider-desk", False),
)

READ_ONLY_SOURCES = (
    ("omarchy", "Omarchy", "/usr/share/omarchy/default/agents/skills"),
    ("grok-bundled", "Grok bundled", "{grok}/bundled/skills"),
)

SKIP_DIR_NAMES = frozenset({".system", "node_modules", ".git", "__pycache__"})


def emit(payload: dict) -> None:
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


def fail(message: str, **extra) -> int:
    payload = {"ok": False, "error": message}
    payload.update(extra)
    emit(payload)
    return 1


def ok(payload: dict) -> int:
    out = {"ok": True}
    out.update(payload)
    emit(out)
    return 0


def parse_frontmatter(text: str) -> dict:
    if not text.startswith("---"):
        return {}
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    body = []
    for line in lines[1:]:
        if line.strip() == "---":
            break
        body.append(line)
    data = {}
    key = None
    acc: list[str] = []

    def flush() -> None:
        nonlocal key, acc
        if not key:
            return
        value = " ".join(part for part in acc if part).strip()
        value = value.strip('"').strip("'")
        data[key] = value
        key = None
        acc = []

    for line in body:
        if key and (line.startswith("  ") or line.startswith("\t") or line.startswith("    ")):
            acc.append(line.strip().strip('"').strip("'"))
            continue
        if ":" not in line:
            continue
        flush()
        raw_key, raw_val = line.split(":", 1)
        key = raw_key.strip()
        raw_val = raw_val.strip()
        if raw_val in (">", "|", ">-", "|-", ">+", "|+"):
            acc = []
        else:
            acc = [raw_val]
    flush()
    return data


def iter_skill_dirs(root: Path):
    if not root.is_dir():
        return
    if (root / "SKILL.md").is_file():
        yield root
        return
    try:
        children = list(root.iterdir())
    except OSError:
        return
    for child in children:
        if child.name.startswith(".") or child.name in SKIP_DIR_NAMES:
            continue
        try:
            if not child.is_dir():
                continue
        except OSError:
            continue
        if (child / "SKILL.md").is_file():
            yield child
            continue
        try:
            grandchildren = list(child.iterdir())
        except OSError:
            continue
        for grandchild in grandchildren:
            if grandchild.name.startswith(".") or grandchild.name in SKIP_DIR_NAMES:
                continue
            if grandchild.is_dir() and (grandchild / "SKILL.md").is_file():
                yield grandchild


def read_skill(path: Path) -> dict | None:
    skill_md = path / "SKILL.md"
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    meta = parse_frontmatter(text)
    name = str(meta.get("name") or path.name).strip() or path.name
    description = str(meta.get("description") or "").strip()
    kind = "dir"
    try:
        if path.is_symlink():
            kind = "symlink"
            target = str(path.resolve())
        else:
            target = str(path)
    except OSError:
        target = str(path)
    return {
        "name": name,
        "folder": path.name,
        "description": description,
        "path": str(path),
        "realPath": target,
        "kind": kind,
        "license": str(meta.get("license") or ""),
        "metadata": meta,
    }


def owner_of(source: str) -> str:
    source = str(source or "")
    return source.split("/")[0].lower() if source else ""


def is_verified_source(source: str) -> bool:
    return owner_of(source) in VERIFIED_OWNERS


def parse_leaderboard_payload(text: str) -> list[dict]:
    """Pull the ranked `initialSkills` array out of the skills.sh homepage or RSC payload."""
    if not text:
        raise ValueError("Empty skills.sh response")
    blob = None
    idx = text.find(INITIAL_SKILLS_MARK)
    if idx >= 0:
        blob = text[idx + len(INITIAL_SKILLS_MARK) :]
    else:
        idx = text.find(INITIAL_SKILLS_ESCAPED)
        if idx >= 0:
            blob = text[idx + len(INITIAL_SKILLS_ESCAPED) :].replace('\\"', '"')
    if blob is None:
        raise ValueError("Could not find the skills.sh leaderboard")
    data, _ = json.JSONDecoder().raw_decode(blob)
    if not isinstance(data, list) or not data:
        raise ValueError("skills.sh leaderboard was empty")
    return data


def format_installs(n) -> str:
    try:
        n = int(n)
    except (TypeError, ValueError):
        return ""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


class Skillkit:
    def __init__(self, home: str | Path | None = None, env: dict | None = None):
        self.env = dict(os.environ if env is None else env)
        self.home = Path(home or self.env.get("HOME") or str(Path.home())).expanduser()
        self.config = Path(self.env.get("XDG_CONFIG_HOME") or (self.home / ".config"))
        self.claude = Path(self.env.get("CLAUDE_CONFIG_DIR") or (self.home / ".claude"))
        self.codex = Path(self.env.get("CODEX_HOME") or (self.home / ".codex"))
        self.grok = Path(self.env.get("GROK_HOME") or (self.home / ".grok"))
        self.hermes = Path(self.env.get("HERMES_HOME") or (self.home / ".hermes"))
        self.vibe = Path(self.env.get("VIBE_HOME") or (self.home / ".vibe"))
        self.canonical_dir = self.home / ".agents" / "skills"

    def expand(self, template: str) -> Path:
        return Path(
            template.format(
                home=str(self.home),
                config=str(self.config),
                claude=str(self.claude),
                codex=str(self.codex),
                grok=str(self.grok),
                hermes=str(self.hermes),
                vibe=str(self.vibe),
            )
        )

    def points_at_canonical(self, path: Path) -> bool:
        try:
            if not path.exists() and not path.is_symlink():
                return False
            return path.resolve() == self.canonical_dir.resolve()
        except OSError:
            return False

    def unique_folders(self, skills_dir: Path) -> list[str]:
        if self.points_at_canonical(skills_dir):
            return []
        have = {p.name for p in iter_skill_dirs(self.canonical_dir)} if self.canonical_dir.is_dir() else set()
        return [p.name for p in iter_skill_dirs(skills_dir) if p.name not in have]

    def harness_records(self, installed_only: bool = False) -> list[dict]:
        rows = []
        for hid, name, skills_tmpl, detect_tmpl, shared in HARNESSES:
            skills_dir = self.expand(skills_tmpl)
            detect_dir = self.expand(detect_tmpl)
            # Shared-canonical agents reuse ~/.agents/skills, so that directory
            # existing is not evidence the harness itself is installed.
            present = detect_dir.exists() or (not shared and skills_dir.exists())
            if installed_only and not present:
                continue
            wired = shared or self.points_at_canonical(skills_dir)
            unique = [] if wired else self.unique_folders(skills_dir)
            if wired:
                skill_count = sum(1 for _ in iter_skill_dirs(self.canonical_dir)) if self.canonical_dir.is_dir() else 0
            elif skills_dir.is_dir():
                skill_count = sum(1 for _ in iter_skill_dirs(skills_dir))
            else:
                skill_count = 0
            rows.append(
                {
                    "id": hid,
                    "name": name,
                    "dir": str(skills_dir),
                    "detectDir": str(detect_dir),
                    "present": present,
                    "sharedCanonical": shared,
                    "wired": wired,
                    "wireable": present and not shared,
                    "readOnly": False,
                    "skillCount": skill_count,
                    "uniqueCount": len(unique),
                    "uniqueFolders": unique,
                }
            )
        return rows

    def bundled_records(self) -> list[dict]:
        rows = []
        for sid, name, tmpl in READ_ONLY_SOURCES:
            path = self.expand(tmpl)
            if not path.is_dir():
                continue
            rows.append(
                {
                    "id": sid,
                    "name": name,
                    "dir": str(path),
                    "detectDir": str(path),
                    "present": True,
                    "sharedCanonical": False,
                    "wired": False,
                    "wireable": False,
                    "readOnly": True,
                    "skillCount": sum(1 for _ in iter_skill_dirs(path)),
                    "uniqueCount": 0,
                    "uniqueFolders": [],
                }
            )
        return rows

    def installed_harnesses(self) -> list[dict]:
        return self.harness_records(installed_only=True)

    def wireable_harnesses(self) -> list[dict]:
        return [h for h in self.installed_harnesses() if h["wireable"]]

    def _origin_for(self, real_path: str, harness_id: str, read_only: bool) -> str:
        if read_only:
            return "bundled"
        try:
            resolved = str(Path(real_path).resolve())
        except OSError:
            resolved = real_path
        bundled_roots = [str(self.expand(tmpl).resolve()) for _, _, tmpl in READ_ONLY_SOURCES if self.expand(tmpl).exists()]
        for root in bundled_roots:
            if resolved == root or resolved.startswith(root + os.sep):
                return "bundled"
        if harness_id == "universal":
            return "canonical"
        return "harness"

    def scan(self, include_bundled: bool = False) -> dict:
        harnesses = self.installed_harnesses()
        sources = list(harnesses)
        if include_bundled:
            sources.extend(self.bundled_records())

        skills: dict[str, dict] = {}
        for src in sources:
            root = Path(src["dir"])
            for skill_dir in iter_skill_dirs(root):
                rec = read_skill(skill_dir)
                if not rec:
                    continue
                key = rec["folder"]
                entry = skills.get(key)
                if entry is None:
                    entry = {
                        "name": rec["name"],
                        "folder": key,
                        "description": rec["description"],
                        "path": rec["path"],
                        "realPath": rec["realPath"],
                        "kind": rec["kind"],
                        "license": rec["license"],
                        "harnesses": [],
                        "missing": [],
                        "origin": self._origin_for(rec["realPath"], src["id"], src["readOnly"]),
                        "canonical": False,
                        "readOnly": src["readOnly"],
                    }
                    skills[key] = entry
                if src["id"] not in entry["harnesses"]:
                    entry["harnesses"].append(src["id"])
                if src["id"] == "universal":
                    entry["canonical"] = True
                    entry["path"] = rec["path"]
                    entry["realPath"] = rec["realPath"]
                if src["readOnly"]:
                    entry["readOnly"] = True
                    if entry["origin"] != "canonical":
                        entry["origin"] = "bundled"
                if not entry["description"] and rec["description"]:
                    entry["description"] = rec["description"]
                    entry["name"] = rec["name"]

        wired_ids = [h["id"] for h in harnesses if h["wired"]]
        for entry in skills.values():
            present = set(entry["harnesses"])
            if entry["canonical"]:
                present.update(wired_ids)
            entry["harnesses"] = sorted(present)
            entry["missing"] = []
            entry["coverage"] = len(present)
            entry["coverageTotal"] = len(harnesses)

        rows = sorted(skills.values(), key=lambda s: s["name"].lower())
        unwired = [h for h in harnesses if h["wireable"] and not h["wired"]]
        return {
            "canonicalDir": str(self.canonical_dir),
            "harnesses": harnesses,
            "bundled": self.bundled_records() if include_bundled else [],
            "skills": rows,
            "skillCount": len(rows),
            "harnessCount": len(harnesses),
            "wiredCount": len(wired_ids),
            "unwiredCount": len(unwired),
        }

    def find_skill(self, folder: str, include_bundled: bool = True) -> dict | None:
        data = self.scan(include_bundled=include_bundled)
        folder = folder.strip()
        for skill in data["skills"]:
            if skill["folder"] == folder or skill["name"] == folder:
                return skill
        return None

    def _symlink_to_canonical(self, skills_dir: Path) -> None:
        self.canonical_dir.mkdir(parents=True, exist_ok=True)
        skills_dir.parent.mkdir(parents=True, exist_ok=True)
        rel = os.path.relpath(self.canonical_dir, skills_dir.parent)
        skills_dir.symlink_to(rel)

    def wire(self, agent_id: str) -> dict:
        by_id = {h["id"]: h for h in self.harness_records()}
        harness = by_id.get(agent_id)
        if not harness:
            raise FileNotFoundError(f"Unknown harness: {agent_id}")
        if harness["sharedCanonical"]:
            return {
                "agent": agent_id,
                "name": harness["name"],
                "wired": True,
                "already": True,
                "adopted": [],
                "backup": "",
            }
        skills_dir = Path(harness["dir"])
        if self.points_at_canonical(skills_dir):
            return {
                "agent": agent_id,
                "name": harness["name"],
                "wired": True,
                "already": True,
                "adopted": [],
                "backup": "",
            }
        adopted = []
        backup = ""
        if skills_dir.is_symlink():
            skills_dir.unlink()
        elif skills_dir.is_dir():
            self.canonical_dir.mkdir(parents=True, exist_ok=True)
            for skill_dir in list(iter_skill_dirs(skills_dir)):
                dest = self.canonical_dir / skill_dir.name
                if dest.exists() or dest.is_symlink():
                    continue
                shutil.move(str(skill_dir), str(dest))
                adopted.append(skill_dir.name)
            backup_name = skills_dir.name + ".bak-skillkit-" + time.strftime("%Y%m%d-%H%M%S")
            backup_path = skills_dir.with_name(backup_name)
            skills_dir.rename(backup_path)
            backup = str(backup_path)
        self._symlink_to_canonical(skills_dir)
        return {
            "agent": agent_id,
            "name": harness["name"],
            "wired": True,
            "already": False,
            "adopted": adopted,
            "backup": backup,
        }

    def wire_all(self) -> dict:
        results = []
        for harness in self.wireable_harnesses():
            if harness["wired"]:
                continue
            results.append(self.wire(harness["id"]))
        return {"wired": results, "count": len(results)}

    def remove(self, folder: str, agent_ids: list[str] | None = None) -> dict:
        skill = self.find_skill(folder, include_bundled=True)
        if not skill:
            raise FileNotFoundError(f"Skill not found: {folder}")
        if skill["origin"] == "bundled" and not skill["canonical"]:
            raise PermissionError("Bundled skills cannot be removed")
        dest = self.canonical_dir / skill["folder"]
        canonical_removed = False
        if dest.is_symlink():
            dest.unlink()
            canonical_removed = True
        elif dest.is_dir():
            shutil.rmtree(dest)
            canonical_removed = True
        return {
            "folder": skill["folder"],
            "name": skill["name"],
            "canonicalRemoved": canonical_removed,
            "unlinked": [],
            "skipped": [],
            "errors": [],
        }

    def http_get(self, url: str, headers: dict | None = None, timeout: int = SEARCH_TIMEOUT) -> str:
        req_headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
        if headers:
            req_headers.update(headers)
        req = urllib.request.Request(url, headers=req_headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8")

    def http_get_json(self, url: str, timeout: int = SEARCH_TIMEOUT) -> dict:
        return json.loads(self.http_get(url, timeout=timeout))

    def fetch_leaderboard_text(self) -> str:
        return self.http_get(
            LEADERBOARD_URL,
            headers={
                "Accept": "text/x-component, text/html;q=0.9",
                "RSC": "1",
                "Next-Url": "/",
            },
        )

    def normalize_remote(self, raw: dict, installed_folders: set[str] | None = None) -> dict:
        source = str(raw.get("source") or "")
        skill_id = str(raw.get("skillId") or raw.get("slug") or raw.get("name") or "")
        ident = str(raw.get("id") or f"{source}/{skill_id}")
        installs = raw.get("installs") or 0
        try:
            installs_n = int(installs)
        except (TypeError, ValueError):
            installs_n = 0
        official = raw.get("isOfficial") is True
        rank = raw.get("rank")
        try:
            rank_n = int(rank) if rank is not None else 0
        except (TypeError, ValueError):
            rank_n = 0
        return {
            "id": ident,
            "name": str(raw.get("name") or skill_id),
            "skillId": skill_id,
            "source": source,
            "owner": owner_of(source),
            "installs": installs_n,
            "installsLabel": format_installs(installs_n),
            "url": f"{SKILLS_SH}/{ident}" if ident else SKILLS_SH,
            "installSpec": f"{source}@{skill_id}" if source and skill_id else source,
            "verified": official or is_verified_source(source),
            "official": official,
            "rank": rank_n,
            "installed": skill_id in (installed_folders or set()),
        }

    def search(self, query: str, limit: int = 25, owner: str | None = None) -> dict:
        query = (query or "").strip()
        if len(query) < 2:
            raise ValueError("Search query must be at least 2 characters")
        params = {"q": query, "limit": str(max(1, min(limit, 100)))}
        if owner:
            params["owner"] = owner
        url = SEARCH_URL + "?" + urllib.parse.urlencode(params)
        payload = self.http_get_json(url)
        installed = {s["folder"] for s in self.scan(include_bundled=False)["skills"]}
        raw_skills = payload.get("skills") or payload.get("data") or []
        skills = [self.normalize_remote(item, installed) for item in raw_skills]
        return {
            "query": query,
            "owner": owner or "",
            "searchType": payload.get("searchType") or "fuzzy",
            "count": len(skills),
            "skills": skills,
            "source": "skills.sh",
        }

    def discover(self, limit: int = 50, verified_only: bool = False) -> dict:
        installed = {s["folder"] for s in self.scan(include_bundled=False)["skills"]}
        ranked = parse_leaderboard_payload(self.fetch_leaderboard_text())
        skills = []
        for index, raw in enumerate(ranked, 1):
            item = dict(raw)
            item["rank"] = index
            row = self.normalize_remote(item, installed)
            if verified_only and not row["verified"]:
                continue
            skills.append(row)
            if len(skills) >= max(1, min(limit, 200)):
                break
        return {
            "query": "",
            "count": len(skills),
            "skills": skills,
            "source": "skills.sh",
            "view": "leaderboard",
            "verifiedOnly": verified_only,
            "errors": [],
        }

    def npx_cmd(self) -> list[str]:
        npx = self.env.get("SKILLKIT_NPX") or shutil.which("npx") or "npx"
        return [npx, "--yes", "skills"]

    def install(self, spec: str, skill: str | None = None, agents: list[str] | None = None) -> dict:
        spec = spec.strip()
        if not spec:
            raise ValueError("Install source is required")
        source = spec
        skill_name = skill
        if "@" in spec and not spec.startswith("http") and skill is None:
            source, skill_name = spec.split("@", 1)
        self.canonical_dir.mkdir(parents=True, exist_ok=True)
        cmd = self.npx_cmd() + ["add", source, "-y", "--json", "--skills-dir", str(self.canonical_dir)]
        if skill_name:
            cmd.extend(["--skill", skill_name])
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=NPX_INSTALL_TIMEOUT,
            env=self.env,
        )
        stdout = (proc.stdout or "").strip()
        stderr = (proc.stderr or "").strip()
        if proc.returncode != 0:
            raise RuntimeError(stderr or stdout or f"skills add failed ({proc.returncode})")
        parsed = None
        if stdout:
            try:
                parsed = json.loads(stdout)
            except json.JSONDecodeError:
                parsed = None
        return {
            "source": source,
            "skill": skill_name or "",
            "agents": agents or [],
            "output": parsed if parsed is not None else stdout,
            "stderr": stderr,
        }


def parse_agents(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [part.strip() for part in raw.replace(" ", ",").split(",") if part.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="skillkit", description="Manage a shared agent skills library")
    parser.add_argument("--home", default=None, help="Override home directory (tests)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    scan = sub.add_parser("scan", help="List installed skills and harness coverage")
    scan.add_argument("--bundled", action="store_true", help="Include read-only bundled skills")

    search = sub.add_parser("search", help="Search skills.sh")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=25)
    search.add_argument("--owner", default=None)

    discover = sub.add_parser("discover", help="Top-ranked skills from the skills.sh leaderboard")
    discover.add_argument("--limit", type=int, default=50)
    discover.add_argument("--verified", action="store_true", help="Only skills marked official / verified")
    discover.add_argument("--all", action="store_true", help="Deprecated: leaderboard already includes all ranks")

    install = sub.add_parser("install", help="Install a skill with the skills CLI")
    install.add_argument("spec", help="owner/repo or owner/repo@skill")
    install.add_argument("--skill", default=None)
    install.add_argument("--agents", default=None, help="Comma-separated harness ids")

    remove = sub.add_parser("remove", help="Remove a skill from the shared library")
    remove.add_argument("folder")
    remove.add_argument("--agents", default=None)

    wire = sub.add_parser("wire", help="Point a harness skills dir at the shared library")
    wire.add_argument("agent")

    sub.add_parser("wire-all", help="Point every installed harness at the shared library")
    sub.add_parser("harnesses", help="List detected harnesses")

    args = parser.parse_args(argv)
    kit = Skillkit(home=args.home)
    try:
        if args.cmd == "scan":
            return ok(kit.scan(include_bundled=args.bundled))
        if args.cmd == "harnesses":
            return ok({"harnesses": kit.installed_harnesses(), "bundled": kit.bundled_records()})
        if args.cmd == "search":
            return ok(kit.search(args.query, limit=args.limit, owner=args.owner))
        if args.cmd == "discover":
            return ok(kit.discover(limit=args.limit, verified_only=args.verified))
        if args.cmd == "install":
            return ok(kit.install(args.spec, skill=args.skill, agents=parse_agents(args.agents)))
        if args.cmd == "remove":
            return ok(kit.remove(args.folder, parse_agents(args.agents) or None))
        if args.cmd == "wire":
            return ok(kit.wire(args.agent))
        if args.cmd == "wire-all":
            return ok(kit.wire_all())
        return fail(f"Unknown command: {args.cmd}")
    except urllib.error.HTTPError as exc:
        return fail(f"skills.sh HTTP {exc.code}", code=exc.code)
    except urllib.error.URLError as exc:
        return fail(f"Network error: {exc.reason}")
    except subprocess.TimeoutExpired:
        return fail("Timed out waiting for the skills CLI")
    except (FileNotFoundError, PermissionError, ValueError, RuntimeError) as exc:
        return fail(str(exc))


if __name__ == "__main__":
    sys.exit(main())
