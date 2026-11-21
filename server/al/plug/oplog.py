"""RUN-OPLOG (F-153, decision 0067): the own-event log through the plug seam
(decision 0056).

attach() gives the core an oplog.OpLog writing events.jsonl to the sidecar
Logs dir (a test or demo core: its own runtime dir, never the sidecar),
subscribes it to metrics.emit (fetch, calc, press) and to the bus (tailer
status events), and adds one tick that compares the consent, web data,
reload and calc start state once a second (oplog.SwitchWatch). No edit of
webfetch.py, bridge.py or core.py: those already emit or publish.
"""

from .. import oplog, paths

ORDER = 850  # after budget (800), before debug (900)


def log_path(core):
    if getattr(core, "_real", False):
        return paths.sidecar_dir("Logs") / oplog.FILE_NAME
    return core.runtime / oplog.FILE_NAME


def attach(core):
    log = oplog.OpLog(log_path(core))
    core.oplog = log
    log.watch_metrics()
    core.bus.add_listener(log.on_bus)
    core.oplog_watch = oplog.SwitchWatch(core, log)
    core.add_tick("tick_oplog", core.oplog_watch.tick)

