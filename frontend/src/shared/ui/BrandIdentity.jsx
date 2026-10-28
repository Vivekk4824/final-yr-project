import React from "react";
import logoMark from "../../assets/vendormap-mark.svg";

export default function BrandIdentity({subtitle, compact = false}) {
  return <div className={`municipal-brand ${compact ? "compact" : ""}`}>
    <span className="municipal-brand-mark"><img src={logoMark} alt="" width="44" height="44"/></span>
    <span className="municipal-wordmark"><strong>VendorMap<span className="brand-period">.</span></strong><small>{subtitle || "A place for your business"}</small></span>
  </div>;
}
