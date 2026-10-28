import test from "node:test";
import assert from "node:assert/strict";
import http from "node:http";
import {createServer} from "vite";

test("browser API requests stay on the website origin, including on a LAN", async t => {
  const previousWindow = Object.getOwnPropertyDescriptor(globalThis, "window");
  Object.defineProperty(globalThis, "window", {configurable: true, value: {location: {protocol: "http:", hostname: "192.168.1.25"}}});
  t.after(() => {if (previousWindow) Object.defineProperty(globalThis, "window", previousWindow); else delete globalThis.window;});
  t.mock.method(globalThis, "fetch", async (url, options) => {
    assert.equal(url, "/api/auth/me");
    assert.equal(options.credentials, "include");
    return new Response(JSON.stringify({role: "VENDOR"}));
  });
  const {apiRequest} = await import("../src/services/api.js?lan-access");
  assert.deepEqual(await apiRequest("/api/auth/me"), {role: "VENDOR"});
});

test("network-facing Vite proxy forwards API requests and session cookies to a loopback backend", async () => {
  let received;
  const backend = http.createServer((request, response) => {
    received = {path: request.url, method: request.method, cookie: request.headers.cookie};
    response.setHeader("Content-Type", "application/json");
    response.setHeader("Set-Cookie", "nmc_session=transport-test; HttpOnly; Path=/; SameSite=Lax");
    response.end(JSON.stringify({ok: true}));
  });
  await new Promise(resolve => backend.listen(0, "127.0.0.1", resolve));
  let vite;
  try {
    vite = await createServer({server: {port: 0, proxy: {"/api": {target: `http://127.0.0.1:${backend.address().port}`}}}});
    assert.equal(vite.config.server.host, "0.0.0.0");
    assert.equal(vite.config.preview.host, "0.0.0.0");
    assert.equal(vite.config.preview.proxy["/api"].target, "http://127.0.0.1:8000");
    await vite.listen();
    const response = await fetch(`http://127.0.0.1:${vite.httpServer.address().port}/api/auth/me`, {headers: {Cookie: "nmc_session=existing-session"}});
    assert.equal(response.status, 200);
    assert.deepEqual(await response.json(), {ok: true});
    assert.deepEqual(received, {path: "/api/auth/me", method: "GET", cookie: "nmc_session=existing-session"});
    assert.match(response.headers.get("set-cookie"), /nmc_session=transport-test; HttpOnly; Path=\/; SameSite=Lax/);
    assert.doesNotMatch(response.headers.get("set-cookie"), /Domain=/i);
  } finally {
    await vite?.close();
    backend.closeAllConnections();
    await new Promise(resolve => backend.close(resolve));
  }
});
