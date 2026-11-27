-- SetuHaul Audit 02: Audited Seeded Edge Cases & Data Anomalies
-- Target: setuhaul_freight_operations.db

-- 1. Contact Info Gap: CON005 at FAC-GGN-01 has NULL email
SELECT contact_id, facility_id, contact_role, contact_name, email, phone 
FROM facility_contacts 
WHERE email IS NULL;

-- 2. Dock D3 Leveller Breakdown (DEVT001) and Affected Slots
SELECT 
    dse.dock_event_id,
    dse.dock_id,
    dse.event_type,
    dse.reason,
    dse.event_start_ts,
    dse.event_end_ts,
    sl.slot_id,
    sl.slot_start_ts,
    sl.slot_end_ts,
    sl.slot_status
FROM dock_status_events dse
JOIN appointment_slots sl ON sl.dock_id = dse.dock_id 
    AND sl.slot_start_ts >= dse.event_start_ts 
    AND sl.slot_end_ts <= dse.event_end_ts
WHERE dse.dock_event_id = 'DEVT001';

-- 3. Dock D5 Reefer Planned Maintenance (DEVT002) and SHP1015 Infeasibility
-- Shows that D5 is blocked 18:00-22:00, preventing SHP1015 (ETA 18:30) from unloading
SELECT 
    sl.slot_id,
    sl.dock_id,
    sl.slot_start_ts,
    sl.slot_end_ts,
    sl.slot_status,
    sl.block_reason
FROM appointment_slots sl
WHERE sl.dock_id = 'DOCK-JAI-D5'
  AND sl.slot_start_ts >= '2026-08-04T18:00:00+05:30';

-- 4. Unload Overrun & Capacity Reduction on D2 (DEVT003 / SHP1002)
SELECT 
    fc.checkin_id,
    fc.shipment_id,
    fc.actual_dock_id,
    fc.dock_in_ts,
    fc.queue_state,
    dse.reason AS disruption_reason
FROM facility_checkins fc
JOIN dock_status_events dse ON dse.dock_id = fc.actual_dock_id
WHERE fc.shipment_id = 'SHP1002';

-- 5. Driver DRV004 Ambiguous Active Shipments
SELECT 
    s.shipment_id,
    s.order_reference,
    s.driver_id,
    s.current_status,
    s.origin_city,
    s.destination_facility_id,
    s.planned_departure_ts,
    s.original_eta_ts
FROM shipments s
WHERE s.driver_id = 'DRV004'
ORDER BY s.planned_departure_ts;

-- 6. Duplicate Inbound Message (MSG015 in THR009)
SELECT 
    chat_message_id,
    thread_id,
    sender_type,
    sender_reference,
    external_message_id,
    is_duplicate,
    message_text
FROM chat_messages
WHERE thread_id IN ('THR001', 'THR009')
ORDER BY message_ts;

-- 7. Low-Confidence / Range ETAs Requiring Clarification
SELECT 
    e.eta_update_id,
    e.shipment_id,
    e.source_type,
    e.confidence_code,
    e.declared_eta_ts,
    e.note
FROM eta_updates e
WHERE e.confidence_code = 'LOW';
