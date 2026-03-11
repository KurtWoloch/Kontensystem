#!/usr/bin/env node
/**
 * Cross-reference March 4 planner log against documentation coverage.
 * Generates data/daily_doc_coverage_2026-03-04.txt
 */

const fs = require('fs');
const path = require('path');

const BASE = path.join('C:', 'Users', 'kurt_', '.openclaw', 'workspace', 'kontensystem');

// ── Load data ─────────────────────────────────────────────────────────────────

const logData = JSON.parse(fs.readFileSync(path.join(BASE, 'logs', 'planner-log-2026-03-04.json'), 'utf8'));

const taskByCode = {};   // code → task entry
const taskByName = {};   // lower-stripped name → task entry

const mtlLines = fs.readFileSync(path.join(BASE, 'data', 'master_task_list_v4.jsonl'), 'utf8').split('\n');
for (const line of mtlLines) {
  const l = line.trim();
  if (!l) continue;
  const t = JSON.parse(l);
  if (t.code) taskByCode[t.code] = t;
  const key = t.name.toLowerCase().trim();
  if (!taskByName[key]) taskByName[key] = t;
}

const docIndex = {};  // doc_id → doc entry
const diLines = fs.readFileSync(path.join(BASE, 'data', 'documentation_index.jsonl'), 'utf8').split('\n');
for (const line of diLines) {
  const l = line.trim();
  if (!l) continue;
  const d = JSON.parse(l);
  docIndex[d.doc_id] = d;
}

const TODAY = new Date('2026-03-05');

function docAgeYears(doc) {
  const lm = doc.last_modified || '';
  if (!lm) return null;
  // Try YYYY-MM-DD prefix
  const m = lm.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (m) {
    const d = new Date(`${m[1]}-${m[2]}-${m[3]}`);
    if (!isNaN(d)) {
      return Math.round(10 * (TODAY - d) / (365.25 * 24 * 3600 * 1000)) / 10;
    }
  }
  return null;
}

// ── Extract 6-char code from activity string ──────────────────────────────────

function extractCode(activity) {
  const m = activity.match(/\b([A-Z]{2,6}[A-Z0-9]{0,4})\s*(?:\([^)]*\))?\s*$/);
  if (m && m[1].length === 6) return m[1];
  return '';
}

// ── Match log entry to master task ────────────────────────────────────────────

function matchTask(entry) {
  const code = extractCode(entry.activity);
  if (code && taskByCode[code]) return [taskByCode[code], 'code'];
  const orig = entry.original_activity || '';
  if (orig) {
    const code2 = extractCode(orig);
    if (code2 && taskByCode[code2]) return [taskByCode[code2], 'orig_code'];
  }
  const nameClean = entry.activity.replace(/\s+[A-Z]{6}\s*(?:\([^)]*\))?\s*$/, '').trim().toLowerCase();
  if (taskByName[nameClean]) return [taskByName[nameClean], 'name_exact'];
  if (nameClean.length >= 10) {
    const prefix20 = nameClean.slice(0, 20);
    for (const [key, t] of Object.entries(taskByName)) {
      if (key.slice(0, 20) === prefix20) return [t, 'name_prefix'];
    }
  }
  return [null, null];
}

// ── Compute actual minutes ─────────────────────────────────────────────────────

function actualMinutes(entry) {
  try {
    const [sh, sm, ss] = entry.started_at.split(':').map(Number);
    const [ch, cm, cs] = entry.completed_at.split(':').map(Number);
    const startSec = sh * 3600 + sm * 60 + ss;
    const endSec = ch * 3600 + cm * 60 + cs;
    let diff = Math.floor((endSec - startSec) / 60);
    if (diff < 0) diff += 24 * 60;
    return diff;
  } catch {
    return entry.minutes || 0;
  }
}

// ── Process log entries ────────────────────────────────────────────────────────

const records = [];
for (const entry of logData) {
  if (entry.skipped) continue;
  const mins = actualMinutes(entry);
  const [task, method] = matchTask(entry);
  const code = extractCode(entry.activity) || extractCode(entry.original_activity || '') || '';

  let docStatus, docRefs, accountPrefix;
  if (task) {
    docStatus = task.doc_status || 'undocumented';
    docRefs = task.doc_refs || [];
    accountPrefix = task.account_prefix || '';
  } else {
    docStatus = 'unmatched';
    docRefs = [];
    accountPrefix = '';
  }

  const docDetails = [];
  for (const ref of docRefs) {
    const doc = docIndex[ref.doc_id];
    if (doc) {
      docDetails.push({
        doc_id: ref.doc_id,
        title: doc.title || ref.doc_id,
        last_modified: doc.last_modified || '?',
        age_years: docAgeYears(doc),
        match_type: ref.match_type || '',
      });
    }
  }

  records.push({
    activity: entry.activity,
    code,
    list: entry.list || '',
    minutes: mins,
    started_at: entry.started_at,
    completed_at: entry.completed_at,
    doc_status: docStatus,
    match_method: method,
    account_prefix: accountPrefix,
    doc_details: docDetails,
    task_name: task ? task.name : '',
  });
}

// ── Aggregate by canonical key (code or stripped name) ─────────────────────────

function canonicalKey(rec) {
  if (rec.code) return rec.code;
  return rec.activity.replace(/\s+[A-Z]{6}\s*(?:\([^)]*\))?\s*$/, '').trim();
}

const STATUS_RANK = { documented: 3, mentioned: 2, undocumented: 1, unmatched: 0 };

const aggregated = {};
for (const rec of records) {
  const key = canonicalKey(rec);
  if (!aggregated[key]) {
    aggregated[key] = {
      activities: [], minutes: 0, doc_status: 'unmatched',
      code: '', account_prefix: '', doc_details: [], task_name: '',
    };
  }
  const agg = aggregated[key];
  agg.activities.push(rec.activity);
  agg.minutes += rec.minutes;
  if ((STATUS_RANK[rec.doc_status] || 0) > (STATUS_RANK[agg.doc_status] || 0)) {
    agg.doc_status = rec.doc_status;
    agg.account_prefix = rec.account_prefix;
    agg.task_name = rec.task_name;
  }
  if (!agg.code && rec.code) agg.code = rec.code;
  const existingIds = new Set(agg.doc_details.map(d => d.doc_id));
  for (const d of rec.doc_details) {
    if (!existingIds.has(d.doc_id)) {
      agg.doc_details.push(d);
      existingIds.add(d.doc_id);
    }
  }
}

// Convert to array, sort by minutes desc
let items = Object.entries(aggregated).map(([key, agg]) => {
  const activity = agg.activities[0];
  let display = activity.replace(/\s+[A-Z]{6}\s*(?:\([^)]*\))?\s*$/, '').trim();
  if (!display) display = activity;
  return {
    key,
    display,
    code: agg.code,
    minutes: agg.minutes,
    doc_status: agg.doc_status,
    account_prefix: agg.account_prefix,
    task_name: agg.task_name,
    doc_details: agg.doc_details,
    occurrences: agg.activities.length,
  };
});

items.sort((a, b) => b.minutes - a.minutes);

// ── Statistics ─────────────────────────────────────────────────────────────────

const totalMins = records.reduce((s, r) => s + r.minutes, 0);
const byStatus = {};
for (const r of records) {
  byStatus[r.doc_status] = (byStatus[r.doc_status] || 0) + r.minutes;
}

const documentedMins = byStatus['documented'] || 0;
const mentionedMins = byStatus['mentioned'] || 0;
const undocumentedMins = byStatus['undocumented'] || 0;
const unmatchedMins = byStatus['unmatched'] || 0;

const pct = n => totalMins ? (100 * n / totalMins).toFixed(1) : '0.0';

// ── Oldest docs ────────────────────────────────────────────────────────────────

const seenDocIds = {};
for (const item of items) {
  for (const dd of item.doc_details) {
    if (dd.age_years !== null && !seenDocIds[dd.doc_id]) {
      seenDocIds[dd.doc_id] = { ...dd, activity: item.display, activity_mins: item.minutes };
    }
  }
}
const oldestDocs = Object.values(seenDocIds)
  .sort((a, b) => b.age_years - a.age_years)
  .slice(0, 10);

// Biggest undoc time sinks
const undocItems = items.filter(i => ['undocumented', 'unmatched'].includes(i.doc_status) && i.minutes > 0);
undocItems.sort((a, b) => b.minutes - a.minutes);

// ── Format helpers ─────────────────────────────────────────────────────────────

const STATUS_ICON = { documented: '✅', mentioned: '⚠️ ', undocumented: '❌', unmatched: '🔍' };
const STATUS_LABEL = { documented: 'DOCUMENTED', mentioned: 'MENTIONED ', undocumented: 'UNDOC     ', unmatched: 'UNMATCHED ' };

function pad(s, n, right = false) {
  s = String(s);
  // For strings with emoji/unicode, rough length
  const vis = s.replace(/[^\x00-\x7F]/g, '  '); // treat non-ASCII as 2 chars
  const len = vis.length;
  if (len >= n) return s;
  const pad = ' '.repeat(n - len);
  return right ? pad + s : s + pad;
}

function truncate(s, n) {
  if (s.length > n) return s.slice(0, n - 1) + '…';
  return s;
}

const out = [];

out.push('='.repeat(80));
out.push('DAILY DOCUMENTATION COVERAGE REPORT — March 4, 2026');
out.push('='.repeat(80));
out.push('Generated: 2026-03-05');
out.push('');

out.push('─'.repeat(80));
out.push('SUMMARY STATISTICS');
out.push('─'.repeat(80));
out.push(`  Total minutes logged        : ${String(totalMins).padStart(4)} min`);
out.push(`  Documented (✅)            : ${String(documentedMins).padStart(4)} min  (${pct(documentedMins).padStart(5)}%)`);
out.push(`  Mentioned  (⚠️)             : ${String(mentionedMins).padStart(4)} min  (${pct(mentionedMins).padStart(5)}%)`);
out.push(`  Undocumented (❌)          : ${String(undocumentedMins).padStart(4)} min  (${pct(undocumentedMins).padStart(5)}%)`);
out.push(`  Unmatched (🔍)             : ${String(unmatchedMins).padStart(4)} min  (${pct(unmatchedMins).padStart(5)}%)`);
out.push(`  Coverage (doc + mentioned)  :        ${pct(documentedMins + mentionedMins).padStart(5)}%`);
out.push('');

out.push('─'.repeat(80));
out.push('FULL ACTIVITY LIST  (sorted by time spent, most first)');
out.push('─'.repeat(80));

for (const item of items) {
  const icon = STATUS_ICON[item.doc_status] || '?';
  const label = STATUS_LABEL[item.doc_status] || item.doc_status;
  const display = truncate(item.display, 44).padEnd(44);
  const codeStr = (item.code || '      ').padEnd(6);
  const minsStr = String(item.minutes).padStart(4);

  if (item.doc_details.length > 0) {
    // Prefer named matches
    const named = item.doc_details.filter(d => d.match_type === 'named');
    let best = named.length > 0 ? named : item.doc_details;
    // Deduplicate by title
    const seenTitles = new Set();
    const dedupedBest = [];
    for (const d of best) {
      if (!seenTitles.has(d.title)) { seenTitles.add(d.title); dedupedBest.push(d); }
    }
    best = dedupedBest.slice(0, 3);

    let first = true;
    for (const d of best) {
      const ageStr = d.age_years !== null ? `${d.age_years.toFixed(1)}y` : '?y';
      const titleShort = truncate(d.title, 38);
      if (first) {
        out.push(`  ${display} ${codeStr}  ${minsStr}  ${icon} ${label}  [${d.doc_id}] ${titleShort} (${ageStr})`);
        first = false;
      } else {
        out.push(`  ${''.padEnd(44)} ${''.padEnd(6)}  ${''.padStart(4)}  ${''.padEnd(13)}  [${d.doc_id}] ${titleShort} (${ageStr})`);
      }
    }
  } else {
    let note = '';
    if (item.doc_status === 'unmatched') {
      note = item.code ? `→ code ${item.code} not in task list` : '→ not in task list';
    } else if (item.doc_status === 'undocumented') {
      note = item.account_prefix ? `→ acct: ${item.account_prefix}` : '→ no account';
    } else if (item.doc_status === 'mentioned') {
      note = `→ acct: ${item.account_prefix}`;
    }
    out.push(`  ${display} ${codeStr}  ${minsStr}  ${icon} ${label}  ${note}`);
  }
}
out.push('');

out.push('─'.repeat(80));
out.push('BIGGEST UNDOCUMENTED / UNMATCHED TIME SINKS  (top 15)');
out.push('─'.repeat(80));
for (let i = 0; i < Math.min(15, undocItems.length); i++) {
  const item = undocItems[i];
  const display = truncate(item.display, 50).padEnd(50);
  const codeStr = item.code ? `[${item.code}]` : '[------]';
  const status = item.doc_status.toUpperCase();
  const acct = item.account_prefix ? `acct=${item.account_prefix}` : 'no acct';
  out.push(`  ${String(i + 1).padStart(2)}. ${display} ${codeStr}  ${String(item.minutes).padStart(4)} min  ${status}  ${acct}`);
}
out.push('');

out.push('─'.repeat(80));
out.push('OLDEST DOCUMENTATION REFERENCED TODAY  (top 10 by age)');
out.push('─'.repeat(80));
if (oldestDocs.length > 0) {
  for (const d of oldestDocs) {
    const titleShort = truncate(d.title, 55);
    out.push(`  [${d.doc_id}] ${titleShort}`);
    out.push(`       Last modified: ${d.last_modified}  (age: ${d.age_years.toFixed(1)} years)  [${d.match_type}]`);
    out.push(`       Referenced by: ${d.activity} (${d.activity_mins} min)`);
    out.push('');
  }
} else {
  out.push('  (No dated documentation found)');
  out.push('');
}

out.push('─'.repeat(80));
out.push('NOTES');
out.push('─'.repeat(80));
out.push('  Status definitions:');
out.push('    ✅ DOCUMENTED  — task has a named or direct doc reference in master task list');
out.push('    ⚠️  MENTIONED   — task is in an account-level doc but not specifically described');
out.push('    ❌ UNDOCUMENTED — task has no doc references at all');
out.push('    🔍 UNMATCHED   — activity could not be matched to any task in master_task_list_v4');
out.push('');
out.push('  Mentioned docs are typically account-level documents that cover the area');
out.push('  broadly (e.g. Dokumentation Lebenserhaltung) but don\'t describe this specific');
out.push('  task. They count as weak coverage.');
out.push('');

const reportPath = path.join(BASE, 'data', 'daily_doc_coverage_2026-03-04.txt');
fs.writeFileSync(reportPath, out.join('\n') + '\n', 'utf8');

console.log(`Report written: ${reportPath}`);
console.log();
console.log('=== QUICK SUMMARY ===');
console.log(`Total minutes logged : ${totalMins}`);
console.log(`✅ Documented        : ${documentedMins} min (${pct(documentedMins)}%)`);
console.log(`⚠️  Mentioned         : ${mentionedMins} min (${pct(mentionedMins)}%)`);
console.log(`❌ Undocumented      : ${undocumentedMins} min (${pct(undocumentedMins)}%)`);
console.log(`🔍 Unmatched         : ${unmatchedMins} min (${pct(unmatchedMins)}%)`);
console.log(`Coverage (doc+ment.) : ${pct(documentedMins + mentionedMins)}%`);
console.log();
console.log('Top 5 undocumented/unmatched time sinks:');
for (const item of undocItems.slice(0, 5)) {
  console.log(`  ${String(item.minutes).padStart(4)} min  [${(item.code || '------').padEnd(6)}]  ${item.display.slice(0, 55)}`);
}
