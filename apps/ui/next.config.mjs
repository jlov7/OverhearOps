import path from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = path.join(path.dirname(fileURLToPath(import.meta.url)), "../..");

export default {
  reactStrictMode: true,
  outputFileTracingRoot: repoRoot
};
