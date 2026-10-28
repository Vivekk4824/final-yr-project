export const PILOT_ZONE_IDS = ["NN_F_013", "PAN_F_019", "SAT_F_014", "NR_F_003", "PAN_F_031"];
export const initialPilotState = {open: false, visited: false, layout: null, selectedId: null, view: "map"};

// Owned by the dashboard, independently of its zone-details drawer.
export function pilotReducer(state, action) {
  switch (action.type) {
    case "open": return {...state, open: true, visited: true};
    case "close": return {...state, open: false};
    case "zone": return {...state, layout:null, selectedId:null};
    case "loaded": return {...state, layout: action.layout, selectedId: state.layout?.zone_id === action.layout.zone_id && action.layout.slots.some(s => s.slot_id === state.selectedId) ? state.selectedId : action.layout.my_slot_id || null};
    case "select": return {...state, selectedId: action.slotId};
    case "view": return {...state, view: action.view};
    case "updated": return {...state, layout: {...state.layout, slots: state.layout.slots.map(slot => slot.slot_id === action.slot.slot_id ? action.slot : slot)}};
    case "deleted": return {...state, layout: {...state.layout, slots: state.layout.slots.filter(slot => slot.slot_id !== action.slotId)}, selectedId: state.selectedId === action.slotId ? null : state.selectedId};
    default: return state;
  }
}
