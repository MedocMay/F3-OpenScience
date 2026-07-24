// TS orchestrator server 打单文件(免运行时 tsx 依赖)。用法:node build.mjs
import { build } from "esbuild";
await build({ entryPoints: ["src/server.ts"], bundle: true, platform: "node",
  target: "node20", format: "esm", outfile: "dist/server.mjs" });
console.log("bundled -> dist/server.mjs");
