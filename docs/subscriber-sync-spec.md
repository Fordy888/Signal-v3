# Subscriber Sync Specification

**Version:** 1.0
**Status:** Ready to implement
**Last updated:** 5 July 2026

## Overview

The Signal pipeline currently uses a static config/subscribers.yaml file.
This spec defines how the pipeline will consume the website API at runtime,
eliminating manual YAML management.

## API Endpoints

### GET /api/pipeline/subscribers

Returns all active subscribers.

- URL: {PUBLIC_BASE_URL}/api/pipeline/subscribers
- Method: GET
- Auth: Authorization: Bearer {SIGNAL_PIPELINE_API_KEY}
- Success: 200 OK

Response:
```json
{
  "subscribers": [
    {"email": "paul@example.com", "firstName": "Paul", "subscribedAt": "2026-06-29T14:30:00.000Z"}
  ]
}
```

### GET /api/pipeline/subscriber-token

Returns the unsubscribe token for a specific subscriber.

- URL: {PUBLIC_BASE_URL}/api/pipeline/subscriber-token?email={email}
- Method: GET
- Auth: Authorization: Bearer {SIGNAL_PIPELINE_API_KEY}
- Success: 200 OK

Response:
```json
{"token": "abc123-unsubscribe-token"}
```

## Pipeline Integration

New module: src/subscribers.py

- fetch_subscribers() -> list[dict] : Fetches active subscribers from website API
- fetch_unsubscribe_token(email) -> str | None : Gets unsubscribe token per subscriber

## Environment Variables

| Variable | Where | Purpose |
|----------|-------|---------|
| SIGNAL_PIPELINE_API_KEY | Render + Website | Shared secret for API auth |
| WEBSITE_BASE_URL | Render | Website URL |
| PROOF_RECIPIENT_EMAIL | Render | Paul's email for proof delivery |

## Migration Path

| Phase | Source | When |
|-------|--------|------|
| Phase 1 (now) | config/subscribers.yaml | Manual YAML edits |
| Phase 2 (11-40 subs) | Website API | Automatic at --send time |
| Phase 3 (40+) | Website API + Resend Broadcasts | Pipeline creates broadcast |

## Error Handling

| Scenario | Behaviour |
|----------|-----------|
| API returns 401 | Abort (auth issue must be fixed) |
| API returns 500 | Retry once after 5s, then abort |
| API timeout (>15s) | Abort |
| Empty list returned | Abort (safety - never send to 0) |
| Token fetch fails | Skip unsubscribe URL, still send |

## Transition Checklist (Phase 1 to Phase 2)

1. Deploy src/subscribers.py to the pipeline
2. Set WEBSITE_BASE_URL and SIGNAL_PIPELINE_API_KEY on Render
3. Update main.py send_to_subscribers() to call fetch_subscribers()
4. Keep subscribers.yaml as fallback
5. Test with: python -m src.main --send --subscriber paul_ford

## Unsubscribe URL Format

{WEBSITE_BASE_URL}/unsubscribe?token={subscriber_token}

Injected into HTML footer of each edition.
