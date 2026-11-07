import { describe, expect, it } from "vitest";
import { isLoopbackHost, loadConfig } from "./config.js";

const base = { HORARIS_DB: "/tmp/horaris.db" };

function messageOf(source: NodeJS.ProcessEnv): string {
  try {
    loadConfig(source);
  } catch (error) {
    return error instanceof Error ? error.message : "";
  }
  return "";
}

describe("loadConfig", () => {
  it("aplica los valores por defecto", () => {
    expect(loadConfig(base)).toEqual({
      dbPath: "/tmp/horaris.db",
      host: "127.0.0.1",
      port: 3000,
      corsOrigin: "http://localhost:5173",
      logLevel: "info",
    });
  });

  it("lee cada variable", () => {
    const config = loadConfig({
      HORARIS_DB: "x.db",
      HOST: "0.0.0.0",
      PORT: "8080",
      CORS_ORIGIN: "https://horaris.example",
      LOG_LEVEL: "debug",
    });
    expect(config).toEqual({
      dbPath: "x.db",
      host: "0.0.0.0",
      port: 8080,
      corsOrigin: "https://horaris.example",
      logLevel: "debug",
    });
  });

  it.each(["abc", "0", "65536", "-1", "3.5"])("rechaza PORT=%j sin revelar el valor", (port) => {
    const message = messageOf({ ...base, PORT: port });
    expect(message).toContain("PORT");
    expect(message).not.toContain(port);
  });

  it("nombra HORARIS_DB cuando falta", () => {
    expect(messageOf({})).toContain("HORARIS_DB");
  });

  it("rechaza LOG_LEVEL inválido sin revelar el valor", () => {
    const message = messageOf({ ...base, LOG_LEVEL: "verbosisimo" });
    expect(message).toContain("LOG_LEVEL");
    expect(message).not.toContain("verbosisimo");
  });
});

describe("isLoopbackHost", () => {
  it.each(["127.0.0.1", "127.5.4.3", "::1", "[::1]", "localhost", "LOCALHOST"])("%s es loopback", (host) => {
    expect(isLoopbackHost(host)).toBe(true);
  });

  it.each(["0.0.0.0", "::", "192.168.1.5", "example.com", "127.0.0.1.evil.example", "1270.0.0.1"])(
    "%s no es loopback",
    (host) => {
      expect(isLoopbackHost(host)).toBe(false);
    },
  );
});
