import assert from "node:assert/strict";

const widths = [320, 360, 390, 768, 1024, 1440];

export async function checkAuthenticationUI({ev, wait, size, layout, c, shot, report}) {
  const language = async value => {await ev(`(()=>{const s=document.querySelector('.auth-language select');s.value=${JSON.stringify(value)};s.dispatchEvent(new Event('change',{bubbles:true}));})()`);await wait(`document.documentElement.lang===${JSON.stringify(value)}`);};
  for (const lang of ["en", "mr", "hi"]) {
    await language(lang);
    for (const width of widths) {await size(width);await layout(`login-${lang}`);}
    assert.equal(await ev("document.querySelectorAll('.auth-language').length"), 1);
    assert.equal(await ev("(()=>{const a=document.querySelector('.municipal-brand').getBoundingClientRect(),b=document.querySelector('.auth-language').getBoundingClientRect();return a.right<=b.left})()"), true);
  }
  await language("en");await size(320);
  assert.equal(await ev("document.querySelector('.auth-card form').checkValidity()"), false);
  await ev(`(()=>{const input=document.querySelector('input[type=tel]');Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(input,'9'+String(Date.now()).slice(-9));input.dispatchEvent(new Event('input',{bubbles:true}));})()`);
  await ev("document.querySelector('.auth-card form').requestSubmit()");await wait("!!document.querySelector('.otp-input')");
  assert.equal(await ev("document.querySelector('.auth-primary').disabled"), true);
  for (const lang of ["en", "mr", "hi"]) {
    await language(lang);
    for (const width of widths) {await size(width);await layout(`otp-${lang}`);}
    await c("Emulation.setDeviceMetricsOverride", {width:360,height:450,deviceScaleFactor:1,mobile:true});
    await ev("document.querySelector('.otp-input').focus();document.querySelector('.otp-input').scrollIntoView({block:'center'});true");
    assert.equal(await ev("(()=>{const r=document.querySelector('.otp-input').getBoundingClientRect();return r.top>=0&&r.bottom<=innerHeight})()"), true);
  }
  await language("en");await size(320);
  await ev(`(()=>{const input=document.querySelector('.otp-input');Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(input,'000000');input.dispatchEvent(new Event('input',{bubbles:true}));})()`);
  await ev("document.querySelector('.auth-card form').requestSubmit()");await wait("!!document.querySelector('.auth-error')");await layout("otp-validation-error");
  await ev(`(()=>{const input=document.querySelector('.otp-input');Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(input,'123456');input.dispatchEvent(new Event('input',{bubbles:true}));})()`);
  await ev("document.querySelector('.auth-card form').requestSubmit()");await wait("!!document.querySelector('.vendor-panel.narrow')");
  report.checks.push("Login, language switching, OTP validation and OTP verification through real forms; reduced viewport remains scrollable");
}

export async function checkProfileUI({ev, wait, size, layout, shot, report, vendor, api}) {
  await size(390);
  assert.equal(await ev("document.querySelector('.vendor-profile-avatar img')===null && document.querySelector('.vendor-profile-avatar').textContent.trim().length>0"), true);
  await ev(`(async()=>{const canvas=document.createElement('canvas');canvas.width=96;canvas.height=96;const ctx=canvas.getContext('2d');ctx.fillStyle='#466b83';ctx.fillRect(0,0,96,96);ctx.fillStyle='#dfedb4';ctx.fillRect(24,24,48,48);const blob=await new Promise(r=>canvas.toBlob(r,'image/png'));const transfer=new DataTransfer();transfer.items.add(new File([blob],'review-profile.png',{type:'image/png'}));const input=document.querySelector('.vendor-photo-input');input.files=transfer.files;input.dispatchEvent(new Event('change',{bubbles:true}));})()`);
  await wait("!!document.querySelector('.vendor-profile-avatar img') && !document.querySelector('.vendor-photo-button').disabled");
  const saved = await api("/api/vendors/me/profile-photo");assert.match(saved.data_url, /^data:image\/jpeg;base64,/);
  await ev("document.querySelector('.vm-identity-preview').open=true");await wait("document.querySelector('.vm-identity-card')?.complete && document.querySelector('.vm-identity-card').naturalWidth>0");
  const svg = await ev("decodeURIComponent(document.querySelector('.vm-identity-card').src.split(',').slice(1).join(','))");
  assert.ok(svg.includes(vendor.application_vendor_id));assert.ok(!svg.includes(vendor.vendor_id));assert.ok(!svg.includes("Please present this card"));
  await shot("profile-mobile");
  for (const lang of ["en", "mr", "hi"]) {
    await ev("document.getElementById('vendor-settings-tab').click()");
    await wait("!!document.querySelector('.vendor-settings-workspace select')");
    const current = await ev("document.querySelector('.vendor-settings-workspace select').value");
    if (current !== lang) {
      await ev(`(()=>{const s=document.querySelector('.vendor-settings-workspace select');s.value=${JSON.stringify(lang)};s.dispatchEvent(new Event('change',{bubbles:true}));})()`);
      await ev("document.querySelector('.vendor-settings-workspace select').closest('form').requestSubmit()");
    }
    await wait(`document.documentElement.lang===${JSON.stringify(lang)}`);
    for (const width of widths) {await size(width);await layout(`settings-${lang}`);}
    await ev("document.getElementById('vendor-personal-tab').click()");
    await wait("!!document.querySelector('#vendor-profile-edit')");
    await wait("!!document.querySelector('.vendor-profile-avatar img')");
    await ev("document.querySelector('.vm-identity-preview').open=true");
    for (const width of widths) {await size(width);await layout(`profile-${lang}`);}
  }
  await api(`/api/vendors/${vendor.vendor_id}`, {preferred_language:"en"}, "PATCH");
  await ev("location.reload();");await wait("document.documentElement.lang==='en' && !!document.querySelector('#vendor-profile-edit')");
  // Capture the actual client-generated download without saving a private browser profile.
  await ev("window.__identityDownload=null;window.__originalAnchorClick=HTMLAnchorElement.prototype.click;HTMLAnchorElement.prototype.click=function(){if(this.download.startsWith('VendorMap-Identity-'))window.__identityDownload={url:this.href,name:this.download};else window.__originalAnchorClick.call(this)};true");
  await ev("document.querySelector('.vendor-id-card-button').click()");await wait("!!window.__identityDownload");
  const image = await ev("(async()=>{const r=await fetch(window.__identityDownload.url);const b=await r.blob();const image=await createImageBitmap(b);return {type:b.type,width:image.width,height:image.height}})()");
  assert.deepEqual(image, {type:"image/png",width:640,height:620});
  await ev("HTMLAnchorElement.prototype.click=window.__originalAnchorClick;true");
  report.checks.push("Profile photo uploads and persists; initials fallback; localized identity preview; PNG download uses the public application reference");
}
