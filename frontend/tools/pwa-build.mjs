import {createHash} from "node:crypto";
import {readFileSync} from "node:fs";

export default function vendorMapPwa() {
  return {
    name: "vendormap-static-pwa",
    apply: "build",
    buildStart() {
      const manifest = JSON.parse(readFileSync(new URL("../public/manifest.webmanifest", import.meta.url), "utf8"));
      for (const icon of [...manifest.icons, {src: "/icons/vendormap-apple-180.png", sizes: "180x180"}]) {
        const data = readFileSync(new URL(`../public${icon.src}`, import.meta.url));
        const [width, height] = icon.sizes.split("x").map(Number);
        if (data.subarray(0, 8).toString("hex") !== "89504e470d0a1a0a" || data.readUInt32BE(16) !== width || data.readUInt32BE(20) !== height) {
          throw new Error(`Invalid install icon: ${icon.src}. Run npm run pwa:icons.`);
        }
      }
    },
    generateBundle(_options, bundle) {
      const worker = readFileSync(new URL("../src/pwa/sw.js", import.meta.url), "utf8");
      const logo = readFileSync(new URL("../src/assets/vendormap-mark.svg", import.meta.url), "utf8");
      const offline = readFileSync(new URL("../src/pwa/offline.html", import.meta.url), "utf8").replace("__VM_LOGO__", logo);
      const hash = value => createHash("sha256").update(value).digest("hex").slice(0, 16);
      const offlinePath = `assets/offline-${hash(offline)}.html`;
      this.emitFile({type: "asset", fileName: offlinePath, source: offline});
      const files = Object.entries(bundle).filter(([name]) => /^assets\/[^/]+-[A-Za-z0-9_-]{8,}\.(?:js|css|svg|png|webp|woff2)$/.test(name)).sort(([a], [b]) => a.localeCompare(b));
      const version = hash(worker + offline + files.map(([name, value]) => name + hash(value.type === "chunk" ? value.code : value.source)).join("\n"));
      const assets = [...files.map(([name]) => `/${name}`), `/${offlinePath}`];
      const source = worker.replace("__VM_VERSION__", JSON.stringify(version)).replace("__VM_ASSETS__", JSON.stringify(assets)).replace("__VM_OFFLINE__", JSON.stringify(`/${offlinePath}`));
      this.emitFile({type: "asset", fileName: "sw.js", source});
    },
  };
}
