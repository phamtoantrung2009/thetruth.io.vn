# Cloudflare Workers

## Overview

Location: `workers/subscribe/`

The project includes a Cloudflare Worker for handling email subscriptions.

## Architecture

```
User Browser
      ↓
Cloudflare Worker
      ↓
┌─────┴─────┐
↓             ↓
KV          D1
(rate limit) (subscribers)
      ↓
Resend API
(email sending)
```

## Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/subscribe` | POST | Submit email |
| `/subscribe/confirm` | GET | Confirm subscription |
| `/subscribe/unsubscribe` | GET | Unsubscribe |

## Subscribe Flow

```
1. User submits email
   POST /subscribe
   Body: { "email": "user@example.com" }

2. Worker validates
   - Check email format
   - Check rate limit (KV)
   - Check duplicates (D1)

3. Create pending record
   - Generate secure token
   - Store in D1

4. Send confirmation email
   - Via Resend API
   - Include confirmation link

5. Return response to user
   - "Check your email"
```

## Confirm Flow

```
1. User clicks confirmation link
   GET /subscribe/confirm?token=xxx

2. Worker validates token

3. Update status to "active"

4. Redirect to homepage with success
```

## Unsubscribe Flow

```
1. User clicks unsubscribe link
   GET /subscribe/unsubscribe?token=xxx

2. Worker validates token

3. Update status to "unsubscribed"

4. Show confirmation page
```

## Database Schema

Location: `workers/subscribe/schema.sql`

```sql
CREATE TABLE subscribers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    created_ip TEXT,
    confirm_token TEXT NOT NULL UNIQUE,
    confirmed_at TEXT,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK(status IN ('pending', 'active', 'unsubscribed'))
);
```

Fields:
- `id` - Primary key
- `email` - Subscriber email (unique)
- `created_at` - Subscription timestamp
- `created_ip` - IP address (for spam prevention)
- `confirm_token` - Secure confirmation token
- `confirmed_at` - Confirmation timestamp
- `status` - pending | active | unsubscribed

## Security

### Token Generation

Uses cryptographically secure random bytes:

```javascript
function generateToken() {
  const bytes = new Uint8Array(32);
  crypto.getRandomValues(bytes);
  // Convert to base64url
  return btoa(String.fromCharCode(...bytes))
    .replace(/\+/g, '-(/\//g,')
    .replace '_')
    .replace(/=+$/, '');
}
```

- 32 bytes = 256 bits entropy
- Base64url encoded (URL-safe)

### Rate Limiting

- Stored in Cloudflare KV
- Key: `ratelimit:{ip}`
- Limit: 1 request per minute per IP
- TTL: 60 seconds

### Anti-Spam

- Email format validation
- Duplicate prevention (D1 UNIQUE)
- Rate limiting (KV)
- IP tracking (optional)

## Environment Variables

| Variable | Description |
|----------|-------------|
| `SUBSCRIBERS_DB` | D1 database binding |
| `SUBSCRIBERS_KV` | KV namespace binding |
| `RESEND_API_KEY` | Resend API key (secret) |
| `OWNER_EMAIL` | Site owner email (secret) |

## Local Development

### Test Worker

```bash
cd workers/subscribe
wrangler dev
```

### Deploy Worker

```bash
cd workers/subscribe
wrangler deploy
```

### View Logs

```bash
wrangler tail
```

## Configuration

Location: `wrangler.toml`

```toml
[[d1_databases]]
binding = "SUBSCRIBERS_DB"
database_name = "thetruth-subscribers"
database_id = "xxx"

[[kv_namespaces]]
binding = "SUBSCRIBERS_KV"
id = "xxx"
```

## Maintenance

### Export Subscribers

Query D1 directly or add an admin endpoint.

### Clean Up Unconfirmed

Run a D1 query to delete old pending records:

```sql
DELETE FROM subscribers 
WHERE status = 'pending' 
AND created_at < datetime('now', '-7 days');
```

## Troubleshooting

### Emails Not Sending

1. Check Resend API key is set: `wrangler secret list`
2. Check worker logs: `wrangler tail`
3. Verify D1 is bound correctly

### Rate Limit Too Strict

Adjust in `workers/subscribe/index.js`:

```javascript
// Change from 60000ms to higher
if (Date.now() - parseInt(lastSubmit) < 60000)
```

### Duplicate Subscriptions

Check D1 for existing records:

```sql
SELECT * FROM subscribers WHERE email = 'user@example.com';
```
