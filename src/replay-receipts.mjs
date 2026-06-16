import { existsSync, readFileSync } from 'node:fs';

const ledgerPath = 'receipts/ledger.ndjson';

if (!existsSync(ledgerPath)) {
  throw new Error('LEDGER_MISSING');
}

const rows = readFileSync(ledgerPath, 'utf8')
  .split('\n')
  .map((line) => line.trim())
  .filter(Boolean)
  .map((line) => JSON.parse(line));

if (rows.length === 0) {
  console.log('LEDGER_EMPTY_REPLAY_OK_FOR_FIRST_RUN');
  process.exit(0);
}

for (const row of rows) {
  for (const key of ['timestamp', 'repository', 'workflow', 'run_id', 'commit_sha', 'classification', 'receipt_path']) {
    if (!(key in row)) {
      throw new Error(`LEDGER_ROW_MISSING_${key}`);
    }
  }
  if (row.classification !== 'REAL') {
    throw new Error(`LEDGER_ROW_NOT_REAL ${row.receipt_path}`);
  }
}

console.log(`REPLAY_VALIDATED_ROWS=${rows.length}`);
