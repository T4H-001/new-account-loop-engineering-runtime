import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';

const receiptDir = 'runtime-receipts';
const required = [
  'status',
  'timestamp',
  'repository',
  'workflow',
  'run_id',
  'commit_sha',
  'evidence',
  'classification',
  'next_action'
];

const files = readdirSync(receiptDir).filter((name) => name.endsWith('.json'));
if (files.length === 0) {
  throw new Error('NO_RECEIPTS_FOUND');
}

for (const file of files) {
  const fullPath = join(receiptDir, file);
  const receipt = JSON.parse(readFileSync(fullPath, 'utf8'));
  for (const field of required) {
    if (!(field in receipt)) {
      throw new Error(`RECEIPT_SCHEMA_MISSING_FIELD ${file} ${field}`);
    }
  }
  if (!receipt.evidence.runner || !receipt.evidence.checkout || !receipt.evidence.receipt_written) {
    throw new Error(`RECEIPT_EVIDENCE_INCOMPLETE ${file}`);
  }
}

console.log(`VALIDATED_RECEIPTS=${files.length}`);
