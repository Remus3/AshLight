# Second-screen dashboard technology

Scope: a dashboard served on 127.0.0.1 for a second monitor (optionally phone/tablet on LAN) alongside a PoE2 overlay. Research date 2026-11-16. Items not confirmed by a source are marked UNVERIFIED.

## Transport: SSE vs WebSocket

- SSE is one-way server to client over plain HTTP, auto-reconnects by default, uses Content-Type text/event-stream with blank-line-separated messages, supports event/data/id/retry fields and colon comment lines usable as keep-alives. https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events (accessed 2026-11-16)
- SSE over HTTP/1 is limited to about 6 connections per browser per domain (shared across tabs); HTTP/2 negotiates about 100. Local plain HTTP is HTTP/1, so keep one EventSource per page and avoid many tabs. Same source (accessed 2026-11-16)
- WebSocket is bidirectional; needed only if the dashboard sends frequent commands. Commands can instead be plain POST requests with SSE for the push path (design choice, not from a source). WebSocket needs explicit Origin checking (see security).
- Basis for the recommendation: the dashboard is mostly read-only telemetry, so SSE means less code, built-in reconnect and no framing library.

## Where to show it

- Edge `--app=URL` gives a site its own standalone window without tabs; stated by an Edge engineer's tips post, no official Microsoft Learn page found. https://textslashplain.com/2022/06/03/microsoft-edge-tips-and-tricks (accessed 2026-11-16) Behaviour on current builds: UNVERIFIED, test. Edge preinstalled on Windows 10/11: UNVERIFIED citation.
- Plain browser tab: zero extra code; background-tab timer throttling rules in current Chromium: UNVERIFIED.
- Electron/Tauri secondary window: extra processes and RAM; WebView2 uses separate browser, renderer and GPU processes per user data folder. https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/process-model (accessed 2026-11-16) Worth it only if the overlay already ships that runtime.
- Phone/tablet on LAN: useful but widens the attack surface; see below.

## Server choice

- Node built-in http module, no framework: smallest dependency set, native streaming for SSE, same language as an Electron overlay. Python aiohttp/FastAPI: viable but adds an interpreter and packaging weight. No benchmark comparing them for this workload was found; at a few clients and 4-10 Hz either is far below any limit (reasoned, UNVERIFIED).
- Bundle all static assets (HTML, JS, CSS, fonts) in the app; no CDN at runtime so the page works offline and leaks no third-party request.

## Security

- Bind 127.0.0.1 only by default; LAN exposure is an explicit opt-in, off by default, with a per-start random token required on every request and a visible indicator when LAN mode is on (design requirements).
- DNS rebinding: a hostile page can make the browser reach a local server under an attacker hostname. Mitigation is validating the Host header against an allowlist (localhost, 127.0.0.1, [::1], and the LAN IP only in LAN mode) and returning 400 otherwise; also validate Origin and require authentication even on localhost. https://docs.gitlab.com/user/application_security/api_security_testing/checks/dns_rebinding_check/ and https://github.com/nccgroup/singularity/wiki/Preventing-DNS-Rebinding-Attacks (accessed 2026-11-16) The MCP TypeScript SDK ships a Host-validation middleware allowing only localhost, 127.0.0.1 and [::1]. https://ts.sdk.modelcontextprotocol.io/v2/api/@modelcontextprotocol/node/middleware/hostHeaderValidation.html (accessed 2026-11-16)
- The MDN DNS rebinding page was not retrievable at the URL tried (404); no MDN citation is made.
- CSP: send a strict Content-Security-Policy (default-src 'self', no inline script, connect-src 'self') plus X-Content-Type-Options nosniff; exact values not checked against a source here: UNVERIFIED, verify against MDN CSP docs when implementing.
- Cross-site request risk for POST commands: require a custom token header (forces CORS preflight) and reject non-matching Origin. Reasoned, UNVERIFIED.

## Glanceable, low-distraction UI

- Glanceability research (Matthews, Forlizzi, Rohrbach, UC Berkeley) defines glanceability as how quickly and easily the visual design conveys information once the user is attending to the display, strongly affected by amount and type of information; peripheral displays must be readable with minimal interruption to the primary task. https://www2.eecs.berkeley.edu/Pubs/TechRpts/2006/EECS-2006-113.html (accessed 2026-11-16) Their work gives a taxonomy of visual variables (such as color and shape) and abstraction techniques such as change detection and feature extraction. https://www2.eecs.berkeley.edu/Pubs/TechRpts/2007/EECS-2007-56.html (accessed 2026-11-16)
- Design rules (derived from the sources above and below):
  - Large type, few items per view; show status and deltas, not raw logs (glanceability sources above).
  - High contrast, dark default: WCAG 2.2 SC 1.4.3 requires 4.5:1 for text (3:1 large) and SC 1.4.6 asks 7:1; target 7:1 for glance text. https://www.w3.org/TR/WCAG22/#contrast-minimum and https://www.w3.org/TR/WCAG22/#contrast-enhanced (accessed 2026-11-16)
  - Color is a secondary signal: SC 1.4.1 says color must not be the only visual means of conveying information; Xbox guidance warns red and green alone fail colorblind players and recommends pairing color with shape or text. https://www.w3.org/TR/WCAG22/#use-of-color and https://learn.microsoft.com/en-us/gaming/accessibility/xbox-accessibility-guidelines/102 (accessed 2026-11-16) (the Xbox numeric contrast table was not retrieved: UNVERIFIED)
  - Minimal motion: SC 2.2.2 requires a way to pause, stop or hide moving, blinking or auto-updating content lasting over 5 seconds; SC 2.3.3 (AAA) lets users disable interaction-triggered animation. Default to no animation and honour prefers-reduced-motion. https://www.w3.org/TR/WCAG22/#pause-stop-hide and https://www.w3.org/TR/WCAG22/#animation-from-interactions (accessed 2026-11-16)
  - Player-configurable text size and a high-contrast mode, in line with Xbox text guidance. https://learn.microsoft.com/en-us/gaming/accessibility/xbox-accessibility-guidelines/101 (accessed 2026-11-16)
  - Update throttling: coalesce changes and repaint at most 4-10 Hz; highlight only on meaningful state change, never for continuous values (design rule).

## Performance

- Fan-out: one in-process event bus, one latest-state object, one serialization per tick, broadcast the same string to all SSE clients; drop intermediate states for slow clients (latest wins) instead of queueing.
- Throttle to 4-10 Hz; send snapshots or diffs; send a comment-line keep-alive every 15-30 s (MDN permits comment lines as keep-alives; the interval is a design choice).
- Long sessions: fixed-length ring buffers (for example 10-20 minutes at 1 Hz downsampled), remove scrolled-out DOM rows, run a 4-hour soak watching heap in DevTools. No published budget found (UNVERIFIED); proposal only.
- Idle: with no clients connected, do no serialization work.

## Recommendation

1. Node built-in http server on 127.0.0.1, SSE push over one EventSource, token-gated POST for commands; no framework, bundled static assets, no CDN.
2. Open in an Edge `--app` window on the second monitor by default; plain browser tab as fallback; LAN access off by default, enabled per session with a token URL and a Host allowlist that includes the LAN IP.
3. Enforce the per-start random token, Host and Origin allowlists, strict CSP and nosniff; reject everything else with 400/403.
4. UI: dark default, 7:1 text contrast, large type, color plus icon or text, no animation by default, 4-10 Hz coalesced updates.
5. Test: DNS-rebinding probe (hostile Host header), 4-hour soak for heap growth, PresentMon run with dashboard open to confirm no FPS change, phone on LAN with token missing or wrong.

## Sources

- https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events
- https://textslashplain.com/2022/06/03/microsoft-edge-tips-and-tricks
- https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/process-model
- https://docs.gitlab.com/user/application_security/api_security_testing/checks/dns_rebinding_check/
- https://github.com/nccgroup/singularity/wiki/Preventing-DNS-Rebinding-Attacks
- https://ts.sdk.modelcontextprotocol.io/v2/api/@modelcontextprotocol/node/middleware/hostHeaderValidation.html
- https://www2.eecs.berkeley.edu/Pubs/TechRpts/2006/EECS-2006-113.html
- https://www2.eecs.berkeley.edu/Pubs/TechRpts/2007/EECS-2007-56.html
- https://www.w3.org/TR/WCAG22/
- https://learn.microsoft.com/en-us/gaming/accessibility/xbox-accessibility-guidelines/101
- https://learn.microsoft.com/en-us/gaming/accessibility/xbox-accessibility-guidelines/102
