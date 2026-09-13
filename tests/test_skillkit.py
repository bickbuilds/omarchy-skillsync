#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import skillkit  # noqa: E402


SKILL_MD = """---
name: {name}
description: >
  {description}
license: MIT
---

Body for {name}.
"""


def write_skill(path: Path, name: str, description: str = "A test skill") -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "SKILL.md").write_text(SKILL_MD.format(name=name, description=description), encoding="utf-8")


class FrontmatterTests(unittest.TestCase):
    def test_folded_description(self):
        meta = skillkit.parse_frontmatter(SKILL_MD.format(name="demo", description="Does the thing"))
        self.assertEqual(meta["name"], "demo")
        self.assertIn("Does the thing", meta["description"])
        self.assertEqual(meta["license"], "MIT")

    def test_plain_description(self):
        text = "---\nname: x\ndescription: Hello world\n---\n\nHi\n"
        meta = skillkit.parse_frontmatter(text)
        self.assertEqual(meta["name"], "x")
        self.assertEqual(meta["description"], "Hello world")


class ScanSyncTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        (self.home / ".agents").mkdir()
        (self.home / ".claude").mkdir()
        (self.home / ".codex").mkdir()
        (self.home / ".cursor").mkdir()
        (self.home / ".grok").mkdir()
        write_skill(self.home / ".agents" / "skills" / "shared", "shared", "Shared everywhere")
        write_skill(self.home / ".codex" / "skills" / "codex-only", "codex-only", "Codex exclusive")
        # Claude already has a symlink to the canonical skill.
        claude_skills = self.home / ".claude" / "skills"
        claude_skills.mkdir()
        os.symlink(
            os.path.relpath(self.home / ".agents" / "skills" / "shared", claude_skills),
            claude_skills / "shared",
        )
        self.kit = skillkit.Skillkit(home=self.home, env={"HOME": str(self.home)})

    def tearDown(self):
        self.tmp.cleanup()

    def test_scan_coverage(self):
        data = self.kit.scan()
        names = {s["folder"] for s in data["skills"]}
        self.assertIn("shared", names)
        self.assertIn("codex-only", names)
        harness_ids = {h["id"] for h in data["harnesses"]}
        self.assertIn("claude-code", harness_ids)
        self.assertIn("codex", harness_ids)
        self.assertIn("cursor", harness_ids)
        self.assertIn("grok", harness_ids)
        self.assertNotIn("cline", harness_ids)
        self.assertNotIn("zed", harness_ids)
        self.assertNotIn("warp", harness_ids)

        shared = next(s for s in data["skills"] if s["folder"] == "shared")
        self.assertTrue(shared["canonical"])
        self.assertIn("universal", shared["harnesses"])

        exclusive = next(s for s in data["skills"] if s["folder"] == "codex-only")
        self.assertIn("codex", exclusive["harnesses"])
        self.assertFalse(exclusive["canonical"])

        by_id = {h["id"]: h for h in data["harnesses"]}
        self.assertTrue(by_id["universal"]["wired"])
        self.assertFalse(by_id["codex"]["wired"])
        self.assertEqual(by_id["codex"]["uniqueCount"], 1)
        self.assertFalse(by_id["cursor"]["wired"])

    def test_wire_adopts_unique_skills_and_replaces_dir(self):
        result = self.kit.wire("codex")
        self.assertTrue(result["wired"])
        self.assertIn("codex-only", result["adopted"])
        self.assertTrue((self.home / ".codex" / "skills").is_symlink())
        self.assertEqual(
            (self.home / ".codex" / "skills").resolve(),
            (self.home / ".agents" / "skills").resolve(),
        )
        self.assertTrue((self.home / ".agents" / "skills" / "codex-only" / "SKILL.md").is_file())
        again = self.kit.scan()
        by_id = {h["id"]: h for h in again["harnesses"]}
        self.assertTrue(by_id["codex"]["wired"])
        self.assertEqual(by_id["codex"]["uniqueCount"], 0)
        exclusive = next(s for s in again["skills"] if s["folder"] == "codex-only")
        self.assertTrue(exclusive["canonical"])

    def test_wire_empty_dir_is_just_a_symlink(self):
        result = self.kit.wire("cursor")
        self.assertTrue(result["wired"])
        self.assertEqual(result["adopted"], [])
        self.assertTrue((self.home / ".cursor" / "skills").is_symlink())

    def test_wire_all_skips_already_wired(self):
        self.kit.wire("cursor")
        result = self.kit.wire_all()
        ids = [row["agent"] for row in result["wired"]]
        self.assertNotIn("cursor", ids)
        self.assertIn("codex", ids)
        self.assertIn("grok", ids)

    def test_remove_from_shared_library(self):
        removed = self.kit.remove("shared")
        self.assertTrue(removed["canonicalRemoved"])
        self.assertFalse((self.home / ".agents" / "skills" / "shared").exists())

    def test_cli_scan_json(self):
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "skillkit.py"), "--home", str(self.home), "scan"],
            capture_output=True,
            text=True,
            check=True,
        )
        payload = json.loads(proc.stdout)
        self.assertTrue(payload["ok"])
        self.assertGreaterEqual(payload["skillCount"], 2)


class RemoteNormalizeTests(unittest.TestCase):
    def test_verified_publisher(self):
        kit = skillkit.Skillkit(home=tempfile.gettempdir())
        item = kit.normalize_remote(
            {
                "id": "anthropics/skills/frontend-design",
                "skillId": "frontend-design",
                "name": "frontend-design",
                "installs": 882914,
                "source": "anthropics/skills",
            },
            installed_folders={"frontend-design"},
        )
        self.assertTrue(item["verified"])
        self.assertTrue(item["installed"])
        self.assertEqual(item["installsLabel"], "882.9K")
        self.assertEqual(item["installSpec"], "anthropics/skills@frontend-design")

    def test_unverified_publisher(self):
        kit = skillkit.Skillkit(home=tempfile.gettempdir())
        item = kit.normalize_remote(
            {
                "id": "random/repo/cool-skill",
                "skillId": "cool-skill",
                "name": "cool-skill",
                "installs": 12,
                "source": "random/repo",
            }
        )
        self.assertFalse(item["verified"])
        self.assertEqual(item["installsLabel"], "12")

    def test_official_flag_counts_as_verified(self):
        kit = skillkit.Skillkit(home=tempfile.gettempdir())
        item = kit.normalize_remote(
            {
                "skillId": "find-skills",
                "name": "find-skills",
                "installs": 3382616,
                "source": "vercel-labs/skills",
                "isOfficial": True,
                "rank": 1,
            }
        )
        self.assertTrue(item["verified"])
        self.assertTrue(item["official"])
        self.assertEqual(item["rank"], 1)
        self.assertEqual(item["installsLabel"], "3.4M")


class LeaderboardParseTests(unittest.TestCase):
    def test_rsc_payload(self):
        payload = (
            '4b:["$",null,{"initialSkills":['
            '{"source":"vercel-labs/skills","skillId":"find-skills","name":"find-skills",'
            '"installs":3382616,"isOfficial":true},'
            '{"source":"mattpocock/skills","skillId":"grill-me","name":"grill-me","installs":1131380}'
            "]}]"
        )
        rows = skillkit.parse_leaderboard_payload(payload)
        self.assertEqual(rows[0]["skillId"], "find-skills")
        self.assertEqual(rows[1]["name"], "grill-me")
        self.assertEqual(len(rows), 2)

    def test_escaped_html_payload(self):
        payload = (
            r'initialSkills\":[{\"source\":\"anthropics/skills\",\"skillId\":\"frontend-design\",'
            r'\"name\":\"frontend-design\",\"installs\":882984,\"isOfficial\":true}]'
        )
        rows = skillkit.parse_leaderboard_payload(payload)
        self.assertEqual(rows[0]["skillId"], "frontend-design")
        self.assertTrue(rows[0]["isOfficial"])

    def test_discover_uses_leaderboard_order(self):
        kit = skillkit.Skillkit(home=tempfile.gettempdir())
        kit.fetch_leaderboard_text = lambda: (
            '{"initialSkills":['
            '{"source":"vercel-labs/skills","skillId":"find-skills","name":"find-skills","installs":10,"isOfficial":true},'
            '{"source":"mattpocock/skills","skillId":"grill-me","name":"grill-me","installs":9}'
            "]}"
        )
        result = kit.discover(limit=10)
        self.assertEqual([s["skillId"] for s in result["skills"]], ["find-skills", "grill-me"])
        self.assertEqual(result["skills"][0]["rank"], 1)
        self.assertEqual(result["skills"][1]["rank"], 2)
        self.assertEqual(result["view"], "leaderboard")


class FormatTests(unittest.TestCase):
    def test_installs(self):
        self.assertEqual(skillkit.format_installs(1_250_000), "1.2M")
        self.assertEqual(skillkit.format_installs(1500), "1.5K")
        self.assertEqual(skillkit.format_installs(9), "9")


if __name__ == "__main__":
    unittest.main()
