import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

const globalSetupPath = fileURLToPath(new URL("./test/global-setup.ts", import.meta.url));

export default defineConfig({
  test: {
    environment: "node",
    include: ["src/**/*.test.ts", "test/**/*.test.ts"],
    // eslint-disable-next-line security/detect-non-literal-fs-filename -- ruta fija calculada en este fichero, sin entrada externa
    globalSetup: existsSync(globalSetupPath) ? [globalSetupPath] : [],
    testTimeout: 20000,
  },
});
