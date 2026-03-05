-- THE TRUTH - D1 Schema for Subscribers

CREATE TABLE IF NOT EXISTS subscribers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    created_ip TEXT,
    confirm_token TEXT NOT NULL UNIQUE,
    confirmed_at TEXT,
    status TEXT NOT NULL DEFAULT 'pending' 
        CHECK(status IN ('pending', 'active', 'unsubscribed'))
);

CREATE INDEX IF NOT EXISTS idx_subscribers_token ON subscribers(confirm_token);
CREATE INDEX IF NOT EXISTS idx_subscribers_status ON subscribers(status);
CREATE INDEX IF NOT EXISTS idx_subscribers_email ON subscribers(email);
