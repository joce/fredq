import { execFileSync, spawnSync } from "node:child_process";

const output = execFileSync("git", ["diff", "--name-only", "--diff-filter=ACMR"], {
  encoding: "utf8",
});
const files = output
  .split(/\r?\n/)
  .map((file) => file.trim())
  .filter(Boolean);

console.log("Checking spelling in modified files...");
if (files.length === 0) {
  console.log("No modified files to check.");
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
