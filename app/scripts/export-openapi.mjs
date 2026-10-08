// Writes app/openapi.json from the FastAPI app, without starting a server.
// Part of `npm run gen:api`; needs uv (https://docs.astral.sh/uv/) on the PATH.
import { execFileSync } from 'node:child_process';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const appDir = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const specPath = resolve(appDir, 'openapi.json');

execFileSync('uv', ['run', 'python', '-m', 'api.scripts.export_openapi', specPath], {
  cwd: resolve(appDir, '..', 'api'),
  stdio: ['ignore', 'ignore', 'inherit'],
});
