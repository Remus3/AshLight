"use strict";
/* Sandboxed preload: exposes ONLY {token, port, credit} to the overlay page
   (credit: the game-data credit line for the About, TC-SNAP-UI).
   The main process reads the token file; the page never gets Node, fs or IPC. */
const { contextBridge, ipcRenderer } = require("electron");

let cfg = {};
try {
  cfg = ipcRenderer.sendSync("al:config") || {};
} catch (e) {
  cfg = {};
}

contextBridge.exposeInMainWorld("al", Object.freeze({
  token: typeof cfg.token === "string" ? cfg.token : "",
  port: Number(cfg.port) || 0,
  credit: typeof cfg.credit === "string" ? cfg.credit.slice(0, 1000) : ""
}));
