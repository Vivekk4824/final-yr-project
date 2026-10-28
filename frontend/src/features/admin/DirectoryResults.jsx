import React from "react";
import {ArrowUpRight, Carrot, CircleCheck, CircleMinus, Flower2, Shapes, Shirt, ShoppingBasket, Store, UtensilsCrossed} from "lucide-react";
import {pretty} from "./viewModel.js";
import "./DirectoryResults.css";

const categoryIcons = {food: UtensilsCrossed, vegetable_fruit: Carrot, clothing: Shirt, flower: Flower2, general_goods: ShoppingBasket, other: Shapes};

export default function DirectoryResults({vendors, onSelect}) {
  return <div className="vm-directory-results">{vendors.map(vendor => {
    const category = Object.hasOwn(categoryIcons, vendor.business_category) ? vendor.business_category : "unknown";
    const CategoryIcon = categoryIcons[category] || Store;
    const allocated = Boolean(vendor.active_allocation);
    const AllocationIcon = allocated ? CircleCheck : CircleMinus;
    return <article className={`vm-vendor-row${allocated ? " has-allocation" : ""}`} key={vendor.vendor_id}>
    <div className="vm-vendor-identity"><span className="vm-business-icon" data-category={category} aria-hidden="true"><CategoryIcon size={21}/></span><div><button className="vendor-directory-name" onClick={() => onSelect(vendor)}>{vendor.full_name || vendor.business_name || "Name not recorded"}</button><small>{vendor.application_vendor_id || vendor.vendor_id}</small></div></div>
    <div className="vm-vendor-business"><strong>{pretty(vendor.business_category)}</strong><small>{vendor.source_division || "No historical division"}</small></div>
    <div className="vm-vendor-allocation"><span className={`vm-allocation-badge ${allocated ? "is-active" : "is-unallocated"}`}><AllocationIcon size={15} aria-hidden="true"/><span>{allocated ? "Active allocation" : "No active allocation"}</span></span>{allocated && <strong className="vm-allocation-zone">{vendor.active_allocation.zone_id}</strong>}</div>
    <button className="vm-vendor-open" onClick={() => onSelect(vendor)} aria-label={`View ${vendor.full_name || vendor.vendor_id}`}>View details<ArrowUpRight size={17}/></button>
  </article>;
  })}</div>;
}
