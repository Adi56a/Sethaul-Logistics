-- SetuHaul Audit 03: Competing Requests for Standard Docks around 11:00 AM at Jaipur DC
-- Target: setuhaul_freight_operations.db

-- 1. Inbound Standard-Dock Shipments with ETA between 10:45 and 12:00
SELECT 
    s.shipment_id,
    s.order_reference,
    s.driver_id,
    s.priority_code,
    s.load_weight_kg,
    s.expected_unload_min,
    le.effective_eta_ts,
    le.eta_confidence,
    a.appointment_id,
    a.slot_id,
    a.appointment_status
FROM shipments s
JOIN v_latest_eta le ON s.shipment_id = le.shipment_id
LEFT JOIN appointments a ON s.shipment_id = a.shipment_id AND a.is_current = 1
WHERE s.destination_facility_id = 'FAC-JAI-01'
  AND s.required_dock_type = 'STANDARD'
  AND le.effective_eta_ts BETWEEN '2026-08-04T10:45:00+05:30' AND '2026-08-04T12:00:00+05:30'
ORDER BY le.effective_eta_ts, s.priority_code DESC;

-- 2. Standard Dock Availability at Jaipur DC (10:00 to 13:00)
SELECT 
    v.slot_id,
    v.dock_code,
    v.slot_start_ts,
    v.slot_end_ts,
    v.availability_status,
    v.appointment_status,
    v.shipment_id
FROM v_slot_availability v
WHERE v.facility_id = 'FAC-JAI-01'
  AND v.dock_type = 'STANDARD'
  AND v.slot_start_ts BETWEEN '2026-08-04T10:00:00+05:30' AND '2026-08-04T13:00:00+05:30'
ORDER BY v.slot_start_ts, v.dock_code;
