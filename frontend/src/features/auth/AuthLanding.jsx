import React, {useEffect, useRef, useState} from "react";
import {ArrowRight, KeyRound, Landmark, Languages, LockKeyhole, Phone, ShieldCheck} from "lucide-react";
import {loginAdmin, requestVendorOtp, verifyVendorOtp} from "../../services/api.js";
import {useI18n} from "../../i18n/react.jsx";
import BrandIdentity from "../../shared/ui/BrandIdentity.jsx";
import "./AuthLanding.css";

export default function AuthLanding({onAuthenticated}) {
  const {language, t, selectLanguage} = useI18n();
  const [mode, setMode] = useState("vendor");
  const [step, setStep] = useState("mobile");
  const [mobile, setMobile] = useState("");
  const [challengeId, setChallengeId] = useState("");
  const [otp, setOtp] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [resendSeconds, setResendSeconds] = useState(0);
  const otpRefs = useRef([]);

  useEffect(() => {
    if (resendSeconds <= 0) return undefined;
    const timer = window.setInterval(() => setResendSeconds(value => Math.max(0, value - 1)), 1000);
    return () => window.clearInterval(timer);
  }, [resendSeconds]);

  useEffect(() => {
    if (step === "otp") otpRefs.current[0]?.focus();
  }, [step, challengeId]);

  const setOtpDigit = (index, value) => {
    const numeric = value.replace(/\D/g, "");
    if (numeric.length > 1) {
      const code = numeric.slice(0, 4);
      setOtp(code);
      otpRefs.current[code.length - 1]?.focus();
      return;
    }
    const digit = numeric.slice(-1);
    const digits = otp.padEnd(4, " ").split("");
    digits[index] = digit || " ";
    setOtp(digits.join("").trimEnd());
    if (digit && index < 3) otpRefs.current[index + 1]?.focus();
  };
  const handleOtpKeyDown = (index, event) => {
    if (event.key === "Backspace" && !otp[index] && index > 0) otpRefs.current[index - 1]?.focus();
    if (event.key === "ArrowLeft" && index > 0) otpRefs.current[index - 1]?.focus();
    if (event.key === "ArrowRight" && index < 3) otpRefs.current[index + 1]?.focus();
  };
  const handleOtpPaste = event => {
    event.preventDefault();
    const digits = event.clipboardData.getData("text").replace(/\D/g, "").slice(0, 4);
    if (!digits) return;
    setOtp(digits);
    otpRefs.current[Math.min(digits.length, 4) - 1]?.focus();
  };

  const run = async action => {
    setBusy(true); setError("");
    try { await action(); } catch (err) { setError(err.message); } finally { setBusy(false); }
  };
  const requestOtp = event => { event.preventDefault(); run(async () => {
    const result = await requestVendorOtp(mobile);
    setChallengeId(result.challenge_id); setStep("otp"); setOtp(""); setResendSeconds(60);
  }); };
  const verifyOtp = event => { event.preventDefault(); run(async () => {
    const result = await verifyVendorOtp(challengeId, mobile, otp);
    onAuthenticated(result);
  }); };
  const resendOtp = () => run(async () => {
    const result = await requestVendorOtp(mobile);
    setChallengeId(result.challenge_id); setOtp(""); setResendSeconds(60);
  });
  const officerLogin = event => { event.preventDefault(); run(async () => {
    onAuthenticated(await loginAdmin(username, password));
  }); };
  const switchMode = next => { setMode(next); setStep("mobile"); setError(""); setOtp(""); };

  return <main className="auth-page">
    <header className="auth-government-header">
      <BrandIdentity subtitle={t("auth.prototype")}/>
      <label className="auth-language"><Languages size={15}/><span>{t("language.label")}</span><select value={language} onChange={event => selectLanguage(event.target.value)}><option value="en">English</option><option value="mr">मराठी</option><option value="hi">हिन्दी</option></select></label>
    </header>
    <section className="auth-panel"><div className="auth-service-heading"><h1>{t("auth.servicesTitle")}</h1><p>{t("auth.servicesHelp")}</p></div><div className="auth-card" aria-busy={busy}>
      <div className="auth-choice" role="group" aria-label={t("auth.servicesTitle")}><button aria-pressed={mode === "vendor"} disabled={busy} className={mode === "vendor" ? "active" : ""} onClick={() => switchMode("vendor")}><Phone size={16}/> {t("auth.vendorAccess")}</button><button aria-pressed={mode === "admin"} disabled={busy} className={mode === "admin" ? "active" : ""} onClick={() => switchMode("admin")}><Landmark size={16}/> {t("auth.officerAccess")}</button></div>
      {mode === "vendor" ? <>
        <div className="auth-section-title"><div className="auth-icon"><KeyRound size={20}/></div><div><h2>{step === "mobile" ? t("auth.mobileTitle") : t("auth.otpTitle")}</h2><p>{step === "mobile" ? t("auth.mobileHelp") : t("auth.otpHelp")}</p></div></div>
        {step === "mobile" ? <form onSubmit={requestOtp}><label><span>{t("auth.mobileLabel")}</span><div className="auth-input"><b>+91</b><input type="tel" disabled={busy} inputMode="tel" autoComplete="tel-national" value={mobile} onChange={event => setMobile(event.target.value)} placeholder={t("auth.mobilePlaceholder")} required/></div></label><button className="auth-primary" disabled={busy}>{busy ? t("auth.requesting") : t("auth.requestOtp")}<ArrowRight size={16}/></button></form>
          : <form onSubmit={verifyOtp}><label><span>{t("auth.otpLabel")}</span><div className="otp-entry"><LockKeyhole size={18}/><div className="otp-boxes" onPaste={handleOtpPaste}>{Array.from({length: 4}, (_, index) => <input key={index} ref={element => {otpRefs.current[index] = element;}} disabled={busy} autoFocus={index === 0} className="otp-box" aria-label={`${t("auth.otpLabel")} ${index + 1}`} inputMode="numeric" pattern="[0-9]" autoComplete={index === 0 ? "one-time-code" : "off"} maxLength="1" value={otp[index] || ""} onChange={event => setOtpDigit(index, event.target.value)} onKeyDown={event => handleOtpKeyDown(index, event)} required/>)}</div></div></label><button className="auth-primary" disabled={busy || otp.length !== 4}>{busy ? t("auth.verifying") : t("auth.verifyContinue")}<ArrowRight size={16}/></button><button type="button" className="auth-link" disabled={busy || resendSeconds > 0} onClick={resendOtp}>{resendSeconds > 0 ? t("auth.resendCountdown").replace("{seconds}", resendSeconds) : t("auth.resendOtp")}</button><button type="button" className="auth-link" disabled={busy} onClick={() => {setStep("mobile"); setOtp(""); setResendSeconds(0);}}>{t("auth.differentMobile")}</button></form>}
      </> : <>
        <div className="auth-section-title"><div className="auth-icon officer"><ShieldCheck size={20}/></div><div><h2>Officer sign in</h2><p>Authorised NMC officers only.</p></div></div>
        <form onSubmit={officerLogin}><label><span>Officer username</span><div className="auth-input"><input disabled={busy} autoComplete="username" value={username} onChange={event => setUsername(event.target.value)} placeholder="Officer username" required/></div></label><label><span>Password</span><div className="auth-input"><LockKeyhole size={16}/><input disabled={busy} type="password" autoComplete="current-password" value={password} onChange={event => setPassword(event.target.value)} placeholder="Password" required/></div></label><button className="auth-primary officer" disabled={busy}>{busy ? "Signing in…" : "Sign in to NMC dashboard"}<ArrowRight size={16}/></button></form>
      </>}
      {error && <div className="auth-error" role="alert">{error}</div>}
      {mode === "vendor" && <p className="auth-new-vendor">{t("auth.newVendorHelp")}</p>}
    </div></section>
    <footer className="auth-footer">{t("auth.prototype")}</footer>
  </main>;
}
