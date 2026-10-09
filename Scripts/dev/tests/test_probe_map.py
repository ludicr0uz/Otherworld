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
        self.assertEqual(plan["net"], [])
        for p in plan["game"]:
            self.assertIn("weapons", probe_map.declared(p)[0])

    def test_net_probes_go_to_the_net_launch(self):
        plan = probe_map.plan(["Scripts/net/guard.py"])
        self.assertIn("probe_net_join", names(plan["net"]))
        self.assertNotIn("probe_net_join", names(plan["game"]))
        self.assertGreaterEqual(plan["clients"], 1)

    def test_unmapped_is_reported_and_probe_edits_are_not(self):
        plan = probe_map.plan(["foo/bar.txt", "Scripts/probes/probe_axe.py"])
        self.assertEqual(plan["unmapped"], ["foo/bar.txt"])
        self.assertEqual(plan["game"], [])

    def test_kinds(self):
        k = probe_map.probe_kind
        self.assertEqual(k(("net",), ("server", "client")), "net")
        self.assertEqual(k(("net",), ("server", "client", "standalone")), "game")
        self.assertEqual(k(("weapons",), None), "game")
        self.assertEqual(k(("load",), ("server",)), "load")
        self.assertEqual(probe_map.clients_needed(("server", "client 2")), 2)


class Command(unittest.TestCase):
    def test_dry_run_lists_the_weapons_probes(self):
        out = subprocess.run([sys.executable, UEPY, "--probes-for",
                              "Scripts/combat/weapon_component/fire.py", "--dry-run"],
                             capture_output=True, text=True)
        text = out.stdout + out.stderr
        self.assertEqual(out.returncode, 0, text)
        self.assertIn("probe_headshot", text)
        self.assertNotIn("--net", text)


if __name__ == "__main__":
    unittest.main()
