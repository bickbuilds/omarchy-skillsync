const test = require("node:test")
const assert = require("node:assert/strict")
const fs = require("node:fs")
const path = require("node:path")
const vm = require("node:vm")

const source = fs.readFileSync(path.join(__dirname, "..", "Model.js"), "utf8")
  .replace(/^\.pragma library\n/, "")
const context = { console }
vm.createContext(context)
vm.runInContext(source, context)

test("filterSkills hides bundled by default and matches query", () => {
  const skills = [
    { name: "Omarchy", folder: "omarchy", description: "desktop", origin: "canonical", canonical: true, harnesses: ["universal"] },
    { name: "Imagine", folder: "imagine", description: "images", origin: "bundled", canonical: false, harnesses: ["grok"] },
    { name: "Frontend design", folder: "frontend-design", description: "UI", origin: "canonical", canonical: true },
  ]
  const local = context.filterSkills(skills, "", "local")
  assert.equal(local.length, 2)
  const orphans = context.filterSkills(skills, "", "orphans")
  assert.equal(orphans.length, 0)
  const q = context.filterSkills(skills, "ui", "local")
  assert.equal(q.length, 1)
})

test("orphans are skills not in the shared library", () => {
  const skills = [
    { name: "A", folder: "a", origin: "canonical", canonical: true },
    { name: "B", folder: "b", origin: "harness", canonical: false, harnesses: ["codex"] },
  ]
  const orphans = context.filterSkills(skills, "", "orphans")
  assert.equal(orphans.map((s) => s.folder).join(","), "b")
  assert.equal(context.originLabel(orphans[0]), "Only on codex")
})

test("summary and installs formatting", () => {
  assert.equal(context.formatInstalls(185000), "185.0K")
  assert.equal(
    context.summaryLine({ skillCount: 12, wiredCount: 3, unwiredCount: 2 }),
    "12 skills · 3 harnesses on the shared folder · 2 not wired"
  )
})

test("parsePayload reads helper JSON", () => {
  const ok = context.parsePayload('{"ok":true,"skillCount":3}')
  assert.equal(ok.ok, true)
  assert.equal(ok.skillCount, 3)
  const bad = context.parsePayload("not-json")
  assert.equal(bad.ok, false)
})
