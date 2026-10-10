# 🎵 Cắt Nhạc MP3 & Ghép Video MP4 (Audio Waveform Editor & Video Remuxer)

Ứng dụng web cục bộ chạy trên máy tính, được thiết kế bám sát 100% sơ đồ giao diện người dùng yêu cầu:

```text
              WAVEFORM MP3
0s ────────┃████████████████┃──────────── 60s
           ↑                ↑
        START 3.250      END 23.000

Bắt đầu                              Kết thúc
[ 3.250 ] giây                       [ 23.000 ] giây
    [-0.1] [+0.1]                       [-0.1] [+0.1]

          Độ dài: 19.750 giây

       [▶ NGHE THỬ]   [✂ CẮT]

------------------------------------------------

CÁC ĐOẠN ĐÃ CẮT

☑ #01   03.250 → 23.000     19.750s    ▶  🗑
☑ #02   30.000 → 41.500     11.500s    ▶  🗑
☑ #03   48.200 → 55.700      7.500s    ▶  🗑

       ↕ KÉO ĐỂ ĐỔI THỨ TỰ

[ GHÉP MP3 ĐÃ CHỌN ]

              ↓

[ CHỌN VIDEO MP4 ]

Audio MP4:
(•) Thay bằng MP3
( ) Giữ audio gốc + trộn MP3
( ) Tắt audio gốc
   - **[ ▶ XEM & NGHE THỬ TRƯỚC (ĐỒNG BỘ VIDEO + MP3) ]**: Nghe và xem thử trực tiếp video chạy cùng nhạc MP3 theo đúng chế độ và âm lượng đã chọn (đồng bộ tua thời gian thực, không cần chờ xuất file!).

[ XUẤT MP4 ]
```

---

## 🚀 Các tính năng chính

1. **Hiển thị sóng âm thực tế (Waveform Visualizer):**
   - Đọc và giải mã dữ liệu âm thanh trực tiếp bằng Web Audio API, hiển thị sóng âm chân thực với thang đo thời gian `0s ... 60s`.
   - Có 2 thanh kéo **START** (xanh lá) và **END** (vàng cam) kèm vùng phủ màu trực quan `┃████████████████┃`.
   - Hỗ trợ chuột kéo thả hoặc bấm vào bất kỳ đâu trên sóng âm để định vị.

2. **Điều khiển thời gian chính xác tới mili-giây (0.001s):**
   - Ô nhập thời gian: `[ 3.250 ] giây` và `[ 23.000 ] giây`.
   - Các nút chỉnh nhanh: `[-0.1]`, `[+0.1]`, `[-1.0s]`, `[+1.0s]`.
   - Tự động tính toán và hiển thị: **Độ dài đoạn: XX.XXX giây**.

3. **Nghe thử & Cắt lưu nhiều đoạn:**
   - **`[▶ NGHE THỬ]`**: Phát chính xác khoảng từ START tới END kèm kim phát sóng (playhead) chạy theo thời gian thực.
   - **`[✂ CẮT]`**: Thêm đoạn đã chọn vào danh sách **CÁC ĐOẠN ĐÃ CẮT**.

4. **Quản lý danh sách đoạn cắt:**
   - Đánh số thứ tự tự động: `#01`, `#02`, `#03`...
   - Checkbox `☑` cho phép chọn hoặc bỏ chọn đoạn cần ghép.
   - Nút `▶` nghe thử riêng từng đoạn cắt.
   - Nút `🗑` xoá đoạn không cần thiết.
   - **`↕ KÉO ĐỂ ĐỔI THỨ TỰ`**: Hỗ trợ kéo thả trực tiếp (HTML5 Drag & Drop) hoặc dùng nút mũi tên `▲` `▼` để sắp xếp thứ tự phát các đoạn.

5. **Ghép nối MP3:**
   - Nút **`[ GHÉP MP3 ĐÃ CHỌN ]`** sử dụng FFmpeg ghép nối mượt mà không bị méo tiếng hoặc lệch pha.
   - Có sẵn trình phát nhạc nghe thử tệp MP3 đã ghép và nút tải về máy.

6. **Ghép nhạc vào Video MP4:**
   - Chọn hoặc kéo thả video MP4 vào để xem trước.
   - 3 chế độ âm thanh:
     - `(•) Thay bằng MP3`: Xoá bỏ toàn bộ tiếng gốc của video, lồng nhạc MP3 đã ghép.
     - `( ) Giữ audio gốc + trộn MP3`: Giữ âm thanh gốc của video và trộn chung với nhạc MP3 (kèm thanh gạt chỉnh âm lượng video gốc và âm lượng nhạc).
     - `( ) Tắt audio gốc`: Tắt tiếng video gốc.
   - **[ ▶ XEM & NGHE THỬ TRƯỚC (ĐỒNG BỘ VIDEO + MP3) ]**: Nghe và xem thử trực tiếp video chạy cùng nhạc MP3 theo đúng chế độ và âm lượng đã chọn (đồng bộ tua thời gian thực, không cần chờ xuất file!).
   - Tốc độ xuất video siêu nhanh nhờ cơ chế copy stream thông minh của FFmpeg.
   - Trình phát xem lại video thành phẩm kèm nút **[ 📁 MỞ FOLDER VIDEO TRÊN MÁY ]** (mở trực tiếp thư mục outputs/ của tool) và nút **[ ⬇ TẢI VỀ TRÌNH DUYỆT ]**.

7. **Cắt & Ghép Video MP4 chuyên dụng (MỚI):**
   - **Giao diện Tab linh hoạt**: Chuyển đổi giữa tab 🎵 Cắt & Ghép Nhạc MP3 và 🎬 Cắt & Ghép Video MP4.
   - **Định vị thời gian cắt thông minh**:
     - Nút [⏱ Đặt START tại thời điểm phát này] và [⏱ Đặt END tại thời điểm phát này] giúp người dùng vừa xem video vừa chọn mốc cắt cực nhanh.
     - Ô nhập thời gian chính xác tới mili-giây cùng các nút nhảy [-1.0s], [-0.1s], [+0.1s], [+1.0s].
     - Nút [▶ XEM THỬ ĐOẠN ĐÃ CHỌN] phát chính xác khoảng thời gian đã chọn trước khi cắt.
   - **Quản lý & sắp xếp đoạn cắt video**:
     - Hỗ trợ cắt nhiều đoạn từ cùng một video hoặc nhiều video khác nhau.
     - Hiển thị nhãn tên video nguồn, thời gian START → END, độ dài từng đoạn.
     - Hỗ trợ kéo thả đổi thứ tự hoặc bấm nút ▲ ▼.
     - Nghe/xem thử riêng từng đoạn cắt ▶ và xoá đoạn thừa 🗑.
     - Tự động tính toán tổng độ dài video ghép dự kiến.
   - **Tùy chọn âm thanh khi ghép video**:
     - (•) Giữ âm thanh gốc của các đoạn video.
     - ( ) Tắt âm thanh (Video câm hoàn toàn).
     - ( ) Thay thế bằng nhạc MP3 (dùng tệp MP3 đã ghép từ Tab 1 hoặc tải lên tệp nhạc mới).
     - ( ) Giữ tiếng video gốc + trộn thêm nhạc MP3 (kèm thanh gạt chỉnh âm lượng riêng biệt).
   - **Xuất video chất lượng cao**:
     - Nút **[ 🚀 GHÉP CÁC ĐOẠN VIDEO ĐÃ CHỌN ]** ghép video siêu mượt, xử lý keyframe chính xác không bị khựng hình hay lệch tiếng.
     - Trình phát xem lại video thành phẩm kèm nút mở thư mục lưu và tải về.

8. **Tải MP3 & MP4 Về Máy Từ Link Online & Quản Lý File (MỚI!):**
   - **Tải từ đường link mạng**: Hỗ trợ dán link video/nhạc từ YouTube, Facebook, TikTok, SoundCloud...
   - **Tự động chuyển đổi**:
     - Tải MP3 (tách audio, nén 192kbps chất lượng cao).
     - Tải MP4 (tải video độ phân giải cao).
   - **Đưa thẳng vào công cụ cắt ghép**:
     - Nút [ ✂ ĐƯA VÀO CẮT GHÉP NGAY ] tự động nạp bài hát vừa tải sang Tab 1 hoặc nạp video vừa tải sang Tab 2 để cắt ngay lập tức.
   - **Thư viện tệp trong thư mục outputs/**: Hiển thị danh sách toàn bộ các file MP3/MP4 có trên máy, kèm nút nghe/xem trước, tải về, mở trên máy, hoặc xoá.

---

## 🛠 Cách khởi động

### Cách 1: Nhấp đúp vào tệp `run.bat`
Trong thư mục `C:\Users\Windows\Desktop\Ghép Nhạc MP3`, nhấp đúp vào **`run.bat`**. Trình duyệt sẽ tự động mở tại địa chỉ:
```
http://127.0.0.1:8765
```

### Cách 2: Chạy bằng lệnh trong terminal
```powershell
cd "C:\Users\Windows\Desktop\Ghép Nhạc MP3"
python app.py
```