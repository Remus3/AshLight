# Test coverage (TEST-COVER)

Generated 2026-11-17 by `python tools/cover.py` (stdlib line tracer, no
coverage package). Lines run in a child process (a spawned core, the
keepalive supervisor, PowerShell scripts, the Electron overlay) are not
counted, so modules driven only that way read lower than they are.
pytest exit code 0; run took 92 s.

- total: 89.1% of 10202 executable lines (server/ 93.1% of 5673, tools/ the rest)
- modules with no line run: 2
- modules under 60%: 2

Driven only in a child process, so low here but tested: tools/wt_sidecar_hook.py (tests/test_wt_sidecar_hook.py runs it as the harness hook), tools/install_hooks.py (one hooks-path config call), the core main loop in server/al/__main__.py (tests/test_keepalive.py end to end) and tools/lane_samples.py (lane fixtures run through subprocess lanes).

## Untested modules (no line run in the suite)

- tools/wt_sidecar_hook.py: 80 lines
- tools/install_hooks.py: 11 lines

## Weakest modules (under 60%)

- tools/lane_samples.py: 28.1% of 160
- server/al/__main__.py: 38.7% of 163

## Every module (lowest first)

One line per module: percent, executable lines, missed line ranges.

- tools/wt_sidecar_hook.py: 0.0% of 80; missed 21-25, 27-29, 31, 33, 36-38, 41-45, 48-54, 57-73, 75-78, 81-89, 91-94, 96-99, 102-111, 113-117, 120-121
- tools/install_hooks.py: 0.0% of 11; missed 8-10, 12, 15-19, 22-23
- tools/lane_samples.py: 28.1% of 160; missed 49, 57-61, 72-81, 87-89, 91-95, 97-100, 102-106, 111-115, 119-120, 125, 130-133, 139-151, 157-169, 177-203, 207-217, 221-225, 229
- server/al/__main__.py: 38.7% of 163; missed 41-59, 117-122, 124-127, 129-144, 146-149, 151, 153-154, 156-162, 164-203, 207
- tools/cover.py: 61.6% of 164; missed 43-49, 58-59, 89, 91-95, 98-108, 116, 136-145, 153, 185, 195, 202-208, 210-215, 217-225, 229
- tools/design_gate.py: 64.9% of 37; missed 44-51, 55-58, 62
- tools/usage_ledger.py: 71.0% of 193; missed 45, 76-84, 93, 100, 161-165, 171-177, 184-196, 201-207, 243-248, 263-264, 266-268, 275
- tools/leak_sweep.py: 77.6% of 263; missed 70-71, 76, 82, 87-88, 111, 120, 128, 171, 187-188, 200-214, 226, 248, 296-297, 321-323, 325-328, 332-335, 337, 345-349, 351-360, 365
- tools/eta.py: 80.8% of 99; missed 56, 59, 113-115, 119-123, 126-133, 137
- tools/tc_pin.py: 84.8% of 342; missed 47, 100-101, 112, 115, 130-131, 158, 197, 203-204, 209, 220-240, 248-249, 260-261, 305, 322-323, 327, 332, 359-360, 372, 397, 469-473, 477
- server/al/theorycraft/bridge.py: 85.4% of 254; missed 79-80, 87, 144-149, 153-154, 169-171, 182-185, 212-213, 216-217, 222-223, 228-232, 240-241, 256-258, 285, 288, 307
- server/al/keepalive.py: 88.4% of 328; missed 74, 82, 91, 95, 100, 116, 121, 125, 133-140, 142, 167-168, 181-182, 192-198, 238-239, 266-267, 378-379, 414-416, 422
- server/al/theorycraft/snapshot.py: 88.8% of 178; missed 95-96, 110-111, 117-130, 211, 249
- tools/synth_client.py: 89.6% of 134; missed 172-184, 188
- server/al/paths.py: 90.3% of 93; missed 53-54, 69, 74, 152-155, 159
- tools/al_loop.py: 90.5% of 1287; missed 148, 187-188, 239-242, 276-280, 285-290, 302, 333, 340-341, 348-351, 376, 387-388, 390, 392-393, 486, 565-569, 644, 653-654, 672-673, 708-709, 724-730, 762, 770, 798, 812, 836, 886-887, 948, 1015-1018, 1030, 1033, 1037, 1041, 1045, 1047, 1061, 1063-1064, 1073-1074, 1077-1078, 1093, 1193-1194, ...
- server/al/procs.py: 90.6% of 233; missed 64, 86, 107, 126-127, 138-139, 239, 265, 267, 270-274, 277-280, 323, 326, 334
- server/al/upgrade.py: 90.7% of 43; missed 67, 71-72, 74
- tools/al_lane.py: 91.3% of 265; missed 123-124, 136-137, 209, 224, 228, 318, 329, 331, 346, 376-382, 400-401, 414-415, 423
- server/al/theorycraft/store.py: 91.8% of 61; missed 47-49, 73-74
- tools/loop_inbox.py: 91.9% of 541; missed 109-110, 160-161, 296, 299-300, 324, 327-328, 369, 392, 405-406, 449-450, 458-461, 465-466, 526, 563-564, 586-588, 590-591, 614, 633, 635, 646-647, 715-716, 722, 728, 760, 773, 779-781
- server/al/gfx.py: 91.9% of 198; missed 57-71, 114
- server/al/logfile.py: 91.9% of 223; missed 35, 38-39, 51-52, 78, 108, 143, 146, 152, 192, 211-212, 224-225, 273, 289, 299
- server/al/webfetch.py: 92.4% of 132; missed 80-83, 122-123, 173-174, 218, 221
- server/al/resume.py: 92.9% of 154; missed 48, 77-80, 119, 135, 186, 189-190, 198
- tools/loop_task.py: 93.0% of 128; missed 47, 53-55, 189-190, 192, 217, 230
- server/al/theorycraft/codec.py: 93.1% of 102; missed 48, 55, 72-73, 89, 112, 158
- tools/ledger_rotate.py: 93.4% of 198; missed 51, 61-62, 159-164, 197-198, 267, 272
- tools/loop_merge.py: 94.0% of 166; missed 65, 68, 120, 122-123, 159, 201, 204, 223, 226
- server/al/ninja.py: 94.4% of 216; missed 66-67, 162-163, 189, 195, 197-200, 210, 250
- tools/loop_roadmap.py: 94.9% of 216; missed 42, 227, 279-280, 312-314, 325-326, 334-335
- server/al/http.py: 95.2% of 478; missed 72, 109-112, 114, 223, 260, 286, 319-320, 342, 346, 377-378, 400, 412, 438, 474, 524, 531, 542, 607
- server/al/trade.py: 95.2% of 63; missed 87, 125-126
- server/al/theorycraft/weights.py: 95.3% of 171; missed 98, 143, 159, 198-199, 201-203
- server/al/core.py: 95.9% of 220; missed 38-39, 55, 57, 182, 220, 288, 293, 296
- server/al/theorycraft/datacredit.py: 96.2% of 26; missed 24
- server/al/theorycraft/item.py: 96.3% of 246; missed 56-57, 96, 112, 146-147, 196, 232-233
- server/al/theorycraft/charjson.py: 96.5% of 171; missed 165-166, 173, 207, 238, 240
- server/al/theorycraft/evaluate.py: 96.8% of 158; missed 63-64, 66, 78, 197
- tools/loop_base.py: 97.5% of 203; missed 209, 217, 220-221, 289
- server/al/acts.py: 97.6% of 164; missed 167, 187, 195, 228
- server/al/theorycraft/delta.py: 97.6% of 84; missed 57, 144
- server/al/layout.py: 98.0% of 99; missed 57, 119
- server/al/theorycraft/shareurl.py: 98.2% of 56; missed 52
- server/al/theorycraft/treedata.py: 98.7% of 150; missed 60, 209
- server/al/parser.py: 98.8% of 168; missed 85-86
- server/al/theorycraft/model.py: 99.1% of 221; missed 188, 239
- server/al/state.py: 99.5% of 589; missed 167-168, 334
- server/al/theorycraft/live.py: 100.0% of 79
- server/al/bus.py: 100.0% of 74
- server/al/price.py: 100.0% of 60
- tools/loop_prompts.py: 100.0% of 42
- server/al/theorycraft/paste.py: 100.0% of 10
- server/al/ports.py: 100.0% of 5
- server/al/__init__.py: 100.0% of 3
