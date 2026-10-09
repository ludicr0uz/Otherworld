"""The graphics benchmark, short form, for the 1 km map and for more pixels.

    python3 Scripts/dev/uepy.py --game --windowed --map /Game/Maps/Lvl_Forest_1000m \
        --probe-timeout 500 --probe Scripts/probes/probe_perf_audit_1km.py

Results go to Saved/uepy/bench/bench_1km.json. See probe_perf_audit.py.
"""

LEVEL = "/Game/Maps/Lvl_Forest_1000m"  # benchmarks the 1 km map
SYSTEMS = ('load',)

from probes import probe_perf_audit as B

B.OUT_NAME = "bench_1km.json"
WRITABLE = B.WRITABLE
unreal = B.unreal


def probe(p):
    def live():
        try:
            hud = p.hud()
        except Exception:
            return None
        return hud if hud is not None and p.get(hud, B.PROFILE_CHECKED_VAR) else None

    yield lambda: live() is not None
    hud, cycle = live(), p.actor_of(B.DAY_NIGHT_CLASS_PATH)
    tuner = p.get(hud, B.GC.TUNER_COMPONENT)
    yield lambda: p.get(hud, B.GC.GFX_APPLIED_VAR) == 0 and not p.get(tuner, B.GC.TUNER_DIRTY_VAR)
    B._cmd(p, "t.MaxFPS 0")
    B._cmd(p, "r.VSync 0")
    yield 5.0
    trees = B._trees(p)
    spot, yaw, n_near, n_all = B._forest_spot(p, trees)
    B._log(f"forest spot {spot.x:.0f},{spot.y:.0f}: {n_near} of {n_all} trees in 35 m")
    pawn, pc = p.pawn(), p.controller()
    pawn.set_actor_location(spot, False, True)
    pc.set_control_rotation(unreal.Rotator(pitch=12.0, yaw=yaw, roll=0.0))
    yield 3.0
    for q, name in ((0, "Low"), (1, "Medium"), (2, "High")):
        yield from B._preset(p, hud, tuner, q)
        pc.set_control_rotation(unreal.Rotator(pitch=12.0, yaw=yaw, roll=0.0))
        yield from B._measure(p, cycle, f"1km forest noon {name}", 12.0)
        sp = B.SL.get_console_variable_float_value("r.ScreenPercentage")
        # 2.4x the edge: the pixels of a 3024x1964 screen from a 1280x720 window.
        B._cmd(p, f"r.ScreenPercentage {min(sp * 2.4, 240):.0f}")
        yield from B._measure(p, cycle, f"1km forest noon {name}, native-retina pixels", 12.0)
        B._cmd(p, f"r.ScreenPercentage {sp:.0f}")
    yield from B._preset(p, hud, tuner, 1)
    yield from B._measure(p, cycle, "1km MED baseline", 12.0)
    B._cmd(p, "ProfileGPU")
    yield 1.0
    B._hide(p, trees, True)
    yield from B._measure(p, cycle, "1km MED + trees hidden", 12.0)
    B._hide(p, trees, False)
    yield from B._toggles(p, cycle, "1km MED", 12.0, (
        ("MaxPixelsPerEdge 2", ["r.Nanite.MaxPixelsPerEdge 2"], ["r.Nanite.MaxPixelsPerEdge 1"]),
        ("MaxPixelsPerEdge 4", ["r.Nanite.MaxPixelsPerEdge 4"], ["r.Nanite.MaxPixelsPerEdge 1"]),
        ("shadows off", ["r.ShadowQuality 0"], ["r.ShadowQuality 2"]),
        ("leaf cut-outs off", ["r.Nanite.ProgrammableRaster 0"], ["r.Nanite.ProgrammableRaster 1"]),
        ("retina pixels (204%)", ["r.ScreenPercentage 204"], ["r.ScreenPercentage 85"]),
        ("retina pixels + MaxPixelsPerEdge 4",
         ["r.ScreenPercentage 204", "r.Nanite.MaxPixelsPerEdge 4"],
         ["r.ScreenPercentage 85", "r.Nanite.MaxPixelsPerEdge 1"]),
    ))
    for cv in ("r.Nanite.ComputeRasterization", "r.Nanite.AllowComputeRasterization",
               "r.Nanite.AsyncRasterization", "r.Nanite.MaxPixelsPerEdge",
               "r.Nanite.MinPixelsPerEdgeHW", "r.Shadow.CSM.MaxCascades",
               "r.Shadow.MaxCSMResolution", "r.Lumen.DiffuseIndirect.Allow"):
        B._log(f"cvar {cv} = {B.SL.get_console_variable_string_value(cv)!r}")
    p.check("benchmark ran", len(B.RESULTS) > 10, f"{len(B.RESULTS)} measurements")
