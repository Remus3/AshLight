"use strict";
/* DESKTOP-CLIENT (decision 0041): the companion window's sandboxed preload.
   It hands the dashboard a small fixed set of named actions, none taking an
   argument and none carrying data (ruling Q-08, REL-AUTOSTART-SWITCH):
   restartOverlay(), autostartOn(), autostartOff() and autostartState()
   (a promise of {enabled}). Main honours each only from the companion
   window's main frame showing the local core. No token, no Node, no fs. */
const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("alClient", Object.freeze({
  restartOverlay: () => ipcRenderer.send("al:restart-overlay"),
  autostartOn: () => ipcRenderer.send("al:autostart-on"),
  autostartOff: () => ipcRenderer.send("al:autostart-off"),
  autostartState: () => ipcRenderer.invoke("al:autostart-state")
}));
