"""Helpers that do not need Origin."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from gui_logic import (
    batch_steps,
    cf_pairs,
    chosen_panels,
    conduction_graph_names,
    conduction_tokens,
    grid_shape,
    normalize_folder,
    pulse_caption,
    pulse_names,
    read_pulse,
    read_sweep,
    same_folder,
    template_pairs,
)


class Names(unittest.TestCase):
    def test_folder_and_membership(self):
        self.assertEqual(normalize_folder("PythonPlots"), "/PythonPlots/")
        self.assertEqual(normalize_folder("\\D114\\PythonPlots\\"), "/D114/PythonPlots/")
        self.assertTrue(same_folder("/PythonPlots/", "/PythonPlots"))
        self.assertTrue(same_folder("/PythonPlots/child", "/PythonPlots/"))
        self.assertFalse(same_folder("/PythonPlotsOld", "/PythonPlots"))
        self.assertFalse(same_folder("/D114/B/all", "/D114/conduction"))

    def test_conduction_names_are_unique_and_short(self):
        pairs = conduction_tokens(["b22-FS-1.0v", "b22-FS-1.0v", "7-FS-2.8v"])
        self.assertEqual(len(pairs), 3)
        seen = set()
        for book, token in pairs:
            self.assertLessEqual(len(book), 21)
            self.assertTrue(book.isidentifier())
            for name in conduction_graph_names(token):
                self.assertTrue(name.isidentifier())
                self.assertLessEqual(len(name), 21)
                self.assertNotIn(name.lower(), seen)
                seen.add(name.lower())

    def test_cf_names_avoid_the_comparison_and_trial_pages(self):
        pairs = cf_pairs(["cfBatch", "sweep", "sweep"])
        flat = [name.lower() for pair in pairs for name in pair]
        self.assertEqual(len(flat), len(set(flat)))
        self.assertNotIn("cfbatch", flat)
        self.assertNotIn("cftryr", flat)

    def test_template_pairs(self):
        books, graphs = zip(*template_pairs(["sweep", "sweep"]))
        self.assertEqual(len(set(books)), 2)
        self.assertEqual(len(set(graphs)), 2)

    def test_panels_keep_the_page_order(self):
        self.assertEqual(chosen_panels(["sclc", "iv"]), ["iv", "sclc"])
        with self.assertRaises(ValueError):
            chosen_panels([])

    def test_hold_uses_the_first_file_as_the_capacitive_reference(self):
        steps = batch_steps(3, "lrcpe", True)
        self.assertEqual(steps[0], {"model": "rcpe", "use_donor": False})
        self.assertEqual(steps[1], {"model": "lrcpe", "use_donor": True})
        self.assertEqual(steps[2]["use_donor"], True)
        both = batch_steps(2, "both", True)
        self.assertEqual(both[0]["model"], "both")
        self.assertFalse(both[0]["use_donor"])
        self.assertTrue(both[1]["use_donor"])
        self.assertEqual(batch_steps(1, "lrcpe", True)[0]["model"], "lrcpe")
        self.assertFalse(batch_steps(2, "rcpe", True)[0]["use_donor"])

    def test_grid(self):
        self.assertEqual(grid_shape(8), (4, 2))
        self.assertEqual(grid_shape(1), (1, 1))
        self.assertEqual(grid_shape(3), (2, 2))


class SweepFile(unittest.TestCase):
    def test_reads_voltage_current_and_time(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "sweep.txt"
            path.write_text("Voltage Current Time\n0 1e-9 0\n1 -2e-9 1\nnan 3 2\n", encoding="utf-8")
            voltage, current, time = read_sweep(path)
            self.assertEqual(voltage, [0.0, 1.0])
            self.assertEqual(current, [1e-9, -2e-9])
            self.assertEqual(time, [0.0, 1.0])

    def test_lowercase_header(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "sweep.txt"
            path.write_text("voltage current time\n0 1e-9 0\n1 -2e-9 1\n", encoding="utf-8")
            voltage, current, time = read_sweep(path)
            self.assertEqual(voltage, [0.0, 1.0])
            self.assertEqual(current, [1e-9, -2e-9])
            self.assertEqual(time, [0.0, 1.0])

    def test_time_is_optional(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "iv.csv"
            path.write_text("Voltage,Current\n0,1\n1,2\n", encoding="utf-8")
            voltage, current, time = read_sweep(path)
            self.assertEqual(voltage, [0.0, 1.0])
            self.assertEqual(current, [1.0, 2.0])
            self.assertIsNone(time)

    def test_missing_columns(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "bad.txt"
            path.write_text("A B\n1 2\n", encoding="utf-8")
            with self.assertRaises(SystemExit):
                read_sweep(path)


ENDURANCE = """# Keithley 2450 TSP Pulse Test: Endurance
# Test Parameters:
#   set_voltage: 2.5
#   reset_voltage: -2.5
#   pulse_width: 0.001
# Measurement_Number\tTimestamp(s)\tVoltage(V)\tCurrent(A)\tResistance(Ohm)\tCycle Number\tOperation
0\t0\t0.3\t1e-4\t3000\t0\tINIT
1\t0\t0.3\t1e-4\t4000\t0\tSET
2\t0.002\t0.3\t1e-4\t3500\t0\tRESET
3\t0.004\t0.3\t1e-4\t4100\t1\tSET
4\t0.006\t0.3\t1e-4\t3400\t1\tRESET
"""

RETENTION = """# Keithley 2450 TSP Pulse Test: Timed Retention
# Test Parameters:
#   pulse_voltage: -2.8
#   pulse_width: 0.01
# Measurement_Number\tTimestamp(s)\tVoltage(V)\tCurrent(A)\tResistance(Ohm)\tOperation
0\t0.03\t-0.3\t-5e-5\t6000\tbaseline
1\t0.11\t-0.3\t-7e-5\t4000\tpost_pulse
2\t60\t-0.3\t-7e-5\t4200\tretention
3\t120\t-0.3\t-7e-5\t4300\tretention
"""


class PulseFile(unittest.TestCase):
    def test_endurance_groups_and_caption(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "13-Endurance-2.5V_1ms_10000cyc-20260811_155116.txt"
            path.write_text(ENDURANCE, encoding="utf-8")
            record = read_pulse(path)
        self.assertEqual(record["kind"], "endurance")
        self.assertEqual(record["label"], "13, ±2.5 V, 1 ms")
        self.assertEqual(record["groups"]["SET"]["cycle"], [0.0, 1.0])
        self.assertEqual(record["groups"]["RESET"]["resistance"], [3500.0, 3400.0])
        self.assertEqual(len(record["groups"]["INIT"]["resistance"]), 1)

    def test_retention_caption_keeps_the_sign(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "53-Timed_Retention-2.8V_10ms-20260817_045011.txt"
            path.write_text(RETENTION, encoding="utf-8")
            record = read_pulse(path)
        self.assertEqual(record["kind"], "retention")
        self.assertEqual(record["label"], "53, −2.8 V, 10 ms")
        self.assertEqual(len(record["groups"]["retention"]["time"]), 2)
        self.assertEqual(pulse_caption(path.name, record["meta"], "retention"), record["label"])

    def test_sweep_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "sweep.txt"
            path.write_text("Voltage Current\n0 1\n1 2\n", encoding="utf-8")
            with self.assertRaises(SystemExit):
                read_pulse(path)

    def test_pulse_names_stay_unique(self):
        stems = [
            "13-Endurance-2.5V_1ms_10000cyc-20260811_155116",
            "26-Endurance-2.5V_1ms_10000cyc-20260811_161717",
            "28-Endurance-2.5V_10ms_10000cyc-20260811_162720",
        ]
        pairs, book, graph = pulse_names(stems, "endurance")
        names = [book, graph]
        for pair in pairs:
            names.extend(pair)
        self.assertEqual(len(names), len({name.lower() for name in names}))
        for name in names:
            self.assertTrue(name.isidentifier())
            self.assertLessEqual(len(name), 21)


if __name__ == "__main__":
    unittest.main()
