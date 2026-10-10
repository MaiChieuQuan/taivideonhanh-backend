// Cloudflare Pages Function: /api/admin/login

export async function onRequestPost({ request }) {
  try {
    const body = await request.json().catch(() => ({}));
    const pass = (body.password || '').trim();

    // Mật khẩu mặc định bảo mật 123456
    if (pass === '123456') {
      return new Response(JSON.stringify({ success: true, message: 'Đăng nhập Admin thành công!', token: 'admin_cloud_session' }), {
        headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' }
      });
    }

    return new Response(JSON.stringify({ success: false, detail: 'Mật khẩu Admin không chính xác!' }), {
      status: 401,
      headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' }
    });
  } catch (e) {
    return new Response(JSON.stringify({ success: false, detail: e.message }), {
      status: 500,
      headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' }
    });
  }
}

export async function onRequestOptions() {
  return new Response(null, {
    headers: {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type'
    }
  });
}
