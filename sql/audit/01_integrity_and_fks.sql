-- SetuHaul Audit 01: Referential Integrity, Constraints, and Row Counts
-- Target: setuhaul_freight_operations.db

-- 1. Foreign Key Verification (Must return 0 violations)
PRAGMA foreign_keys = ON;
PRAGMA foreign_key_check;

-- 2. Database Storage Integrity (Must return 'ok')
PRAGMA integrity_check;

-- 3. Inventory & Row Counts
SELECT 'carriers' AS table_name, COUNT(*) AS row_count FROM carriers
UNION ALL SELECT 'drivers', COUNT(*) FROM drivers
UNION ALL SELECT 'vehicle_types', COUNT(*) FROM vehicle_types
UNION ALL SELECT 'vehicles', COUNT(*) FROM vehicles
UNION ALL SELECT 'facilities', COUNT(*) FROM facilities
UNION ALL SELECT 'docks', COUNT(*) FROM docks
UNION ALL SELECT 'facility_contacts', COUNT(*) FROM facility_contacts
UNION ALL SELECT 'facility_rules', COUNT(*) FROM facility_rules
UNION ALL SELECT 'shipments', COUNT(*) FROM shipments
UNION ALL SELECT 'eta_updates', COUNT(*) FROM eta_updates
UNION ALL SELECT 'appointment_slots', COUNT(*) FROM appointment_slots
UNION ALL SELECT 'appointments', COUNT(*) FROM appointments
UNION ALL SELECT 'dock_status_events', COUNT(*) FROM dock_status_events
UNION ALL SELECT 'facility_checkins', COUNT(*) FROM facility_checkins
UNION ALL SELECT 'chat_threads', COUNT(*) FROM chat_threads
UNION ALL SELECT 'chat_messages', COUNT(*) FROM chat_messages
UNION ALL SELECT 'driver_exceptions', COUNT(*) FROM driver_exceptions
UNION ALL SELECT 'operational_messages', COUNT(*) FROM operational_messages;

-- 4. Verify Partial Unique Indexes
-- A. ux_active_appointment_per_slot (Must return 0 rows with count > 1)
SELECT slot_id, COUNT(*) AS active_count
FROM appointments
WHERE appointment_status IN ('PENDING_CONFIRMATION', 'CONFIRMED', 'IN_PROGRESS')
GROUP BY slot_id
HAVING COUNT(*) > 1;

-- B. ux_current_active_appointment_per_shipment (Must return 0 rows with count > 1)
SELECT shipment_id, COUNT(*) AS active_count
FROM appointments
WHERE is_current = 1 AND appointment_status IN ('PENDING_CONFIRMATION', 'CONFIRMED', 'IN_PROGRESS')
GROUP BY shipment_id
HAVING COUNT(*) > 1;
