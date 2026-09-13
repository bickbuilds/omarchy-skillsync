.pragma library

function lower(value) {
  return String(value || "").toLowerCase()
}

function includesQuery(haystack, query) {
  if (!query) return true
  return lower(haystack).indexOf(query) !== -1
}

function skillMatches(skill, query, originFilter) {
  if (originFilter === "bundled" && skill.origin !== "bundled") return false
  if (originFilter === "local" && skill.origin === "bundled") return false
  if (originFilter === "orphans" && skill.canonical) return false
  if (originFilter === "orphans" && skill.origin === "bundled") return false
  if (!query) return true
  return includesQuery(skill.name, query)
    || includesQuery(skill.folder, query)
    || includesQuery(skill.description, query)
    || includesQuery((skill.harnesses || []).join(" "), query)
}

function filterSkills(skills, query, originFilter) {
  var list = skills || []
  var q = lower(query).trim()
  var out = []
  for (var i = 0; i < list.length; i++) {
    if (skillMatches(list[i], q, originFilter || "local")) out.push(list[i])
  }
  return out
}

function filterRemote(skills, query, verifiedOnly) {
  var list = skills || []
  var q = lower(query).trim()
  var out = []
  for (var i = 0; i < list.length; i++) {
    var item = list[i]
    if (verifiedOnly && !item.verified) continue
    if (q && !(includesQuery(item.name, q) || includesQuery(item.source, q) || includesQuery(item.skillId, q)))
      continue
    out.push(item)
  }
  return out
}

function formatInstalls(n) {
  var value = Number(n || 0)
  if (!isFinite(value)) return ""
  if (value >= 1000000) return (value / 1000000).toFixed(1) + "M"
  if (value >= 1000) return (value / 1000).toFixed(1) + "K"
  return String(Math.round(value))
}

function originLabel(skill) {
  if (skill && skill.canonical) return "Shared library"
  if (skill && skill.origin === "bundled") return "Bundled"
  var have = (skill && skill.harnesses) ? skill.harnesses : []
  if (have.length === 1) return "Only on " + have[0]
  if (have.length > 1) return "Only on " + have.join(", ")
  return "Local"
}

function harnessName(harnesses, id) {
  var list = harnesses || []
  for (var i = 0; i < list.length; i++) {
    if (list[i].id === id) return list[i].name || id
  }
  return id
}

function parsePayload(text) {
  var raw = String(text || "").trim()
  if (!raw) return { ok: false, error: "Empty response" }
  try {
    return JSON.parse(raw)
  } catch (e) {
    return { ok: false, error: "Could not parse helper output" }
  }
}

function summaryLine(scan) {
  if (!scan) return "Scanning skills…"
  var skills = Number(scan.skillCount || 0)
  var unwired = Number(scan.unwiredCount || 0)
  var wired = Number(scan.wiredCount || 0)
  var parts = [skills + " skill" + (skills === 1 ? "" : "s")]
  if (wired > 0) parts.push(wired + " harness" + (wired === 1 ? "" : "es") + " on the shared folder")
  if (unwired > 0) parts.push(unwired + " not wired")
  return parts.join(" · ")
}

function initialFor(name) {
  var text = String(name || "?").trim()
  return text ? text.charAt(0).toUpperCase() : "?"
}
