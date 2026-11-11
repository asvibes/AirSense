-- =============================================================================
-- AirSense - demonstration queries                                  queries.sql
-- =============================================================================
-- Shows joins, aggregation, subqueries, CTEs, window functions, views,
-- transactions, constraints and integrity checks on the AirSense schema
-- (the 13 tables in schema.sql / schema_sqlite.sql).
--
-- READ THIS FIRST
--   * Run it on a SCRATCH database that was created from schema.sql
--     (PostgreSQL 16) or schema_sqlite.sql (SQLite). Never on production data:
--     Section 1 inserts demo rows and Sections 4-5 modify them.
--   * It is plain SQL for the application schema (PostgreSQL and SQLite). It is
--     NOT the Azure SQL / SQL Server design in database/migrations/*.sql, which
--     has different table names and was never run.
--   * The application itself does not run this SQL; it uses SQLAlchemy. These
--     queries illustrate the same relational operations. The views in Section 3
--     are teaching examples that the application does not define or use; the
--     cleanup block at the end drops them (drop them before any Alembic
--     downgrade).
--   * The data is invented demo data (example.test addresses, fake hashes).
--   * PostgreSQL: run `SET TIME ZONE 'UTC';` first (see the line below) so that
--     date(...) groups by UTC day. SQLite needs no setup.
--   * Dialect-specific statements are in Section 8 and marked [PG] / [SQLite].
--
-- Tested on PostgreSQL 16 and SQLite 3 at commit ce1a862 (see
-- database_sql_notes.md for the results and known differences).
-- =============================================================================

-- [PostgreSQL only] Uncomment when using psql:
-- SET TIME ZONE 'UTC';
-- [SQLite only] Uncomment to enforce foreign keys:
-- PRAGMA foreign_keys = ON;


-- =============================================================================
-- SECTION 1. DEMO DATA  (inserts in foreign-key order: parents before children)
-- =============================================================================
BEGIN;

INSERT INTO users (id, email, display_name, password_hash) VALUES
  ('u-1', 'owner@example.test',  'Asha Owner',   'demo-not-a-real-hash'),
  ('u-2', 'member@example.test', 'Ravi Member',  'demo-not-a-real-hash'),
  ('u-3', 'other@example.test',  'Other Person', 'demo-not-a-real-hash');

INSERT INTO homes (id, name) VALUES
  ('h-1', 'Demo Flat'),
  ('h-2', 'Other Home');

INSERT INTO home_memberships (home_id, user_id, role) VALUES
  ('h-1', 'u-1', 'owner'),
  ('h-1', 'u-2', 'member'),
  ('h-2', 'u-3', 'owner');

INSERT INTO home_invitations (id, home_id, email, role, token_hash, created_by, expires_at) VALUES
  ('inv-1', 'h-1', 'invitee@example.test', 'member', 'demo-token-hash-1', 'u-1', '2026-11-11T09:00:00Z');

INSERT INTO rooms (id, home_id, name) VALUES
  ('r-living',  'h-1', 'Living Room'),
  ('r-bedroom', 'h-1', 'Bedroom'),
  ('r-kitchen', 'h-1', 'Kitchen'),      -- no sensor and no policy (used by the anti-join demos)
  ('r-other',   'h-2', 'Study');

-- CO2 already exists (schema.sql inserts it, as the application does).
INSERT INTO metrics (code, name, unit) VALUES ('TEMPERATURE', 'Temperature', 'C');

INSERT INTO sensors (id, home_id, room_id, name, key_hash, last_seen_at) VALUES
  ('s-1', 'h-1', 'r-living',  'Living room sensor', 'demo-key-hash-1', '2026-11-10T09:30:00Z'),
  ('s-2', 'h-1', 'r-bedroom', 'Bedroom sensor',     'demo-key-hash-2', NULL);   -- never reported

INSERT INTO threshold_policies
  (home_id, room_id, metric_code, high_threshold, elevated_threshold,
   elevated_duration_seconds, rapid_rise_per_minute, all_clear_duration_seconds,
   max_reading_gap_seconds)
VALUES
  ('h-1', 'r-living',  'CO2', 1500, 1000, 300, 200, 300, 900),
  ('h-1', 'r-bedroom', 'CO2', 1500, 1000, 300, 200, 300, 900);

-- Living room CO2 from the device, every 5 minutes.
INSERT INTO air_readings (home_id, room_id, metric_code, value, source, measured_at, sensor_id, received_at) VALUES
  ('h-1','r-living','CO2',  800,'device','2026-11-10T09:00:00Z','s-1','2026-11-10T09:00:02Z'),
  ('h-1','r-living','CO2',  950,'device','2026-11-10T09:05:00Z','s-1','2026-11-10T09:05:02Z'),
  ('h-1','r-living','CO2', 1100,'device','2026-11-10T09:10:00Z','s-1','2026-11-10T09:10:02Z'),
  ('h-1','r-living','CO2', 1400,'device','2026-11-10T09:15:00Z','s-1','2026-11-10T09:15:02Z'),
  ('h-1','r-living','CO2', 1650,'device','2026-11-10T09:20:00Z','s-1','2026-11-10T09:20:02Z'),
  ('h-1','r-living','CO2', 1700,'device','2026-11-10T09:25:00Z','s-1','2026-11-10T09:25:02Z'),
  ('h-1','r-living','CO2', 1500,'device','2026-11-10T09:30:00Z','s-1','2026-11-10T09:30:02Z');
-- Living room temperature from the same device.
INSERT INTO air_readings (home_id, room_id, metric_code, value, source, measured_at, sensor_id, received_at) VALUES
  ('h-1','r-living','TEMPERATURE', 24.5,'device','2026-11-10T09:00:00Z','s-1','2026-11-10T09:00:02Z'),
  ('h-1','r-living','TEMPERATURE', 25.1,'device','2026-11-10T09:15:00Z','s-1','2026-11-10T09:15:02Z'),
  ('h-1','r-living','TEMPERATURE', 25.8,'device','2026-11-10T09:30:00Z','s-1','2026-11-10T09:30:02Z');
-- Bedroom: imported dataset rows and one simulated row (no sensor).
INSERT INTO air_readings (home_id, room_id, metric_code, value, source, measured_at, sensor_id) VALUES
  ('h-1','r-bedroom','CO2', 700,'dataset',  '2026-11-09T22:00:00Z', NULL),
  ('h-1','r-bedroom','CO2', 720,'dataset',  '2026-11-09T22:05:00Z', NULL),
  ('h-1','r-bedroom','CO2', 760,'dataset',  '2026-11-09T22:10:00Z', NULL),
  ('h-1','r-bedroom','CO2',1200,'simulated','2026-11-10T08:00:00Z', NULL);
-- Another home (used to show that joins on home_id keep homes separate).
INSERT INTO air_readings (home_id, room_id, metric_code, value, source, measured_at) VALUES
  ('h-2','r-other','CO2', 620,'dataset','2026-11-10T09:00:00Z');

-- Alerts: one acknowledged (open), one rapid-rise (open), one closed.
INSERT INTO air_alerts
  (home_id, room_id, metric_code, level, status, trigger_value, threshold_value,
   latest_value, threshold_unit, clear_duration_seconds, created_at,
   acknowledged_at, acknowledged_by, all_clear_at, detail)
VALUES
  ('h-1','r-living','CO2','high','acknowledged',1650,1500,1700,'ppm',300,
   '2026-11-10T09:20:00Z','2026-11-10T09:22:00Z','Asha Owner',NULL,'CO2 above the high threshold'),
  ('h-1','r-living','CO2','rapid_rise','active',1400,200,1650,'ppm',300,
   '2026-11-10T09:15:00Z',NULL,NULL,NULL,'CO2 rising quickly'),
  ('h-1','r-living','CO2','elevated','all_clear',1100,1000,900,'ppm',300,
   '2026-11-10T09:10:00Z',NULL,NULL,'2026-11-10T09:40:00Z','Elevated CO2 has cleared');

INSERT INTO audit_logs (home_id, actor_user_id, event_type, entity_type, entity_id, details_json, created_at) VALUES
  ('h-1','u-1', 'invitation_created',    'invitation', 'inv-1', '{}', '2026-11-10T08:30:00Z'),
  ('h-1', NULL, 'device_key_rejected',   'sensor',     's-1',   '{}', '2026-11-10T08:45:00Z');

COMMIT;


-- =============================================================================
-- SECTION 2. SELECT QUERIES: JOINS, AGGREGATES, SUBQUERIES, CTEs, WINDOWS
-- =============================================================================

-- Q1. INNER JOIN (3 tables): who belongs to which home, with role.
SELECT h.name AS home, u.display_name AS member, m.role
FROM home_memberships AS m
JOIN homes AS h ON h.id = m.home_id
JOIN users AS u ON u.id = m.user_id
ORDER BY h.name, m.role, u.display_name;

-- Q2. INNER JOIN (5 tables): readable reading history with names and units.
SELECT h.name AS home, r.name AS room, mt.name AS metric,
       a.value, mt.unit, a.source, a.measured_at
FROM air_readings AS a
JOIN homes   AS h  ON h.id  = a.home_id
JOIN rooms   AS r  ON r.id  = a.room_id
JOIN metrics AS mt ON mt.code = a.metric_code
WHERE h.id = 'h-1' AND a.metric_code = 'CO2'
ORDER BY r.name, a.measured_at;

-- Q3. LEFT JOIN: every room with its sensor count (rooms without sensors show 0).
SELECT r.name AS room, COUNT(s.id) AS sensors
FROM rooms AS r
LEFT JOIN sensors AS s ON s.room_id = r.id
WHERE r.home_id = 'h-1'
GROUP BY r.id, r.name
ORDER BY r.name;

-- Q4. LEFT JOIN + IS NULL (anti-join): rooms that have NO threshold policy.
SELECT r.name AS room_without_policy
FROM rooms AS r
LEFT JOIN threshold_policies AS p ON p.room_id = r.id
WHERE r.home_id = 'h-1' AND p.id IS NULL;

-- Q5. NOT EXISTS: sensors that have never produced a reading.
SELECT s.name AS silent_sensor
FROM sensors AS s
WHERE NOT EXISTS (SELECT 1 FROM air_readings AS a WHERE a.sensor_id = s.id);

-- Q6. GROUP BY / HAVING: per-room CO2 summary, kept separate by source
--     (the dashboard never mixes sources in one average).
SELECT r.name AS room, a.source,
       COUNT(*)              AS readings,
       MIN(a.value)          AS min_ppm,
       ROUND(AVG(a.value))   AS avg_ppm,
       MAX(a.value)          AS max_ppm
FROM air_readings AS a
JOIN rooms AS r ON r.id = a.room_id
WHERE a.home_id = 'h-1' AND a.metric_code = 'CO2'
GROUP BY r.name, a.source
HAVING COUNT(*) >= 1
ORDER BY r.name, a.source;

-- Q7. JOIN to the threshold policy + CASE: classify every living-room CO2 reading.
SELECT a.measured_at, a.value,
       CASE WHEN a.value >= p.high_threshold     THEN 'high'
            WHEN a.value >= p.elevated_threshold THEN 'elevated'
            ELSE 'normal' END AS band
FROM air_readings AS a
JOIN threshold_policies AS p
  ON p.home_id = a.home_id AND p.room_id = a.room_id AND p.metric_code = a.metric_code
WHERE a.room_id = 'r-living' AND a.metric_code = 'CO2' AND a.source = 'device'
ORDER BY a.measured_at;

-- Q8. Correlated subquery: the latest reading of each room/metric.
SELECT r.name AS room, a.metric_code, a.value, a.measured_at
FROM air_readings AS a
JOIN rooms AS r ON r.id = a.room_id
WHERE a.home_id = 'h-1'
  AND a.measured_at = (SELECT MAX(b.measured_at) FROM air_readings AS b
                       WHERE b.home_id = a.home_id AND b.room_id = a.room_id
                         AND b.metric_code = a.metric_code)
ORDER BY r.name, a.metric_code;

-- Q9. Window function LAG: change since the previous reading (device CO2).
--     (Dividing by elapsed minutes is dialect-specific: see Section 8.)
SELECT measured_at, value,
       value - LAG(value) OVER (ORDER BY measured_at) AS change_since_previous
FROM air_readings
WHERE room_id = 'r-living' AND metric_code = 'CO2' AND source = 'device'
ORDER BY measured_at;

-- Q10. CTE + window RANK: peak CO2 reading per room, ranked across the home.
WITH peaks AS (
  SELECT room_id, MAX(value) AS peak_ppm
  FROM air_readings
  WHERE home_id = 'h-1' AND metric_code = 'CO2'
  GROUP BY room_id
)
SELECT r.name AS room, p.peak_ppm,
       RANK() OVER (ORDER BY p.peak_ppm DESC) AS peak_rank
FROM peaks AS p
JOIN rooms AS r ON r.id = p.room_id
ORDER BY peak_rank;

-- Q11. Open alerts with room name (the same set the partial unique index guards).
SELECT r.name AS room, al.level, al.status, al.trigger_value, al.threshold_unit,
       al.created_at, al.acknowledged_by
FROM air_alerts AS al
JOIN rooms AS r ON r.id = al.room_id
WHERE al.status IN ('active', 'acknowledged')
ORDER BY al.created_at;

-- Q12. Alert counts by level and status (GROUP BY with two keys).
SELECT level, status, COUNT(*) AS alerts
FROM air_alerts
GROUP BY level, status
ORDER BY level, status;

-- Q13. UNION ALL: one timeline of alerts and audit events for a home.
SELECT created_at AS at, 'alert' AS kind, level || ' / ' || status AS what
FROM air_alerts WHERE home_id = 'h-1'
UNION ALL
SELECT created_at, 'audit', event_type
FROM audit_logs WHERE home_id = 'h-1'
ORDER BY at;

-- Q14. Access check (authorisation join): may user u-2 see home h-1, and as what?
SELECT m.role
FROM home_memberships AS m
WHERE m.user_id = 'u-2' AND m.home_id = 'h-1';

-- Q15. Pending invitations (not accepted) per home.
SELECT h.name AS home, i.email, i.role, i.expires_at
FROM home_invitations AS i
JOIN homes AS h ON h.id = i.home_id
WHERE i.accepted_at IS NULL
ORDER BY i.expires_at;


-- =============================================================================
-- SECTION 3. VIEWS  (teaching examples; not defined or used by the application)
-- =============================================================================

DROP VIEW IF EXISTS vw_latest_room_readings;
CREATE VIEW vw_latest_room_readings AS
SELECT a.home_id, r.name AS room, a.metric_code, a.value, mt.unit, a.source, a.measured_at
FROM air_readings AS a
JOIN rooms   AS r  ON r.id = a.room_id
JOIN metrics AS mt ON mt.code = a.metric_code
WHERE a.measured_at = (SELECT MAX(b.measured_at) FROM air_readings AS b
                       WHERE b.home_id = a.home_id AND b.room_id = a.room_id
                         AND b.metric_code = a.metric_code);

DROP VIEW IF EXISTS vw_open_alerts;
CREATE VIEW vw_open_alerts AS
SELECT al.id, al.home_id, r.name AS room, al.metric_code, al.level, al.status,
       al.trigger_value, al.threshold_unit, al.created_at, al.acknowledged_by
FROM air_alerts AS al
JOIN rooms AS r ON r.id = al.room_id
WHERE al.status IN ('active', 'acknowledged');

DROP VIEW IF EXISTS vw_daily_room_summary;
CREATE VIEW vw_daily_room_summary AS
SELECT a.home_id, r.name AS room, a.metric_code, a.source,
       date(a.measured_at) AS day,           -- UTC day (PostgreSQL: SET TIME ZONE 'UTC')
       COUNT(*)            AS readings,
       MIN(a.value)        AS min_value,
       AVG(a.value)        AS avg_value,
       MAX(a.value)        AS max_value
FROM air_readings AS a
JOIN rooms AS r ON r.id = a.room_id
GROUP BY a.home_id, r.name, a.metric_code, a.source, date(a.measured_at);

-- Using the views:
SELECT * FROM vw_latest_room_readings WHERE home_id = 'h-1' ORDER BY room, metric_code;
SELECT * FROM vw_open_alerts          WHERE home_id = 'h-1' ORDER BY created_at;
SELECT * FROM vw_daily_room_summary   WHERE home_id = 'h-1' AND metric_code = 'CO2'
ORDER BY day, room, source;


-- =============================================================================
-- SECTION 4. TRANSACTIONS  (illustrate atomic units of work and rollback)
-- =============================================================================
-- The application does its equivalent work through SQLAlchemy sessions; this is
-- the same idea written as SQL.

-- T1. COMMIT: store a new device reading and open the matching alert together,
--     so a reading can never be saved without its alert (or the reverse).
BEGIN;
  INSERT INTO air_readings (home_id, room_id, metric_code, value, source, measured_at, sensor_id, received_at)
  VALUES ('h-1','r-bedroom','CO2', 1600,'device','2026-11-10T09:35:00Z','s-2','2026-11-10T09:35:02Z');
  INSERT INTO air_alerts
    (home_id, room_id, metric_code, level, status, trigger_value, threshold_value,
     latest_value, threshold_unit, clear_duration_seconds, created_at, detail)
  VALUES ('h-1','r-bedroom','CO2','high','active',1600,1500,1600,'ppm',300,
          '2026-11-10T09:35:00Z','CO2 above the high threshold');
  UPDATE sensors SET last_seen_at = '2026-11-10T09:35:02Z' WHERE id = 's-2';
COMMIT;

SELECT status, COUNT(*) AS alerts FROM air_alerts WHERE room_id = 'r-bedroom' GROUP BY status;

-- T2. COMMIT: acknowledge that alert and record who did it, in one transaction.
--     The ck_alerts_transition_metadata CHECK requires acknowledged_at and
--     acknowledged_by to be set together with the status change.
BEGIN;
  UPDATE air_alerts
     SET status = 'acknowledged', acknowledged_at = '2026-11-10T09:40:00Z',
         acknowledged_by = 'Asha Owner'
   WHERE room_id = 'r-bedroom' AND level = 'high' AND status = 'active';
  INSERT INTO audit_logs (home_id, actor_user_id, event_type, entity_type, entity_id, details_json, created_at)
  VALUES ('h-1', 'u-1', 'alert_acknowledged_demo', 'alert', 'bedroom-high', '{}', '2026-11-10T09:40:00Z');
COMMIT;

-- T3. ROLLBACK: a change that is visible inside the transaction and undone after.
BEGIN;
  UPDATE sensors SET status = 'revoked' WHERE id = 's-1';
  SELECT id, status FROM sensors WHERE id = 's-1';      -- shows 'revoked' inside the transaction
ROLLBACK;
SELECT id, status FROM sensors WHERE id = 's-1';        -- back to 'active'

-- T4. Duplicate-safe insert: ON CONFLICT DO NOTHING silently skips a reading that
--     already exists for the same home, room, metric and instant (the table's
--     uq_readings_home_room_metric_time rule). Works in PostgreSQL and SQLite 3.24+.
BEGIN;
  INSERT INTO air_readings (home_id, room_id, metric_code, value, source, measured_at, sensor_id)
  VALUES ('h-1','r-living','CO2', 800,'device','2026-11-10T09:00:00Z','s-1')
  ON CONFLICT (home_id, room_id, metric_code, measured_at) DO NOTHING;
COMMIT;
SELECT COUNT(*) AS living_co2_at_0900
FROM air_readings
WHERE room_id = 'r-living' AND metric_code = 'CO2' AND measured_at = '2026-11-10T09:00:00Z';   -- still 1


-- =============================================================================
-- SECTION 5. OTHER DML  (UPDATE and DELETE with joins/subqueries)
-- =============================================================================

-- U1. Revoke the sensor of a room (set-based UPDATE through a subquery).
UPDATE sensors
   SET status = 'revoked'
 WHERE room_id IN (SELECT id FROM rooms WHERE home_id = 'h-1' AND name = 'Bedroom');

-- U2. Mark an invitation as accepted.
UPDATE home_invitations SET accepted_at = '2026-11-10T10:00:00Z' WHERE id = 'inv-1';

-- D1. Remove an old simulated reading (DELETE with a filter).
DELETE FROM air_readings WHERE source = 'simulated' AND room_id = 'r-bedroom';


-- =============================================================================
-- SECTION 6. INTEGRITY AND CONSISTENCY CHECKS  (all should return zero rows)
-- =============================================================================

-- C1. Readings whose room belongs to a different home. The database does NOT
--     enforce this (no composite foreign key); the application guarantees it.
SELECT a.id FROM air_readings AS a JOIN rooms AS r ON r.id = a.room_id WHERE r.home_id <> a.home_id;

-- C2. Same check for sensors, policies and alerts.
SELECT 'sensor' AS tbl, CAST(s.id AS VARCHAR(64)) AS id FROM sensors AS s JOIN rooms AS r ON r.id = s.room_id WHERE r.home_id <> s.home_id
UNION ALL
SELECT 'policy', CAST(p.id AS VARCHAR(64)) FROM threshold_policies AS p JOIN rooms AS r ON r.id = p.room_id WHERE r.home_id <> p.home_id
UNION ALL
SELECT 'alert',  CAST(al.id AS VARCHAR(64)) FROM air_alerts AS al JOIN rooms AS r ON r.id = al.room_id WHERE r.home_id <> al.home_id;

-- C3. Values the application validates but the database does not constrain.
SELECT id FROM air_readings WHERE source NOT IN ('device', 'dataset', 'simulated');
SELECT home_id, user_id FROM home_memberships WHERE role NOT IN ('owner', 'member');

-- C4. Every home should have at least one owner.
SELECT h.id FROM homes AS h
WHERE NOT EXISTS (SELECT 1 FROM home_memberships AS m WHERE m.home_id = h.id AND m.role = 'owner');


-- =============================================================================
-- SECTION 7. CONSTRAINT DEMONSTRATIONS  (each statement is EXPECTED TO FAIL)
-- =============================================================================
-- Uncomment ONE statement at a time. In PostgreSQL a failed statement aborts the
-- open transaction, so run each on its own (outside BEGIN) or follow it with ROLLBACK.

-- X1. Duplicate reading -> violates uq_readings_home_room_metric_time (UNIQUE).
-- INSERT INTO air_readings (home_id, room_id, metric_code, value, source, measured_at)
-- VALUES ('h-1','r-living','CO2', 999,'device','2026-11-10T09:05:00Z');

-- X2. Second open alert of the same level -> violates uq_open_alert_home_room_metric_level.
-- INSERT INTO air_alerts (home_id, room_id, metric_code, level, status, trigger_value,
--   threshold_value, latest_value, threshold_unit, clear_duration_seconds, created_at, detail)
-- VALUES ('h-1','r-living','CO2','high','active',1800,1500,1800,'ppm',300,'2026-11-10T09:50:00Z','dup');

-- X3. Invalid alert status -> violates ck_alerts_status (CHECK).
-- UPDATE air_alerts SET status = 'ignored' WHERE id = 1;

-- X4. 'acknowledged' without who/when -> violates ck_alerts_transition_metadata.
-- UPDATE air_alerts SET status = 'acknowledged' WHERE status = 'active' AND room_id = 'r-living';

-- X5. Sensor interval outside 30-86400 seconds -> violates ck_sensors_reporting_interval.
-- UPDATE sensors SET reporting_interval_seconds = 5 WHERE id = 's-1';

-- X6. Reading for a room that does not exist -> violates the foreign key.
-- INSERT INTO air_readings (home_id, room_id, metric_code, value, source, measured_at)
-- VALUES ('h-1','no-such-room','CO2', 700,'device','2026-11-10T11:00:00Z');

-- X7. Room names are unique per home ignoring case -> violates uq_rooms_home_lower_name.
-- INSERT INTO rooms (id, home_id, name) VALUES ('r-dup', 'h-1', 'living room');

-- X8. Deleting a room that still has readings -> foreign key blocks it (no cascade).
-- DELETE FROM rooms WHERE id = 'r-living';


-- =============================================================================
-- SECTION 8. DIALECT-SPECIFIC QUERIES (run the one for your database)
-- =============================================================================

-- [PG] S1. Hourly average with date_trunc.
-- SELECT date_trunc('hour', measured_at) AS hour, ROUND(AVG(value)::numeric, 1) AS avg_ppm
-- FROM air_readings WHERE room_id = 'r-living' AND metric_code = 'CO2' AND source = 'device'
-- GROUP BY 1 ORDER BY 1;

-- [SQLite] S1. Hourly average with strftime.
-- SELECT strftime('%Y-%m-%d %H:00', measured_at) AS hour, ROUND(AVG(value), 1) AS avg_ppm
-- FROM air_readings WHERE room_id = 'r-living' AND metric_code = 'CO2' AND source = 'device'
-- GROUP BY 1 ORDER BY 1;

-- [PG] S2. CO2 rise per minute between consecutive readings (rapid-rise idea).
-- SELECT measured_at, value,
--        (value - LAG(value) OVER w)
--        / NULLIF(EXTRACT(EPOCH FROM (measured_at - LAG(measured_at) OVER w)) / 60, 0) AS ppm_per_min
-- FROM air_readings
-- WHERE room_id = 'r-living' AND metric_code = 'CO2' AND source = 'device'
-- WINDOW w AS (ORDER BY measured_at) ORDER BY measured_at;

-- [SQLite] S2. The same with julianday.
-- SELECT measured_at, value,
--        (value - LAG(value) OVER w)
--        / NULLIF((julianday(measured_at) - julianday(LAG(measured_at) OVER w)) * 1440, 0) AS ppm_per_min
-- FROM air_readings
-- WHERE room_id = 'r-living' AND metric_code = 'CO2' AND source = 'device'
-- WINDOW w AS (ORDER BY measured_at) ORDER BY measured_at;

-- [PG] S3. Query plan: does the history lookup use ix_readings_home_room_metric_time?
-- (On a tiny demo table PostgreSQL may choose a sequential scan; that is normal.)
-- EXPLAIN SELECT value FROM air_readings
--  WHERE home_id = 'h-1' AND room_id = 'r-living' AND metric_code = 'CO2'
--    AND measured_at >= '2026-11-10T09:00:00Z';

-- [SQLite] S3. Query plan.
-- EXPLAIN QUERY PLAN SELECT value FROM air_readings
--  WHERE home_id = 'h-1' AND room_id = 'r-living' AND metric_code = 'CO2'
--    AND measured_at >= '2026-11-10T09:00:00Z';


-- =============================================================================
-- SECTION 9. CLEANUP  (drops only the teaching views; run before any Alembic downgrade)
-- =============================================================================
DROP VIEW IF EXISTS vw_daily_room_summary;
DROP VIEW IF EXISTS vw_open_alerts;
DROP VIEW IF EXISTS vw_latest_room_readings;
-- To remove the demo rows too, simply drop the scratch database.