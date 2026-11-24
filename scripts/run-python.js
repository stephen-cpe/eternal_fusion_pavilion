// Runs a Python command using the venv that belongs to a service folder,
// so the root package.json can start Flask and the AI agent without
// anyone activating a venv by hand.
//
// Usage: node scripts/run-python.js <service-dir> [--env KEY=VALUE ...] <python args...>
// Example: node scripts/run-python.js backend/ai_agent --env AI_MOCK=true -m pytest tests/
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const [serviceDir, ...rest] = process.argv.slice(2);

if (!serviceDir) {
  console.error("Usage: node scripts/run-python.js <service-dir> [--env KEY=VALUE ...] <python args...>");
  process.exit(2);
}

// Python buffers stdout when it is not attached to a terminal, which would
// hide Flask/uvicorn logs behind concurrently. Force line-by-line output.
const env = { ...process.env, PYTHONUNBUFFERED: "1" };
const args = [];
for (let i = 0; i < rest.length; i++) {
  if (rest[i] === "--env") {
    const [key, ...value] = (rest[++i] ?? "").split("=");
    env[key] = value.join("=");
  } else {
    args.push(rest[i]);
  }
}

const cwd = path.join(root, serviceDir);
const python =
  process.platform === "win32"
    ? path.join(cwd, "venv", "Scripts", "python.exe")
    : path.join(cwd, "venv", "bin", "python");

if (!existsSync(python)) {
  console.error(`No virtual environment found at ${python}`);
  console.error(`Create it first (see README.md, "Configure Backend" / "Configure AI Agent").`);
  process.exit(1);
}

const child = spawn(python, args, { cwd, env, stdio: "inherit" });
child.on("exit", (code, signal) => process.exit(code ?? (signal ? 1 : 0)));
for (const sig of ["SIGINT", "SIGTERM"]) {
  process.on(sig, () => child.kill(sig));
}
