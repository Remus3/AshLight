"use strict";
/* Sandboxed preload: exposes ONLY {token, port} to the overlay page.
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
  port: Number(cfg.port) || 0
}));
