"use strict";
/* DESKTOP-CLIENT (decision 0041): the tray menu, as plain data so node
   --test covers it. state: {overlayOn, companionShown, wakeOn}; actions:
   {restart, toggleOverlay, toggleCompanion, toggleWake, quit}. Left-click on
   the icon restores the companion (window.js); this is the right-click menu.
   OVL-WAKE-COMPANION: the "Open AshLight when the game wakes" checkbox is
   the one switch for the companion's return (saved in client-prefs.json
   under the runtime dir, default on). */

const TOOLTIP = "AshLight is running. Click to open it. Right-click for the menu.";
const CLOSED_NOTE = "AshLight keeps running here. Right-click this icon to quit.";
const WAKE_LABEL = "Open AshLight when the game wakes";

function trayTemplate(state, actions) {
  const s = state || {};
  return [
    { id: "companion", label: s.companionShown ? "Minimize AshLight" : "Restore AshLight",
      click: actions.toggleCompanion },
    { id: "overlay", label: "Show in-game overlay", type: "checkbox",
      checked: s.overlayOn === true, click: actions.toggleOverlay },
    { id: "wake", label: WAKE_LABEL, type: "checkbox",
      checked: s.wakeOn === true, click: actions.toggleWake },
    { id: "restart", label: "Restart overlay", click: actions.restart },
    { type: "separator" },
    { id: "quit", label: "Quit AshLight", click: actions.quit }
  ];
}

module.exports = { trayTemplate, TOOLTIP, CLOSED_NOTE, WAKE_LABEL };
