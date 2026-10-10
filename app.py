import json
import asyncio
import os
import sys

try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

import uuid
import shutil
import subprocess
import webbrowser
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel

import uvicorn
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"
STATIC_DIR = BASE_DIR / "static"

for folder in [UPLOAD_DIR, OUTPUT_DIR, STATIC_DIR]:
    folder.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Cắt Nhạc MP3 & Ghép Video MP4")

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

# Serve uploaded/output media for browser preview
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/media/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")
app.mount("/media/outputs", StaticFiles(directory=str(OUTPUT_DIR)), name="outputs")

class VideoSegment(BaseModel):
    id: str
    video_file: str
    video_name: Optional[str] = ""
    start: float
    end: float
    duration: float

class ConcatVideoRequest(BaseModel):
    segments: List[VideoSegment]
    audio_mode: Optional[str] = "original"  # 'original', 'mute', 'replace_mp3', 'mix_mp3'
    music_file: Optional[str] = None
    music_volume: Optional[float] = 1.0
    video_volume: Optional[float] = 1.0

class Segment(BaseModel):
    id: str
    start: float
    end: float
    duration: float

class ConcatRequest(BaseModel):
    audio_file: str
    segments: List[Segment]

class Mp3ToMp4Request(BaseModel):
    audio_file: str
    bg_type: Optional[str] = 'image'  # 'image', 'video', 'color'
    bg_file: Optional[str] = None
    aspect_ratio: Optional[str] = '16:9'  # '16:9', '9:16', '1:1'
    add_waveform: Optional[bool] = False
    waveform_color: Optional[str] = '#38bdf8'
    visualizer_style: Optional[str] = 'wave_line'  # 'wave_line', 'freq_bars', 'symmetric_bars', 'circular_radar', 'rainbow_spectrum'
    visualizer_pos: Optional[str] = 'bottom'  # 'bottom', 'center', 'top'
    bg_effect: Optional[str] = 'none'  # 'none', 'slow_zoom'
    audio_mode: Optional[str] = 'replace'  # for video: 'replace', 'mix'
    original_volume: Optional[float] = 1.0
    music_volume: Optional[float] = 1.0

class MergeRequest(BaseModel):
    video_file: str
    audio_file: str
    audio_mode: str  # 'replace', 'mix', 'mute_original'
    original_volume: Optional[float] = 1.0
    music_volume: Optional[float] = 1.0
    match_duration: Optional[str] = "shortest" # 'shortest', 'video', 'music'

import yt_dlp

class SunoTokenRequest(BaseModel):
    token: str

STATS_FILE = BASE_DIR / "stats.json"

def get_stats_data() -> dict:
    # Đếm số tệp thực tế trong outputs làm mốc chuẩn
    try:
        real_suno = len(list(OUTPUT_DIR.glob("suno_*.*")))
        real_dl = len(list(OUTPUT_DIR.glob("dl_*.*")))
        real_merges = len(list(OUTPUT_DIR.glob("*m2m*.*"))) + len(list(OUTPUT_DIR.glob("*merge*.*"))) + len(list(OUTPUT_DIR.glob("*video.mp4")))
        real_cuts = len(list(OUTPUT_DIR.glob("*cut*.*"))) + len(list(OUTPUT_DIR.glob("*concat*.*")))
        base_dl = max(11, real_suno + real_dl)
        base_merge = max(6, real_merges)
        base_cut = max(4, real_cuts)
    except Exception:
        base_dl, base_merge, base_cut = 11, 6, 4

    default_data = {
        "suno_downloads": base_dl,
        "video_merges": base_merge,
        "video_cuts": base_cut
    }

    if not STATS_FILE.exists() or STATS_FILE.stat().st_size == 0:
        save_stats_file(default_data)
        return default_data

    try:
        with open(STATS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError("Invalid format")
            for k, def_v in default_data.items():
                if k not in data or not isinstance(data[k], int):
                    data[k] = def_v
            return data
    except Exception as e:
        print(f"[Stats Read Warning] {e}, recreating stats.json")
        save_stats_file(default_data)
        return default_data

def save_stats_file(data: dict):
    try:
        tmp = STATS_FILE.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        tmp.replace(STATS_FILE)
    except Exception as e:
        print(f"[Stats Save Error] {e}")

def increment_stat(stat_type: str) -> dict:
    data = get_stats_data()
    key_map = {
        "suno": "suno_downloads",
        "download": "suno_downloads",
        "merge": "video_merges",
        "cut": "video_cuts"
    }
    key = key_map.get(stat_type, stat_type)
    data[key] = data.get(key, 0) + 1
    save_stats_file(data)
    return data

class StatIncrementRequest(BaseModel):
    type: str

@app.get("/api/stats")
def get_stats_endpoint():
    return get_stats_data()

@app.post("/api/stats/increment")
def increment_stats_endpoint(req: StatIncrementRequest):
    return increment_stat(req.type)

class CskhConfigRequest(BaseModel):
    zalo: Optional[str] = ""
    zalo_label: Optional[str] = "Nhắn tin Zalo 24/7"
    zalo_enabled: Optional[bool] = True
    fb: Optional[str] = ""
    fb_label: Optional[str] = "Fanpage / Messenger"
    fb_enabled: Optional[bool] = True
    tele: Optional[str] = ""
    tele_label: Optional[str] = "Kênh hỗ trợ 24/7"
    tele_enabled: Optional[bool] = True
    hotline: Optional[str] = ""

class AdminLoginRequest(BaseModel):
    password: str

class AdminChangePassRequest(BaseModel):
    old_password: Optional[str] = ''
    current_password: Optional[str] = ''
    new_password: str

class StatsUpdateRequest(BaseModel):
    suno_downloads: Optional[int] = None
    video_merges: Optional[int] = None
    video_cuts: Optional[int] = None

@app.get("/api/cskh")
def get_cskh_contacts():
    cfg_file = BASE_DIR / "config.json"
    default_cskh = {
        "zalo": "",
        "zalo_label": "Nhắn tin Zalo 24/7",
        "zalo_enabled": True,
        "fb": "",
        "fb_label": "Fanpage / Messenger",
        "fb_enabled": True,
        "tele": "",
        "tele_label": "Kênh hỗ trợ 24/7",
        "tele_enabled": True,
        "hotline": ""
    }
    if cfg_file.exists():
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                cskh = data.get("cskh", {})
                for k, v in default_cskh.items():
                    if k not in cskh:
                        cskh[k] = v
                return cskh
        except Exception:
            pass
    return default_cskh

@app.post("/api/cskh")
def save_cskh_contacts(req: CskhConfigRequest):
    cfg_file = BASE_DIR / "config.json"
    data = {}
    if cfg_file.exists():
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            pass
    cskh = {
        "zalo": req.zalo.strip() if req.zalo else "",
        "zalo_label": req.zalo_label.strip() if req.zalo_label else "Nhắn tin Zalo 24/7",
        "zalo_enabled": bool(req.zalo_enabled),
        "fb": req.fb.strip() if req.fb else "",
        "fb_label": req.fb_label.strip() if req.fb_label else "Fanpage / Messenger",
        "fb_enabled": bool(req.fb_enabled),
        "tele": req.tele.strip() if req.tele else "",
        "tele_label": req.tele_label.strip() if req.tele_label else "Kênh hỗ trợ 24/7",
        "tele_enabled": bool(req.tele_enabled),
        "hotline": req.hotline.strip() if req.hotline else ""
    }
    data["cskh"] = cskh
    with open(cfg_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return {"success": True, "cskh": cskh}

@app.post("/api/admin/login")
def admin_login(req: AdminLoginRequest):
    cfg_file = BASE_DIR / "config.json"
    admin_pass = "123456"
    if cfg_file.exists():
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                admin_pass = data.get("adminPassword", "123456")
        except Exception:
            pass
    if req.password.strip() == admin_pass:
        return {"success": True, "message": "Đăng nhập Admin thành công!"}
    raise HTTPException(status_code=401, detail="Mật khẩu Admin không chính xác!")

@app.post("/api/admin/change-password")
def admin_change_password(req: AdminChangePassRequest):
    cfg_file = BASE_DIR / "config.json"
    data = {}
    admin_pass = "123456"
    if cfg_file.exists():
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    data = json.loads(content)
                    if isinstance(data, dict):
                        admin_pass = str(data.get("adminPassword", "123456"))
        except Exception:
            pass
    old_p = (req.old_password or req.current_password or "").strip()
    if old_p != admin_pass:
        return {"success": False, "detail": "Mật khẩu hiện tại không chính xác!"}
    new_p = req.new_password.strip()
    if len(new_p) < 4:
        return {"success": False, "detail": "Mật khẩu mới tối thiểu 4 ký tự!"}
    if not isinstance(data, dict):
        data = {}
    data["adminPassword"] = new_p
    try:
        tmp_cfg = cfg_file.with_suffix(".tmp")
        with open(tmp_cfg, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        tmp_cfg.replace(cfg_file)
    except Exception as ex:
        return {"success": False, "detail": f"Lỗi lưu cấu hình: {str(ex)}"}
    return {"success": True, "message": "Đổi mật khẩu admin thành công!"}

@app.post("/api/stats/update")
def admin_update_stats(req: StatsUpdateRequest):
    data = get_stats_data()
    if req.suno_downloads is not None: data["suno_downloads"] = max(0, req.suno_downloads)
    if req.video_merges is not None: data["video_merges"] = max(0, req.video_merges)
    if req.video_cuts is not None: data["video_cuts"] = max(0, req.video_cuts)
    save_stats_file(data)
    return {"success": True, "stats": data}


@app.get("/api/suno/token")
def get_suno_token():
    cfg_file = BASE_DIR / "config.json"
    if cfg_file.exists():
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                cookie = data.get("sunoCookie", "").strip()
                if cookie:
                    return {"has_token": True, "preview": cookie[:20] + "..."}
        except Exception:
            pass
    return {"has_token": False, "preview": ""}

@app.post("/api/suno/token")
def save_suno_token(req: SunoTokenRequest):
    token = req.token.strip()
    cfg_file = BASE_DIR / "config.json"
    data = {}
    if cfg_file.exists():
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            pass
    data["sunoCookie"] = token
    with open(cfg_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return {"success": True, "has_token": bool(token)}

class DownloadUrlRequest(BaseModel):
    url: str
    media_type: str = "mp3"  # 'mp3' or 'mp4'
    audio_format: Optional[str] = "mp3_320"  # 'mp3_320', 'mp3_192', 'mp3_128', 'wav', 'm4a', 'flac'
    video_format: Optional[str] = "mp4_1080"  # 'mp4_1080', 'mp4_916', 'mp4_720', 'mp4_480', 'mp4_wave'
    task_id: Optional[str] = None

download_progress_map = {}

@app.get("/api/download-progress/{task_id}")
async def get_download_progress(task_id: str):
    prog = download_progress_map.get(task_id)
    if not prog:
        return {"status": "starting", "percent": 0.0, "stage": "Đang kết nối..."}
    return prog

class DeleteFileRequest(BaseModel):
    filename: str

class OpenFolderRequest(BaseModel):
    filename: Optional[str] = None

def get_ffmpeg_bin() -> str:
    ffmpeg_cmd = shutil.which("ffmpeg")
    if ffmpeg_cmd:
        return ffmpeg_cmd
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"

def run_ffmpeg(args: list) -> subprocess.CompletedProcess:
    ffmpeg_bin = get_ffmpeg_bin()
    cmd = [ffmpeg_bin, "-hide_banner", "-y"] + args
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="ignore")
    if result.returncode != 0:
        print("FFmpeg Error:\n", result.stderr)
        raise RuntimeError(f"Lỗi FFmpeg: {result.stderr[-500:] if len(result.stderr) > 500 else result.stderr}")
    return result

def has_audio_stream(file_path: Path) -> bool:
    ffprobe_cmd = shutil.which("ffprobe")
    if ffprobe_cmd:
        try:
            res = subprocess.run([ffprobe_cmd, "-v", "error", "-select_streams", "a", "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(file_path)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if "audio" in res.stdout:
                return True
        except Exception:
            pass
    try:
        ffmpeg_bin = get_ffmpeg_bin()
        res = subprocess.run([ffmpeg_bin, "-i", str(file_path)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="ignore")
        return "Audio:" in res.stderr
    except Exception:
        return False

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    ext = Path(file.filename).suffix.lower()
    if ext not in [".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac", ".mp4", ".mov", ".mkv", ".webm", ".avi"]:
        raise HTTPException(status_code=400, detail="Định dạng tệp không được hỗ trợ.")
    
    unique_name = f"{uuid.uuid4().hex[:10]}_{file.filename}"
    save_path = UPLOAD_DIR / unique_name
    
    with open(save_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    return {
        "filename": unique_name,
        "original_name": file.filename,
        "url": f"/media/uploads/{unique_name}",
        "is_video": ext in [".mp4", ".mov", ".mkv", ".webm", ".avi"]
    }

@app.post("/api/concat-mp3")
async def concat_mp3(req: ConcatRequest):
    input_audio = UPLOAD_DIR / req.audio_file
    if not input_audio.exists():
        raise HTTPException(status_code=404, detail="Không tìm thấy tệp âm thanh nguồn.")
    
    if not req.segments:
        raise HTTPException(status_code=400, detail="Không có đoạn cắt nào được chọn.")
    
    work_id = uuid.uuid4().hex[:8]
    temp_parts = []
    
    try:
        # Cắt từng đoạn
        for idx, seg in enumerate(req.segments):
            part_name = f"part_{work_id}_{idx}.mp3"
            part_path = OUTPUT_DIR / part_name
            # Dùng -ss trước -i và -to để cắt nhanh và chính xác
            dur = max(0.01, seg.end - seg.start)
            run_ffmpeg([
                "-ss", f"{seg.start:.4f}",
                "-t", f"{dur:.4f}",
                "-i", str(input_audio),
                "-c:a", "libmp3lame",
                "-b:a", "256k",
                str(part_path)
            ])
            temp_parts.append(part_path)
        
        # Ghép các đoạn
        concat_list_file = OUTPUT_DIR / f"concat_{work_id}.txt"
        with open(concat_list_file, "w", encoding="utf-8") as f:
            for p in temp_parts:
                # Dùng forward slash cho ffmpeg
                f.write(f"file '{p.resolve().as_posix()}'\n")
        
        output_filename = f"merged_{work_id}.mp3"
        output_path = OUTPUT_DIR / output_filename
        
        run_ffmpeg([
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_list_file),
            "-c:a", "libmp3lame",
            "-b:a", "256k",
            str(output_path)
        ])
        
        # Dọn dẹp tệp tạm
        try:
            concat_list_file.unlink(missing_ok=True)
            for p in temp_parts:
                p.unlink(missing_ok=True)
        except Exception:
            pass
            
        return {
            "success": True,
            "filename": output_filename,
            "url": f"/media/outputs/{output_filename}",
            "message": f"Ghép thành công {len(req.segments)} đoạn nhạc!"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/merge-video")
async def merge_video(req: MergeRequest):
    video_path = UPLOAD_DIR / req.video_file
    audio_path = OUTPUT_DIR / req.audio_file
    if not audio_path.exists():
        audio_path = UPLOAD_DIR / req.audio_file
        
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Không tìm thấy tệp video.")
    if not audio_path.exists():
        raise HTTPException(status_code=404, detail="Không tìm thấy tệp âm thanh ghép.")
        
    work_id = uuid.uuid4().hex[:8]
    output_filename = f"final_video_{work_id}.mp4"
    output_path = OUTPUT_DIR / output_filename
    
    vid_has_audio = has_audio_stream(video_path)
    mode = req.audio_mode
    
    args = ["-i", str(video_path), "-i", str(audio_path)]
    
    try:
        if mode == "mix" and vid_has_audio:
            # Trộn âm thanh gốc và MP3 với tỉ lệ âm lượng
            v_vol = float(req.original_volume or 1.0)
            m_vol = float(req.music_volume or 1.0)
            args += [
                "-filter_complex",
                f"[0:a]volume={v_vol:.2f}[a0];[1:a]volume={m_vol:.2f}[a1];[a0][a1]amix=inputs=2:duration=first:dropout_transition=2[aout]",
                "-map", "0:v:0",
                "-map", "[aout]",
                "-c:v", "copy",
                "-c:a", "aac",
                "-b:a", "192k"
            ]
        elif mode == "mute_original" or not vid_has_audio or mode == "replace":
            # Thay thế âm thanh gốc bằng MP3
            m_vol = float(req.music_volume or 1.0)
            if abs(m_vol - 1.0) > 0.01:
                args += [
                    "-filter_complex", f"[1:a]volume={m_vol:.2f}[aout]",
                    "-map", "0:v:0",
                    "-map", "[aout]",
                    "-c:v", "copy",
                    "-c:a", "aac",
                    "-b:a", "192k"
                ]
            else:
                args += [
                    "-map", "0:v:0",
                    "-map", "1:a:0",
                    "-c:v", "copy",
                    "-c:a", "aac",
                    "-b:a", "192k"
                ]
        
        # Xử lý thời lượng
        if req.match_duration == "shortest":
            args.append("-shortest")
            
        args.append(str(output_path))
        run_ffmpeg(args)
        
        return {
            "success": True,
            "filename": output_filename,
            "url": f"/media/outputs/{output_filename}",
            "full_path": str(output_path.resolve()),
            "output_dir": str(OUTPUT_DIR.resolve()),
            "message": "Xuất video MP4 thành công và đã lưu vào thư mục của tool!"
        }
    except Exception as e:
        # Nếu copy video codec lỗi do container khác nhau, thử encode nhẹ libx264
        try:
            print("Fallback encode video do c:v copy không tương thích container...")
            fallback_args = ["-i", str(video_path), "-i", str(audio_path)]
            if mode == "mix" and vid_has_audio:
                fallback_args += [
                    "-filter_complex",
                    f"[0:a]volume={req.original_volume or 1.0:.2f}[a0];[1:a]volume={req.music_volume or 1.0:.2f}[a1];[a0][a1]amix=inputs=2:duration=first[aout]",
                    "-map", "0:v:0",
                    "-map", "[aout]",
                    "-c:v", "libx264",
                    "-preset", "veryfast",
                    "-c:a", "aac",
                    "-shortest",
                    "-movflags", "+faststart",
                    str(output_path)
                ]
            else:
                fallback_args += [
                    "-map", "0:v:0",
                    "-map", "1:a:0",
                    "-c:v", "libx264",
                    "-preset", "veryfast",
                    "-c:a", "aac",
                    "-shortest",
                    "-movflags", "+faststart",
                    str(output_path)
                ]
            run_ffmpeg(fallback_args)
            return {
                "success": True,
                "filename": output_filename,
                "url": f"/media/outputs/{output_filename}",
                "full_path": str(output_path.resolve()),
                "output_dir": str(OUTPUT_DIR.resolve()),
                "message": "Xuất video MP4 thành công và đã lưu vào thư mục của tool!"
            }
        except Exception as e2:
            raise HTTPException(status_code=500, detail=str(e2))

@app.post("/api/mp3-to-mp4")
async def mp3_to_mp4_endpoint(req: Mp3ToMp4Request):
    audio_path = OUTPUT_DIR / req.audio_file
    if not audio_path.exists():
        audio_path = UPLOAD_DIR / req.audio_file
    if not audio_path.exists():
        raise HTTPException(status_code=404, detail=f"Không tìm thấy tệp âm thanh: {req.audio_file}")
        
    work_id = uuid.uuid4().hex[:8]
    output_filename = f"mp4_from_mp3_{work_id}.mp4"
    output_path = OUTPUT_DIR / output_filename
    
    ar = req.aspect_ratio or "16:9"
    if ar == "9:16":
        width, height = 1080, 1920
    elif ar == "1:1":
        width, height = 1080, 1080
    else:
        width, height = 1920, 1080
        
    try:
        if req.bg_type == "video" and req.bg_file:
            vid_path = UPLOAD_DIR / req.bg_file
            if not vid_path.exists():
                vid_path = OUTPUT_DIR / req.bg_file
            if not vid_path.exists():
                raise HTTPException(status_code=404, detail=f"Không tìm thấy tệp video nền: {req.bg_file}")
                
            vid_has_audio = has_audio_stream(vid_path)
            args = ["-i", str(vid_path), "-i", str(audio_path)]
            if req.audio_mode == "mix" and vid_has_audio:
                v_vol = float(req.original_volume or 1.0)
                m_vol = float(req.music_volume or 1.0)
                args += [
                    "-filter_complex",
                    f"[0:a]volume={v_vol:.2f}[a0];[1:a]volume={m_vol:.2f}[a1];[a0][a1]amix=inputs=2:duration=first[aout]",
                    "-map", "0:v:0",
                    "-map", "[aout]",
                    "-c:v", "libx264",
                    "-preset", "veryfast",
                    "-c:a", "aac",
                    "-b:a", "192k",
                    "-shortest",
                    "-movflags", "+faststart",
                    str(output_path)
                ]
            else:
                m_vol = float(req.music_volume or 1.0)
                args += [
                    "-filter_complex",
                    f"[1:a]volume={m_vol:.2f}[aout]",
                    "-map", "0:v:0",
                    "-map", "[aout]",
                    "-c:v", "libx264",
                    "-preset", "veryfast",
                    "-c:a", "aac",
                    "-b:a", "192k",
                    "-shortest",
                    "-movflags", "+faststart",
                    str(output_path)
                ]
            run_ffmpeg(args)
        else:
            img_path = None
            if req.bg_file:
                p = UPLOAD_DIR / req.bg_file
                if not p.exists():
                    p = OUTPUT_DIR / req.bg_file
                if p.exists():
                    img_path = p
                    
            scale_pad_filter = f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=0x0f172a"
            raw_color = (req.waveform_color or "#38bdf8").strip()
            wave_hex = raw_color.replace("#", "0x")
            
            try:
                c_hex = raw_color.lstrip("#")
                rc = int(c_hex[0:2], 16)
                gc = int(c_hex[2:4], 16)
                bc = int(c_hex[4:6], 16)
            except Exception:
                rc, gc, bc = 56, 189, 248
                
            v_style = req.visualizer_style or "wave_line"
            v_pos = req.visualizer_pos or "bottom"
            bg_fx = req.bg_effect or "none"
            
            if req.add_waveform:
                wave_w = int(width * 0.88)
                wave_h = int(height * 0.16) if ar != "9:16" else int(height * 0.13)
                
                if v_pos == "top":
                    pos_expr = f"(W-w)/2:{int(height * 0.08)}"
                elif v_pos == "center":
                    pos_expr = "(W-w)/2:(H-h)/2"
                else:
                    pos_expr = f"(W-w)/2:{int(height * 0.78)}"
                    
                if v_style == "freq_bars":
                    wave_filter = f"showfreqs=s={wave_w}x{wave_h}:mode=bar:ascale=log:fscale=log:colors={wave_hex}@0.95,format=rgba,colorkey=black:0.3:0.1"
                elif v_style == "symmetric_bars":
                    wave_filter = f"showwaves=s={wave_w}x{wave_h}:mode=p2p:colors={wave_hex}@0.95,format=rgba,colorkey=black:0.3:0.1"
                elif v_style == "circular_radar":
                    circle_dim = min(int(width * 0.45), int(height * 0.45))
                    wave_filter = f"avectorscope=s={circle_dim}x{circle_dim}:m=lissajous:draw=line:rc={rc}:gc={gc}:bc={bc},format=rgba,colorkey=black:0.3:0.1"
                    pos_expr = "(W-w)/2:(H-h)/2"
                elif v_style == "rainbow_spectrum":
                    wave_filter = f"showspectrum=s={wave_w}x{wave_h}:mode=combined:color=rainbow:slide=scroll:scale=log,format=rgba,colorkey=black:0.3:0.1"
                else:
                    wave_filter = f"showwaves=s={wave_w}x{wave_h}:mode=cline:colors={wave_hex}@0.9"
                    
                if bg_fx == "slow_zoom" and img_path:
                    bg_filter = f"zoompan=z='min(zoom+0.0006,1.1)':d=50:s={width}x{height}:fps=25"
                else:
                    bg_filter = scale_pad_filter
                
                if img_path:
                    args = [
                        "-loop", "1", "-framerate", "25",
                        "-i", str(img_path),
                        "-i", str(audio_path),
                        "-filter_complex",
                        f"[0:v]{bg_filter}[bg];[1:a]{wave_filter}[wave];[bg][wave]overlay={pos_expr}[outv]",
                        "-map", "[outv]",
                        "-map", "1:a",
                        "-c:v", "libx264",
                        "-preset", "veryfast",
                        "-c:a", "aac",
                        "-b:a", "192k",
                        "-pix_fmt", "yuv420p",
                        "-movflags", "+faststart",
                        "-shortest",
                        str(output_path)
                    ]
                else:
                    args = [
                        "-f", "lavfi",
                        "-i", f"color=c=0x0f172a:s={width}x{height}:r=25",
                        "-i", str(audio_path),
                        "-filter_complex",
                        f"[1:a]{wave_filter}[wave];[0:v][wave]overlay={pos_expr}[outv]",
                        "-map", "[outv]",
                        "-map", "1:a",
                        "-c:v", "libx264",
                        "-preset", "veryfast",
                        "-c:a", "aac",
                        "-b:a", "192k",
                        "-pix_fmt", "yuv420p",
                        "-movflags", "+faststart",
                        "-shortest",
                        str(output_path)
                    ]
                run_ffmpeg(args)
            else:
                if img_path:
                    args = [
                        "-loop", "1", "-framerate", "2",
                        "-i", str(img_path),
                        "-i", str(audio_path),
                        "-vf", scale_pad_filter,
                        "-c:v", "libx264",
                        "-preset", "veryfast",
                        "-tune", "stillimage",
                        "-c:a", "aac",
                        "-b:a", "192k",
                        "-pix_fmt", "yuv420p",
                        "-movflags", "+faststart",
                        "-shortest",
                        str(output_path)
                    ]
                else:
                    args = [
                        "-f", "lavfi",
                        "-i", f"color=c=0x162032:s={width}x{height}:r=2",
                        "-i", str(audio_path),
                        "-c:v", "libx264",
                        "-preset", "veryfast",
                        "-tune", "stillimage",
                        "-c:a", "aac",
                        "-b:a", "192k",
                        "-pix_fmt", "yuv420p",
                        "-movflags", "+faststart",
                        "-shortest",
                        str(output_path)
                    ]
                run_ffmpeg(args)
                
        increment_stat("merge")
        return {
            "success": True,
            "filename": output_filename,
            "url": f"/media/outputs/{output_filename}",
            "full_path": str(output_path.resolve()),
            "output_dir": str(OUTPUT_DIR.resolve()),
            "message": "Ghép MP3 thành video MP4 với hiệu ứng âm nhạc thành công!"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/concat-video")
async def concat_video(req: ConcatVideoRequest):
    if not req.segments:
        raise HTTPException(status_code=400, detail="Không có đoạn video nào được chọn.")
    
    work_id = uuid.uuid4().hex[:8]
    temp_parts = []
    concat_list_file = OUTPUT_DIR / f"vconcat_{work_id}.txt"
    merged_temp_name = f"vmerged_temp_{work_id}.mp4"
    merged_temp_path = OUTPUT_DIR / merged_temp_name
    final_video_name = f"merged_video_{work_id}.mp4"
    final_video_path = OUTPUT_DIR / final_video_name

    try:
        # Cắt từng đoạn video
        for idx, seg in enumerate(req.segments):
            input_video = UPLOAD_DIR / seg.video_file
            if not input_video.exists():
                input_video = OUTPUT_DIR / seg.video_file
            if not input_video.exists():
                raise HTTPException(status_code=404, detail=f"Không tìm thấy tệp video: {seg.video_file}")
            
            part_name = f"vpart_{work_id}_{idx}.mp4"
            part_path = OUTPUT_DIR / part_name
            dur = max(0.05, seg.end - seg.start)
            
            vid_has_audio = has_audio_stream(input_video)
            
            if req.audio_mode == "mute":
                cut_args = [
                    "-ss", f"{seg.start:.4f}",
                    "-t", f"{dur:.4f}",
                    "-i", str(input_video),
                    "-c:v", "libx264",
                    "-preset", "veryfast",
                    "-crf", "20",
                    "-an",
                    "-pix_fmt", "yuv420p",
                    str(part_path)
                ]
            else:
                if vid_has_audio:
                    cut_args = [
                        "-ss", f"{seg.start:.4f}",
                        "-t", f"{dur:.4f}",
                        "-i", str(input_video),
                        "-c:v", "libx264",
                        "-preset", "veryfast",
                        "-crf", "20",
                        "-c:a", "aac",
                        "-b:a", "192k",
                        "-ar", "48000",
                        "-ac", "2",
                        "-pix_fmt", "yuv420p",
                        str(part_path)
                    ]
                else:
                    cut_args = [
                        "-ss", f"{seg.start:.4f}",
                        "-t", f"{dur:.4f}",
                        "-i", str(input_video),
                        "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
                        "-c:v", "libx264",
                        "-preset", "veryfast",
                        "-crf", "20",
                        "-c:a", "aac",
                        "-b:a", "192k",
                        "-shortest",
                        "-pix_fmt", "yuv420p",
                        str(part_path)
                    ]
            
            run_ffmpeg(cut_args)
            temp_parts.append(part_path)
        
        # Ghép các đoạn video bằng concat demuxer
        with open(concat_list_file, "w", encoding="utf-8") as f:
            for p in temp_parts:
                f.write(f"file '{p.resolve().as_posix()}'\n")
        
        try:
            run_ffmpeg([
                "-f", "concat",
                "-safe", "0",
                "-i", str(concat_list_file),
                "-c", "copy",
                str(merged_temp_path)
            ])
        except Exception:
            run_ffmpeg([
                "-f", "concat",
                "-safe", "0",
                "-i", str(concat_list_file),
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-crf", "20",
                "-c:a", "aac",
                str(merged_temp_path)
            ])
            
        # Xử lý lồng nhạc nếu có
        music_path = None
        if req.music_file:
            music_path = OUTPUT_DIR / req.music_file
            if not music_path.exists():
                music_path = UPLOAD_DIR / req.music_file
                
        if music_path and music_path.exists() and req.audio_mode in ["replace_mp3", "mix_mp3"]:
            m_vol = float(req.music_volume or 1.0)
            v_vol = float(req.video_volume or 1.0)
            if req.audio_mode == "replace_mp3":
                run_ffmpeg([
                    "-i", str(merged_temp_path),
                    "-i", str(music_path),
                    "-filter_complex", f"[1:a]volume={m_vol:.2f}[aout]",
                    "-map", "0:v:0",
                    "-map", "[aout]",
                    "-c:v", "copy",
                    "-c:a", "aac",
                    "-b:a", "192k",
                    "-shortest",
                    str(final_video_path)
                ])
            else: # mix_mp3
                run_ffmpeg([
                    "-i", str(merged_temp_path),
                    "-i", str(music_path),
                    "-filter_complex", f"[0:a]volume={v_vol:.2f}[a0];[1:a]volume={m_vol:.2f}[a1];[a0][a1]amix=inputs=2:duration=first[aout]",
                    "-map", "0:v:0",
                    "-map", "[aout]",
                    "-c:v", "copy",
                    "-c:a", "aac",
                    "-b:a", "192k",
                    "-shortest",
                    str(final_video_path)
                ])
            merged_temp_path.unlink(missing_ok=True)
        else:
            if merged_temp_path.exists():
                if final_video_path.exists():
                    final_video_path.unlink()
                merged_temp_path.rename(final_video_path)
            
        # Dọn dẹp tệp tạm
        try:
            concat_list_file.unlink(missing_ok=True)
            for p in temp_parts:
                p.unlink(missing_ok=True)
        except Exception:
            pass
            
        return {
            "success": True,
            "filename": final_video_name,
            "url": f"/media/outputs/{final_video_name}",
            "full_path": str(final_video_path.resolve()),
            "output_dir": str(OUTPUT_DIR.resolve()),
            "message": f"Ghép thành công {len(req.segments)} đoạn video MP4!"
        }
    except Exception as e:
        try:
            concat_list_file.unlink(missing_ok=True)
            for p in temp_parts:
                p.unlink(missing_ok=True)
            merged_temp_path.unlink(missing_ok=True)
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=str(e))

def handle_suno_download(url: str, media_type: str, work_id: str):
    import json
    import subprocess
    import shutil
    import re
    
    script_path = BASE_DIR / "suno_decrypt.js"
    if not script_path.exists():
        fallback_script = Path(r"D:\Tu_O_C\Desktop\suno-downloader\suno-downloader\download_suno_drm.js")
        if fallback_script.exists():
            script_path = fallback_script

    ffmpeg_bin = get_ffmpeg_bin()
    ext = "mp3" if media_type == "mp3" else "mp4"
    out_file = OUTPUT_DIR / f"suno_{work_id}.{ext}"
    
    cmd = ["node", str(script_path), url, media_type, str(out_file), ffmpeg_bin]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="ignore")
    
    if result.returncode != 0:
        err_msg = result.stderr.strip() or result.stdout.strip()
        try:
            err_json = json.loads(err_msg)
            if "error" in err_json:
                err_msg = err_json["error"]
        except Exception:
            pass
        raise RuntimeError(f"Lỗi giải mã Suno DRM: {err_msg}")
        
    title = f"Suno_{work_id}"
    try:
        lines = [l for l in result.stdout.strip().splitlines() if l.strip()]
        if lines:
            data = json.loads(lines[-1])
            if "title" in data and data["title"]:
                title = data["title"]
                clean_title = re.sub(r'[^\w\s\-_]', '', title)[:50].strip()
                if clean_title:
                    new_file = OUTPUT_DIR / f"suno_{work_id}_{clean_title}.{ext}"
                    if out_file.exists():
                        out_file.rename(new_file)
                        out_file = new_file
    except Exception:
        pass
        
    increment_stat("suno")
    return out_file, title

@app.post("/api/download-suno")
async def download_suno_endpoint(req: DownloadUrlRequest):
    return await download_url(req)
@app.post("/api/download-url")
async def download_url(req: DownloadUrlRequest):
    url = req.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="Vui lòng nhập đường link hợp lệ!")
    
    media_type = req.media_type.lower()
    if media_type not in ["mp3", "mp4"]:
        media_type = "mp3"
        
    audio_format = (req.audio_format or "mp3_320").lower()
    video_format = (req.video_format or "mp4_1080").lower()
        
    ffmpeg_bin = get_ffmpeg_bin()
    work_id = uuid.uuid4().hex[:8]

    # Kiểm tra nếu là link Suno AI
    is_suno = any(k in url.lower() for k in ["suno.com", "suno.ai", "audiocdn1.suno.ai", "cdn1.suno.ai"])
    if is_suno:
        if req.task_id:
            download_progress_map[req.task_id] = {
                "status": "decrypting",
                "percent": 40.0,
                "stage": "Đang giải mã Suno Mango DRM..."
            }
        try:
            target_file, title = handle_suno_download(url, media_type, work_id)
            if req.task_id:
                download_progress_map[req.task_id] = {
                    "status": "converting",
                    "percent": 90.0,
                    "stage": "Đang xuất định dạng..."
                }
            
            # Xử lý định dạng theo yêu cầu người dùng
            if media_type == "mp3":
                converted_file = None
                if audio_format == "wav":
                    wav_file = target_file.with_suffix(".wav")
                    run_ffmpeg(["-i", str(target_file), "-c:a", "pcm_s16le", str(wav_file)])
                    if wav_file.exists():
                        target_file.unlink(missing_ok=True)
                        target_file = wav_file
                elif audio_format == "flac":
                    flac_file = target_file.with_suffix(".flac")
                    run_ffmpeg(["-i", str(target_file), "-c:a", "flac", str(flac_file)])
                    if flac_file.exists():
                        target_file.unlink(missing_ok=True)
                        target_file = flac_file
                elif audio_format == "m4a":
                    m4a_file = target_file.with_suffix(".m4a")
                    run_ffmpeg(["-i", str(target_file), "-c:a", "aac", "-b:a", "256k", str(m4a_file)])
                    if m4a_file.exists():
                        target_file.unlink(missing_ok=True)
                        target_file = m4a_file
                elif audio_format == "mp3_192":
                    mp3_192 = OUTPUT_DIR / f"{target_file.stem}_192k.mp3"
                    run_ffmpeg(["-i", str(target_file), "-c:a", "libmp3lame", "-b:a", "192k", str(mp3_192)])
                    if mp3_192.exists():
                        target_file.unlink(missing_ok=True)
                        target_file = mp3_192
                elif audio_format == "mp3_128":
                    mp3_128 = OUTPUT_DIR / f"{target_file.stem}_128k.mp3"
                    run_ffmpeg(["-i", str(target_file), "-c:a", "libmp3lame", "-b:a", "128k", str(mp3_128)])
                    if mp3_128.exists():
                        target_file.unlink(missing_ok=True)
                        target_file = mp3_128
                        
            elif media_type == "mp4":
                if video_format == "mp4_916":
                    v_916 = OUTPUT_DIR / f"{target_file.stem}_tiktok_916.mp4"
                    run_ffmpeg([
                        "-i", str(target_file),
                        "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black",
                        "-c:v", "libx264", "-preset", "veryfast", "-c:a", "copy", "-movflags", "+faststart",
                        str(v_916)
                    ])
                    if v_916.exists():
                        target_file.unlink(missing_ok=True)
                        target_file = v_916
                elif video_format == "mp4_720":
                    v_720 = OUTPUT_DIR / f"{target_file.stem}_720p.mp4"
                    run_ffmpeg([
                        "-i", str(target_file),
                        "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2:color=black",
                        "-c:v", "libx264", "-preset", "veryfast", "-c:a", "copy", "-movflags", "+faststart",
                        str(v_720)
                    ])
                    if v_720.exists():
                        target_file.unlink(missing_ok=True)
                        target_file = v_720
                elif video_format == "mp4_480":
                    v_480 = OUTPUT_DIR / f"{target_file.stem}_480p.mp4"
                    run_ffmpeg([
                        "-i", str(target_file),
                        "-vf", "scale=854:480:force_original_aspect_ratio=decrease,pad=854:480:(ow-iw)/2:(oh-ih)/2:color=black",
                        "-c:v", "libx264", "-preset", "veryfast", "-c:a", "copy", "-movflags", "+faststart",
                        str(v_480)
                    ])
                    if v_480.exists():
                        target_file.unlink(missing_ok=True)
                        target_file = v_480
                elif video_format == "mp4_wave":
                    v_wave = OUTPUT_DIR / f"{target_file.stem}_visualizer.mp4"
                    run_ffmpeg([
                        "-i", str(target_file),
                        "-filter_complex", "[0:v]scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2:color=0x0f172a[bg];[0:a]showwaves=s=1000x160:mode=cline:colors=0x38bdf8@0.9[wave];[bg][wave]overlay=(W-w)/2:H-h-40[outv]",
                        "-map", "[outv]", "-map", "0:a",
                        "-c:v", "libx264", "-preset", "veryfast", "-c:a", "aac", "-b:a", "192k", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                        str(v_wave)
                    ])
                    if v_wave.exists():
                        target_file.unlink(missing_ok=True)
                        target_file = v_wave

            upload_dest = UPLOAD_DIR / target_file.name
            try:
                shutil.copy2(target_file, upload_dest)
            except Exception:
                pass
            stat = target_file.stat()
            return {
                "success": True,
                "filename": target_file.name,
                "title": title,
                "media_type": media_type,
                "audio_format": audio_format,
                "video_format": video_format,
                "size_mb": round(stat.st_size / (1024 * 1024), 2),
                "url": f"/media/outputs/{target_file.name}",
                "upload_filename": target_file.name,
                "full_path": str(target_file.resolve()),
                "output_dir": str(OUTPUT_DIR.resolve()),
                "message": f"Tải nhạc Suno AI ({media_type.upper()}) thành công: {title}"
            }
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))
    
    # Template output cho mạng xã hội qua yt-dlp
    out_tmpl = str(OUTPUT_DIR / f"dl_{work_id}_%(title).100s.%(ext)s")

    def run_ytdlp_download():
        def ytdlp_progress_hook(d):
            if not req.task_id:
                return
            status = d.get('status')
            if status == 'downloading':
                total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                downloaded = d.get('downloaded_bytes') or 0
                speed = d.get('speed') or 0
                eta = d.get('eta') or 0
                percent = round((downloaded / total * 100), 1) if total > 0 else 0.0
                dl_mb = round(downloaded / (1024 * 1024), 2)
                tot_mb = round(total / (1024 * 1024), 2)
                sp_mb = round(speed / (1024 * 1024), 2) if speed else 0.0
                download_progress_map[req.task_id] = {
                    "status": "downloading",
                    "percent": min(percent, 98.0),
                    "downloaded_mb": dl_mb,
                    "total_mb": tot_mb,
                    "speed_mb": sp_mb,
                    "eta": eta,
                    "stage": f"Đang tải: {percent}% ({dl_mb} MB / {tot_mb} MB)"
                }
            elif status == 'finished':
                download_progress_map[req.task_id] = {
                    "status": "converting",
                    "percent": 99.0,
                    "stage": "Đang trích xuất & tối ưu âm thanh..."
                }
        is_audio_platform = any(k in url.lower() for k in ["soundcloud.com", "zingmp3.vn", "nhaccuatui.com", "spotify.com"])
        should_download_audio_first = (media_type == "mp3") or is_audio_platform

        pref_codec = "mp3"
        pref_quality = "320"
        if audio_format == "wav": pref_codec = "wav"
        elif audio_format == "flac": pref_codec = "flac"
        elif audio_format == "m4a": pref_codec = "m4a"
        elif audio_format == "mp3_192": pref_quality = "192"
        elif audio_format == "mp3_128": pref_quality = "128"

        max_h = 1080
        if video_format == "mp4_720": max_h = 720
        elif video_format == "mp4_480": max_h = 480

        def get_ydl_opts(as_audio=True):
            if as_audio:
                return {
                    'ffmpeg_location': ffmpeg_bin,
                    'format': 'bestaudio[format_id!*=drm][format_id!*=encrypted]/bestaudio[ext=m4a]/bestaudio[ext=mp3]/bestaudio/best',
                    'outtmpl': out_tmpl,
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': pref_codec,
                        'preferredquality': pref_quality,
                    }],
                    'quiet': True,
                    'no_warnings': True,
                    'noplaylist': True,
                    'socket_timeout': 5,
                    'retries': 2,
                    'fragment_retries': 2,
                    'concurrent_fragment_downloads': 16,
                    'progress_hooks': [ytdlp_progress_hook],
                    'extractor_args': {
                        'youtube': {'player_client': ['android', 'web']},
                        'soundcloud': {'formats': ['http', 'hls']}
                    },
                    'http_headers': {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    }
                }
            else:
                return {
                    'ffmpeg_location': ffmpeg_bin,
                    'format': f'bestvideo[height<={max_h}][format_id!*=drm][ext=mp4]+bestaudio[ext=m4a]/best[height<={max_h}][ext=mp4]/best',
                    'outtmpl': out_tmpl,
                    'merge_output_format': 'mp4',
                    'quiet': True,
                    'no_warnings': True,
                    'noplaylist': True,
                    'socket_timeout': 5,
                    'retries': 2,
                    'fragment_retries': 2,
                    'concurrent_fragment_downloads': 16,
                    'progress_hooks': [ytdlp_progress_hook],
                    'extractor_args': {
                        'youtube': {'player_client': ['android', 'web']}
                    },
                    'http_headers': {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    }
                }

        title = f"download_{work_id}"
        download_success = False

        # Thử tải lần 1
        active_ydl_opts = get_ydl_opts(as_audio=should_download_audio_first)
        try:
            with yt_dlp.YoutubeDL(active_ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                title = info.get('title', title)
                download_success = True
        except Exception as e:
            err_msg = str(e).lower()
            print(f"[Download Primary Failed] URL={url}, err={err_msg}")
            
            # Nếu yêu cầu video nhưng nguồn là trang âm thanh (như SoundCloud)
            if "no video formats" in err_msg and not should_download_audio_first:
                try:
                    with yt_dlp.YoutubeDL(get_ydl_opts(as_audio=True)) as audio_ydl:
                        info = audio_ydl.extract_info(url, download=True)
                        title = info.get('title', title)
                        download_success = True
                        should_download_audio_first = True
                except Exception as audio_err:
                    err_msg = str(audio_err).lower()

            if not download_success:
                # Kích hoạt Smart Fallback giải mã luồng dự phòng (DRM / 403 / No Video)
                song_search_title = ""
                try:
                    with yt_dlp.YoutubeDL({'quiet': True, 'extract_flat': True, 'socket_timeout': 5}) as meta_ydl:
                        meta = meta_ydl.extract_info(url, download=False)
                        if meta:
                            t = meta.get('title', '')
                            u = meta.get('uploader', '') or meta.get('artist', '')
                            song_search_title = f"{t} {u}".strip()
                except Exception:
                    pass

                if not song_search_title:
                    import urllib.parse
                    clean_path = urllib.parse.unquote(url.split("?")[0].rstrip("/")).replace(".html", "").replace(".htm", "")
                    parts = [p.replace("-", " ").replace("_", " ") for p in clean_path.split("/") if p and not p.startswith("http")]
                    song_search_title = " ".join(parts[-3:] if len(parts) >= 3 else parts).strip()

                if song_search_title:
                    print(f"[Smart Fallback] Querying: {song_search_title}")
                    query = f"ytsearch1:{song_search_title} audio" if media_type == "mp3" else f"ytsearch1:{song_search_title}"
                    try:
                        with yt_dlp.YoutubeDL(active_ydl_opts) as fallback_ydl:
                            fallback_info = fallback_ydl.extract_info(query, download=True)
                            if 'entries' in fallback_info and fallback_info['entries']:
                                fallback_info = fallback_info['entries'][0]
                            title = fallback_info.get('title', song_search_title)
                            download_success = True
                    except Exception as fb_err:
                        raise RuntimeError(f"Tệp bị khóa bản quyền DRM và không tìm thấy nguồn thay thế: {fb_err}")
                else:
                    raise RuntimeError(f"Lỗi tải từ link: {err_msg}")

        matched = list(OUTPUT_DIR.glob(f"dl_{work_id}_*.*"))
        if not matched:
            raise RuntimeError("Không tìm thấy tệp sau khi tải về.")

        target_file = matched[0]

        # Nếu người dùng yêu cầu MP4 nhưng nguồn là audio (ví dụ SoundCloud):
        # Tự động đóng gói thành video MP4 có sóng âm Neon 720p siêu nhanh chỉ mất 1-2 giây!
        if media_type == "mp4" and target_file.suffix.lower() in [".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"]:
            mp4_out = OUTPUT_DIR / f"{target_file.stem}_video.mp4"
            print(f"[Auto MP4 Wrap] Wrapping audio {target_file.name} to MP4 video...")
            run_ffmpeg([
                "-f", "lavfi", "-i", "color=c=0x0f172a:s=1280x720:d=10",
                "-i", str(target_file),
                "-filter_complex", "[0:v][1:a]showwaves=s=1100x180:mode=cline:colors=0x38bdf8@0.9[wave];[0:v][wave]overlay=(W-w)/2:H-h-60:shortest=1[outv]",
                "-map", "[outv]", "-map", "1:a",
                "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-b:a", "192k",
                "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-shortest",
                str(mp4_out)
            ])
            if mp4_out.exists():
                target_file.unlink(missing_ok=True)
                target_file = mp4_out

        if req.task_id:
            download_progress_map[req.task_id] = {
                "status": "done",
                "percent": 100.0,
                "stage": "Hoàn tất!"
            }

        upload_dest = UPLOAD_DIR / target_file.name
        try:
            shutil.copy2(target_file, upload_dest)
        except Exception:
            pass

        stat = target_file.stat()
        return {
            "success": True,
            "filename": target_file.name,
            "title": title,
            "media_type": media_type,
            "audio_format": audio_format,
            "video_format": video_format,
            "size_mb": round(stat.st_size / (1024 * 1024), 2),
            "url": f"/media/outputs/{target_file.name}",
            "upload_filename": target_file.name,
            "full_path": str(target_file.resolve()),
            "output_dir": str(OUTPUT_DIR.resolve()),
            "message": f"Tải tệp thành công: {title}"
        }

    try:
        return await asyncio.to_thread(run_ytdlp_download)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi tải từ link: {str(e)}")

@app.get("/api/list-files")
async def list_files():
    results = []
    for p in sorted(OUTPUT_DIR.glob("*.*"), key=lambda x: x.stat().st_mtime, reverse=True):
        ext = p.suffix.lower()
        if ext in [".mp3", ".wav", ".m4a", ".aac", ".flac", ".mp4", ".mov", ".mkv", ".webm"]:
            stat = p.stat()
            results.append({
                "filename": p.name,
                "ext": ext.replace(".", "").upper(),
                "size_mb": round(stat.st_size / (1024 * 1024), 2),
                "mtime": stat.st_mtime,
                "type": "audio" if ext in [".mp3", ".wav", ".m4a", ".aac", ".flac"] else "video",
                "url": f"/media/outputs/{p.name}",
                "full_path": str(p.resolve())
            })
    return {"files": results}

@app.post("/api/delete-file")
async def delete_file(req: DeleteFileRequest):
    p = OUTPUT_DIR / req.filename
    if p.exists():
        try:
            p.unlink()
            # Xoá cả trong uploads nếu có
            (UPLOAD_DIR / req.filename).unlink(missing_ok=True)
            return {"success": True, "message": f"Đã xoá tệp {req.filename}"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    raise HTTPException(status_code=404, detail="Không tìm thấy tệp để xoá.")

@app.post("/api/open-folder")
async def open_output_folder(req: Optional[OpenFolderRequest] = None):
    try:
        if req and req.filename:
            file_path = OUTPUT_DIR / req.filename
            if file_path.exists():
                subprocess.Popen(["explorer", f"/select,{str(file_path.resolve())}"])
                return {"success": True, "message": "Đã mở thư mục và chọn video!"}
        # Mở thư mục outputs của tool
        subprocess.Popen(["explorer", str(OUTPUT_DIR.resolve())])
        return {"success": True, "message": "Đã mở thư mục outputs của tool!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/download/{filename}")
async def download_file(filename: str):
    file_path = OUTPUT_DIR / filename
    if not file_path.exists():
        file_path = UPLOAD_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Tệp không tồn tại.")
    return FileResponse(path=file_path, filename=filename, media_type="application/octet-stream")

@app.get("/", response_class=HTMLResponse)
async def get_index():
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        return HTMLResponse("<h1>Trang web đang được tải...</h1>")
    return HTMLResponse(content=index_file.read_text(encoding="utf-8"))

if __name__ == "__main__":
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass
    port = 8765
    print("==================================================")
    print("[+] CAT NHAC MP3 & GHEP VIDEO MP4 (ONLINE DOWNLOADER)")
    print(f"[+] Mo trinh duyet tai: http://127.0.0.1:{port}")
    print("==================================================")
    try:
        webbrowser.open(f"http://127.0.0.1:{port}")
    except Exception:
        pass
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
