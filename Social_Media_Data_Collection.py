# social_media_data_collection.py
import sys
import time
import re
import csv
import statistics
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from collections import defaultdict
import math

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# ------------ CONFIG ------------
USE_MOBILE_LAYOUT = False         # Desktop is more reliable for counts
POSTS_TO_FETCH = 25               # last N posts to analyze
USERNAMES = [
    "all.american.eng",


    # add more handles here (no @)
]
MIN_HASHTAG_OCCURRENCES = 2       # for hashtag efficiency stats
# ---------------------------------

# ---------- Utilities / parsing ----------
def convert_count(text: str) -> int:
    t = (text or "").strip().upper().replace(",", "")
    try:
        if t.endswith("K"): return int(float(t[:-1]) * 1_000)
        if t.endswith("M"): return int(float(t[:-1]) * 1_000_000)
        return int(t)
    except Exception:
        return 0

def extract_hashtags(text: str) -> List[str]:
    return re.findall(r"#\w+", text or "")

def parse_iso_or_text_date(dt: str) -> Optional[datetime]:
    if not dt: return None
    dt = dt.strip()
    try:
        if dt.endswith("Z"): dt = dt[:-1] + "+00:00"
        return datetime.fromisoformat(dt)
    except Exception:
        pass
    m = re.search(r"(\d{4}-\d{2}-\d{2})", dt)
    if m:
        try:
            return datetime.fromisoformat(m.group(1))
        except Exception:
            return None
    return None

def guess_theme(hashtags: List[str], caption: str) -> str:
    blob = (" ".join(hashtags) + " " + (caption or "")).lower()
    themes = [
        ("grammar",         ["grammar", "grammartips", "pasttense", "presentperfect", "articles", "tenses"]),
        ("vocabulary",      ["vocabulary", "vocab", "wordoftheday", "phrases", "idioms", "phrasalverbs"]),
        ("pronunciation",   ["pronunciation", "accent", "phonetics", "ipa", "sounds"]),
        ("exam/test prep",  ["ielts", "toefl", "toeic", "cambridge", "pte"]),
        ("slang/culture",   ["slang", "culture", "britishvsamerican", "usvsuk"]),
        ("business english",["businessenglish", "interview", "resume", "cv", "email"]),
        ("study tips",      ["study", "tips", "learnenglish", "englishlearning"]),
    ]
    for label, kws in themes:
        if any(kw in blob for kw in kws):
            return label
    return "general english"

def guess_country_from_bio(bio: str) -> str:
    if not bio: return "Unknown"
    bio_low = bio.lower()
    mapping = {
        "United States": ["usa", "us", "america", "american"],
        "United Kingdom": ["uk", "united kingdom", "british", "england"],
        "Canada": ["canada", "canadian"],
        "Australia": ["australia", "aussie", "australian"],
        "India": ["india", "indian"],
        "Poland": ["poland", "polish"],
        "France": ["france", "french"],
        "Germany": ["germany", "german"],
        "Spain": ["spain", "spanish"],
        "Italy": ["italy", "italian"],
        "Brazil": ["brazil", "brazilian"],
        "Mexico": ["mexico", "mexican"],
        "China": ["china", "chinese"],
        "Japan": ["japan", "japanese"],
        "Korea": ["korea", "korean"],
        "Turkey": ["turkey", "turkish"],
    }
    for country, kws in mapping.items():
        if any(kw in bio_low for kw in kws):
            return country
    return "Unknown"

def posts_per_week(timestamps: List[datetime]) -> Optional[float]:
    ts = [t for t in timestamps if isinstance(t, datetime)]
    if len(ts) < 2: return None
    ts.sort()
    days = (ts[-1] - ts[0]).days or 1
    return len(ts) / (days / 7.0) if days > 0 else None

def pearson_r(xs: List[float], ys: List[float]) -> Optional[float]:
    if len(xs) != len(ys) or len(xs) < 2: return None
    mean_x = sum(xs) / len(xs); mean_y = sum(ys) / len(ys)
    num = sum((x-mean_x)*(y-mean_y) for x, y in zip(xs, ys))
    den_x = math.sqrt(sum((x-mean_x)**2 for x in xs))
    den_y = math.sqrt(sum((y-mean_y)**2 for y in ys))
    if den_x == 0 or den_y == 0: return None
    return num / (den_x * den_y)

# ---------- WebDriver ----------
def get_driver(use_mobile=False, headless=False) -> webdriver.Chrome:
    opts = Options()
    if headless: opts.add_argument("--headless=new")
    opts.add_argument("--disable-gpu"); opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--lang=en-US")

    if use_mobile:
        opts.add_argument(
            "--user-agent=Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
        )
        opts.add_argument("--window-size=390,844")
    else:
        opts.add_argument(
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        )
        opts.add_argument("--window-size=1280,1800")

    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=opts)

def accept_cookies(driver, timeout=10):
    try:
        wait = WebDriverWait(driver, timeout)
        btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Accept')]")))
        btn.click(); time.sleep(0.8)
    except Exception:
        pass

# ---------- Scraping ----------
def get_profile_identity(driver, username: str):
    """
    Return (display_name, bio_text, followers, following).
    """
    url = f"https://www.tiktok.com/@{username}?lang=en"
    driver.get(url)
    accept_cookies(driver)
    time.sleep(1.2)
    wait = WebDriverWait(driver, 10)

    def metric(sel: str) -> int:
        try:
            el = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, sel)))
            return convert_count(el.text)
        except Exception:
            return 0

    followers = metric("strong[data-e2e='followers-count']")
    following = metric("strong[data-e2e='following-count']")

    # display name (best-effort)
    display_name = username
    for sel in ("h1[data-e2e='user-title']", "[data-e2e='user-title']", "h1"):
        try:
            el = driver.find_element(By.CSS_SELECTOR, sel)
            if el.text.strip():
                display_name = el.text.strip()
                break
        except Exception:
            continue

    # bio (best-effort)
    bio_text = ""
    for sel in ("[data-e2e='user-bio']", "[data-e2e='profile-bio']", "h2+div"):
        try:
            el = driver.find_element(By.CSS_SELECTOR, sel)
            if el.text.strip():
                bio_text = el.text.strip()
                break
        except Exception:
            continue

    return display_name, bio_text, followers, following

def collect_recent_post_urls(driver, username: str, limit: int) -> List[str]:
    url = f"https://www.tiktok.com/@{username}?lang=en"
    driver.get(url)
    accept_cookies(driver)
    time.sleep(1.0)

    urls: List[str] = []
    last_h = 0; stuck = 0
    while len(urls) < limit and stuck < 4:
        anchors = driver.find_elements(By.CSS_SELECTOR, "a[href*='/video/']")
        for a in anchors:
            href = a.get_attribute("href")
            if href and "/video/" in href and href not in urls:
                urls.append(href)
                if len(urls) >= limit: break
        driver.execute_script("window.scrollBy(0, 1200);")
        time.sleep(0.9)
        new_h = driver.execute_script("return document.body.scrollHeight")
        stuck = stuck + 1 if new_h == last_h else 0
        last_h = new_h
    return urls[:limit]

def scrape_post(driver, post_url: str) -> Dict:
    """
    JSON-first scrape; fallback to DOM.
    """
    driver.get(post_url)
    accept_cookies(driver)
    wait = WebDriverWait(driver, 10)
    time.sleep(0.6)
    try:
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    except Exception:
        pass

    html = driver.page_source

    def rx(pattern, flags=0, cast=int, default=None):
        m = re.search(pattern, html, flags)
        if not m: return default
        try: return cast(m.group(1))
        except Exception: return default

    views    = rx(r'"playCount"\s*:\s*(\d+)', cast=int, default=None)
    likes    = rx(r'"diggCount"\s*:\s*(\d+)', cast=int, default=None)
    comments = rx(r'"commentCount"\s*:\s*(\d+)', cast=int, default=None)
    shares   = rx(r'"shareCount"\s*:\s*(\d+)', cast=int, default=None)
    saves    = rx(r'"collectCount"\s*:\s*(\d+)', cast=int, default=0)

    caption  = rx(r'"desc"\s*:\s*"([^"]*)"', flags=re.DOTALL, cast=str, default="") or ""
    caption  = bytes(caption, "utf-8").decode("unicode_escape") if caption else caption
    create_ts = rx(r'"createTime"\s*:\s*"(\d+)"', cast=int, default=None)
    ts = datetime.fromtimestamp(create_ts) if create_ts else None

    def first_text(selectors) -> str:
        for by, sel in selectors:
            try:
                el = driver.find_element(by, sel)
                txt = el.text.strip()
                if txt: return txt
            except Exception:
                continue
        return ""

    if views is None:
        views_txt = first_text([
            (By.CSS_SELECTOR, "[data-e2e='play-count']"),
            (By.XPATH, "//*[contains(@data-e2e,'play-count') or contains(., ' views') or contains(., 'Views')]"),
        ])
        views = convert_count(views_txt) if views_txt else 0

    if likes is None:
        likes_txt = first_text([
            (By.CSS_SELECTOR, "[data-e2e='like-count']"),
            (By.XPATH, "//strong[contains(text(),'K') or contains(text(),'M') or contains(text(),'0')]"),
        ])
        likes = convert_count(likes_txt) if likes_txt else 0

    if comments is None:
        comments_txt = first_text([
            (By.CSS_SELECTOR, "[data-e2e='comment-count']"),
            (By.XPATH, "//*[contains(@aria-label,'comment') or contains(., 'Comment')]/following::strong[1]"),
        ])
        comments = convert_count(comments_txt) if comments_txt else 0

    if shares is None:
        shares_txt = first_text([
            (By.CSS_SELECTOR, "[data-e2e='share-count']"),
            (By.XPATH, "//*[contains(@aria-label,'share') or contains(., 'Share')]/following::strong[1]"),
        ])
        shares = convert_count(shares_txt) if shares_txt else 0

    if not caption:
        caption = first_text([
            (By.CSS_SELECTOR, "[data-e2e='browse-video-desc'], [data-e2e='video-desc']"),
            (By.XPATH, "//div[contains(@data-e2e,'video-desc')]"),
        ]) or ""

    if ts is None:
        try:
            t_el = driver.find_element(By.CSS_SELECTOR, "time")
            dt_attr = t_el.get_attribute("datetime") or t_el.get_attribute("title") or t_el.text
            from_iso = parse_iso_or_text_date(dt_attr)
            if from_iso: ts = from_iso
        except Exception:
            from_src = parse_iso_or_text_date(html[:4000])
            if from_src: ts = from_src

    hashtags = extract_hashtags(caption)
    theme = guess_theme(hashtags, caption)
    caption_len = len(caption or "")

    er_view = None
    if views and views > 0:
        er_view = (likes + comments + shares + (saves or 0)) / views

    return {
        "url": post_url,
        "views": views or 0,
        "likes": likes or 0,
        "comments": comments or 0,
        "shares": shares or 0,
        "saves": saves or 0,
        "er_view": er_view,
        "caption": caption,
        "caption_len": caption_len,
        "hashtags": hashtags,
        "timestamp": ts,
        "theme": theme,
    }

# ---------- Analysis helpers ----------
def summarize_er(posts: List[Dict]) -> Tuple[float, float]:
    ers = [p["er_view"] for p in posts if p.get("er_view") is not None]
    if not ers: return (0.0, 0.0)
    return (statistics.mean(ers), statistics.median(ers))

def hashtag_efficiency(posts: List[Dict], min_occurrences=2):
    ers = [p["er_view"] for p in posts if p.get("er_view") is not None]
    overall = statistics.mean(ers) if ers else 0.0
    bucket = defaultdict(list)
    for p in posts:
        if p.get("er_view") is None: continue
        for h in set(p.get("hashtags", [])):
            bucket[h.lower()].append(p["er_view"])
    rows = []
    for h, vals in bucket.items():
        if len(vals) >= min_occurrences:
            avg = statistics.mean(vals); lift = avg - overall
            rows.append((h, len(vals), avg, lift))
    rows.sort(key=lambda x: x[3], reverse=True)
    return overall, rows

def posting_window_performance(posts: List[Dict]):
    hour_bucket = defaultdict(list); weekday_bucket = defaultdict(list)
    for p in posts:
        if p.get("er_view") is None or not isinstance(p.get("timestamp"), datetime):
            continue
        ts = p["timestamp"]
        hour_bucket[ts.hour].append(p["er_view"])
        weekday_bucket[ts.weekday()].append(p["er_view"])  # 0=Mon
    def top_avg(bucket, topn=3):
        avgs = []
        for k, vals in bucket.items():
            if len(vals) >= 2:
                avgs.append((k, statistics.mean(vals), len(vals)))
        avgs.sort(key=lambda x: x[1], reverse=True)
        return avgs[:topn]
    return top_avg(hour_bucket), top_avg(weekday_bucket)

def caption_length_vs_er(posts: List[Dict]):
    pts = [(p["caption_len"], p["er_view"]) for p in posts if p.get("er_view") is not None]
    if not pts: return None, {}
    xs, ys = zip(*pts)
    r = pearson_r(list(xs), list(ys))
    bins = [(0,20), (21,40), (41,60), (61,80), (81,120), (121,9999)]
    labels = ["0-20", "21-40", "41-60", "61-80", "81-120", "121+"]
    bucket = {label: [] for label in labels}
    for length, er in pts:
        for (lo, hi), lab in zip(bins, labels):
            if lo <= length <= hi:
                bucket[lab].append(er); break
    bucket_avg = {lab: (statistics.mean(v) if v else 0.0, len(v)) for lab, v in bucket.items()}
    return r, bucket_avg

def content_category_lift(posts: List[Dict]):
    ers = [p["er_view"] for p in posts if p.get("er_view") is not None]
    overall = statistics.mean(ers) if ers else 0.0
    cat_bucket = defaultdict(list)
    for p in posts:
        if p.get("er_view") is None: continue
        cat_bucket[p.get("theme","general english")].append(p["er_view"])
    rows = []
    for cat, vals in cat_bucket.items():
        if len(vals) >= 2:
            avg = statistics.mean(vals); lift = avg - overall
            rows.append((cat, len(vals), avg, lift))
    rows.sort(key=lambda x: x[3], reverse=True)
    return overall, rows

# ---------- CSV writer ----------
CSV_COLUMNS = [
    "tiktok_profile_name",
    "username",
    "posts_analyzed",
    "avg_likes",
    "avg_comments",
    "engagement_rate_view_adj_mean",
    "post_frequency_per_week",
    "content_type",
    "content_theme",
    "avg_shares",
    "avg_saves",
    "hashtags_used",
    "country_region",
    "hashtag_efficiency_top",
    "posting_window_performance",
    "caption_length_vs_er",
    "content_category_lift_top",
]

def write_profile_summary_csv(username: str, row: Dict):
    fname = f"{username}_summary.csv"
    with open(fname, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        w.writeheader()
        w.writerow(row)
    print(f"Saved: {fname}")

# ---------- Orchestration / output ----------
def main():
    print("Python interpreter:", sys.executable)
    driver = get_driver(use_mobile=USE_MOBILE_LAYOUT, headless=False)

    try:
        for username in USERNAMES:
            print(f"\n===== @{username} =====")
            display_name, bio, followers, following = get_profile_identity(driver, username)
            post_urls = collect_recent_post_urls(driver, username, POSTS_TO_FETCH)
            if not post_urls:
                print("No recent posts found (profile private or grid blocked).")
                continue

            posts = []
            for i, url in enumerate(post_urls, 1):
                print(f"  Scraping post {i}/{len(post_urls)} …")
                try:
                    posts.append(scrape_post(driver, url))
                except Exception as e:
                    print(f"   (skipped due to error: {e})")
                    continue

            # Aggregates
            likes_list    = [p["likes"]    for p in posts]
            comments_list = [p["comments"] for p in posts]
            shares_list   = [p["shares"]   for p in posts]
            saves_list    = [p["saves"]    for p in posts if p.get("saves") is not None]
            timestamps    = [p["timestamp"] for p in posts if p["timestamp"]]

            avg_likes    = statistics.mean(likes_list) if likes_list else 0.0
            avg_comments = statistics.mean(comments_list) if comments_list else 0.0
            avg_shares   = statistics.mean(shares_list) if shares_list else 0.0
            avg_saves    = statistics.mean(saves_list) if saves_list else 0.0

            # ER view-adjusted
            er_vals = [p["er_view"] for p in posts if p.get("er_view") is not None]
            er_mean = statistics.mean(er_vals) if er_vals else 0.0
            er_median = statistics.median(er_vals) if er_vals else 0.0  # not in CSV, but printed

            # Post frequency
            freq = posts_per_week(timestamps)
            post_freq = round(freq, 4) if freq else None

            # Theme majority
            themes = [p["theme"] for p in posts]
            try:
                content_theme = statistics.mode(themes) if themes else "general english"
            except statistics.StatisticsError:
                content_theme = "general english"

            # Country/Region
            country = guess_country_from_bio(bio)

            # Hashtags used (unique)
            all_tags = []
            for p in posts: all_tags.extend(p["hashtags"])
            unique_tags = sorted(set(all_tags))
            hashtags_used_str = ";".join(unique_tags)

            # Hashtag efficiency (top 5)
            overall_er, tag_rows = hashtag_efficiency(posts, MIN_HASHTAG_OCCURRENCES)
            top_tags = [f"{tag}:{lift:+.4f}(n={n})" for tag, n, avg, lift in tag_rows[:5]]
            tag_eff_str = ";".join(top_tags) if top_tags else ""

            # Posting window performance (top 3 hours & weekdays)
            hour_tops, weekday_tops = posting_window_performance(posts)
            hours_str = ",".join([f"h{h}@{avg:.4f}(n={n})" for h, avg, n in hour_tops]) if hour_tops else ""
            wd_map = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
            wdays_str = ",".join([f"{wd_map[d]}@{avg:.4f}(n={n})" for d, avg, n in weekday_tops]) if weekday_tops else ""
            posting_perf_str = f"hours[{hours_str}]|weekdays[{wdays_str}]"

            # Caption length vs ER (Pearson r + buckets)
            r, buckets = caption_length_vs_er(posts)
            if r is not None:
                bucket_parts = [f"{lab}:{avg:.4f}(n={n})" for lab, (avg, n) in buckets.items()]
                caption_vs_er_str = f"r={r:.3f}; " + ";".join(bucket_parts)
            else:
                caption_vs_er_str = "r=N/A"

            # Content category lift (top 5)
            overall_cat, cat_rows = content_category_lift(posts)
            top_cats = [f"{cat}:{lift:+.4f}(n={n})" for cat, n, avg, lift in cat_rows[:5]]
            cat_lift_str = ";".join(top_cats) if top_cats else ""

            # Console summary (optional)
            print(f"Followers:              {followers:,}")
            print(f"Following:              {following:,}")
            print(f"Analyzed posts:         {len(posts)}")
            print(f"Avg Likes:              {avg_likes:,.2f}")
            print(f"Avg Comments:           {avg_comments:,.2f}")
            print(f"View-adjusted ER:       mean={er_mean:.4f}, median={er_median:.4f}")
            print(f"Post frequency:         {post_freq if post_freq is not None else 'Unknown'} posts/week")
            print(f"Content type:           Video (TikTok)")
            print(f"Content theme:          {content_theme}")
            print(f"Avg shares / saves:     {avg_shares:.2f} / {avg_saves:.2f}")
            print(f"Country/Region:         {country}")

            # Build CSV row (order matters!)
            row = {
                "tiktok_profile_name": display_name,
                "username": username,
                "posts_analyzed": len(posts),
                "avg_likes": round(avg_likes, 4),
                "avg_comments": round(avg_comments, 4),
                "engagement_rate_view_adj_mean": round(er_mean, 6),
                "post_frequency_per_week": round(post_freq, 4) if post_freq is not None else "",
                "content_type": "Video (TikTok)",
                "content_theme": content_theme,
                "avg_shares": round(avg_shares, 4),
                "avg_saves": round(avg_saves, 4),
                "hashtags_used": hashtags_used_str,
                "country_region": country,
                "hashtag_efficiency_top": tag_eff_str,
                "posting_window_performance": posting_perf_str,
                "caption_length_vs_er": caption_vs_er_str,
                "content_category_lift_top": cat_lift_str,
            }

            write_profile_summary_csv(username, row)

            # Per-post snapshot (kept for visibility)
            print("\nPer-post snapshot (views, likes, comments, shares, ER, date, caption…):")
            for i, p in enumerate(posts, 1):
                ts = p["timestamp"].strftime("%Y-%m-%d") if isinstance(p["timestamp"], datetime) else "?"
                cap = (p["caption"] or "").replace("\n", " ")
                if len(cap) > 60: cap = cap[:57] + "..."
                er = p["er_view"]; er_str = f"{er:.4f}" if er is not None else "NA"
                print(f" {i:02d}. ▶ {p['views']:>7} | ♥ {p['likes']:>6} | 💬 {p['comments']:>5} | ↗ {p['shares']:>5} | ER {er_str:>6} | {ts} | {cap}")

    finally:
        driver.quit()

if __name__ == "__main__":
    main()
