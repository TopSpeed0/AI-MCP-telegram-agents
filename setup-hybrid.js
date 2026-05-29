#!/usr/bin/env node
// setup-hybrid.js — Sets up the Hermes + VS Code Copilot hybrid bridge.
// Run AFTER setup.js (which creates .telegram-config).
//
// What it does:
//   1. Reads .telegram-config (bot_token + chat_id from setup.js)
//   2. Checks prerequisites (Hermes, gh CLI, Node)
//   3. Ensures gh auth is OAuth (not PAT — PATs don't work with Copilot API)
//   4. Configures Hermes: model → GitHub Copilot, gateway → Telegram
//   5. Injects the delegation environment_hint into Hermes config.yaml
//   6. Optionally fixes corporate TLS proxy (exports Windows root CAs)
//   7. Starts the gateway and prints next steps
//
// Zero dependencies. Run: `node setup-hybrid.js`

'use strict';
const fs = require('fs');
const path = require('path');
const { execSync, spawnSync } = require('child_process');
const readline = require('readline');

const ROOT = __dirname;
const CONFIG_PATH = path.join(ROOT, '.telegram-config');

const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
const ask = (q) => new Promise((res) => rl.question(q, (a) => res(a.trim())));

function log(msg) { process.stdout.write(msg + '\n'); }
function ok(msg)  { log(`\x1b[32m✓\x1b[0m ${msg}`); }
function info(m)  { log(`\x1b[36mℹ\x1b[0m ${m}`); }
function warn(m)  { log(`\x1b[33m!\x1b[0m ${m}`); }
function err(m)   { log(`\x1b[31m✗\x1b[0m ${m}`); }

function run(cmd, opts = {}) {
  try {
    return execSync(cmd, { encoding: 'utf-8', timeout: 30000, ...opts }).trim();
  } catch (e) {
    return null;
  }
}

function fileExists(p) { try { fs.accessSync(p); return true; } catch { return false; } }

async function main() {
  log('');
  log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  log('  Hybrid Setup — Hermes Agent + VS Code Copilot Bridge');
  log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  log('');

  // ─── Step 1: Check .telegram-config ───
  info('Step 1: Checking Telegram config...');
  if (!fileExists(CONFIG_PATH)) {
    err('.telegram-config not found. Run "node setup.js" first.');
    process.exit(1);
  }
  const config = JSON.parse(fs.readFileSync(CONFIG_PATH, 'utf-8'));
  if (!config.bot_token || !config.chat_id) {
    err('.telegram-config is incomplete. Run "node setup.js" first.');
    process.exit(1);
  }
  ok(`Telegram config found (chat_id: ${config.chat_id})`);

  // ─── Step 2: Check prerequisites ───
  info('Step 2: Checking prerequisites...');

  // Node
  const nodeMajor = parseInt(process.versions.node.split('.')[0], 10);
  if (nodeMajor < 22) {
    err(`Node.js ${process.versions.node} found — need 22.10+`);
    process.exit(1);
  }
  ok(`Node.js ${process.versions.node}`);

  // Hermes
  const hermesVersion = run('hermes --version');
  if (!hermesVersion) {
    err('Hermes Agent not found. Install it first:');
    log('  pip install hermes-agent');
    log('  or visit: https://hermes-agent.nousresearch.com/docs/getting-started/installation');
    process.exit(1);
  }
  ok(`Hermes: ${hermesVersion.split('\n')[0]}`);

  // gh CLI
  const ghVersion = run('gh --version');
  if (!ghVersion) {
    err('GitHub CLI (gh) not found. Install it:');
    log('  https://cli.github.com/');
    process.exit(1);
  }
  ok(`GitHub CLI: ${ghVersion.split('\n')[0]}`);

  // ─── Step 3: Check gh auth (needs OAuth, not PAT) ───
  info('Step 3: Checking GitHub authentication...');

  // Clear GH_TOKEN if it's a PAT — Copilot API doesn't accept PATs
  const ghToken = process.env.GH_TOKEN || '';
  if (ghToken.startsWith('github_pat_') || ghToken.startsWith('ghp_')) {
    warn('GH_TOKEN is a Personal Access Token — Copilot API requires OAuth.');
    warn('The PAT will work for git but NOT for Copilot inference.');
    const fix = await ask('Remove GH_TOKEN and login via browser for OAuth? (Y/n): ');
    if (fix.toLowerCase() !== 'n') {
      if (process.platform === 'win32') {
        run('powershell -NoProfile -Command "[System.Environment]::SetEnvironmentVariable(\'GH_TOKEN_BACKUP\', $env:GH_TOKEN, \'User\'); [System.Environment]::SetEnvironmentVariable(\'GH_TOKEN\', $null, \'User\')"');
        ok('GH_TOKEN backed up to GH_TOKEN_BACKUP and removed');
      }
      delete process.env.GH_TOKEN;
    }
  }

  // Check if we have a valid OAuth token
  const authStatus = run('gh auth status 2>&1') || '';
  if (authStatus.includes('keyring') && authStatus.includes('gho_')) {
    ok('GitHub OAuth token found (keyring)');
  } else if (authStatus.includes('Logged in')) {
    // Logged in but maybe with PAT — check token type
    const token = run('gh auth token 2>&1') || '';
    if (token.startsWith('gho_')) {
      ok('GitHub OAuth token found');
    } else {
      warn('No OAuth token — need browser login for Copilot API.');
      info('Running: gh auth login -h github.com -p https -w');
      const result = spawnSync('gh', ['auth', 'login', '-h', 'github.com', '-p', 'https', '-w'], {
        stdio: 'inherit',
        timeout: 300000,
      });
      if (result.status !== 0) {
        err('gh auth login failed. Run it manually: gh auth login -h github.com -p https -w');
        process.exit(1);
      }
      ok('GitHub OAuth login complete');
    }
  } else {
    info('Not logged in to GitHub. Running browser login...');
    const result = spawnSync('gh', ['auth', 'login', '-h', 'github.com', '-p', 'https', '-w'], {
      stdio: 'inherit',
      timeout: 300000,
    });
    if (result.status !== 0) {
      err('gh auth login failed.');
      process.exit(1);
    }
    ok('GitHub OAuth login complete');
  }

  // ─── Step 4: Configure Hermes model ───
  info('Step 4: Configuring Hermes model (GitHub Copilot)...');

  // Find Hermes config path
  const hermesConfigDir = process.platform === 'win32'
    ? path.join(process.env.LOCALAPPDATA || '', 'hermes')
    : path.join(process.env.HOME || '', '.hermes');
  const hermesConfigPath = path.join(hermesConfigDir, 'config.yaml');

  if (!fileExists(hermesConfigPath)) {
    info('No Hermes config found. Running initial setup...');
    const r = spawnSync('hermes', ['setup'], { stdio: 'inherit', timeout: 300000 });
    if (r.status !== 0) warn('Hermes setup may have had issues — continuing anyway.');
  }

  // Set model to GitHub Copilot via CLI
  run('hermes config set model.provider copilot');
  run('hermes config set model.default claude-sonnet-4.6');
  run('hermes config set model.base_url https://api.githubcopilot.com');
  run('hermes config set model.api_mode chat_completions');
  ok('Model set: claude-sonnet-4.6 via GitHub Copilot');

  // ─── Step 5: Inject delegation environment_hint ───
  info('Step 5: Injecting hybrid delegation instructions...');

  const queuePath = path.resolve(ROOT, '.vscode-queue.json').replace(/\\/g, '/');
  const hint = [
    'YOU ARE A HYBRID AGENT. A VS Code Copilot worker runs in parallel, polling a queue file for tasks from you.',
    '',
    'DELEGATION PROTOCOL - use this for ANY task requiring workspace access (file editing, terminal commands, code, infrastructure):',
    `1. Use your file_write tool to write to: ${queuePath}`,
    '2. Write this JSON structure (update id, task, timestamps):',
    '   {"id": "task-001", "task": "description of what to do", "context": "optional extra context", "status": "pending", "created": "<ISO timestamp>", "updated": "<ISO timestamp>"}',
    '3. After writing, poll the same file with file_read every 10 seconds',
    '4. When "status" changes to "done", read the "result" field and send it to the user',
    '5. When "status" changes to "error", report the error to the user',
    '6. Increment the task id for each new task (task-001, task-002, etc.)',
    '',
    'CRITICAL RULES:',
    '- NEVER ask users for credentials or connection details - the VS Code worker has everything',
    '- Tell the user you are delegating to VS Code and waiting for the result',
    '- For simple chat, greetings, general knowledge - handle directly without delegating',
  ].join('\n');

  // Read config, replace environment_hint
  if (fileExists(hermesConfigPath)) {
    let yaml = fs.readFileSync(hermesConfigPath, 'utf-8');
    // Replace existing environment_hint
    const hintRegex = /environment_hint:.*(?:\n    .*?)*/;
    const yamlHint = 'environment_hint: |\n' + hint.split('\n').map(l => '    ' + l).join('\n');
    if (yaml.match(hintRegex)) {
      yaml = yaml.replace(hintRegex, yamlHint);
    } else {
      // Append after environment_probe line
      yaml = yaml.replace(
        /(environment_probe:.*\n)/,
        `$1  ${yamlHint}\n`
      );
    }
    fs.writeFileSync(hermesConfigPath, yaml);
    ok('Delegation instructions injected into Hermes config');
  } else {
    warn('Could not find Hermes config — set environment_hint manually');
  }

  // ─── Step 6: Configure Telegram gateway ───
  info('Step 6: Configuring Hermes Telegram gateway...');

  // Check if already configured
  const statusOutput = run('hermes status 2>&1') || '';
  if (statusOutput.includes('Telegram') && statusOutput.includes('configured')) {
    ok('Telegram gateway already configured');
  } else {
    info('Running Hermes gateway setup...');
    info('When prompted:');
    info('  - Select Telegram (option 1)');
    info(`  - Enter bot token: ${config.bot_token.substring(0, 10)}...`);
    info(`  - Enter allowed user ID: ${config.chat_id}`);
    const r = spawnSync('hermes', ['setup', 'gateway'], { stdio: 'inherit', timeout: 300000 });
    if (r.status !== 0) warn('Gateway setup may need manual completion.');
  }

  // ─── Step 7: Corporate TLS proxy fix (Windows only) ───
  if (process.platform === 'win32') {
    info('Step 7: Checking corporate TLS proxy...');
    const certDir = path.join(hermesConfigDir);
    const combinedCa = path.join(certDir, 'combined-ca.pem');

    if (fileExists(combinedCa)) {
      ok('Combined CA bundle already exists');
    } else {
      const fixProxy = await ask('Are you behind a corporate TLS proxy (Zscaler, etc.)? (y/N): ');
      if (fixProxy.toLowerCase() === 'y') {
        info('Exporting corporate root CAs from Windows cert store...');
        const psScript = `
          $certifi = python -c "import certifi; print(certifi.where())" 2>$null
          if (-not $certifi) { Write-Host "NO_CERTIFI"; exit 1 }
          $combined = "${combinedCa.replace(/\\/g, '\\\\')}"
          Copy-Item $certifi $combined -Force
          $corps = Get-ChildItem Cert:\\LocalMachine\\Root | Where-Object { $_.Subject -notmatch 'Microsoft|DigiCert|GlobalSign|Comodo|GeoTrust|Thawte|VeriSign|Entrust|Baltimore|Amazon|Starfield|Google|Apple|Mozilla' }
          foreach ($c in $corps) {
            $b64 = [Convert]::ToBase64String($c.RawData, 'InsertLineBreaks')
            Add-Content $combined "-----BEGIN CERTIFICATE-----"
            Add-Content $combined $b64
            Add-Content $combined "-----END CERTIFICATE-----"
            Add-Content $combined ""
          }
          Write-Host "DONE:$($corps.Count)"
        `;
        const result = run(`powershell -NoProfile -Command "${psScript.replace(/"/g, '\\"')}"`);
        if (result && result.includes('DONE:')) {
          const count = result.split('DONE:')[1];
          ok(`Exported ${count} corporate CAs to combined bundle`);

          // Add to Hermes .env
          const envPath = path.join(hermesConfigDir, '.env');
          let envContent = fileExists(envPath) ? fs.readFileSync(envPath, 'utf-8') : '';
          if (!envContent.includes('SSL_CERT_FILE')) {
            envContent += `\n# Corporate TLS proxy CA bundle\nSSL_CERT_FILE=${combinedCa}\nREQUESTS_CA_BUNDLE=${combinedCa}\n`;
            fs.writeFileSync(envPath, envContent);
            ok('SSL_CERT_FILE and REQUESTS_CA_BUNDLE added to Hermes .env');
          }
        } else {
          warn('Could not export CAs — you may need to fix SSL manually.');
          warn('See: SESSION-SUMMARY.md for the manual SSL fix steps.');
        }
      } else {
        ok('Skipping TLS proxy fix');
      }
    }
  }

  // ─── Done ───
  log('');
  log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  ok('Hybrid setup complete!');
  log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  log('');
  info('To start the hybrid:');
  log('');
  log('  1. Start Hermes gateway:');
  log('     hermes gateway start');
  log('');
  log('  2. Open VS Code → Copilot Chat → new panel → type:');
  log('     @vscode-worker start worker');
  log('');
  log('  3. Send a message to your bot on Telegram!');
  log('');
  info('To stop:');
  log('     hermes gateway stop');
  log('     (close the worker chat panel)');
  log('');
  info('Architecture:');
  log('     You (Telegram) → Hermes → .vscode-queue.json → @vscode-worker → result → Telegram');
  log('');

  rl.close();
}

main().catch((e) => { err(e.message); process.exit(1); });
