BEGIN;

CREATE TABLE IF NOT EXISTS signal_releases (
    id UUID PRIMARY KEY,
    edition_number INTEGER NOT NULL CHECK (edition_number > 0),
    issue_date DATE NOT NULL,
    edition_type TEXT NOT NULL CHECK (edition_type IN ('daily', 'weekly_wrap')),
    release_scope TEXT NOT NULL CHECK (release_scope IN ('proof', 'production')),
    state TEXT NOT NULL CHECK (state IN (
        'PREPARING', 'HELD', 'LOCKED', 'SCHEDULED', 'DELIVERING',
        'DELIVERED', 'LATE_RECOVERY', 'FAILED', 'EXPIRED'
    )),
    editorial_revision TEXT NOT NULL,
    renderer TEXT NOT NULL,
    release_id TEXT NOT NULL,
    git_commit CHAR(40) NOT NULL,
    subject TEXT NOT NULL,
    html_body TEXT NOT NULL,
    html_sha256 CHAR(64) NOT NULL,
    image_id TEXT,
    image_sha256 CHAR(64),
    audience_sha256 CHAR(64) NOT NULL,
    audience_count INTEGER NOT NULL CHECK (audience_count > 0 AND audience_count <= 500),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    scheduled_for TIMESTAMPTZ NOT NULL,
    window_start TIMESTAMPTZ NOT NULL,
    window_end TIMESTAMPTZ NOT NULL,
    claim_token UUID,
    claim_expires_at TIMESTAMPTZ,
    locked_at TIMESTAMPTZ,
    delivered_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT signal_releases_edition_type_scope_unique UNIQUE (edition_number, edition_type, release_scope),
    CONSTRAINT signal_releases_issue_type_scope_unique UNIQUE (issue_date, edition_type, release_scope),
    CONSTRAINT signal_releases_window_order CHECK (
        window_start <= scheduled_for AND scheduled_for <= window_end
    ),
    CONSTRAINT signal_releases_html_sha_format CHECK (html_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT signal_releases_audience_sha_format CHECK (audience_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT signal_releases_image_pair CHECK (
        (image_id IS NULL AND image_sha256 IS NULL)
        OR (image_id IS NOT NULL AND image_sha256 ~ '^[0-9a-f]{64}$')
    ),
    CONSTRAINT signal_releases_claim_pair CHECK (
        (claim_token IS NULL AND claim_expires_at IS NULL)
        OR (claim_token IS NOT NULL AND claim_expires_at IS NOT NULL)
    )
);

CREATE TABLE IF NOT EXISTS signal_release_recipients (
    id BIGSERIAL PRIMARY KEY,
    release_id UUID NOT NULL REFERENCES signal_releases(id) ON DELETE RESTRICT,
    subscriber_id BIGINT,
    recipient_email TEXT NOT NULL,
    recipient_hash CHAR(64) NOT NULL,
    first_name TEXT,
    unsubscribe_token TEXT,
    recipient_html_body TEXT NOT NULL,
    recipient_html_sha256 CHAR(64) NOT NULL,
    delivery_state TEXT NOT NULL DEFAULT 'PENDING' CHECK (
        delivery_state IN ('PENDING', 'SENDING', 'SENT', 'DELIVERED', 'BOUNCED', 'FAILED')
    ),
    idempotency_key TEXT NOT NULL,
    provider_message_id TEXT,
    attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    last_error TEXT,
    sent_at TIMESTAMPTZ,
    delivered_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT signal_release_recipient_unique UNIQUE (release_id, recipient_hash),
    CONSTRAINT signal_release_idempotency_unique UNIQUE (idempotency_key),
    CONSTRAINT signal_release_provider_message_unique UNIQUE (provider_message_id),
    CONSTRAINT signal_release_recipient_hash_format CHECK (recipient_hash ~ '^[0-9a-f]{64}$'),
    CONSTRAINT signal_release_recipient_html_sha_format CHECK (recipient_html_sha256 ~ '^[0-9a-f]{64}$')
    ,CONSTRAINT signal_release_provider_state_check CHECK (
        delivery_state IN ('PENDING', 'SENDING', 'FAILED')
        OR (provider_message_id IS NOT NULL AND sent_at IS NOT NULL)
    )
);

CREATE TABLE IF NOT EXISTS signal_release_events (
    id BIGSERIAL PRIMARY KEY,
    release_id UUID REFERENCES signal_releases(id) ON DELETE RESTRICT,
    recipient_id BIGINT REFERENCES signal_release_recipients(id) ON DELETE RESTRICT,
    event_type TEXT NOT NULL,
    from_state TEXT,
    to_state TEXT,
    event_key TEXT UNIQUE,
    event_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    payload JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS signal_release_recipients_pending_idx
    ON signal_release_recipients (release_id, delivery_state);
CREATE INDEX IF NOT EXISTS signal_release_events_release_time_idx
    ON signal_release_events (release_id, event_time);

CREATE OR REPLACE FUNCTION signal_validate_release_update()
RETURNS TRIGGER AS $$
DECLARE
    transition_ok BOOLEAN;
BEGIN
    transition_ok := CASE OLD.state
        WHEN 'PREPARING' THEN NEW.state IN ('PREPARING', 'HELD', 'LOCKED')
        WHEN 'HELD' THEN NEW.state IN ('HELD', 'PREPARING', 'EXPIRED')
        WHEN 'LOCKED' THEN NEW.state IN ('LOCKED', 'SCHEDULED', 'EXPIRED')
        WHEN 'SCHEDULED' THEN NEW.state IN ('SCHEDULED', 'DELIVERING', 'EXPIRED')
        WHEN 'DELIVERING' THEN NEW.state IN ('DELIVERING', 'DELIVERED', 'FAILED', 'LATE_RECOVERY')
        WHEN 'DELIVERED' THEN NEW.state = 'DELIVERED'
        WHEN 'LATE_RECOVERY' THEN NEW.state = 'LATE_RECOVERY'
        WHEN 'FAILED' THEN NEW.state = 'FAILED'
        WHEN 'EXPIRED' THEN NEW.state = 'EXPIRED'
        ELSE FALSE
    END;

    IF NOT transition_ok THEN
        RAISE EXCEPTION 'illegal Signal release transition: % -> %', OLD.state, NEW.state;
    END IF;

    IF OLD.state IN ('LOCKED', 'SCHEDULED', 'DELIVERING', 'DELIVERED', 'LATE_RECOVERY', 'FAILED', 'EXPIRED')
       AND (
            NEW.edition_number IS DISTINCT FROM OLD.edition_number
            OR NEW.issue_date IS DISTINCT FROM OLD.issue_date
            OR NEW.edition_type IS DISTINCT FROM OLD.edition_type
            OR NEW.release_scope IS DISTINCT FROM OLD.release_scope
            OR NEW.editorial_revision IS DISTINCT FROM OLD.editorial_revision
            OR NEW.renderer IS DISTINCT FROM OLD.renderer
            OR NEW.release_id IS DISTINCT FROM OLD.release_id
            OR NEW.git_commit IS DISTINCT FROM OLD.git_commit
            OR NEW.subject IS DISTINCT FROM OLD.subject
            OR NEW.html_body IS DISTINCT FROM OLD.html_body
            OR NEW.html_sha256 IS DISTINCT FROM OLD.html_sha256
            OR NEW.image_id IS DISTINCT FROM OLD.image_id
            OR NEW.image_sha256 IS DISTINCT FROM OLD.image_sha256
            OR NEW.audience_sha256 IS DISTINCT FROM OLD.audience_sha256
            OR NEW.audience_count IS DISTINCT FROM OLD.audience_count
            OR NEW.metadata IS DISTINCT FROM OLD.metadata
            OR NEW.scheduled_for IS DISTINCT FROM OLD.scheduled_for
            OR NEW.window_start IS DISTINCT FROM OLD.window_start
            OR NEW.window_end IS DISTINCT FROM OLD.window_end
       ) THEN
        RAISE EXCEPTION 'locked Signal release identity is immutable';
    END IF;

    NEW.updated_at := NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger
        WHERE tgname = 'signal_release_update_guard'
          AND tgrelid = 'signal_releases'::regclass
          AND NOT tgisinternal
    ) THEN
        CREATE TRIGGER signal_release_update_guard
        BEFORE UPDATE ON signal_releases
        FOR EACH ROW EXECUTE FUNCTION signal_validate_release_update();
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION signal_validate_recipient_update()
RETURNS TRIGGER AS $$
DECLARE
    release_state TEXT;
    transition_ok BOOLEAN;
BEGIN
    SELECT state INTO release_state FROM signal_releases WHERE id = OLD.release_id;
    IF release_state IN ('LOCKED', 'SCHEDULED', 'DELIVERING', 'DELIVERED', 'LATE_RECOVERY', 'FAILED', 'EXPIRED')
       AND (
            NEW.release_id IS DISTINCT FROM OLD.release_id
            OR NEW.subscriber_id IS DISTINCT FROM OLD.subscriber_id
            OR NEW.recipient_email IS DISTINCT FROM OLD.recipient_email
            OR NEW.recipient_hash IS DISTINCT FROM OLD.recipient_hash
            OR NEW.first_name IS DISTINCT FROM OLD.first_name
            OR NEW.unsubscribe_token IS DISTINCT FROM OLD.unsubscribe_token
            OR NEW.recipient_html_body IS DISTINCT FROM OLD.recipient_html_body
            OR NEW.recipient_html_sha256 IS DISTINCT FROM OLD.recipient_html_sha256
            OR NEW.idempotency_key IS DISTINCT FROM OLD.idempotency_key
       ) THEN
        RAISE EXCEPTION 'locked Signal recipient identity is immutable';
    END IF;

    transition_ok := CASE OLD.delivery_state
        WHEN 'PENDING' THEN NEW.delivery_state IN ('PENDING', 'SENDING')
        WHEN 'SENDING' THEN NEW.delivery_state IN ('SENDING', 'SENT', 'FAILED')
        WHEN 'SENT' THEN NEW.delivery_state IN ('SENT', 'DELIVERED', 'BOUNCED')
        WHEN 'DELIVERED' THEN NEW.delivery_state IN ('DELIVERED', 'BOUNCED')
        WHEN 'BOUNCED' THEN NEW.delivery_state = 'BOUNCED'
        WHEN 'FAILED' THEN NEW.delivery_state = 'FAILED'
        ELSE FALSE
    END;
    IF NOT transition_ok THEN
        RAISE EXCEPTION 'illegal Signal recipient transition: % -> %', OLD.delivery_state, NEW.delivery_state;
    END IF;
    NEW.updated_at := NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger
        WHERE tgname = 'signal_recipient_update_guard'
          AND tgrelid = 'signal_release_recipients'::regclass
          AND NOT tgisinternal
    ) THEN
        CREATE TRIGGER signal_recipient_update_guard
        BEFORE UPDATE ON signal_release_recipients
        FOR EACH ROW EXECUTE FUNCTION signal_validate_recipient_update();
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION signal_events_append_only()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Signal release events are append-only';
END;
$$ LANGUAGE plpgsql;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger
        WHERE tgname = 'signal_events_no_update'
          AND tgrelid = 'signal_release_events'::regclass
          AND NOT tgisinternal
    ) THEN
        CREATE TRIGGER signal_events_no_update
        BEFORE UPDATE OR DELETE ON signal_release_events
        FOR EACH ROW EXECUTE FUNCTION signal_events_append_only();
    END IF;
END;
$$;
