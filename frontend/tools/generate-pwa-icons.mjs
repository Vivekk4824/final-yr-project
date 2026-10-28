import {readFile, writeFile, mkdir} from "node:fs/promises";
import {launchBrowser} from "./browser.mjs";

const logo = await readFile(new URL("../src/assets/vendormap-mark.svg", import.meta.url), "utf8");
const directory = new URL("../public/icons/", import.meta.url);
await mkdir(directory, {recursive: true});
const browser = await launchBrowser();
try {
  for (const [name, size, scale] of [["vendormap-192.png",192,.82],["vendormap-512.png",512,.82],["vendormap-maskable-512.png",512,.62],["vendormap-apple-180.png",180,.82]]) {
    const data = await browser.evaluate(`(async()=>{const image=new Image();image.src=${JSON.stringify(`data:image/svg+xml;charset=utf-8,${encodeURIComponent(logo)}`)};await image.decode();const canvas=document.createElement('canvas');canvas.width=canvas.height=${size};const ctx=canvas.getContext('2d');ctx.fillStyle='#f6f5ef';ctx.fillRect(0,0,${size},${size});const edge=${size}*${scale};ctx.drawImage(image,(${size}-edge)/2,(${size}-edge)/2,edge,edge);return canvas.toDataURL('image/png').split(',')[1]})()`);
    await writeFile(new URL(name, directory), Buffer.from(data, "base64"));
    console.log(`Created ${name} (${size} × ${size}) from the existing SVG logo`);
  }
} finally {await browser.close();}
