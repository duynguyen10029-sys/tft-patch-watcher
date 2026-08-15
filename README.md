# TFT Patch Watcher

Tool tự động theo dõi thay đổi dữ liệu TFT (champion, trait, item) từ
[Community Dragon](https://raw.communitydragon.org/), lưu lịch sử dạng
version-controlled trong Git, và gửi cảnh báo Discord khi phát hiện
patch mới hoặc thay đổi balance — giúp bạn nắm thông tin sớm hơn để
theorycraft đội hình trước khi cộng đồng bắt kịp.

## Cách hoạt động

1. `scripts/fetch_and_diff.py` tải file dữ liệu TFT mới nhất từ CDragon.
2. So sánh với snapshot lần chạy trước (`data/last_snapshot.json`).
3. Nếu có thay đổi (champion mới, trait breakpoint đổi, item buff/nerf...):
   - Ghi log chi tiết vào `data/diff_log.jsonl`
   - Gửi cảnh báo qua Discord webhook (nếu đã cấu hình)
4. GitHub Actions (`.github/workflows/tft-patch-watch.yml`) chạy script
   này tự động mỗi giờ — hoàn toàn miễn phí, không cần server riêng.

## Cài đặt

### 1. Đưa code lên GitHub

```bash
cd tft-patch-watcher
git init
git add .
git commit -m "init: tft patch watcher"
git branch -M main
git remote add origin <URL_REPO_CUA_BAN>
git push -u origin main
```

Repo public thì GitHub Actions free hoàn toàn. Repo private vẫn free
trong giới hạn 2000 phút/tháng (task này rất nhẹ, mỗi lần chạy vài giây
nên gần như không đáng kể).

### 2. (Tuỳ chọn) Cấu hình Discord webhook

- Trong server Discord của bạn: **Server Settings → Integrations →
  Webhooks → New Webhook** → copy URL.
- Trên GitHub repo: **Settings → Secrets and variables → Actions →
  New repository secret**
  - Name: `DISCORD_WEBHOOK_URL`
  - Value: URL webhook vừa copy

Nếu không cấu hình, tool vẫn chạy bình thường và ghi log vào
`data/diff_log.jsonl`, chỉ là không gửi thông báo Discord.

### 3. Bật GitHub Actions

Vào tab **Actions** trên repo → nếu chưa bật, bấm "I understand my
workflows, go ahead and enable them". Workflow sẽ tự chạy theo lịch
cron đã đặt (mặc định: mỗi giờ).

Bạn cũng có thể chạy tay ngay lập tức: **Actions → TFT Patch Watcher →
Run workflow**.

## Chạy thử ở local

```bash
pip install --break-system-packages -r requirements.txt   # không có dependency ngoài, chỉ dùng thư viện chuẩn
python scripts/fetch_and_diff.py
```

Chạy lần đầu sẽ không có gì để so sánh (chỉ tạo snapshot gốc). Chạy
lần thứ 2 trở đi mới bắt đầu phát hiện diff.

Muốn theo dõi bản PBE thay vì live:

```bash
CDRAGON_REGION=pbe python scripts/fetch_and_diff.py
```

Set biến `CDRAGON_REGION=pbe` tương tự trong workflow YAML nếu muốn
GitHub Actions theo dõi PBE — đây là nơi patch/set mới xuất hiện SỚM
NHẤT, trước khi lên live, nên rất đáng theo dõi để có lợi thế
"first mover".

## Cấu trúc dữ liệu lưu trữ

- `data/last_snapshot.json` — trạng thái dữ liệu game tại lần chạy gần
  nhất (champion stats, trait breakpoints, item effects...).
- `data/diff_log.jsonl` — lịch sử toàn bộ các lần phát hiện thay đổi,
  mỗi dòng là 1 bản ghi JSON có timestamp + chi tiết diff. File này
  chính là "dataset" bạn dùng để phân tích xu hướng balance qua thời
  gian.

## Mở rộng tiếp theo (gợi ý)

- Thêm bước tính toán "theorycraft score" tự động (so sánh damage/mana
  ratio giữa các champion cùng cost) ngay sau khi có diff mới.
- Thêm dashboard web đơn giản (đọc `diff_log.jsonl`) để xem lịch sử
  patch trực quan.
- Theo dõi thêm augment pool nếu CDragon expose riêng endpoint đó.
