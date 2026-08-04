-- SQLite migration for deployments that manage schema manually.
-- Run once against a database that already has the original manual_payments table.
-- The bot also performs the same column checks idempotently in db/core.py.

ALTER TABLE manual_payments ADD COLUMN review_source TEXT;
ALTER TABLE manual_payments ADD COLUMN route_reason TEXT;
ALTER TABLE manual_payments ADD COLUMN file_sha256 TEXT;
ALTER TABLE manual_payments ADD COLUMN perceptual_hash TEXT;
ALTER TABLE manual_payments ADD COLUMN gpt_result_json TEXT;
ALTER TABLE manual_payments ADD COLUMN gpt_decision TEXT;
ALTER TABLE manual_payments ADD COLUMN gpt_reason TEXT;
ALTER TABLE manual_payments ADD COLUMN gpt_confidence REAL;
ALTER TABLE manual_payments ADD COLUMN analysis_started_at DATETIME;
ALTER TABLE manual_payments ADD COLUMN analysis_completed_at DATETIME;
ALTER TABLE manual_payments ADD COLUMN receipt_retry_count INTEGER NOT NULL DEFAULT 0;

CREATE INDEX IF NOT EXISTS idx_manual_payments_status
    ON manual_payments(status);
CREATE INDEX IF NOT EXISTS idx_manual_payments_user_created
    ON manual_payments(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_manual_payments_sha256
    ON manual_payments(file_sha256);
