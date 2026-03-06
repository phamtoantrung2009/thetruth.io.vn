/**
 * THE TRUTH - Email Subscribe Worker
 * Double opt-in flow with secure tokens
 */

const SITE_URL = "https://thetruth.io.vn";

// CORS headers
const corsHeaders = {
  "Access-Control-Allow-Origin": SITE_URL,
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};

// Generate cryptographically secure token (32 bytes)
function generateToken() {
  const bytes = new Uint8Array(32);
  crypto.getRandomValues(bytes);
  // Convert to base64url
  const binary = String.fromCharCode(...bytes);
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

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

  // Check for existing subscriber
  let existing;
  try {
    existing = await DB.prepare(
      "SELECT status FROM subscribers WHERE email = ?"
    ).bind(email).first();
  } catch (e) {
    // Table might not exist yet
  }

  if (existing) {
    if (existing.status === 'active') {
      return new Response(JSON.stringify({ success: false, message: "Email đã đăng ký." }), {
        status: 409,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      });
    }
    if (existing.status === 'pending') {
      return new Response(JSON.stringify({ success: true, message: "Email đã được gửi. Kiểm tra hòm thư." }), {
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      });
    }
  }

  // Generate confirmation token
  const token = generateToken();
  const confirmUrl = `${SITE_URL}/subscribe/confirm?token=${token}`;

  // Insert pending subscriber FIRST (before sending email)
  await DB.prepare(
    "INSERT INTO subscribers (email, confirm_token, created_ip) VALUES (?, ?, ?)"
  ).bind(email, token, ip).run();

  // Send confirmation email
  let emailSent = false;
  let emailError = "";
  
  try {
    emailSent = await sendEmail(RESEND_API_KEY, OWNER_EMAIL,
      email,
      "Xác nhận đăng ký - THE TRUTH",
      `<h2>Xác nhận đăng ký</h2>
       <p>Nhấp vào link bên dưới để xác nhận:</p>
       <p><a href="${confirmUrl}" style="background:#e63946;color:#fff;padding:12px 24px;text-decoration:none;border-radius:4px;display:inline-block;">Xác nhận</a></p>
       <p>Link hết hạn sau 24 giờ.</p>
       <p><small>Nếu bạn không đăng ký, bỏ qua email này.</small></p>`
    );
  } catch (e) {
    emailError = e.message;
  }

  // Notify owner (non-blocking)
  if (OWNER_EMAIL && RESEND_API_KEY) {
    sendEmail(RESEND_API_KEY, OWNER_EMAIL,
      OWNER_EMAIL,
      "🔔 New subscriber",
      `<p>New pending subscriber: ${email}</p>`
    ).catch(() => {}); // Don't fail if owner notification fails
  }

  if (!emailSent) {
    // Email failed - log for debugging
    console.log("Email send failed. Error:", emailError, "RESEND_KEY exists:", !!RESEND_API_KEY);
  }

  return new Response(JSON.stringify({ success: true, message: "Kiểm tra email để xác nhận." }), {
    headers: { ...corsHeaders, 'Content-Type': 'application/json' },
  });
}

// Build welcome email HTML
function buildWelcomeEmail() {
  return `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="background:#0d0d0d;color:#e5e5e5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;margin:0;padding:40px 20px;line-height:1.6;">
  <div style="max-width:520px;margin:0 auto;">
    <p style="margin-bottom:30px;">Bạn đã đến đây.</p>
    
    <p>Đó không phải một quyết định ngẫu nhiên. Bạn không tình cờ nhấn nút đăng ký. Có một lý do bạn muốn hiểu cách thức vận hành của thứ gọi là "hệ thống" — và tại sao nó khiến cuộc sống trở nên khó hiểu đến vậy.</p>
    
    <p>THE TRUTH không phải một diễn giả. Chúng tôi không động viên. Chúng tôi không kể bạn nghe những gì bạn muốn nghe.</p>
    
    <p>Chúng tôi là một công cụ quan sát. Phân tích cấu trúc. Bằng chứng, không phải cảm xúc.</p>
    
    <p>Mỗi tuần, bạn sẽ nhận được những bài viết đi sâu vào các lực định hình cuộc sống tầng lớp trung lưu Việt Nam: thu nhập vs tài sản, làm việc vs vốn, nghĩa vụ gia đình vs tự chủ. Không có câu trả lời dễ dàng. Chỉ có câu hỏi được làm rõ hơn.</p>
    
    <p><strong>Đây là điều bạn sẽ nhận được:</strong></p>
    <ul style="margin:20px 0;">
      <li>Phân tích về những gì thực sự đang xảy ra với kinh tế, xã hội, và cấu trúc quyền lực ở Việt Nam.</li>
      <li>Những góc nhìn mà truyền thông chính thức không đề cập.</li>
      <li>Không hype. Không motivational quotes. Chỉ sự thật lạnh lùng.</li>
    </ul>
    
    <p style="margin-top:30px;">Nếu bạn muốn bắt đầu ngay hôm nay:</p>
    
    <p><a href="https://thetruth.io.vn/cai-bay-cong-luong-lam-phat-vietnam" style="color:#e63946;text-decoration:underline;">Cai Bay Công Lương, Lạm Phát Vietnam →</a></p>
    <p><a href="https://thetruth.io.vn/khung-hoang-nam-tinh-ap-luc-tru-cot" style="color:#e63946;text-decoration:underline;">Khung Hoảng Năm Tính, Áp Lực Trụ Cột →</a></p>
    <p><a href="https://thetruth.io.vn/tiet-kiem-khong-mua-duoc-nha-pho" style="color:#e63946;text-decoration:underline;">Tiết Kiệm Không Mua Được Nhà Phố →</a></p>
    
    <p style="margin-top:40px;color:#666;">Hoặc không. Đọc khi nào bạn sẵn sàng.</p>
    
    <p style="color:#666;">Thực tại không chờ ai.</p>
    
    <p style="margin-top:40px;">— THE TRUTH</p>
  </div>
</body>
</html>`;
}

async function handleConfirm(request, env) {
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
      "SELECT email FROM subscribers WHERE confirm_token = ? AND status = 'pending'"
    ).bind(token).first();
  } catch (e) {
    return new Response("Database error", { status: 500 });
  }

  if (!subscriber) {
    return new Response("Invalid or expired token", { status: 404 });
  }

  // Activate
  await DB.prepare(
    "UPDATE subscribers SET status = 'active', confirmed_at = datetime('now') WHERE confirm_token = ?"
  ).bind(token).run();

  // Send welcome email (non-blocking)
  const { RESEND_API_KEY, OWNER_EMAIL } = env;
  if (RESEND_API_KEY) {
    sendEmail(RESEND_API_KEY, OWNER_EMAIL,
      subscriber.email,
      "Chào mừng. Đây là thực tại.",
      buildWelcomeEmail()
    ).catch(() => {}); // Don't fail redirect if email fails
  }

  // Redirect to home with success
  return new Response.redirect(SITE_URL + "?subscribed=true", 302);
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
      if (path === '/subscribe' && request.method === 'POST') {
        return handleSubscribe(request, env);
      }

      if (path === '/subscribe/confirm' && request.method === 'GET') {
        return handleConfirm(request, env);
      }

      if (path === '/subscribe/unsubscribe' && request.method === 'GET') {
        return handleUnsubscribe(request, env);
      }

      return new Response("Not found", { status: 404 });

    } catch (e) {
      return new Response("Internal error: " + e.message, { status: 500 });
    }
  },
};
