import React, {useEffect, useRef, useState} from "react";
import {Camera, LoaderCircle, UserRound} from "lucide-react";
import {useI18n} from "../../i18n/react.jsx";
import "./ProfilePhotoControl.css";

export default function ProfilePhotoControl({photo, name, busy, onChange}) {
  const {t} = useI18n();
  const input = useRef(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [photo]);
  const initials = name?.trim().split(/\s+/u).slice(0, 2).map(part => Array.from(part)[0]).join("").toLocaleUpperCase();
  return <div className="vendor-profile-photo-area" aria-busy={busy}>
    <div className="vendor-profile-avatar">{photo && !failed ? <img src={photo} alt={t("account.photoPreview", {name: name || t("identity.registeredVendor")})} onError={() => setFailed(true)}/> : initials || <UserRound size={28}/>}</div>
    <input ref={input} className="vendor-photo-input" type="file" accept="image/*" disabled={busy} onChange={onChange}/>
    <button className="vendor-secondary vendor-photo-button" type="button" disabled={busy} onClick={() => input.current?.click()}>{busy ? <LoaderCircle size={17} className="vm-spinner"/> : <Camera size={17}/>}<span>{t(busy ? "account.photoUploading" : photo ? "account.changePhoto" : "account.uploadPhoto")}</span></button>
  </div>;
}
