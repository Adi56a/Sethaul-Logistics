-- SetuHaul Audit 04: View Validation Queries
-- Target: setuhaul_freight_operations.db

-- 1. View: v_latest_eta
-- Confirms each shipment has exactly 1 latest effective ETA record
SELECT 
    COUNT(*) AS total_shipments_in_view,
    COUNT(DISTINCT shipment_id) AS distinct_shipments
FROM v_latest_eta;

-- 2. View: v_slot_availability
-- Summary of slot states across the dataset
SELECT 
    facility_id,
    availability_status,
    COUNT(*) AS slot_count
FROM v_slot_availability
GROUP BY facility_id, availability_status
ORDER BY facility_id, availability_status;

-- 3. View: v_inbound_operational_state
-- Inspect high-priority shipments in transit to Jaipur DC
SELECT 
    shipment_id,
    priority_code,
    current_status,
    effective_eta_ts,
    slot_id,
    planned_dock_code,
    queue_state
FROM v_inbound_operational_state
WHERE destination_facility_id = 'FAC-JAI-01'
  AND priority_code IN ('HIGH', 'CRITICAL')
ORDER BY effective_eta_ts;

-- 4. View: v_current_facility_queue
-- Check all physical trucks currently waiting at facilities
SELECT 
    facility_id,
    shipment_id,
    driver_id,
    arrival_state,
    queue_state,
    queue_position,
    expected_unload_min
FROM v_current_facility_queue
ORDER BY facility_id, queue_position;
