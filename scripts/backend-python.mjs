import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const DEFAULT_ENV_DEFAULTS = Object.freeze({});

export function resolveBackendPython({
  repoRoot = process.cwd(),
  env = process.env,
  exists = existsSync,
  platform = process.platform,
} = {}) {
  const configured = env.BACKEND_PYTHON?.trim();
  if (configured) {
    return configured;
  }

  const backendDir = resolve(repoRoot, 'backend');
  const candidates = [
    join(backendDir, '.venv', 'Scripts', 'python.exe'),
    join(backendDir, '.venv', 'bin', 'python'),
    join(backendDir, '.venv-linux', 'bin', 'python'),
  ];

  return candidates.find((candidate) => exists(candidate)) ?? (platform === 'win32' ? 'python' : 'python3');
}

export function parseCliArgs(argv, env = process.env) {
  const separatorIndex = argv.indexOf('--');
  const optionArgs = separatorIndex === -1 ? [] : argv.slice(0, separatorIndex);
  const rawPythonArgs = separatorIndex === -1 ? argv : argv.slice(separatorIndex + 1);
  const envDefaults = { ...DEFAULT_ENV_DEFAULTS };
  let cwd = 'root';

  for (let index = 0; index < optionArgs.length; index += 1) {
    const option = optionArgs[index];
    if (option === '--cwd') {
      cwd = optionArgs[index + 1] ?? 'root';
      index += 1;
      continue;
    }
    if (option === '--env-default') {
      const [key, value = ''] = (optionArgs[index + 1] ?? '').split('=');
      if (key) {
        envDefaults[key] = value;
      }
      index += 1;
      continue;
    }
    throw new Error(`Unknown option: ${option}`);
  }

  const pythonArgs = rawPythonArgs.map((arg) =>
    arg.replace(/\{env:([A-Z0-9_]+)\}/gi, (_match, key) => env[key] ?? envDefaults[key] ?? '')
  );

  return { cwd, pythonArgs };
}

export function resolveRunCwd(repoRoot, cwdOption) {
  if (cwdOption === 'backend') {
    return resolve(repoRoot, 'backend');
  }
  if (cwdOption === 'root') {
    return resolve(repoRoot);
  }
  throw new Error(`Unsupported --cwd value: ${cwdOption}`);
}

export function runBackendPython(argv = process.argv.slice(2), options = {}) {
  const repoRoot = resolve(options.repoRoot ?? process.cwd());
  const { cwd, pythonArgs } = parseCliArgs(argv, options.env ?? process.env);
  if (pythonArgs.length === 0) {
    throw new Error('No Python arguments provided. Pass them after "--".');
  }

  const python = resolveBackendPython({
    repoRoot,
    env: options.env ?? process.env,
    exists: options.exists ?? existsSync,
    platform: options.platform ?? process.platform,
  });

  const child = spawn(python, pythonArgs, {
    cwd: resolveRunCwd(repoRoot, cwd),
    env: { ...(options.env ?? process.env), PYTHONUNBUFFERED: '1' },
    stdio: options.stdio ?? 'inherit',
    shell: false,
  });

  child.on('exit', (code, signal) => {
    if (signal) {
      process.kill(process.pid, signal);
      return;
    }
    process.exit(code ?? 1);
  });

  child.on('error', (error) => {
    console.error(`[backend-python] Failed to start ${python}: ${error.message}`);
    process.exit(1);
  });

  return child;
}

const isMain = process.argv[1] && fileURLToPath(import.meta.url) === resolve(process.argv[1]);
if (isMain) {
  runBackendPython();
}
