"""
Danbooru Post Count & Social Links Fetcher v3
==============================================
读取画师存档 JSON，通过 Danbooru API 并发抓取每位画师的 post count 和社交链接。

特性:
  - 多线程并发请求 (默认 8 线程)，速度提升 8 倍+
  - 实时进度条 + ETA
  - 断点续传：中断后再跑自动跳过已处理的
  - 自动将 tag 空格转换为 Danbooru 的下划线格式
  - 抓取画师的 Pixiv / Twitter / 个人网站等社交链接

用法:
  python fetch_danbooru_counts.py                     # 处理最新备份
  python fetch_danbooru_counts.py path/to/file.json   # 指定文件
  python fetch_danbooru_counts.py --test               # 仅前 10 个
  python fetch_danbooru_counts.py --workers 12         # 用 12 线程
  python fetch_danbooru_counts.py --force              # 重新抓取全部
  python fetch_danbooru_counts.py --no-urls            # 不抓取社交链接
"""

import json
import os
import sys
import time
import re
import urllib.request
import urllib.parse
import urllib.error
import ssl
import argparse
import io
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

# ----- Windows 控制台 UTF-8 -----
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)
    os.system('chcp 65001 >nul 2>&1')

# ===== 配置 =====
DANBOORU_API = "https://danbooru.donmai.us"
DEFAULT_WORKERS = 8       # 并发线程数
SAVE_EVERY = 50           # 每 N 个保存
MAX_RETRIES = 2           # 重试次数 (减少重试以加快失败处理)
RETRY_DELAY = 3           # 重试间隔
TIMEOUT = 10              # HTTP 超时
RATE_LIMIT = 5            # 每秒最大请求数 (调低以防 Danbooru 由于请求太快而断开，可适当调高)
PROXY_URL = None          # 全局代理地址

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '数据文件夹')

# ===== 线程安全的速率限制器 =====
class RateLimiter:
    """令牌桶算法限速器"""
    def __init__(self, rate_per_sec):
        self.rate = rate_per_sec
        self.lock = threading.Lock()
        self.tokens = rate_per_sec
        self.last_time = time.monotonic()

    def acquire(self):
        while True:
            with self.lock:
                now = time.monotonic()
                elapsed = now - self.last_time
                self.tokens = min(self.rate, self.tokens + elapsed * self.rate)
                self.last_time = now
                if self.tokens >= 1:
                    self.tokens -= 1
                    return
            time.sleep(0.05)  # 等一下再尝试

rate_limiter = RateLimiter(RATE_LIMIT)

# ===== 线程安全的日志 + 进度 =====
_print_lock = threading.Lock()
_progress = {'done': 0, 'found': 0, 'not_found': 0, 'error': 0, 'skipped': 0, 'total': 0}
_start_time = 0
_last_progress_line_len = 0

def _flush_print(*args, **kwargs):
    """线程安全的 print"""
    with _print_lock:
        print(*args, **kwargs, flush=True)

def log(msg, level="INFO"):
    ts = datetime.now().strftime("%H:%M:%S")
    prefix = {"INFO": "[i]", "OK": "[+]", "WARN": "[!]", "ERR": "[X]", "SKIP": "[-]"}.get(level, "   ")
    _flush_print(f"[{ts}] {prefix} {msg}")

def show_progress(tag_info=""):
    """刷新进度条 (覆盖当前行)"""
    global _last_progress_line_len
    with _print_lock:
        d = _progress
        total = d['total']
        done = d['done']
        if total == 0:
            return

        pct = done / total
        elapsed = time.monotonic() - _start_time
        speed = done / elapsed if elapsed > 0 else 0
        eta = (total - done) / speed if speed > 0 else 0

        bar_len = 30
        filled = int(bar_len * pct)
        bar = '#' * filled + '-' * (bar_len - filled)

        eta_str = f"{int(eta//60)}m{int(eta%60):02d}s" if eta < 3600 else f"{eta/3600:.1f}h"

        line = (
            f"\r[{bar}] {pct*100:5.1f}% ({done}/{total}) "
            f"| OK:{d['found']} Miss:{d['not_found']} Err:{d['error']} "
            f"| {speed:.1f}/s ETA:{eta_str}"
        )
        if tag_info:
            line += f" | {tag_info[:25]}"

        # 用空格覆盖上一行残留字符
        pad = max(0, _last_progress_line_len - len(line))
        sys.stdout.write(line + ' ' * pad)
        sys.stdout.flush()
        _last_progress_line_len = len(line)


# ===== Tag 处理 =====
def normalize_tag(tag):
    tag = tag.strip()
    tag = re.sub(r'^,?\s*a?rt?ist:\s*', '', tag, flags=re.IGNORECASE)
    tag = tag.replace(' ', '_')
    tag = tag.lower()
    tag = re.sub(r'_+', '_', tag).strip('_')
    return tag

# ===== SSL Context (复用) =====
_ssl_ctx = ssl.create_default_context()
_opener = None

def get_opener():
    global _opener
    if _opener is None:
        if PROXY_URL:
            # 使用代理并包含 SSL Context
            handler = urllib.request.ProxyHandler({'http': PROXY_URL, 'https': PROXY_URL})
            _opener = urllib.request.build_opener(handler, urllib.request.HTTPSHandler(context=_ssl_ctx))
        else:
            _opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=_ssl_ctx))
    return _opener

def _http_get_json(url):
    """单次 HTTP GET -> JSON"""
    rate_limiter.acquire()
    req = urllib.request.Request(url, headers={
        'User-Agent': 'ArtistManagerTool/2.0',
        'Accept': 'application/json'
    })
    
    with get_opener().open(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode('utf-8'))

def make_request(url):
    """带重试的 HTTP 请求"""
    for attempt in range(MAX_RETRIES):
        try:
            return _http_get_json(url), None
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(RETRY_DELAY * (attempt + 2))
                continue
            return None, f"HTTP {e.code}"
        except (urllib.error.URLError, OSError) as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
            else:
                return None, f"conn_err"
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
            else:
                return None, f"err:{type(e).__name__}"
    return None, "max_retries"


def fetch_tag_count(tag_name):
    """
    Danbooru tag 查询 (最多 2 次 API 调用)
    策略 1: 精确匹配 artist 类
    策略 2: 精确匹配 任意类 (兜底)
    """
    normalized = normalize_tag(tag_name)
    if not normalized:
        return 0, None, 'empty'

    # 策略 1: artist category (category=1)
    url = f"{DANBOORU_API}/tags.json?search[name]={urllib.parse.quote(normalized)}&search[category]=1&limit=1"
    data, err = make_request(url)
    if err:
        return 0, None, f'error:{err}'
    if data and len(data) > 0:
        return data[0]['post_count'], data[0]['name'], 'exact_artist'

    # 策略 2: any category
    url = f"{DANBOORU_API}/tags.json?search[name]={urllib.parse.quote(normalized)}&limit=1"
    data, err = make_request(url)
    if err:
        return 0, None, f'error:{err}'
    if data and len(data) > 0:
        return data[0]['post_count'], data[0]['name'], 'exact_any'

    return 0, None, 'not_found'


def fetch_artist_urls(tag_name):
    """
    通过两步完整查询画师的社交链接
    返回: (URL 字符串列表, err_msg)
    """
    normalized = normalize_tag(tag_name)
    if not normalized:
        return [], None

    # Step 1: 查出画师在 Danbooru 的真实 artist_id
    artist_url = f"{DANBOORU_API}/artists.json?search[name]={urllib.parse.quote(normalized)}&limit=1"
    artist_data, err = make_request(artist_url)
    if err:
        return None, f"artists.json err: {err}"
    if not artist_data or not isinstance(artist_data, list) or len(artist_data) == 0:
        return [], None
        
    artist_id = artist_data[0].get('id')
    if not artist_id:
        return [], None

    # Step 2: 严格根据 artist_id 查询只属于该画师的社交链接
    url = f"{DANBOORU_API}/artist_urls.json?search[artist_id]={artist_id}"
    data, err = make_request(url)
    if err:
        return None, err
    if not data:
        return [], None

    urls = []
    
    # 现在的 data 是包含 {url, is_active} 的对象列表
    for item in data:
        if isinstance(item, dict):
            u = item.get('url', '')
            # 跳过被标记为非活跃的链接
            if item.get('is_active', True) and u:
                urls.append(u)
        elif isinstance(item, str) and item:
            urls.append(item)

    # 自动去重机制 (保留插入排序，同时忽略结尾斜杠的差异)
    seen = set()
    unique_urls = []
    for u in urls:
        u_norm = u.strip().rstrip('/')
        if u_norm not in seen:
            seen.add(u_norm)
            unique_urls.append(u.strip())

    return unique_urls, None


# ===== Worker =====
def process_one(idx, artist, result_list, results_lock, fetch_urls=True, urls_only=False):
    """单个画师的处理函数 (在线程中运行)
    urls_only=True: 跳过 count 查询，仅抓取链接 (用于已有 count 但缺链接的画师)
    """
    tag = artist.get('tag', '')
    if not tag.strip():
        with results_lock:
            _progress['skipped'] += 1
            _progress['done'] += 1
        return

    if urls_only:
        # 已有 count，只需要抓链接
        existing_count = artist.get('danbooruCount', 0)
        social_urls, err_msg = fetch_artist_urls(tag) if fetch_urls else ([], None)
        with results_lock:
            if err_msg:
                # 出现网络或 429 错误时，不保存空列表，仅记录错误
                result_list.append((idx, existing_count, None, f'error:{err_msg}', None))
                _progress['error'] += 1
            else:
                result_list.append((idx, existing_count, None, 'urls_only', social_urls))
                if social_urls:
                    _progress['found'] += 1
                else:
                    _progress['not_found'] += 1
            _progress['done'] += 1
        show_progress(tag)
        return

    count, matched, method = fetch_tag_count(tag)

    # 抓取社交链接
    social_urls = []
    if fetch_urls and count > 0:
        social_urls_res, url_err = fetch_artist_urls(tag)
        if url_err:
            method = f'error:{url_err}'
            social_urls = None # 置空，不覆盖
        else:
            social_urls = social_urls_res

    with results_lock:
        if count > 0:
            result_list.append((idx, count, matched, method, social_urls))
            _progress['found'] += 1
        elif 'error' in (method or ''):
            _progress['error'] += 1
        else:
            _progress['not_found'] += 1
        _progress['done'] += 1

    show_progress(tag)


# ===== 找最新备份 =====
def find_latest_backup(data_dir):
    backups = []
    for f in os.listdir(data_dir):
        if f.startswith('artist_manager_backup') and f.endswith('.json') and '_updated' not in f:
            fpath = os.path.join(data_dir, f)
            backups.append((os.path.getmtime(fpath), fpath, f))
    if backups:
        backups.sort(reverse=True)
        return backups[0][1], backups[0][2]
    return None, None


# ===== 主函数 =====
def main():
    global _start_time

    parser = argparse.ArgumentParser(description='Danbooru Post Count & Social Links Fetcher v3 - 并发抓取画师 post count 和社交链接')
    parser.add_argument('input_file', nargs='?', default=None, help='输入 JSON (默认最新备份)')
    parser.add_argument('--force', action='store_true', help='强制更新所有画师')
    parser.add_argument('--test', action='store_true', help='测试模式 (仅前 10 个)')
    parser.add_argument('--workers', type=int, default=DEFAULT_WORKERS, help=f'并发线程数 (默认 {DEFAULT_WORKERS})')
    parser.add_argument('--output', '-o', default=None, help='输出文件')
    parser.add_argument('--save-interval', type=int, default=SAVE_EVERY, help=f'保存间隔 (默认 {SAVE_EVERY})')
    parser.add_argument('--no-urls', action='store_true', help='不抓取社交链接 (仅抓取 count)')
    parser.add_argument('--proxy', default=None, help='设置代理地址，例如 http://127.0.0.1:7890 用来访问被墙的 Danbooru')
    args = parser.parse_args()

    global PROXY_URL
    if args.proxy:
        PROXY_URL = args.proxy

    # 输入文件
    if args.input_file:
        input_path = args.input_file
        if not os.path.exists(input_path):
            log(f"文件不存在: {input_path}", "ERR")
            sys.exit(1)
    else:
        input_path, fname = find_latest_backup(DATA_DIR)
        if not input_path:
            log(f"在 {DATA_DIR} 中找不到备份文件", "ERR")
            sys.exit(1)
        log(f"自动选择最新备份: {fname}")

    # 输出文件
    if args.output:
        output_path = args.output
    else:
        base, ext = os.path.splitext(input_path)
        output_path = f"{base}_updated{ext}"

    # 读取
    log(f"读取文件: {os.path.basename(input_path)}")
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    artists = data.get('artists', [])
    if not artists and isinstance(data, list):
        artists = data
        data = {'artists': artists}

    total = len(artists)
    log(f"共 {total} 位画师")

    # 筛选
    fetch_urls = not args.no_urls
    if args.force:
        to_process = list(range(total))
        urls_only_set = set()  # force 模式全部重新抓
        log(f"强制模式：处理全部 {total}")
    else:
        need_count = []   # 完全没有 count 的
        need_urls = []    # 有 count 但缺 socialLinks 的
        for i, a in enumerate(artists):
            if a.get('danbooruCount', 0) == 0:
                need_count.append(i)
            elif fetch_urls and ('socialLinks' not in a or a.get('socialLinks') is None):
                need_urls.append(i)
        to_process = need_count + need_urls
        urls_only_set = set(need_urls)  # 标记哪些只需要抓链接
        log(f"需要抓取 count: {len(need_count)} / {total}")
        if need_urls:
            log(f"需要补抓链接: {len(need_urls)} / {total}")

    if args.test:
        to_process = to_process[:10]
        log(f"测试模式：仅前 {len(to_process)} 个")

    # 加载进度 (断点续传)
    progress_path = output_path + '.progress'
    processed_tags = set()
    if os.path.exists(progress_path):
        try:
            with open(progress_path, 'r', encoding='utf-8') as f:
                processed_tags = set(json.load(f))
            log(f"已有进度：{len(processed_tags)} 个已处理，将跳过")
        except:
            pass

    # 如果有 _updated 文件且有进度，加载它
    if os.path.exists(output_path) and len(processed_tags) > 0:
        log(f"从上次进度继续...")
        try:
            with open(output_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                artists = data.get('artists', artists)
        except:
            log("加载失败，用原始数据", "WARN")

    # 过滤掉已处理的
    actual_to_process = []
    for i in to_process:
        tag = artists[i].get('tag', '')
        if tag and tag not in processed_tags:
            actual_to_process.append(i)
        elif tag in processed_tags:
            _progress['skipped'] += 1

    if len(actual_to_process) == 0:
        log("没有需要更新的画师", "OK")
        return

    fetch_urls = not args.no_urls
    log(f"开始并发抓取 (线程={args.workers}, 速率限制={RATE_LIMIT}/s, 抓取链接={'否' if args.no_urls else '是'}, 代理={PROXY_URL or '未使用'})")
    log(f"输出: {os.path.basename(output_path)}")
    _flush_print("=" * 60)

    _progress['total'] = len(actual_to_process)
    _progress['done'] = 0
    _start_time = time.monotonic()

    results_lock = threading.Lock()
    result_list = []  # [(idx, count, matched_name, method), ...]
    save_counter = 0

    # ===== 并发执行 =====
    try:
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = {}
            for i in actual_to_process:
                is_urls_only = i in urls_only_set
                f = executor.submit(process_one, i, artists[i], result_list, results_lock, fetch_urls, is_urls_only)
                futures[f] = i

            for future in as_completed(futures):
                try:
                    future.result()  # 触发异常
                except Exception as e:
                    with results_lock:
                        _progress['error'] += 1
                        _progress['done'] += 1

                save_counter += 1

                # 定期保存
                if save_counter % args.save_interval == 0:
                    with results_lock:
                        # 应用已有结果
                        for idx, count, matched, method, social_urls in result_list:
                            artists[idx]['danbooruCount'] = count
                            if social_urls is not None:
                                artists[idx]['socialLinks'] = social_urls
                        applied = len(result_list)

                    # 更新已处理的 tag 集合
                    done_tags = processed_tags.copy()
                    for i in actual_to_process[:save_counter]:
                        tag = artists[i].get('tag', '')
                        if tag:
                            done_tags.add(tag)

                    data['artists'] = artists
                    with open(output_path, 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False)
                    with open(progress_path, 'w', encoding='utf-8') as f:
                        json.dump(list(done_tags), f)

    except KeyboardInterrupt:
        _flush_print("")  # 换行
        log("用户中断! 正在保存已有进度...", "WARN")

    # 应用所有结果
    for idx, count, matched, method, social_urls in result_list:
        artists[idx]['danbooruCount'] = count
        if social_urls is not None:
            artists[idx]['socialLinks'] = social_urls

    # 更新已处理的 tag
    for i in actual_to_process[:_progress['done']]:
        tag = artists[i].get('tag', '')
        if tag:
            processed_tags.add(tag)

    # 最终保存
    data['artists'] = artists
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)
    with open(progress_path, 'w', encoding='utf-8') as f:
        json.dump(list(processed_tags), f)

    elapsed = time.monotonic() - _start_time

    # 如果全部完成，删除进度文件
    if _progress['done'] >= _progress['total']:
        if os.path.exists(progress_path):
            os.remove(progress_path)

    _flush_print("")  # 换行
    _flush_print("=" * 60)

    d = _progress
    # 统计有多少画师获取到了社交链接
    urls_count = sum(1 for a in artists if a.get('socialLinks'))
    _flush_print(f"""
+----------------------------------------------+
|      Danbooru Fetch Results (v3)              |
+----------------------------------------------+
|  [+] Matched:    {d['found']:>6} artists              |
|  [-] Not found:  {d['not_found']:>6} artists              |
|  [X] Errors:     {d['error']:>6}                       |
|  [>] Skipped:    {d['skipped']:>6} (already done)        |
|  [L] With URLs:  {urls_count:>6} artists              |
+----------------------------------------------+
|  Speed:  {d['done']/elapsed if elapsed>0 else 0:>6.1f} tags/sec                    |
|  Time:   {elapsed:>6.1f} sec ({elapsed/60:.1f} min)            |
|  Output: {os.path.basename(output_path):<34}|
+----------------------------------------------+
""")

    if d['done'] < _progress['total']:
        log(f"未完成! 再次运行可从断点继续 ({d['done']}/{_progress['total']})", "WARN")
    else:
        log("全部完成!", "OK")


if __name__ == '__main__':
    main()
