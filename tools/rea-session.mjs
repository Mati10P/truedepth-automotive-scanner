// Reuse one local REA provider session for sequential, read-only native queries.
// Input: one JSON object per line: {name, arguments, output}; {close:true} ends it.
import { createRequire } from 'node:module';
import { pathToFileURL, fileURLToPath } from 'node:url';
import path from 'node:path';
import fs from 'node:fs/promises';
import { createWriteStream } from 'node:fs';
import { createInterface } from 'node:readline';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const runtime = path.join(root, '.local/tools/rea-runtime');
const requireLocal = createRequire(path.join(runtime, 'package.json'));
const { Client } = await import(pathToFileURL(requireLocal.resolve('@modelcontextprotocol/client')));
const { StdioClientTransport } = await import(pathToFileURL(requireLocal.resolve('@modelcontextprotocol/client/stdio')));
const evidenceDir = path.join(root, '.local/rea-evidence');
await fs.mkdir(evidenceDir, { recursive: true });
const transport = new StdioClientTransport({
  command: process.execPath,
  args: [path.join(runtime, 'node_modules/rea-agents/scripts/rea.mjs'), '--mcp'],
  env: {
    ...process.env,
    JAVA_HOME: process.env.JAVA_HOME || 'C:\\Program Files\\Java\\jdk-21',
    GHIDRA_INSTALL_DIR: path.join(root, '.local/tools/ghidra_12.1.4_PUBLIC'),
    REA_ANALYSIS_PROVIDER: 'ghidra',
    GHIDRA_HEADLESS_MAXMEM: '2G',
    REA_GHIDRA_STARTUP_TIMEOUT_MS: '900000',
  },
  stderr: 'pipe',
});
const client = new Client({ name: 'truedepth-readonly-research', version: '1' });
const stderrLog = createWriteStream(path.join(evidenceDir, 'session-stderr.log'), { flags: 'a' });
stderrLog.on('error', error => console.error(`REA log error: ${error.message}`));
// Narrow allowlist; extend only after inspecting the actual advertised schemas.
const allowed = new Set([
  'open_binary', 'close_binary', 'xrefs', 'resolve_containing_procedure',
  'procedure_info', 'procedure_references', 'procedure_pseudo_code',
  'search_strings',
]);
let lines;
try {
  await client.connect(transport);
  transport.stderr?.pipe(stderrLog);
  const catalog = [];
  let cursor;
  do {
    const page = await client.listTools(cursor ? { cursor } : {});
    catalog.push(...page.tools);
    cursor = page.nextCursor;
  } while (cursor);
  const selected = catalog.filter(t => allowed.has(t.name))
    .map(({ name, description, inputSchema }) => ({ name, description, inputSchema }));
  await fs.writeFile(path.join(evidenceDir, 'session-tool-schemas.json'), JSON.stringify(selected, null, 2));
  console.log(JSON.stringify({ ready: true, tools: selected.map(t => t.name) }));
  lines = createInterface({ input: process.stdin, crlfDelay: Infinity });
  for await (const line of lines) {
    if (!line.trim()) continue;
    try {
      const request = JSON.parse(line);
      if (request.close === true) break;
      if (!allowed.has(request.name)) throw new Error('Tool not on read-only allowlist');
      if (typeof request.output !== 'string' || !/^[a-z0-9][a-z0-9_-]*\.json$/.test(request.output)) {
        throw new Error('Output must be a simple JSON filename');
      }
      const handle = await fs.open(path.join(evidenceDir, request.output), 'wx');
      try {
        try {
          const result = await client.callTool({ name: request.name, arguments: request.arguments || {} }, { timeout: 1000000 });
          await handle.writeFile(JSON.stringify(result, null, 2));
          console.log(JSON.stringify({ saved: request.output, isError: Boolean(result.isError) }));
        } catch (error) {
          await handle.writeFile(JSON.stringify({ clientError: error.message }, null, 2));
          throw error;
        }
      } finally {
        await handle.close();
      }
    } catch (error) {
      console.log(JSON.stringify({ error: error.message }));
    }
  }
} finally {
  lines?.close();
  try { await client.callTool({ name: 'close_binary', arguments: {} }, { timeout: 30000 }); } catch {}
  await client.close();
  await transport.close();
  stderrLog.end();
}
