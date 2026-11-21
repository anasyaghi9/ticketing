SELECT count(*) AS total_bookings FROM events_booking;

SELECT indexname AS idx FROM pg_indexes
WHERE tablename = 'events_booking' AND indexdef LIKE '%(status, hold_expires_at)%' \gset
\echo Index under test: :idx

\echo
\echo === WITH the index ===
EXPLAIN (ANALYZE, BUFFERS)
SELECT id FROM events_booking WHERE status = 'pending' AND hold_expires_at < now();

BEGIN;
DROP INDEX :"idx";
\echo
\echo === WITHOUT the index ===
EXPLAIN (ANALYZE, BUFFERS)
SELECT id FROM events_booking WHERE status = 'pending' AND hold_expires_at < now();
ROLLBACK;

\echo
\echo === index is back after ROLLBACK? ===
SELECT indexname FROM pg_indexes WHERE tablename = 'events_booking' AND indexdef LIKE '%(status, hold_expires_at)%';