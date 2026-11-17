# Third-party notices

AshLight's own code is Apache-2.0 (LICENSE, NOTICE). This file lists
third-party software AshLight can use. Nothing below is bundled in this
repository: the optional theorycraft calc component is fetched on the
user's machine by `scripts/setup.ps1 -TcCalc` (off by default) from the
upstream projects, at the exact versions and SHA-256 hashes pinned in
`config/tc_pins.json`, and run unmodified as a separate process
(decisions 0004 and 0017). The license check is recorded in
`docs/decisions/0017-tc-pin.md`.

## Path of Building Community (PoE2)

- Source: https://github.com/PathOfBuildingCommunity/PathOfBuilding-PoE2
- Pinned: tag v0.23.1, commit 7d6f530cbdab20389ff8bc6ba97a37ac27f74e41
- License: MIT (text below, from LICENSE.md at the pinned commit,
  read 2026-11-17)

```
Copyright (c) 2016 David Gowor

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

### Components inside Path of Building

PoB's LICENSE.md also carries the notices of the components it ships. The
full texts arrive with the fetched source (`LICENSE.md` at the root of the
checkout in the sidecar Cache) and are not repeated here. Sections present
at the pinned commit: PUC-Rio Lua interpreter (in Update.exe), Lua-cURL,
libcurl, base64.lua, dkjson.lua, lua-profiler.lua, sha1, sha2, xml.lua,
Bitstream Vera font family, Liberation font family, SimpleGraphic, Khronos
Cross-Platform Standards, GLEXT, LuaJIT, fmtlib, libsodium, re2, abseil,
ANGLE, stb, libjpeg-turbo, GIFLIB, luasocket, lua-utf8. AshLight's bridge
(TC-BRIDGE) runs only PoB's Lua sources through LuaJIT; it does not run
PoB's GUI binaries.

## LuaJIT

- Source: https://github.com/LuaJIT/LuaJIT (rolling releases, branch v2.1)
- Pinned: version 2.1.1794386141, commit
  63c8f1a9b479ba5518cf6a170ff7729178bc3cfd
- License: MIT, with the Lua 5.1/5.2 MIT notice and a public-domain
  dlmalloc notice (text below, from COPYRIGHT at the pinned commit, read
  2026-11-17)

```
LuaJIT -- a Just-In-Time Compiler for Lua. https://luajit.org/

Copyright (C) 2005-2026 Mike Pall. All rights reserved.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.  IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.

[ MIT license: https://www.opensource.org/licenses/mit-license.php ]

[ LuaJIT includes code from Lua 5.1/5.2, which has this license statement: ]

Copyright (C) 1994-2012 Lua.org, PUC-Rio.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.  IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.

[ LuaJIT includes code from dlmalloc, which has this license statement: ]

This is a version (aka dlmalloc) of malloc/free/realloc written by
Doug Lea and released to the public domain, as explained at
https://creativecommons.org/licenses/publicdomain
```
