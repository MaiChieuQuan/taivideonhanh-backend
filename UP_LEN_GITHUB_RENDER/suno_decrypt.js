const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');
const { Readable } = require('stream');

function b64ToUint8(b64) {
  return Buffer.from(b64, 'base64');
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
  return Buffer.from(decrypted);
}

const UUID_REGEX = /[0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12}/i;
function normalizeUUID(str) {
  if (!str) return null;
  const match = str.match(UUID_REGEX);
  if (!match) return null;
  let clean = match[0].replace(/-/g, '').toLowerCase();
  if (clean.length === 32) {
    return `${clean.slice(0, 8)}-${clean.slice(8, 12)}-${clean.slice(12, 16)}-${clean.slice(16, 20)}-${clean.slice(20, 32)}`;
  }
  return match[0].toLowerCase();
}

function loadSunoToken() {
  const candidateFiles = [
    path.join(__dirname, 'config.json'),
    'D:\\Tu_O_C\\Desktop\\suno-downloader\\suno-downloader\\config.json'
  ];
  for (const f of candidateFiles) {
    if (fs.existsSync(f)) {
      try {
        const data = JSON.parse(fs.readFileSync(f, 'utf8'));
        if (data.sunoCookie && typeof data.sunoCookie === 'string' && data.sunoCookie.trim()) {
          return data.sunoCookie.trim();
        }
      } catch (e) {}
    }
  }
  return process.env.SUNO_COOKIE || '';
}

async function resolveSong(input) {
  let songId = normalizeUUID(input);
  let title = 'Suno_Track';
  let imageUrl = null;
  
  if (input.startsWith('http')) {
    try {
      const res = await fetch(input, {
        headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' },
        redirect: 'follow',
        signal: AbortSignal.timeout(6000)
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
  
  if (!songId) throw new Error('Không tìm thấy mã bài hát (UUID) của Suno từ liên kết.');
  if (!imageUrl) {
    imageUrl = `https://cdn2.suno.ai/image_large_${songId}.jpeg`;
  }
  return { songId, title, imageUrl };
}

async function decryptSunoAudio(songId) {
  const rightsRes = await fetch('https://studio-api.prod.suno.com/api/mango/rights', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
      'Referer': 'https://suno.com/'
    },
    body: JSON.stringify({ content_params: { content_id: songId, content_type: 'clip' } }),
    signal: AbortSignal.timeout(10000)
  });

  if (!rightsRes.ok) throw new Error('Không lấy được quyền giải mã từ Suno: HTTP ' + rightsRes.status);
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
    },
    signal: AbortSignal.timeout(15000)
  });

  if (!mediaRes.ok) throw new Error('Lỗi tải stream âm thanh Suno: HTTP ' + mediaRes.status);
  const encBuffer = Buffer.from(await mediaRes.arrayBuffer());

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

  return Buffer.from(decryptedMedia);
}

async function main() {
  const args = process.argv.slice(2);
  if (args.length < 3) {
    console.error('Usage: node suno_decrypt.js <song_id_or_url> <format> <output_file> [ffmpeg_bin]');
    process.exit(1);
  }

  const [rawInput, format, outputPath, ffmpegBin = 'ffmpeg'] = args;
  const isMp4 = format.toLowerCase() === 'mp4';
  let { songId, title, imageUrl } = await resolveSong(rawInput);
  const sunoToken = loadSunoToken();

  // === PHƯƠNG THỨC 1: TẢI TRỰC TIẾP QUA API CHÍNH THỨC CỦA SUNO (SIÊU TỐC 1-2S) ===
  if (sunoToken) {
    try {
      const authHeader = sunoToken.startsWith('Bearer ') ? sunoToken : `Bearer ${sunoToken}`;
      const feedRes = await fetch(`https://studio-api.prod.suno.com/api/feed/?ids=${songId}`, {
        headers: {
          'Authorization': authHeader,
          'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        },
        signal: AbortSignal.timeout(5000)
      });
      if (feedRes.ok) {
        const feedData = await feedRes.json();
        if (Array.isArray(feedData) && feedData.length > 0) {
          const item = feedData[0];
          if (item.title) title = item.title;
          const directUrl = isMp4 ? item.video_url : item.audio_url;
          if (directUrl && !directUrl.includes('forbidden') && directUrl.startsWith('http')) {
            const dlRes = await fetch(directUrl, {
              headers: { 'User-Agent': 'Mozilla/5.0' },
              signal: AbortSignal.timeout(20000)
            });
            if (dlRes.ok) {
              const buf = Buffer.from(await dlRes.arrayBuffer());
              if (buf.length > 50000) {
                fs.writeFileSync(outputPath, buf);
                console.log(JSON.stringify({ success: true, songId, title, outputPath, method: 'SUNO_OFFICIAL_API' }));
                return;
              }
            }
          }
        }
      }
    } catch (apiErr) {
      // Fallback sang DRM engine
    }
  }

  // === KIỂM TRA TẢI TRỰC TIẾP TỪ SUNO CDN (SIÊU TỐC NẾU CÓ SẴN) ===
  const cdnExt = isMp4 ? 'mp4' : 'mp3';
  const cdnUrls = [
    `https://cdn1.suno.ai/${songId}.${cdnExt}`,
    `https://audiocdn1.suno.ai/${songId}.${cdnExt}`
  ];
  for (const cUrl of cdnUrls) {
    try {
      const cRes = await fetch(cUrl, {
        headers: { 'User-Agent': 'Mozilla/5.0' },
        signal: AbortSignal.timeout(2500)
      });
      if (cRes.ok && (cRes.headers.get('content-type')?.includes('audio') || cRes.headers.get('content-type')?.includes('video') || cRes.headers.get('content-type')?.includes('octet-stream'))) {
        const cBuf = Buffer.from(await cRes.arrayBuffer());
        if (cBuf.length > 50000) {
          fs.writeFileSync(outputPath, cBuf);
          console.log(JSON.stringify({ success: true, songId, title, outputPath, method: 'SUNO_DIRECT_CDN' }));
          return;
        }
      }
    } catch(e) {}
  }

  // === PHƯƠNG THỨC 2: GIẢI MÃ MANGO DRM ĐỘC QUYỀN (TỰ ĐỘNG 100%) ===
  const decAudio = await decryptSunoAudio(songId);

  if (isMp4) {
    // Thử tải trực tiếp MP4 từ CDN Suno nếu có sẵn (timeout 3s)
    let downloadedDirectVideo = false;
    const directVideoUrls = [
      `https://cdn1.suno.ai/${songId}.mp4`,
      `https://d2lwuy8qc234o3.cloudfront.net/1/clip/${songId}.mp4`
    ];
    for (const vUrl of directVideoUrls) {
      try {
        const vRes = await fetch(vUrl, {
          headers: { 'User-Agent': 'Mozilla/5.0' },
          signal: AbortSignal.timeout(3000)
        });
        if (vRes.ok && vRes.headers.get('content-type')?.includes('video')) {
          const buf = Buffer.from(await vRes.arrayBuffer());
          if (buf.length > 50000) {
            fs.writeFileSync(outputPath, buf);
            downloadedDirectVideo = true;
            break;
          }
        }
      } catch (e) {}
    }

    if (!downloadedDirectVideo) {
      const tempCoverPath = path.join(path.dirname(outputPath), `temp_cover_${Date.now()}.jpg`);
      let hasCover = false;
      try {
        const imgRes = await fetch(imageUrl, {
          headers: { 'User-Agent': 'Mozilla/5.0' },
          signal: AbortSignal.timeout(4000)
        });
        if (imgRes.ok) {
          const imgBuf = Buffer.from(await imgRes.arrayBuffer());
          fs.writeFileSync(tempCoverPath, imgBuf);
          hasCover = true;
        }
      } catch (e) {}

      await new Promise((resolve, reject) => {
        let ffArgs = [];
        if (hasCover) {
          ffArgs = [
            '-hide_banner', '-y',
            '-framerate', '1',
            '-loop', '1', '-i', tempCoverPath,
            '-i', 'pipe:0',
            '-c:v', 'libx264', '-preset', 'ultrafast', '-tune', 'stillimage', '-crf', '30',
            '-r', '1',
            '-c:a', 'aac', '-b:a', '192k',
            '-pix_fmt', 'yuv420p',
            '-movflags', '+faststart',
            '-shortest',
            outputPath
          ];
        } else {
          ffArgs = [
            '-hide_banner', '-y',
            '-f', 'lavfi', '-i', 'color=c=0x0f172a:s=1280x720:r=1',
            '-i', 'pipe:0',
            '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '32',
            '-c:a', 'aac', '-b:a', '192k',
            '-pix_fmt', 'yuv420p',
            '-movflags', '+faststart',
            '-shortest',
            outputPath
          ];
        }

        const ff = spawn(ffmpegBin, ffArgs);
        ff.stdin.on('error', () => {});
        Readable.from(decAudio).pipe(ff.stdin);

        ff.on('close', code => {
          try { if (fs.existsSync(tempCoverPath)) fs.unlinkSync(tempCoverPath); } catch(e) {}
          if (code === 0 && fs.existsSync(outputPath)) resolve();
          else reject(new Error('Lỗi xuất video MP4 (FFmpeg mã: ' + code + ')'));
        });
        ff.on('error', err => {
          try { if (fs.existsSync(tempCoverPath)) fs.unlinkSync(tempCoverPath); } catch(e) {}
          reject(err);
        });
      });
    }
  } else {
    // Xuất MP3 320kbps
    await new Promise((resolve, reject) => {
      const ff = spawn(ffmpegBin, [
        '-hide_banner', '-y', '-i', 'pipe:0',
        '-c:a', 'libmp3lame', '-b:a', '320k',
        '-metadata', `title=${title}`,
        outputPath
      ]);
      
      ff.stdin.on('error', () => {});
      Readable.from(decAudio).pipe(ff.stdin);
      
      ff.on('close', code => {
        if (code === 0 && fs.existsSync(outputPath)) resolve();
        else reject(new Error('FFmpeg exited with code ' + code));
      });
      ff.on('error', err => {
        fs.writeFileSync(outputPath, decAudio);
        resolve();
      });
    });
  }

  console.log(JSON.stringify({ success: true, songId, title, outputPath, method: 'MANGO_DRM_DECRYPT' }));
}

main().catch(err => {
  console.error(JSON.stringify({ success: false, error: err.message }));
  process.exit(1);
});