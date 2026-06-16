import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

const now = new Date().toISOString();
const outDir = 'runtime-receipts';
mkdirSync(outDir, { recursive: true });

const receipt = {
  status: 'REAL',
  timestamp: now,
  repository: process.env.GITHUB_REPOSITORY || 'unknown',
  workflow: process.env.GITHUB_WORKFLOW || 'unknown',
  run_id: process.env.GITHUB_RUN_ID || 'local',
  commit_sha: process.env.GITHUB_SHA || 'local',
  duration_seconds: null,
  evidence: {
    runner: true,
    checkout: true,
    receipt_written: true,
    artifact_uploaded: false,
    validation_passed: false
  },
  classification: 'PARTIAL',
  gaps: [
    'artifact upload not yet observed by runner',
    'schema validation runs after receipt creation'
  ],
  recovery_action: 'rerun workflow_dispatch if receipt or artifact is missing',
  next_action: 'validate receipt schema and upload artifact'
};

const safeTimestamp = now.replace(/[:.]/g, '-');
const path = join(outDir, `receipt-${safeTimestamp}.json`);
writeFileSync(path, JSON.stringify(receipt, null, 2));
console.log(`RECEIPT_WRITTEN=${path}`);
console.log(JSON.stringify(receipt, null, 2));
