"""uepylib/probe_map.py: paths to systems, systems to probe launches."""
import os
import subprocess
import sys
import unittest

from _paths import *  # noqa: F401,F403  (puts Scripts/dev on sys.path)
from uepylib import probe_map

UEPY = os.path.join(os.path.dirname(__file__), "..", "uepy.py")


def names(paths):
    return {os.path.basename(p)[:-3] for p in paths}


class SystemsFor(unittest.TestCase):
    def test_rules(self):
        f = probe_map.systems_for
        self.assertEqual(f("Scripts/combat/weapon_component/fire.py"), ("weapons",))
        self.assertEqual(f("Scripts/npc/ward.py"), ("npc",))
        self.assertEqual(set(f("Source/Otherworld/Private/OtherworldShotTrace.cpp")),
                         {"weapons", "net"})
        self.assertEqual(f("README.md"), ())

    def test_every_rule_names_known_systems(self):
        from probes import systems
        for _rule, tags in probe_map.RULES:
            self.assertTrue(set(tags) <= set(systems.SYSTEMS), tags)


class Plan(unittest.TestCase):
    def test_weapon_component_runs_only_weapons_probes(self):
        plan = probe_map.plan(["Scripts/combat/weapon_component/fire.py"])
        self.assertEqual(plan["systems"], {"weapons"})
        self.assertTrue({"probe_headshot", "probe_ads_hit"} <= names(plan["game"]))
        # The one weapons probe that is a net probe (probe_server/probe_client,
        # no RUNS_ON) goes to the net launch, not a --game one it cannot run in.
        self.assertEqual(names(plan["net"]), {"probe_net_fire_action"})
        for p in plan["game"] + plan["net"]:
            self.assertIn("weapons", probe_map.declared(p)[0])

    def test_net_probes_go_to_the_net_launch(self):
        plan = probe_map.plan(["Scripts/net/guard.py"])
        self.assertIn("probe_net_join", names(plan["net"]))
        self.assertNotIn("probe_net_join", names(plan["game"]))
        self.assertGreaterEqual(plan["clients"], 2)

    def test_a_helper_module_beside_the_probes_is_not_launched(self):
        # probe_clothing_drag.py and probe_clothing_draw.py hold checks other
        # probes import; they define no probe function and failed every
        # --game launch that picked them up by their SYSTEMS.
        plan = probe_map.plan(["Scripts/clothing/items.py"])
        launched = names(plan["game"] + plan["net"] + plan["title"])
        self.assertIn("probe_clothing", launched)
        self.assertNotIn("probe_clothing_drag", launched)
        self.assertNotIn("probe_clothing_draw", launched)
        self.assertEqual(probe_map.declared(os.path.join(
            probe_map.PROBES_DIR, "probe_clothing_drag.py"))[2], ())
        self.assertEqual(probe_map.declared(os.path.join(
            probe_map.PROBES_DIR, "probe_net_fire_action.py"))[1:],
            (None, ("probe_server", "probe_client")))

    def test_a_net_launch_has_two_clients_unless_a_probe_wants_more(self):
        # probe_net_campfire and probe_net_throw stand client 2 behind client 1
        # but say only ("server", "client"): a one-client launch failed them.
        self.assertEqual(probe_map.NET_CLIENTS, 2)
        self.assertEqual(probe_map.clients_needed(("server", "client")), 2)
        self.assertEqual(probe_map.clients_needed(("server", "client 3")), 3)
        self.assertEqual(probe_map.plan(["Scripts/survival/hunger.py"])["clients"], 2)

    def test_unmapped_is_reported_and_probe_edits_are_not(self):
        plan = probe_map.plan(["foo/bar.txt", "Scripts/probes/probe_axe.py"])
        self.assertEqual(plan["unmapped"], ["foo/bar.txt"])
        self.assertEqual(plan["game"], [])

    def test_kinds(self):
        k = probe_map.probe_kind
        self.assertEqual(k(("net",), ("server", "client")), "net")
        self.assertEqual(k(("net",), ("server", "client", "standalone")), "game")
        self.assertEqual(k(("weapons",), None), "game")
        self.assertEqual(k(("weapons",), None, ("probe_server", "probe_client")), "net")
        self.assertEqual(k(("weapons",), None, ("probe", "probe_client")), "game")
        self.assertEqual(k(("load",), ("server",)), "load")
        self.assertEqual(probe_map.clients_needed(("server", "client 2")), 2)


class VerifiersFor(unittest.TestCase):
    def test_a_package_maps_to_its_verifier(self):
        f = probe_map.verifiers_for
        self.assertEqual(f(["Scripts/graphics_menu/mode_tick.py"]),
                         ["Scripts/verify_graphics_menu.py"])
        self.assertEqual(f(["Scripts/combat/weapon_component/fire.py", "Scripts/loot/x.py"]),
                         ["Scripts/verify_weapons_and_combat.py"])
        self.assertEqual(f(["Scripts/build_npc_blueprints.py"]),
                         ["Scripts/verify_npc_blueprints.py"])

    def test_probes_docs_and_dev_map_to_none(self):
        self.assertEqual(probe_map.verifiers_for(
            ["Scripts/probes/probe_x.py", "docs/current_state.md", "Scripts/dev/uepy.py",
             "CLAUDE.md", "Scripts/dev/tests/test_x.py"]), [])

    def test_a_verifier_maps_to_itself_and_levels_to_their_own(self):
        f = probe_map.verifiers_for
        self.assertEqual(f(["Scripts/verify_survival.py"]), ["Scripts/verify_survival.py"])
        self.assertEqual(f(["Scripts/generated_levels/Lvl_Probe_50m/forest.py"]),
                         ["Scripts/generated_levels/Lvl_Probe_50m/verify_Lvl_Probe_50m.py"])
        levels = f(["Scripts/forest_generator/trees.py"])
        self.assertEqual(len(levels), 3)
        self.assertTrue(all("generated_levels" in p for p in levels))

    def test_suite_order_tops_then_levels_each_once(self):
        got = probe_map.verifiers_for(["Scripts/forest_generator/a.py", "Scripts/npc/b.py",
                                       "Scripts/combat/c.py", "Scripts/combat/d.py"])
        self.assertEqual(got[:2], ["Scripts/verify_npc_blueprints.py",
                                   "Scripts/verify_weapons_and_combat.py"])
        self.assertEqual(len(got), 5)

    def test_every_rule_names_a_verifier_on_disk(self):
        for _rule, scripts in probe_map.VERIFIER_RULES:
            for s in scripts:
                self.assertTrue(os.path.isfile(os.path.join(probe_map.ROOT, "Scripts", s)), s)


class Command(unittest.TestCase):
    def test_dry_run_lists_the_weapons_probes(self):
        out = subprocess.run([sys.executable, UEPY, "--probes-for",
                              "Scripts/combat/weapon_component/fire.py", "--dry-run"],
                             capture_output=True, text=True)
        text = out.stdout + out.stderr
        self.assertEqual(out.returncode, 0, text)
        self.assertIn("probe_headshot", text)
        self.assertIn("--net --clients 2: probe_net_fire_action", text)
        self.assertNotIn("probe_net_join", text)

    def test_verify_for_dry_run_names_the_verifier_or_none(self):
        out = subprocess.run([sys.executable, UEPY, "--verify-for",
                              "Scripts/survival/hunger.py", "--dry-run"],
                             capture_output=True, text=True)
        text = out.stdout + out.stderr
        self.assertEqual(out.returncode, 0, text)
        self.assertIn("verify_survival.py", text)
        out = subprocess.run([sys.executable, UEPY, "--verify-for",
                              "Scripts/probes/probe_x.py", "--dry-run"],
                             capture_output=True, text=True)
        self.assertEqual(out.returncode, 0)
        self.assertIn("none", out.stdout + out.stderr)


if __name__ == "__main__":
    unittest.main()
