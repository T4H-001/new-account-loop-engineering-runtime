import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';

const registry = JSON.parse(readFileSync('managed-repositories.json', 'utf8'));
const timestamp = new Date().toISOString();
const outDir = 'receipts/managed-repositories';
mkdirSync(outDir, { recursive: true });

const results = [];

for (const repo of registry) {
  const safe = repo.repository.replace('/', '__');
  const target = `tmp/${safe}`;
  mkdirSync('tmp', { recursive: true });

  const result = {
    repository: repo.repository,
    runtime: repo.runtime,
    status: repo.status,
    native_actions: repo.native_actions,
    execution_model: repo.execution_model,
    checked_at: timestamp,
    clone: false,
    files_listed: false,
    classification: 'PARTIAL',
    gaps: []
  };

  try {
    execFileSync('git', ['clone', '--depth', '1', `https://github.com/${repo.repository}.git`, target], { stdio: 'pipe' });
    result.clone = true;
    execFileSync('find', [target, '-maxdepth', '2', '-type', 'f'], { stdio: 'pipe' });
    result.files_listed = true;
    result.classification = 'REAL';
  } catch (error) {
    result.classification = 'BLOCKED';
    result.gaps.push(String(error.message || error));
  }

  results.push(result);
}

const report = {
  timestamp,
  workflow: process.env.GITHUB_WORKFLOW || 'local',
  run_id: process.env.GITHUB_RUN_ID || 'local',
  commit_sha: process.env.GITHUB_SHA || 'local',
  runtime_repository: process.env.GITHUB_REPOSITORY || 'T4H001/new-account-loop-engineering-runtime',
  managed_repository_count: registry.length,
  results
};

const path = `${outDir}/managed-repositories-${timestamp.replace(/[:.]/g, '-')}.json`;
writeFileSync(path, JSON.stringify(report, null, 2));
console.log(`MANAGED_REPOSITORY_AUDIT=${path}`);
console.log(JSON.stringify(report, null, 2));
