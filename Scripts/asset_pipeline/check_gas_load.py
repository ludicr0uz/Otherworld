"""check_gas_load.py -- load what import_gas.py copied and say what the engine
complained of while it did.  Editor side.

    python3 Scripts/dev/uepy.py Scripts/asset_pipeline/check_gas_load.py

Loads SandboxCharacter_CMC_ABP, every PoseSearch database and chooser under
/Game/GAS, then every other package of gas_manifest.txt, and reads the
editor's own log back between two markers: a package the copy left behind
shows there as a warning (a failed import, a missing class from a plugin that
is not enabled), not as a Python error.  The result is also written to
Saved/gas_load.txt.  Raises when a package did not load or a line of the log
names a missing asset, so uepy.py exits non-zero.
"""
import glob
import os
import sys
import time

import unreal

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
for _m in [m for m in sys.modules if m.split(".")[0] == "asset_pipeline"]:
    del sys.modules[_m]

from asset_pipeline.gas_paths import ABP, GAME_ROOT, gas  # noqa: E402

MANIFEST = os.path.join(HERE, "gas_manifest.txt")
OUT = os.path.join(unreal.Paths.convert_relative_path_to_full(
    unreal.Paths.project_saved_dir()), "gas_load.txt")

# What a missing package, class or plugin looks like in the log.
BAD = ("Failed to load", "Can't find file", "VerifyImport", "Failed to find",
       "Missing Class", "missing-asset", "Unable to load", "CreateExport",
       "Failed import", "unknown class", "Could not find", "LoadErrors")


def _log_file():
    logs = glob.glob(os.path.join(unreal.Paths.convert_relative_path_to_full(
        unreal.Paths.project_log_dir()), "*.log"))
    return max(logs, key=os.path.getmtime) if logs else None


def _between(path, start, end):
    with open(path, errors="replace") as f:
        text = f.read()
    a = text.rfind(start)
    b = text.rfind(end)
    return text[a:b if b > a else None].splitlines() if a >= 0 else None


def _of_class(reg, name):
    flt = unreal.ARFilter(package_paths=[GAME_ROOT], recursive_paths=True)
    return sorted(str(a.package_name) for a in reg.get_assets(flt) or []
                  if str(a.asset_class_path.asset_name) == name)


def main():
    stamp = f"GAS-LOAD-{int(time.time())}"
    reg = unreal.AssetRegistryHelpers.get_asset_registry()
    reg.scan_paths_synchronous([GAME_ROOT], True)
    databases = _of_class(reg, "PoseSearchDatabase")
    choosers = _of_class(reg, "ChooserTable")
    with open(MANIFEST) as f:
        rest = [gas(line.strip()) for line in f if line.strip()]
    unreal.log_warning(f"{stamp} begin")
    failed = []
    order = [ABP] + databases + choosers
    order += [p for p in rest if p not in set(order)]
    with unreal.ScopedSlowTask(len(order), "Loading GAS") as task:
        for pkg in order:
            task.enter_progress_frame(1)
            if unreal.EditorAssetLibrary.load_asset(pkg) is None:
                failed.append(pkg)
    abp = unreal.EditorAssetLibrary.load_asset(ABP)
    status = abp.get_editor_property("status") if abp else None
    if abp and status == unreal.BlueprintStatus.BS_ERROR:
        failed.append(f"{ABP} (loads, does not compile)")
    unreal.log_warning(f"{stamp} end")
    unreal.SystemLibrary.execute_console_command(None, "log flush")

    log = _log_file()
    lines = _between(log, f"{stamp} begin", f"{stamp} end") if log else None
    bad = [l for l in (lines or []) if any(b in l for b in BAD)]
    noisy = [l for l in (lines or [])
             if ("Warning:" in l or "Error:" in l) and l not in bad
             and stamp not in l]
    report = [
        f"anim blueprint: {ABP} ({status})",
        f"pose search databases: {len(databases)}",
        f"choosers: {len(choosers)}",
        f"packages loaded: {len(order) - len(failed)} of {len(order)}",
        f"log: {log} ({'not read' if lines is None else len(lines)} lines)",
        f"did not load: {len(failed)}", *("  " + p for p in failed),
        f"missing-asset lines: {len(bad)}", *("  " + l for l in bad),
        f"other warnings and errors: {len(noisy)}", *("  " + l for l in noisy),
    ]
    with open(OUT, "w") as f:
        f.write("\n".join(report) + "\n")
    for line in report[:5] + [report[5], f"missing-asset lines: {len(bad)}",
                              f"other warnings and errors: {len(noisy)}"]:
        unreal.log_warning("[GAS] " + line)
    unreal.log_warning(f"[GAS] full report: {OUT}")
    if lines is None:
        raise RuntimeError("the editor's log could not be read back")
    if not databases or failed or bad:
        raise RuntimeError(f"GAS did not load clean: {len(failed)} packages "
                           f"failed, {len(bad)} missing-asset lines ({OUT})")


main()
