/**
 * THE TRUTH - Email Subscribe Worker
 * Single opt-in flow: insert active immediately, send welcome email.
 */

const SITE_URL = "https://thetruth.io.vn";

// CORS headers
const corsHeaders = {
  "Access-Control-Allow-Origin": SITE_URL,
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};

// Validate email format
function isValidEmail(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

// Rate limiting check
async function checkRateLimit(KV, ip) {
  const key = `ratelimit:${ip}`;
  const lastSubmit = await KV.get(key);
  if (lastSubmit && Date.now() - parseInt(lastSubmit) < 60000) {
    return false; // Too soon
  }
  await KV.put(key, Date.now().toString(), { expirationTtl: 60 });
  return true;
}

// Send email via Resend
async function sendEmail(RESEND_API_KEY, OWNER_EMAIL, to, subject, html) {
  if (!RESEND_API_KEY) {
    console.error("RESEND_API_KEY not configured");
    return false;
  }

  try {
    const response = await fetch('https://api.resend.com/emails', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${RESEND_API_KEY}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        from: 'THE TRUTH <noreply@thetruth.io.vn>',
        to: to,
        subject: subject,
        html: html,
      }),
    });

    const result = await response.json();
    console.log("Resend response:", result);

    return response.ok;
  } catch (e) {
    console.error("Resend error:", e);
    return false;
  }
}

// Build welcome email HTML
function buildWelcomeEmail() {
  return `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="background:#0d0d0d;color:#e5e5e5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;margin:0;padding:40px 20px;line-height:1.7;">
  <div style="max-width:520px;margin:0 auto;">

    <p style="margin-bottom:24px;">Chào bạn,</p>

    <p style="margin-bottom:16px;">Bạn vừa đăng ký theo dõi THE TRUTH.</p>

    <p style="margin-bottom:16px;">Trước khi chúng ta bắt đầu, có một điều cần làm rõ: Đây không phải là nơi để tìm kiếm sự an ủi, những lời động viên suông, hay những mẹo làm giàu nhanh chóng. Nếu bạn đang tìm kiếm một "người truyền cảm hứng", có lẽ bạn đã chọn nhầm địa chỉ.</p>

    <p style="margin-bottom:24px;color:#e63946;font-weight:600;">THE TRUTH là một công cụ quan sát.</p>

    <p style="margin-bottom:16px;">Tại đây, chúng tôi không phân tích cá nhân. Chúng tôi phân tích hệ thống. Những áp lực mà nam giới Việt Nam 30+ đang gánh vác — từ cái bẫy thu nhập so với tài sản, cho đến sự giằng xé giữa nghĩa vụ gia đình và quyền tự chủ — không phải là "lỗi của riêng bạn". Đó là kết quả của những cấu trúc kinh tế và xã hội đã được thiết kế sẵn.</p>

    <p style="margin-bottom:12px;font-weight:600;">Chúng tôi cam kết 03 điều:</p>
    <ul style="margin:0 0 24px 20px;padding:0;">
      <li style="margin-bottom:8px;"><strong>Hệ thống, không phải cá nhân:</strong> Vạch trần cơ chế, không đổ lỗi cho nạn nhân.</li>
      <li style="margin-bottom:8px;"><strong>Bằng chứng hơn giả định:</strong> Dùng dữ liệu và logic để giải mã, không dùng cảm xúc để dẫn dắt.</li>
      <li style="margin-bottom:8px;"><strong>Giải pháp hơn phẫn nộ:</strong> Mỗi bài phân tích sẽ giúp bạn nhìn rõ câu hỏi, thay vì lún sâu vào sự tuyệt vọng.</li>
    </ul>

    <p style="margin-bottom:24px;">Chúng tôi theo dõi 15 điểm căng thẳng cốt lõi trong cuộc sống của bạn: từ việc thuê trọ vs sở hữu, cho đến sự đối đầu giữa lương và lạm phát.</p>

    <p style="margin-bottom:16px;"><strong>Bước tiếp theo:</strong> Hãy chuẩn bị tinh thần cho những sự thật khó chịu. Chúng tôi không ở đây để làm bạn vui, chúng tôi ở đây để giúp bạn nhìn thấy thực tại một cách chính xác nhất.</p>

    <p style="margin-bottom:24px;">Bạn có thể theo dõi thêm các lát cắt thực tế tại TikTok: <a href="https://tiktok.com/@pepsiman1331" style="color:#e63946;">@pepsiman1331</a></p>

    <p style="margin-bottom:8px;">Chào mừng bạn đã gia nhập hàng ngũ những người chọn cách quan sát thay vì chấp nhận mù quáng.</p>

    <p style="margin-top:40px;font-weight:700;">THE TRUTH</p>
    <p style="color:#666;font-size:0.9em;">Giải mã thực tại kinh tế - xã hội.</p>

  </div>
</body>
</html>`;
}

async function handleSubscribe(request, env) {
  const { DB, SUBSCRIBERS_KV, RESEND_API_KEY, OWNER_EMAIL } = env;

  // Rate limit
  const ip = request.headers.get('CF-Connecting-IP') || 'unknown';
  if (!(await checkRateLimit(SUBSCRIBERS_KV, ip))) {
    return new Response(JSON.stringify({ success: false, message: "Thử lại sau 1 phút." }), {
      status: 429,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });
  }

  let body;
  try {
    body = await request.json();
  } catch {
    return new Response(JSON.stringify({ success: false, message: "Invalid JSON" }), {
      status: 400,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });
  }

  const email = body.email?.toLowerCase().trim();
  if (!email || !isValidEmail(email)) {
    return new Response(JSON.stringify({ success: false, message: "Email không hợp lệ." }), {
      status: 400,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });
  }

  // Check for existing subscriber (any status)
  let existing;
  try {
    existing = await DB.prepare(
      "SELECT status FROM subscribers WHERE email = ?"
    ).bind(email).first();
  } catch (e) {
    // Table might not exist yet — continue to insert
  }

  if (existing) {
    return new Response(JSON.stringify({ success: false, message: "Email đã đăng ký." }), {
      status: 409,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });
  }

  // Insert as active immediately (no confirmation step)
  try {
    await DB.prepare(
      "INSERT INTO subscribers (email, status, created_ip) VALUES (?, 'active', ?)"
    ).bind(email, ip).run();
  } catch (e) {
    console.error("DB insert error:", e);
    return new Response(JSON.stringify({ success: false, message: "Lỗi hệ thống. Thử lại sau." }), {
      status: 500,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    });
  }

  // Send welcome email (blocking for debug)
  const emailOk = await sendEmail(RESEND_API_KEY, OWNER_EMAIL, email, "Chào mừng bạn đến với THE TRUTH", buildWelcomeEmail());
  console.log("Welcome email result:", emailOk);

  // Notify owner (non-blocking)
  if (OWNER_EMAIL && RESEND_API_KEY) {
    sendEmail(RESEND_API_KEY, OWNER_EMAIL,
      OWNER_EMAIL,
      "🔔 New subscriber",
      `<p>New subscriber (active): ${email}</p>`
    ).catch(() => { });
  }

  return new Response(JSON.stringify({ success: true, message: "Đăng ký thành công! Kiểm tra email của bạn." }), {
    headers: { ...corsHeaders, 'Content-Type': 'application/json' },
  });
}

async function handleUnsubscribe(request, env) {
  const { DB } = env;
  const url = new URL(request.url);
  const token = url.searchParams.get('token');

  if (!token) {
    return new Response("Missing token", { status: 400 });
  }

  // Find by token
  let subscriber;
  try {
    subscriber = await DB.prepare(
      "SELECT email FROM subscribers WHERE confirm_token = ?"
    ).bind(token).first();
  } catch (e) {
    return new Response("Database error", { status: 500 });
  }

  if (!subscriber) {
    return new Response("Invalid token", { status: 404 });
  }

  // Unsubscribe
  await DB.prepare(
    "UPDATE subscribers SET status = 'unsubscribed' WHERE confirm_token = ?"
  ).bind(token).run();

  return new Response(`<html><body style="background:#0d0d0d;color:#e5e5e5;font-family:system-ui;padding:40px;text-align:center;"><h2>Đã hủy đăng ký.</h2><p><a href="${SITE_URL}" style="color:#e63946;">Quay lại trang chủ</a></p></body></html>`, {
    headers: { 'Content-Type': 'text/html' },
  });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = url.pathname;

    // Handle CORS preflight
    if (request.method === 'OPTIONS') {
      return new Response(null, { headers: corsHeaders });
    }

    try {
      // Routes
      if (path === '/api/subscribe' && request.method === 'POST') {
        return handleSubscribe(request, env);
      }

      if (path === '/api/subscribe/confirm') {
        // Double opt-in removed — this endpoint is no longer used
        return new Response("Gone: confirmation step removed.", { status: 410 });
      }

      if (path === '/api/subscribe/unsubscribe' && request.method === 'GET') {
        return handleUnsubscribe(request, env);
      }

      return new Response("Not found", { status: 404 });

    } catch (e) {
      return new Response("Internal error: " + e.message, { status: 500 });
    }
  },
};
