import { execFileSync, spawnSync } from "node:child_process";
import { existsSync } from "node:fs";

// Files changed on this branch (since it left the default branch), plus those
// modified or added and not yet committed. A check that looked only at
// uncommitted files would find nothing to check once the work is committed,
// which is when it runs before a push.

function git(...args) {
  const result = spawnSync("git", ["-c", "core.quotePath=false", ...args], {
    encoding: "utf8",
  });
  return result.status === 0 ? result.stdout.trim() : null;
}

function lines(text) {
  return (text ?? "")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
}

const remoteDefault = git("symbolic-ref", "-q", "--short", "refs/remotes/origin/HEAD");
const candidates = [remoteDefault, "origin/main", "origin/master", "@{upstream}", "main", "master"];
let base = null;
let baseRef = null;
for (const ref of candidates) {
  if (!ref) continue;
  const mergeBase = git("merge-base", ref, "HEAD");
  if (mergeBase) {
    base = mergeBase;
    baseRef = ref;
    break;
  }
}

if (base === null) {
  console.log("(no default branch, upstream or main to compare with: checking uncommitted files only)");
} else if (!baseRef.startsWith("origin/")) {
  console.log(`(no remote default branch: comparing with ${baseRef})`);
}

const changed = git("diff", "--name-only", "--diff-filter=ACMR", base ?? "HEAD");
const untracked = git("ls-files", "--others", "--exclude-standard");
const files = [...new Set([...lines(changed), ...lines(untracked)])]
  .filter((file) => existsSync(file))
  .sort();

console.log("Checking spelling in changed files...");
if (files.length === 0) {
  console.log("No changed files to check.");
  process.exit(0);
}

console.log("Files to check:");
for (const file of files) {
  console.log(`  ${file}`);
}

const result = spawnSync(
  process.execPath,
  ["node_modules/cspell/bin.mjs", "--no-must-find-files", ...files],
  {
    stdio: "inherit",
  },
);

if (result.error) {
  throw result.error;
}
if (result.status !== 0) {
  process.exit(result.status ?? 1);
}

console.log("Spelling check passed!");
