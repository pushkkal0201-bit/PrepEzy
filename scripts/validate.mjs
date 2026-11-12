#!/usr/bin/env node
// Structural checks for the cracked skill pack. Zero dependencies.
// Run: node scripts/validate.mjs
import { readFileSync, readdirSync, existsSync, statSync } from "node:fs";
import { join, dirname, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const errors = [];
const warnings = [];
const err = (m) => errors.push(m);
const warn = (m) => warnings.push(m);

// Skills that exist to be called by other skills; they don't need a README row.
const INTERNAL = new Set(["cracked-profile"]);
const NAME_RE = /^[a-z0-9]+(-[a-z0-9]+)*$/;

function parseFrontmatter(text, file) {
  const m = text.match(/^---\n([\s\S]*?)\n---\n/);
  if (!m) {
    err(`${file}: missing YAML frontmatter`);
    return {};
  }
  const out = {};
  for (const line of m[1].split("\n")) {
    const kv = line.match(/^([a-zA-Z-]+):\s*(.*)$/);
    if (kv) out[kv[1]] = kv[2].replace(/^["']|["']$/g, "");
  }
  return out;
}

// 1. Discover skills: skills/<category>/<name>/SKILL.md
const skillsDir = join(root, "skills");
const skills = [];
for (const cat of readdirSync(skillsDir)) {
  const catDir = join(skillsDir, cat);
  if (!statSync(catDir).isDirectory()) continue;
  for (const name of readdirSync(catDir)) {
    const dir = join(catDir, name);
    if (!statSync(dir).isDirectory()) continue;
    skills.push({ cat, name, dir, rel: `./${relative(root, dir)}` });
  }
}

const names = new Set(skills.map((s) => s.name));
const userInvokedNames = new Set(
  skills
    .filter((s) => existsSync(join(s.dir, "SKILL.md")) && /^disable-model-invocation:\s*true\s*$/m.test(readFileSync(join(s.dir, "SKILL.md"), "utf8")))
    .map((s) => s.name),
);

for (const s of skills) {
  const skillFile = join(s.dir, "SKILL.md");
  const relFile = relative(root, skillFile);
  if (!existsSync(skillFile)) {
    err(`${s.rel}: missing SKILL.md`);
    continue;
  }
  const text = readFileSync(skillFile, "utf8");
  const fm = parseFrontmatter(text, relFile);

  // Frontmatter
  if (fm.name !== s.name) err(`${relFile}: frontmatter name "${fm.name}" must equal folder name "${s.name}"`);
  if (!NAME_RE.test(s.name)) err(`${relFile}: name must be lowercase-kebab-case`);
  if (!fm.description) err(`${relFile}: missing description`);
  else {
    if (fm.description.length > 1024) err(`${relFile}: description is ${fm.description.length} chars (max 1024)`);
    if (fm.description.length < 80) warn(`${relFile}: description is short; add trigger phrases`);
    const userInvoked = fm["disable-model-invocation"] === "true";
    if (!userInvoked && !/Use when/i.test(fm.description)) warn(`${relFile}: description has no "Use when…" trigger phrasing`);
  }

  // Body size: keep skills lean so they load fast
  const lines = text.split("\n").length;
  if (lines > 500) err(`${relFile}: ${lines} lines (max 500); move reference material into sibling files`);

  // Codex metadata
  const yaml = join(s.dir, "agents", "openai.yaml");
  if (!existsSync(yaml)) err(`${s.rel}: missing agents/openai.yaml`);
  else {
    const y = readFileSync(yaml, "utf8");
    if (!/display_name:\s*".+"/.test(y)) err(`${relative(root, yaml)}: missing interface.display_name`);
    if (!/short_description:\s*".+"/.test(y)) err(`${relative(root, yaml)}: missing interface.short_description`);
    // Invocation must agree across harnesses (Claude Code frontmatter vs Codex policy)
    const codexUserOnly = /allow_implicit_invocation:\s*false/.test(y);
    if (codexUserOnly !== (fm["disable-model-invocation"] === "true")) {
      err(`${s.rel}: disable-model-invocation and agents/openai.yaml policy.allow_implicit_invocation disagree`);
    }
  }

  // Relative links resolve
  for (const md of readdirSync(s.dir).filter((f) => f.endsWith(".md"))) {
    // Ignore links inside fenced code blocks (templates use placeholder links).
    const body = readFileSync(join(s.dir, md), "utf8").replace(/^(`{3,}|~{3,})[\s\S]*?^\1/gm, "");
    for (const [, target] of body.matchAll(/\]\(([^)#\s]+)(#[^)]*)?\)/g)) {
      if (/^[a-z]+:/i.test(target)) continue; // URLs
      if (!existsSync(join(s.dir, target))) err(`${relative(root, join(s.dir, md))}: broken link -> ${target}`);
    }
  }

  // Skill-to-skill calls reference real, model-invoked skills
  for (const [, called] of text.matchAll(/Call the Skill tool with "([^"]+)"/g)) {
    if (!names.has(called)) err(`${relFile}: calls unknown skill "${called}"`);
    else if (userInvokedNames.has(called)) err(`${relFile}: calls user-invoked skill "${called}" (only humans can invoke it)`);
  }

  // Skills that use the data dir must load the profile (which defines it)
  if (s.name !== "cracked-profile" && text.includes("$CRACKED_DIR") && !text.includes('Call the Skill tool with "cracked-profile"')) {
    err(`${relFile}: uses $CRACKED_DIR without calling cracked-profile`);
  }
}

// 2. plugin.json lists exactly the discovered skills
const plugin = JSON.parse(readFileSync(join(root, ".claude-plugin", "plugin.json"), "utf8"));
const listed = new Set(plugin.skills ?? []);
for (const s of skills) if (!listed.has(s.rel)) err(`plugin.json: skill ${s.rel} is not listed`);
for (const p of listed) if (!skills.some((s) => s.rel === p)) err(`plugin.json: lists ${p}, which does not exist`);

// 3. marketplace.json is consistent
const market = JSON.parse(readFileSync(join(root, ".claude-plugin", "marketplace.json"), "utf8"));
if (!market.plugins?.some((p) => p.name === plugin.name)) err(`marketplace.json: no plugin entry named "${plugin.name}"`);

// 4. The preserved upstream README documents every user-facing Cracked skill.
// PrepEzy owns the root README as the unified application entry point.
const readmePath = join(root, "UPSTREAM_CRACKED_README.md");
if (!existsSync(readmePath)) err("UPSTREAM_CRACKED_README.md is missing");
else {
  const readme = readFileSync(readmePath, "utf8");
  for (const s of skills) {
    if (INTERNAL.has(s.name)) continue;
    if (!readme.includes(`/${s.name}`)) err(`UPSTREAM_CRACKED_README.md: does not mention /${s.name}`);
  }
}

// 5. CHANGELOG mentions the current version
const changelog = join(root, "CHANGELOG.md");
if (existsSync(changelog) && !readFileSync(changelog, "utf8").includes(plugin.version)) {
  err(`CHANGELOG.md: no entry for version ${plugin.version}`);
}

const userFacing = skills.filter((s) => !INTERNAL.has(s.name)).length;
for (const w of warnings) console.log(`warn  ${w}`);
for (const e of errors) console.log(`error ${e}`);
console.log(`\n${skills.length} skills (${userFacing} user-facing) · ${errors.length} errors · ${warnings.length} warnings`);
process.exit(errors.length ? 1 : 0);
