import {spawn} from "node:child_process";
import {mkdtemp, readFile, rm} from "node:fs/promises";
import {tmpdir} from "node:os";
import path from "node:path";

export const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
export async function launchBrowser() {
  const profile = await mkdtemp(path.join(tmpdir(), "vendormap-pwa-"));
  const browser = spawn(process.env.EDGE_PATH || "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe", ["--headless=new", "--disable-gpu", "--no-first-run", "--remote-debugging-port=0", `--user-data-dir=${profile}`, "about:blank"], {windowsHide: true, stdio: "ignore"});
  let port;
  for (let i = 0; i < 100; i++) {try {port = Number((await readFile(path.join(profile, "DevToolsActivePort"), "utf8")).split("\n")[0]); break;} catch {await delay(100);}}
  if (!port) {browser.kill(); throw new Error("Headless browser did not start");}
  const pages = await fetch(`http://127.0.0.1:${port}/json/list`).then(response => response.json());
  const socket = new WebSocket(pages.find(page => page.type === "page").webSocketDebuggerUrl);
  await new Promise(resolve => socket.addEventListener("open", resolve, {once: true}));
  let sequence = 0;
  const pending = new Map(), errors = [];
  socket.addEventListener("message", event => {
    const result = JSON.parse(event.data);
    if (result.id) {const task = pending.get(result.id); pending.delete(result.id); result.error ? task.reject(result.error) : task.resolve(result.result);}
    else if (result.method === "Runtime.exceptionThrown") errors.push(result.params.exceptionDetails.exception?.description || result.params.exceptionDetails.text);
  });
  const command = (method, params = {}, sessionId) => new Promise((resolve, reject) => {const id = ++sequence; pending.set(id, {resolve, reject}); socket.send(JSON.stringify({id, method, params, ...(sessionId ? {sessionId} : {})}));});
  const evaluate = async expression => {const result = await command("Runtime.evaluate", {expression, returnByValue: true, awaitPromise: true}); if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text); return result.result.value;};
  const waitFor = async expression => {for (let i = 0; i < 150; i++) {if (await evaluate(expression)) return; await delay(100);} throw new Error(`Browser wait failed: ${expression}; ${errors.join("\n")}`);};
  await command("Page.enable"); await command("Runtime.enable");
  return {command, evaluate, waitFor, errors, close: async () => {
    socket.close(); browser.kill(); await delay(500);
    const target = path.resolve(profile);
    if (path.dirname(target) !== path.resolve(tmpdir()) || !path.basename(target).startsWith("vendormap-pwa-")) throw new Error("Unexpected temporary browser directory");
    await rm(target, {recursive: true, force: true, maxRetries: 5, retryDelay: 300}).catch(() => {});
  }};
}
