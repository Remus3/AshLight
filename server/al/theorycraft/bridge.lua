-- AshLight TC-BRIDGE (decision 0022): our own stdio JSON bridge that drives
-- an UNMODIFIED, pinned Path of Building PoE2 source checkout (decision 0018)
-- through PoB's own src/HeadlessWrapper.lua. Written from scratch for
-- AshLight; no code from any other PoB bridge or MCP server.
--
-- Run by server/al/theorycraft/bridge.py as: luajit.exe <this file>, with
-- the checkout's src/ as the working directory.
--
-- Protocol: one JSON request per stdin line, {"id": n, "cmd": ...}; one
-- reply per request on stdout as  ALB1 {"id": n, "ok": true, "result": {}}
-- or  ALB1 {"id": n, "ok": false, "error": "..."}. Anything PoB prints is
-- sent to stderr (or, if it bypasses print, carries no ALB1 prefix and the
-- client ignores it). One ready frame with id 0 is sent after start.
--
-- Commands: "ping", "load_build" {xml}, "set_item" {text, slot?},
-- "outputs" {keys?}, "main_skill", "support_fit", "quit"; "probe_confinement" is for the
-- tests only.
--
-- This script reads only its stdin and PoB's own files; it runs no shell,
-- opens no network connection and writes no file. Once PoB has loaded,
-- the lockdown block below takes the shell, process, file-write, native
-- library and FFI entry points away from PoB and any data it parses
-- (TC-CALC-CONFINE-LUA); PoB itself stays unmodified.

local PREFIX = "ALB1 "
local out_handle = io.stdout
local in_handle = io.stdin
-- Kept as a local: the lockdown takes debug.getupvalue away from PoB, and
-- pob_main() still needs it to find the launch object.
local getupvalue = type(debug) == "table" and debug.getupvalue or nil

-- ---------------------------------------------------------------- JSON --

local encode

local function encode_string(s)
  s = s:gsub('[%c"\\]', function(c)
    if c == '"' then return '\\"' end
    if c == "\\" then return "\\\\" end
    if c == "\n" then return "\\n" end
    if c == "\r" then return "\\r" end
    if c == "\t" then return "\\t" end
    return string.format("\\u%04x", c:byte())
  end)
  return '"' .. s .. '"'
end

local function is_array(t)
  local n = 0
  for k in pairs(t) do
    if type(k) ~= "number" or k < 1 or k % 1 ~= 0 then return false end
    n = n + 1
  end
  return n == #t
end

encode = function(v)
  local tv = type(v)
  if tv == "nil" then return "null" end
  if tv == "boolean" then return v and "true" or "false" end
  if tv == "number" then
    if v ~= v or v == math.huge or v == -math.huge then return "null" end
    return string.format("%.17g", v)
  end
  if tv == "string" then return encode_string(v) end
  if tv == "table" then
    local parts = {}
    if next(v) ~= nil and is_array(v) then
      for i = 1, #v do parts[i] = encode(v[i]) end
      return "[" .. table.concat(parts, ",") .. "]"
    end
    for k, val in pairs(v) do
      parts[#parts + 1] = encode_string(tostring(k)) .. ":" .. encode(val)
    end
    return "{" .. table.concat(parts, ",") .. "}"
  end
  return "null"
end

local function utf8_char(cp)
  if cp < 0x80 then return string.char(cp) end
  if cp < 0x800 then
    return string.char(0xC0 + math.floor(cp / 0x40), 0x80 + cp % 0x40)
  end
  if cp < 0x10000 then
    return string.char(0xE0 + math.floor(cp / 0x1000),
      0x80 + math.floor(cp / 0x40) % 0x40, 0x80 + cp % 0x40)
  end
  return string.char(0xF0 + math.floor(cp / 0x40000),
    0x80 + math.floor(cp / 0x1000) % 0x40,
    0x80 + math.floor(cp / 0x40) % 0x40, 0x80 + cp % 0x40)
end

local ESCAPES = { ['"'] = '"', ["\\"] = "\\", ["/"] = "/", b = "\b",
  f = "\f", n = "\n", r = "\r", t = "\t" }

local function decode(text)
  local pos = 1
  local value

  local function fail(msg)
    error("bad json at " .. pos .. ": " .. msg, 0)
  end

  local function skip()
    pos = text:find("[^ \t\r\n]", pos) or (#text + 1)
  end

  local function str()
    pos = pos + 1 -- opening quote
    local buf = {}
    while true do
      local c = text:sub(pos, pos)
      if c == "" then fail("unterminated string") end
      if c == '"' then pos = pos + 1; break end
      if c == "\\" then
        local e = text:sub(pos + 1, pos + 1)
        if e == "u" then
          local hex = text:sub(pos + 2, pos + 5)
          if not hex:match("^%x%x%x%x$") then fail("bad \\u escape") end
          local cp = tonumber(hex, 16)
          pos = pos + 6
          if cp >= 0xD800 and cp <= 0xDBFF and text:sub(pos, pos + 1) == "\\u" then
            local lo = tonumber(text:sub(pos + 2, pos + 5), 16)
            if lo and lo >= 0xDC00 and lo <= 0xDFFF then
              cp = 0x10000 + (cp - 0xD800) * 0x400 + (lo - 0xDC00)
              pos = pos + 6
            end
          end
          buf[#buf + 1] = utf8_char(cp)
        elseif ESCAPES[e] then
          buf[#buf + 1] = ESCAPES[e]
          pos = pos + 2
        else
          fail("bad escape")
        end
      else
        local stop = text:find('["\\]', pos) or (#text + 1)
        buf[#buf + 1] = text:sub(pos, stop - 1)
        pos = stop
      end
    end
    return table.concat(buf)
  end

  value = function()
    skip()
    local c = text:sub(pos, pos)
    if c == "{" then
      pos = pos + 1
      local obj = {}
      skip()
      if text:sub(pos, pos) == "}" then pos = pos + 1; return obj end
      while true do
        skip()
        if text:sub(pos, pos) ~= '"' then fail("object key expected") end
        local k = str()
        skip()
        if text:sub(pos, pos) ~= ":" then fail("':' expected") end
        pos = pos + 1
        obj[k] = value()
        skip()
        local d = text:sub(pos, pos)
        pos = pos + 1
        if d == "}" then return obj end
        if d ~= "," then fail("',' or '}' expected") end
      end
    elseif c == "[" then
      pos = pos + 1
      local arr = {}
      skip()
      if text:sub(pos, pos) == "]" then pos = pos + 1; return arr end
      while true do
        arr[#arr + 1] = value()
        skip()
        local d = text:sub(pos, pos)
        pos = pos + 1
        if d == "]" then return arr end
        if d ~= "," then fail("',' or ']' expected") end
      end
    elseif c == '"' then
      return str()
    elseif text:sub(pos, pos + 3) == "true" then
      pos = pos + 4; return true
    elseif text:sub(pos, pos + 4) == "false" then
      pos = pos + 5; return false
    elseif text:sub(pos, pos + 3) == "null" then
      pos = pos + 4; return nil
    else
      local num = text:match("^-?%d+%.?%d*[eE]?[-+]?%d*", pos)
      if not num or num == "" then fail("value expected") end
      pos = pos + #num
      local n = tonumber(num)
      if not n then fail("bad number") end
      return n
    end
  end

  local result = value()
  skip()
  if pos <= #text then fail("trailing data") end
  return result
end

-- ------------------------------------------------------------- frames --

local function send(id, ok, payload)
  local frame = { id = id, ok = ok }
  if ok then frame.result = payload or {} else frame.error = tostring(payload) end
  out_handle:write(PREFIX, encode(frame), "\n")
  out_handle:flush()
end

-- PoB prints progress and warnings; keep them off the protocol stream.
print = function(...)
  local parts = {}
  for i = 1, select("#", ...) do parts[i] = tostring((select(i, ...))) end
  io.stderr:write(table.concat(parts, "\t"), "\n")
end

-- --------------------------------------------------------- PoB start --

-- TC-CALC-VERIFY-USE (F-139): package loader guard. The native (C) loaders
-- of require answer only for NATIVE_ALLOW, and only until the lockdown
-- below; any other native module (a network or archive DLL) is refused, so
-- PoB or parsed data can never pull a DLL into the calc. Lua modules load
-- as before. The real loaders live on only as upvalues, which the lockdown
-- hides from debug.
local NATIVE_ALLOW = { ["lua-utf8"] = true }
local native_open = true
do
  local loaders = package.loaders or package.searchers
  if type(loaders) == "table" then
    for i = 3, #loaders do
      local real = loaders[i]
      loaders[i] = function(name)
        if native_open and NATIVE_ALLOW[name] then return real(name) end
        return "\n\tno native module '" .. tostring(name)
          .. "' (refused by the AshLight calc bridge)"
      end
    end
  end
end

-- A native module PoB requires may be missing from a plain luajit.exe run;
-- fall back to the string library for lua-utf8 (ASCII-safe subset).
if not pcall(require, "lua-utf8") then
  package.loaded["lua-utf8"] = setmetatable({ charpattern = "[\0-\x7F\xC2-\xFD][\x80-\xBF]*" },
    { __index = string })
end

-- TC-LIVE: current LuaJIT v2.1 parses a first line that starts with "#" but
-- not "#!" as a line-number directive, so PoB's files that begin with "#@"
-- (a SimpleGraphic launcher hint: HeadlessWrapper.lua, Launch.lua) fail to
-- load ("unexpected symbol near '#'"). PoB's own runtime skips that line;
-- so do we, read-only, without touching the checkout. Line numbers stay
-- (the skipped line becomes empty).
local real_loadfile = loadfile
local function pob_loadfile(name, ...)
  if type(name) ~= "string" or select("#", ...) > 0 then
    return real_loadfile(name, ...)
  end
  local ok, iter = pcall(io.lines, name)
  if not ok then return nil, tostring(iter) end
  local parts, first = {}, true
  for line in iter do
    if first and line:sub(1, 1) == "#" then line = "" end
    first = false
    parts[#parts + 1] = line
  end
  return loadstring(table.concat(parts, "\n"), "@" .. name)
end
loadfile = pob_loadfile
dofile = function(name)
  local f, err = pob_loadfile(name)
  if not f then error(err, 2) end
  return f()
end

-- HeadlessWrapper waits on io.read when PoB reports a start-up problem;
-- that would swallow our first request, so reads return nil during start.
local real_read = io.read
io.read = function() return nil end
local started, start_err = pcall(dofile, "HeadlessWrapper.lua")
io.read = real_read

-- TC-LIVE: the pinned HeadlessWrapper keeps its launch object in a LOCAL
-- (`local mainObject`, set by SetMainObject), not a global. Read it from
-- runCallback's upvalue (read-only introspection), else the old global.
-- TC-BRIDGE-NEXT: a later PoB may publish it as the global __mainObject__;
-- that shape is read first, the upvalue path stays for the current pin.
local function pob_main()
  if type(mainObject) == "table" then return mainObject end
  if type(__mainObject__) == "table" then return __mainObject__ end
  if type(runCallback) == "function" and getupvalue then
    for i = 1, 64 do
      local name, value = getupvalue(runCallback, i)
      if name == nil then break end
      if name == "mainObject" and type(value) == "table" then return value end
    end
  end
  return nil
end

local function build_mode()
  local m = pob_main()
  if not m or not m.main or not m.main.modes then
    return nil
  end
  return m.main.modes["BUILD"]
end

local function frame()
  if type(runCallback) == "function" then runCallback("OnFrame") end
end

if not started then
  send(0, false, "PoB failed to start: " .. tostring(start_err))
  return
end
if pob_main() and pob_main().promptMsg then
  send(0, false, "PoB start-up message: " .. tostring(pob_main().promptMsg))
  return
end

-- ------------------------------------------------------------ lockdown --

-- TC-CALC-CONFINE-LUA (F-138): PoB has loaded, so the entry points a calc
-- never needs are taken away before the first request: no shell or child
-- process, no native library, no FFI, no file write, rename or delete.
-- Checked against the pinned checkout: PoB's headless path calls none of
-- them (os.remove / os.rename only in build-list and update code, ffi and
-- debug nowhere). The removed calls raise; os.remove, os.rename and a
-- write-mode open return nil plus a reason, the shape of a failed file op,
-- so a stray PoB call degrades instead of breaking the calc. The job object
-- (TC-CALC-CONFINE-PROC) still stops a second process if this is bypassed.
local REFUSED = "refused by the AshLight calc bridge (read-only)"
os.execute = nil
io.popen = nil
os.tmpname = nil
os.remove = function() return nil, "os.remove " .. REFUSED end
os.rename = function() return nil, "os.rename " .. REFUSED end
package.loadlib = nil
package.cpath = ""
native_open = false -- TC-CALC-VERIFY-USE: no native require from here on
package.loaded["ffi"] = nil
if type(package.preload) == "table" then package.preload["ffi"] = nil end
rawset(_G, "ffi", nil)
local real_open = io.open
io.open = function(name, mode)
  if mode == nil or mode == "r" or mode == "rb" then return real_open(name, mode or "r") end
  return nil, tostring(name) .. ": mode " .. tostring(mode) .. " " .. REFUSED
end
local real_output = io.output
io.output = function(file)
  if type(file) == "string" then error("io.output to a file " .. REFUSED, 2) end
  return real_output(file)
end
-- The originals above live on as upvalues and locals; without these debug
-- functions no Lua code can reach them again.
if type(debug) == "table" then
  for _, k in ipairs({ "debug", "getlocal", "setlocal", "getupvalue", "setupvalue",
                       "upvalueid", "upvaluejoin", "getregistry", "setmetatable",
                       "setfenv" }) do
    debug[k] = nil
  end
end

-- ------------------------------------------------------------ commands --

local handlers = {}
local GC_CEILING_KB = 384 * 1024 -- MATH-PERF: Lua heap size that forces a full GC

handlers["ping"] = function()
  return { pong = true }
end

handlers["load_build"] = function(req)
  if type(req.xml) ~= "string" or req.xml == "" then error("xml required", 0) end
  if type(loadBuildFromXML) == "function" then
    loadBuildFromXML(req.xml, "AshLight")
  else
    local m = pob_main()
    if not m then error("PoB launch object not found", 0) end
    m.main:SetMode("BUILD", false, "AshLight", req.xml)
    frame()
  end
  frame()
  local build = build_mode()
  if not build or not build.calcsTab then error("PoB did not load the build", 0) end
  -- TC-LIVE: a load does not always recalculate on the next frame (seen
  -- with a sparse build after a full one: the old mainOutput stayed), so
  -- rebuild the output once here; reads never see a stale build.
  if type(build.calcsTab.BuildOutput) == "function" then
    build.calcsTab:BuildOutput()
  end
  -- MATH-PERF (decision 0028): every load leaves the old build as garbage
  -- (~20 MB for a real level 90 build) and LuaJIT's default GC pause let
  -- the heap reach ~600 MB (working set ~900 MB, never returned to the OS)
  -- over one item check's reloads. A full collect only when the heap is
  -- past the ceiling keeps the working set near 500 MB at no median cost.
  if collectgarbage("count") > GC_CEILING_KB then collectgarbage("collect") end
  return { loaded = true }
end

handlers["set_item"] = function(req)
  local build = build_mode()
  if not build or not build.itemsTab then error("no build loaded", 0) end
  if type(req.text) ~= "string" or req.text == "" then error("text required", 0) end
  local text = req.text:gsub("\r\n", "\n")
  local item = new("Item", text)
  if not item or not item.base then error("PoB did not recognise the item", 0) end
  if item.NormaliseQuality then item:NormaliseQuality() end
  local slotName = req.slot
  if not slotName and item.GetPrimarySlot then slotName = item:GetPrimarySlot() end
  local slot = slotName and build.itemsTab.slots[slotName]
  if not slot then error("no such slot: " .. tostring(slotName), 0) end
  build.itemsTab:AddItem(item, true)
  slot:SetSelItemId(item.id)
  build.itemsTab:PopulateSlots()
  build.itemsTab:AddUndoState()
  build.buildFlag = true
  frame()
  return { slot = slotName }
end

handlers["outputs"] = function(req)
  local build = build_mode()
  if not build or not build.calcsTab then error("no build loaded", 0) end
  frame()
  local main = build.calcsTab.mainOutput
  if type(main) ~= "table" then error("PoB produced no output", 0) end
  local want
  if type(req.keys) == "table" then
    want = {}
    for _, k in ipairs(req.keys) do want[k] = true end
  end
  local result = {}
  for k, v in pairs(main) do
    if type(k) == "string" and (not want or want[k]) then
      if type(v) == "boolean" then
        result[k] = v
      elseif type(v) == "number" and v == v and v ~= math.huge and v ~= -math.huge then
        result[k] = v
      end
    end
  end
  -- AREA-AUDIT P7-1: PoB sets some outputs only in its CALCS pass
  -- (`if breakdown then`: FlaskChargeGen, CharmEffect, ...). A REQUESTED
  -- key the main table lacks comes from PoB's own calcsOutput (same build,
  -- same frame); a keyless read stays the main table alone.
  local calcs = build.calcsTab.calcsOutput
  if want and type(calcs) == "table" then
    for k in pairs(want) do
      local v = calcs[k]
      if result[k] == nil and main[k] == nil then
        if type(v) == "boolean" then
          result[k] = v
        elseif type(v) == "number" and v == v and v ~= math.huge and v ~= -math.huge then
          result[k] = v
        end
      end
    end
  end
  return { outputs = result }
end

-- MATH-WEAPON-TYPE (decision 0032 amendment): PoB's own verdict on the main
-- skill after the last calc: is it disabled, and PoB's reason (e.g. "Main
-- Hand weapon is not usable with this skill", CalcActiveSkill.lua). Read
-- only; no recalculation (the preceding "outputs" already ran the frame).
handlers["main_skill"] = function()
  local build = build_mode()
  if not build or not build.calcsTab then error("no build loaded", 0) end
  local env = build.calcsTab.mainEnv
  local skill = type(env) == "table" and type(env.player) == "table" and env.player.mainSkill
  if type(skill) ~= "table" then return { found = false } end
  local disabled = false
  local eff = skill.activeEffect
  if type(eff) == "table" and type(eff.statSet) == "table"
      and type(eff.statSet.skillFlags) == "table" and eff.statSet.skillFlags.disable then
    disabled = true
  end
  if type(skill.skillFlags) == "table" and skill.skillFlags.disable then disabled = true end
  local name
  if type(eff) == "table" and type(eff.grantedEffect) == "table" then
    name = eff.grantedEffect.name
  end
  local reason = skill.disableReason
  return { found = true, disabled = disabled,
           reason = type(reason) == "string" and reason or nil,
           name = type(name) == "string" and name or nil }
end

-- KINDLER-SUPPORT-FIT (decision 0081): PoB's own answer, per active skill of
-- the loaded build, whether each linked support applies to it. PoB decides
-- it in calcs.createActiveSkill (CalcActiveSkill.lua): a support that
-- calcLib.canGrantedEffectSupportActiveSkill accepts goes into the skill's
-- effectList after the active effect; a rejected one stays only in its
-- supportList. Read only; no own rule, nothing guessed: a linked gem PoB
-- did not recognise is in neither list and is not reported.
local function effect_name(eff)
  if type(eff) ~= "table" then return nil end
  if type(eff.gemData) == "table" and type(eff.gemData.name) == "string" then
    return eff.gemData.name
  end
  if type(eff.grantedEffect) == "table" and type(eff.grantedEffect.name) == "string" then
    return eff.grantedEffect.name
  end
  return nil
end

handlers["support_fit"] = function()
  local build = build_mode()
  if not build or not build.calcsTab then error("no build loaded", 0) end
  frame()
  local env = build.calcsTab.mainEnv
  local list = type(env) == "table" and type(env.player) == "table"
    and env.player.activeSkillList
  local skills = {}
  if type(list) ~= "table" then return { skills = skills } end
  for _, active in ipairs(list) do
    local name = type(active) == "table" and effect_name(active.activeEffect)
    if name and type(active.supportList) == "table" then
      local used = {}
      if type(active.effectList) == "table" then
        for i = 2, #active.effectList do used[active.effectList[i]] = true end
      end
      local sups = {}
      for _, sup in ipairs(active.supportList) do
        local sname = effect_name(sup)
        if sname then sups[#sups + 1] = { name = sname, applies = used[sup] == true } end
      end
      skills[#skills + 1] = { skill = name, supports = sups }
    end
  end
  return { skills = skills }
end

-- TC-CALC-CONFINE-LUA: test-only (tests/test_tc_bridge.py); the core never
-- sends it. It tries each locked entry point with harmless arguments and
-- reports what happened: os.execute() with no command, a write-mode open
-- of a probe file under TEMP, a read of PoB's own HeadlessWrapper.lua.
handlers["probe_confinement"] = function()
  local function attempt(f)
    local ok, a, b = pcall(f)
    if not ok then return { ok = false, error = tostring(a) } end
    return { ok = a ~= nil, error = b ~= nil and tostring(b) or nil }
  end
  local probe = (os.getenv("TEMP") or ".") .. "/alb-confine-probe.txt"
  local writes = {}
  for _, mode in ipairs({ "w", "wb", "a", "a+", "r+", "w+b" }) do
    writes[mode] = attempt(function()
      local f, err = io.open(probe, mode)
      if f then f:close() end
      return f, err
    end)
  end
  local reads = attempt(function()
    local f, err = io.open("HeadlessWrapper.lua", "r")
    if f then f:close() end
    return f, err
  end)
  local ffi_ok = pcall(require, "ffi")
  -- TC-CALC-VERIFY-USE: native requires (both DLLs sit in PoB's runtime)
  local native = {}
  for _, name in ipairs({ "socket", "lzip" }) do
    local ok, err = pcall(require, name)
    native[name] = { ok = ok, error = not ok and tostring(err) or nil }
  end
  return {
    native = native,
    execute = attempt(function() return os.execute() end),
    popen = type(io.popen),
    tmpname = type(os.tmpname),
    loadlib = type(package.loadlib),
    cpath = package.cpath,
    ffi = ffi_ok,
    remove = attempt(function() return os.remove(probe) end),
    rename = attempt(function() return os.rename(probe, probe .. ".x") end),
    output = attempt(function() return io.output(probe) end),
    getupvalue = type(debug) == "table" and type(debug.getupvalue) or "nil",
    getlocal = type(debug) == "table" and type(debug.getlocal) or "nil",
    writes = writes,
    read = reads,
  }
end

-- ---------------------------------------------------------------- loop --

send(0, true, { ready = true })

while true do
  local line = in_handle:read("*l")
  if not line then break end
  if line:find("%S") then
    local ok, req = pcall(decode, line)
    if not ok or type(req) ~= "table" then
      send(nil, false, "bad request: " .. tostring(req))
    elseif req.cmd == "quit" then
      send(req.id, true, {})
      break
    else
      local handler = handlers[req.cmd]
      if not handler then
        send(req.id, false, "unknown command: " .. tostring(req.cmd))
      else
        local hok, result = pcall(handler, req)
        if hok then send(req.id, true, result) else send(req.id, false, result) end
      end
    end
  end
end
