"""
SetuHaul Logistics — Deterministic Feasibility Service Unit Tests
Tests compatibility (standard, reefer, heavy), breakdown events, operating hours, and ambiguity.
"""

import unittest
from app.repositories.db import DatabaseRepository, resolve_db_path
from app.services.feasibility import FeasibilityService
from app.tools.schemas import ResultCode


class TestFeasibilityService(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo = DatabaseRepository(resolve_db_path())
        cls.service = FeasibilityService(cls.repo)

    def test_multi_shipment_ambiguity_drv004(self):
        """Driver DRV004 has dual active shipments (SHP1004 & SHP1020); must return AMBIGUOUS_IDENTITY."""
        res = self.service.resolve_driver_context(driver_id="DRV004")
        self.assertEqual(res["result_code"], ResultCode.AMBIGUOUS_IDENTITY)
        self.assertTrue(res["is_ambiguous"])
        self.assertEqual(len(res["active_shipments"]), 2)
        refs = [s["order_reference"] for s in res["active_shipments"]]
        self.assertIn("ORD-260804-004", refs)
        self.assertIn("ORD-260804-020", refs)

    def test_single_shipment_resolution_drv012(self):
        """Driver DRV012 has exactly 1 active shipment (SHP1012); must resolve cleanly without ambiguity."""
        res = self.service.resolve_driver_context(driver_id="DRV012")
        self.assertEqual(res["result_code"], ResultCode.AVAILABLE)
        self.assertFalse(res["is_ambiguous"])
        self.assertEqual(res["selected_shipment"]["shipment_id"], "SHP1012")

    def test_standard_shipment_feasible_slots_shp1006(self):
        """SHP1006 (ETA 11:20) should find standard slots starting at 12:00 on D2 and D4."""
        res = self.service.search_feasible_slots("SHP1006", min_time="2026-08-04T11:20:00+05:30")
        self.assertEqual(res.result_code, ResultCode.AVAILABLE)
        self.assertGreater(len(res.feasible_slots), 0)
        
        # Verify standard docks (D1, D2, D3, D4) are matched, while D5 (Reefer) and D6 (Heavy) are excluded
        for slot in res.feasible_slots:
            self.assertGreaterEqual(slot.slot_start_ts, "2026-08-04T12:00:00+05:30")
            self.assertIn(slot.dock_code, ["D1", "D2", "D3", "D4"])

    def test_reefer_compatibility_shp1010(self):
        """SHP1010 requires temperature control; candidate slots must be on reefer docks only (D5)."""
        res = self.service.search_feasible_slots("SHP1010", min_time="2026-08-04T11:00:00+05:30")
        self.assertEqual(res.result_code, ResultCode.AVAILABLE)
        for slot in res.feasible_slots:
            self.assertEqual(slot.dock_code, "D5")
            self.assertEqual(slot.dock_type, "REEFER")

    def test_reefer_breakdown_escalation_shp1015(self):
        """SHP1015 (ETA 18:30) requires Reefer, but D5 is under maintenance (DEVT002) 18:00-22:00 -> NO_FEASIBLE_SLOT."""
        res = self.service.search_feasible_slots("SHP1015", min_time="2026-08-04T18:30:00+05:30")
        self.assertEqual(res.result_code, ResultCode.NO_FEASIBLE_SLOT)
        self.assertEqual(len(res.feasible_slots), 0)
        self.assertIn("No feasible compatible slots found", res.message)

    def test_heavy_vehicle_compatibility_shp1016(self):
        """SHP1016 is 31,000 kg and requires 90 min; must only match Heavy Dock D6."""
        res = self.service.search_feasible_slots("SHP1016", min_time="2026-08-04T12:00:00+05:30")
        self.assertEqual(res.result_code, ResultCode.AVAILABLE)
        for slot in res.feasible_slots:
            self.assertEqual(slot.dock_code, "D6")
            self.assertEqual(slot.dock_type, "HEAVY")
            self.assertGreaterEqual(slot.duration_min, 90)

    def test_dock_d3_breakdown_exclusion(self):
        """DOCK-JAI-D3 has hydraulic leveller breakdown 09:15-13:00; no feasible slot can be on D3 before 13:00."""
        res = self.service.search_feasible_slots("SHP1006", min_time="2026-08-04T11:20:00+05:30")
        d3_morning_slots = [s for s in res.feasible_slots if s.dock_code == "D3" and s.slot_start_ts < "2026-08-04T13:00:00+05:30"]
        self.assertEqual(len(d3_morning_slots), 0)


if __name__ == "__main__":
    unittest.main()
