#!/usr/bin/env node
// sync-skills.js — Builds ~/.claude/skills/.skills-index.txt at Hermes startup.
// Zero dependencies. Each line: skill_name:keyword1 keyword2 ...
// Usage: node scripts/sync-skills.js

'use strict';
const fs   = require('fs');
const path = require('path');
const os   = require('os');

// --- Load optional config for extra skills_dirs ---
const CONFIG_FILE = path.join(__dirname, '..', '.telegram-config');
let extraSkillsDirs = [];
try {
  const cfg = JSON.parse(fs.readFileSync(CONFIG_FILE, 'utf-8'));
  if (Array.isArray(cfg.skills_dirs)) {
    extraSkillsDirs = cfg.skills_dirs.map(d => d.replace(/^~/, os.homedir()));
  }
} catch { /* no config or parse error — silent, defaults apply */ }

const DEFAULT_SKILLS_DIR = path.join(os.homedir(), '.claude', 'skills');
const ALL_SKILLS_DIRS    = [...new Set([DEFAULT_SKILLS_DIR, ...extraSkillsDirs])];
const INDEX_FILE         = path.join(DEFAULT_SKILLS_DIR, '.skills-index.txt');

const STOP_WORDS = new Set([
  'when','user','the','and','for','this','with','that','from','are','via',
  'into','has','not','all','any','only','also','or','to','of','in','a','an',
  'is','it','at','on','up','by','as','be','do','if','no','so','us','we',
  'my','me','run','use','new','get','set','add','see','can','will','your',
  'their','them','they','you','its','our','was','been','have','had','note',
  'each','both','more','very','much','such','than','then','these','those',
  'would','could','should','must','need','want','make','take','give','let',
  'trigger','mentions','triggers','true','false','null','value','type',
  'command','commands','option','options','parameter','parameters',
  'example','examples','file','files','path','paths',
]);

function extractKeywords(content, skillName) {
  const kw = new Set();

  // Skill name and its parts
  kw.add(skillName.toLowerCase());
  skillName.split(/[-_]/).forEach(p => p.length > 2 && kw.add(p.toLowerCase()));

  // --- Parse YAML frontmatter ---
  const fmMatch = content.match(/^---\r?\n([\s\S]*?)\r?\n---/);
  if (fmMatch) {
    const fm = fmMatch[1];

    // description block (possibly multi-line with > or quotes)
    const descMatch = fm.match(/description:\s*[>|]?\s*["']?([\s\S]*?)(?:\ntags:|\n\w+:|$)/);
    if (descMatch) {
      const desc = descMatch[1];

      // Backtick-quoted identifiers: `Update-MobaPassword` → update-mobapassword
      (desc.match(/`([^`\n]+)`/g) || []).forEach(m => {
        kw.add(m.replace(/`/g, '').toLowerCase());
      });

      // Slash-separated trigger words: "lpoa01 / dataops / clone / ..."
      desc.split(/[\s\/,;\|]+/).forEach(tok => {
        const clean = tok.replace(/^["'>]+|["'>]+$/g, '').toLowerCase().replace(/[^a-z0-9_.\-]/g, '');
        if (clean.length > 2 && !STOP_WORDS.has(clean)) kw.add(clean);
      });
    }

    // tags: [netapp, hci, solidfire]
    const tagsMatch = fm.match(/tags:\s*\[([^\]]+)\]/);
    if (tagsMatch) {
      tagsMatch[1].split(',').forEach(t => {
        const clean = t.trim().replace(/['"]/g, '').toLowerCase();
        if (clean.length > 1) kw.add(clean);
      });
    }
  }

  // --- Body: extract ## headings and code-block hostnames/identifiers ---
  const bodyLines = content.split('\n');
  let inFm = false, fmDone = false, fmCount = 0;
  for (const line of bodyLines) {
    if (line.trim() === '---') { fmCount++; if (fmCount >= 2) fmDone = true; continue; }
    if (!fmDone) continue;

    // ## Section headings
    const headingMatch = line.match(/^#{1,3}\s+(.+)/);
    if (headingMatch) {
      headingMatch[1].split(/\s+/).forEach(w => {
        const clean = w.toLowerCase().replace(/[^a-z0-9_.\-]/g, '');
        if (clean.length > 3 && !STOP_WORDS.has(clean)) kw.add(clean);
      });
    }

    // Hostnames, IPs, identifiers in code blocks / table cells
    const identifiers = line.match(/`([^`]+)`/g) || [];
    identifiers.forEach(m => {
      const id = m.replace(/`/g, '').toLowerCase();
      if (id.length > 2 && !STOP_WORDS.has(id)) kw.add(id);
    });

    // Explicit host/IP patterns
    (line.match(/\b[\w-]+\.(cognyte\.local|local|com|net|io)\b/gi) || []).forEach(h => kw.add(h.toLowerCase()));
    (line.match(/\b10\.\d+\.\d+\.\d+\b/g) || []).forEach(ip => kw.add(ip));
  }

  return [...kw].filter(k => k.length > 2 && !STOP_WORDS.has(k)).sort();
}

// --- Main ---

// Ensure default skills dir exists
if (!fs.existsSync(DEFAULT_SKILLS_DIR)) {
  console.error(`✗ Default skills dir not found: ${DEFAULT_SKILLS_DIR}`);
  process.exit(1);
}

// Collect all skill entries across all dirs (name → first-seen wins, no duplicates)
const seen  = new Set();
const lines = [];

for (const skillsDir of ALL_SKILLS_DIRS) {
  if (!fs.existsSync(skillsDir)) {
    console.warn(`  ! Skipping missing dir: ${skillsDir}`);
    continue;
  }

  const entries = fs.readdirSync(skillsDir).filter(f => {
    try { return fs.statSync(path.join(skillsDir, f)).isDirectory(); } catch { return false; }
  });

  for (const name of entries.sort()) {
    if (seen.has(name)) continue;          // first-seen wins (default dir takes priority)
    const mdPath = path.join(skillsDir, name, 'SKILL.md');
    if (!fs.existsSync(mdPath)) continue;
    try {
      const content  = fs.readFileSync(mdPath, 'utf-8');
      const keywords = extractKeywords(content, name);
      lines.push(`${name}:${keywords.join(' ')}`);
      seen.add(name);
    } catch (e) {
      console.warn(`  ! Skipped ${name}: ${e.message}`);
    }
  }
}

fs.writeFileSync(INDEX_FILE, lines.join('\n') + '\n', 'utf-8');
const extra = ALL_SKILLS_DIRS.length > 1 ? ` (${ALL_SKILLS_DIRS.length} dirs)` : '';
console.log(`✓ Skills index: ${lines.length} skills → ${INDEX_FILE}${extra}`);
