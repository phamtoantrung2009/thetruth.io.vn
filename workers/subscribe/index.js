/**
THE TRUTH - Email Subscribe Worker
Double opt-in flow with secure tokens
*/

const SITE_URL = "https://thetruth.io.vn";

// CORS headers
const corsHeaders = {
  "Access-Control-Allow-Origin": SITE_URL,
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};

// Generate cryptographically secure token
function generateToken() {
  const bytes = new Uint8Array(32);
  crypto.getRandomValues(bytes);

  const binary = String.fromCharCode(...bytes);
  return btoa(binary)
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
}

// Validate email
function isValidEmail(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

// Rate limit
async function checkRateLimit(KV, ip) {
  const key = `ratelimit:${ip}`;
  const lastSubmit = await KV.get(key);

  if (lastSubmit && Date.now() - parseInt(lastSubmit) < 60000) {
    return false;
  }

  await KV.put(key, Date.now().toString(), { expirationTtl: 60 });

  return true;
}

// Send email
async function sendEmail(apiKey, to, subject, html) {
  const response = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${apiKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      from: "THE TRUTH <noreply@thetruth.io.vn>",
      to,
      subject,
      html,
    }),
  });

  return response.ok;
}

async function handleSubscribe(request, env) {
  const DB = env.DB;
  const KV = env.SUBSCRIBERS_KV;

  const ip = request.headers.get("CF-Connecting-IP") || "unknown";

  if (!(await checkRateLimit(KV, ip))) {
    return new Response(
      JSON.stringify({
        success: false,
        message: "Thử lại sau 1 phút.",
      }),
      {
        status: 429,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      }
    );
  }

  let body;

  try {
    body = await request.json();
  } catch {
    return new Response(
      JSON.stringify({
        success: false,
        message: "Invalid JSON",
      }),
      {
        status: 400,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      }
    );
  }

  const email = body.email?.toLowerCase().trim();

  if (!email || !isValidEmail(email)) {
    return new Response(
      JSON.stringify({
        success: false,
        message: "Email không hợp lệ.",
      }),
      {
        status: 400,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      }
    );
  }

  let existing;

  try {
    existing = await DB.prepare(
      "SELECT status FROM subscribers WHERE email = ?"
    )
      .bind(email)
      .first();
  } catch (e) { }

  if (existing) {
    if (existing.status === "active") {
      return new Response(
        JSON.stringify({
          success: false,
          message: "Email đã đăng ký.",
        }),
        {
          status: 409,
          headers: { ...corsHeaders, "Content-Type": "application/json" },
        }
      );
    }

    if (existing.status === "pending") {
      return new Response(
        JSON.stringify({
          success: true,
          message: "Email đã được gửi. Kiểm tra hòm thư.",
        }),
        {
          headers: { ...corsHeaders, "Content-Type": "application/json" },
        }
      );
    }
  }

  const token = generateToken();

  const confirmUrl = `${SITE_URL}/subscribe/confirm?token=${token}`;

  try {
    await DB.prepare(
      "INSERT INTO subscribers (email, confirm_token, created_ip) VALUES (?, ?, ?)"
    )
      .bind(email, token, ip)
      .run();

    await sendEmail(
      env.RESEND_API_KEY,
      email,
      "Xác nhận đăng ký - THE TRUTH",
      `
      <h2>Xác nhận đăng ký</h2>
      <p>Nhấp vào link bên dưới để xác nhận:</p>
      <p>
        <a href="${confirmUrl}" 
        style="background:#e63946;color:#fff;padding:12px 24px;text-decoration:none;border-radius:4px;display:inline-block;">
        Xác nhận
        </a>
      </p>
      <p>Link hết hạn sau 24 giờ.</p>
      <p><small>Nếu bạn không đăng ký, bỏ qua email này.</small></p>
      `
    );

    await sendEmail(
      env.RESEND_API_KEY,
      env.OWNER_EMAIL,
      "🔔 New subscriber",
      `<p>New pending subscriber: ${email}</p>`
    );

    return new Response(
      JSON.stringify({
        success: true,
        message: "Kiểm tra email để xác nhận.",
      }),
      {
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      }
    );
  } catch (e) {
    return new Response(
      JSON.stringify({
        success: false,
        message: "Lỗi server. Thử lại sau.",
      }),
      {
        status: 500,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      }
    );
  }
}

async function handleConfirm(request, env) {
  const DB = env.DB;

  const url = new URL(request.url);
  const token = url.searchParams.get("token");

  if (!token) {
    return new Response("Missing token", { status: 400 });
  }

  const subscriber = await DB.prepare(
    "SELECT email FROM subscribers WHERE confirm_token = ? AND status = 'pending'"
  )
    .bind(token)
    .first();

  if (!subscriber) {
    return new Response("Invalid or expired token", { status: 404 });
  }

  await DB.prepare(
    "UPDATE subscribers SET status='active', confirmed_at=datetime('now') WHERE confirm_token=?"
  )
    .bind(token)
    .run();

  return Response.redirect(`${SITE_URL}?subscribed=true`, 302);
}

async function handleUnsubscribe(request, env) {
  const DB = env.DB;

  const url = new URL(request.url);
  const token = url.searchParams.get("token");

  if (!token) {
    return new Response("Missing token", { status: 400 });
  }

  const subscriber = await DB.prepare(
    "SELECT email FROM subscribers WHERE confirm_token = ?"
  )
    .bind(token)
    .first();

  if (!subscriber) {
    return new Response("Invalid token", { status: 404 });
  }

  await DB.prepare(
    "UPDATE subscribers SET status='unsubscribed' WHERE confirm_token=?"
  )
    .bind(token)
    .run();

  return new Response(
    `
    <html>
    <body style="background:#0d0d0d;color:#e5e5e5;font-family:system-ui;padding:40px;text-align:center;">
      <h2>Đã hủy đăng ký.</h2>
      <p><a href="${SITE_URL}" style="color:#e63946;">Quay lại trang chủ</a></p>
    </body>
    </html>
    `,
    {
      headers: { "Content-Type": "text/html" },
    }
  );
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = url.pathname;

    if (request.method === "OPTIONS") {
      return new Response(null, { headers: corsHeaders });
    }

    try {
      if (path === "/subscribe" && request.method === "POST") {
        return handleSubscribe(request, env);
      }

      if (path === "/subscribe/confirm" && request.method === "GET") {
        return handleConfirm(request, env);
      }

      if (path === "/subscribe/unsubscribe" && request.method === "GET") {
        return handleUnsubscribe(request, env);
      }

      return new Response("Not found", { status: 404 });
    } catch (e) {
      return new Response("Internal error: " + e.message, { status: 500 });
    }
  },
};