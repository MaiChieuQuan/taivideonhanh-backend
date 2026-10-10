// Cloudflare Pages Function: /api/download-suno
// Tự động phân tích và giải mã Mango DRM của Suno AI trên Cloudflare Edge 24/7 khi tắt máy!

function normalizeUUID(str) {
  if (!str) return null;
  const match = str.match(/[0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12}/i);
  if (!match) return null;
  let clean = match[0].replace(/-/g, '').toLowerCase();
  if (clean.length === 32) {
    return `${clean.slice(0, 8)}-${clean.slice(8, 12)}-${clean.slice(12, 16)}-${clean.slice(16, 20)}-${clean.slice(20, 32)}`;
  }
  return match[0].toLowerCase();
}

function b64ToUint8(b64) {
  const binary = atob(b64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}

async function sha256(str) {
  const enc = new TextEncoder().encode(str);
  return await crypto.subtle.digest('SHA-256', enc);
}

async function decryptAesGcm(ciphertextWithIv, keyRaw, additionalDataStr) {
  const iv = ciphertextWithIv.subarray(0, 12);
  const data = ciphertextWithIv.subarray(12);
  const key = await crypto.subtle.importKey('raw', keyRaw, { name: 'AES-GCM' }, false, ['decrypt']);
  const decrypted = await crypto.subtle.decrypt(
    { name: 'AES-GCM', iv, additionalData: new TextEncoder().encode(additionalDataStr) },
    key,
    data
  );
  return new Uint8Array(decrypted);
}

async function resolveSong(input) {
  let songId = normalizeUUID(input);
  let title = 'Suno_Track';
  let imageUrl = null;

  if (input.startsWith('http')) {
    try {
      const res = await fetch(input, {
        headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' },
        redirect: 'follow'
      });
      const finalId = normalizeUUID(res.url);
      if (finalId) songId = finalId;
      const html = await res.text();
      if (!songId) {
        songId = normalizeUUID(html);
      }
      const tMatch = html.match(/<meta\s+property="og:title"\s+content="([^"]*)"/i) || html.match(/<title>([^<]*)<\/title>/i);
      if (tMatch && tMatch[1]) {
        title = tMatch[1].replace(/\s*\|\s*Suno.*$/i, '').trim();
      }
      const imgMatch = html.match(/<meta\s+property="og:image"\s+content="([^"]*)"/i);
      if (imgMatch && imgMatch[1]) {
        imageUrl = imgMatch[1];
      }
    } catch (e) {}
  }

  if (!songId) throw new Error('Không tìm thấy ID bài hát Suno AI từ liên kết này.');
  if (!imageUrl) {
    imageUrl = `https://cdn2.suno.ai/image_large_${songId}.jpeg`;
  }
  return { songId, title, imageUrl };
}

export async function onRequestPost({ request }) {
  try {
    const body = await request.json().catch(() => ({}));
    const rawUrl = (body.url || '').trim();
    const mediaType = (body.media_type || 'mp3').toLowerCase();

    if (!rawUrl) {
      return new Response(JSON.stringify({ success: false, detail: 'Vui lòng cung cấp link Suno AI!' }), {
        status: 400,
        headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' }
      });
    }

    const { songId, title, imageUrl } = await resolveSong(rawUrl);

    // 1. Thử tải trực tiếp nếu file sẵn có trên CDN của Suno
    const cdnUrls = [
      `https://cdn1.suno.ai/${songId}.${mediaType === 'mp4' ? 'mp4' : 'mp3'}`,
      `https://audiocdn1.suno.ai/${songId}.${mediaType === 'mp4' ? 'mp4' : 'mp3'}`
    ];
    for (const cUrl of cdnUrls) {
      try {
        const cRes = await fetch(cUrl, { headers: { 'User-Agent': 'Mozilla/5.0' } });
        if (cRes.ok && cRes.headers.get('content-length') && parseInt(cRes.headers.get('content-length')) > 50000) {
          const stream = cRes.body;
          const ext = mediaType === 'mp4' ? 'mp4' : 'mp3';
          const mime = mediaType === 'mp4' ? 'video/mp4' : 'audio/mpeg';
          return new Response(stream, {
            headers: {
              'Content-Type': mime,
              'Content-Disposition': `attachment; filename="${encodeURIComponent(title || 'Suno_Track')}.${ext}"`,
              'X-Song-Title': encodeURIComponent(title || 'Suno_Track'),
              'Access-Control-Allow-Origin': '*'
            }
          });
        }
      } catch (e) {}
    }

    // 2. Tự động giải mã Mango DRM bằng Web Crypto API trên Cloudflare Edge
    const rightsRes = await fetch('https://studio-api.prod.suno.com/api/mango/rights', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://suno.com/'
      },
      body: JSON.stringify({ content_params: { content_id: songId, content_type: 'clip' } })
    });

    if (!rightsRes.ok) {
      throw new Error('Suno từ chối cấp quyền giải mã (HTTP ' + rightsRes.status + ')');
    }

    const rights = await rightsRes.json();
    const guestKeyRaw = await sha256(rights.glt);

    const keyCiphertext = b64ToUint8(rights.key);
    const ivCiphertext = b64ToUint8(rights.iv);

    const decryptedAesKey = await decryptAesGcm(keyCiphertext, guestKeyRaw, songId);
    const decryptedInitialIv = await decryptAesGcm(ivCiphertext, guestKeyRaw, songId);

    const mediaUrl = `https://d2lwuy8qc234o3.cloudfront.net/1/clip/${songId}.m4a`;
    const mediaRes = await fetch(mediaUrl, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://suno.com/'
      }
    });

    if (!mediaRes.ok) {
      throw new Error('Không thể tải luồng âm thanh Suno (HTTP ' + mediaRes.status + ')');
    }

    const encBuffer = await mediaRes.arrayBuffer();

    const cryptoSubtleKey = await crypto.subtle.importKey(
      'raw',
      decryptedAesKey,
      { name: 'AES-CTR' },
      false,
      ['decrypt']
    );

    const decryptedMedia = await crypto.subtle.decrypt(
      { name: 'AES-CTR', counter: decryptedInitialIv, length: 128 },
      cryptoSubtleKey,
      encBuffer
    );

    return new Response(decryptedMedia, {
      headers: {
        'Content-Type': 'audio/mp4',
        'Content-Disposition': `attachment; filename="${encodeURIComponent(title || 'Suno_Track')}.m4a"`,
        'X-Song-Title': encodeURIComponent(title || 'Suno_Track'),
        'Access-Control-Allow-Origin': '*'
      }
    });

  } catch (error) {
    return new Response(JSON.stringify({ success: false, detail: error.message }), {
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
