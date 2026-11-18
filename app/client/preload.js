"use strict";
/* DESKTOP-CLIENT (decision 0041): the companion window's sandboxed preload.
   It hands the dashboard exactly one action, restartOverlay(), a fixed IPC
   message with no data. Main honours it only from the companion window's
   main frame showing the local core. No token, no Node, no fs. */
const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("alClient", Object.freeze({
  restartOverlay: () => ipcRenderer.send("al:restart-overlay")
}));
