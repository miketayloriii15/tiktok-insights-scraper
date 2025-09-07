# TikTok Insights Scraper

This repository contains a Python script that scrapes recent TikTok videos for one or more usernames using **Selenium**. It collects engagement data and exports a **one-row CSV summary per account** with metrics such as:

- Average likes, comments, shares, and saves  
- View-adjusted engagement rate (ER)  
- Posting frequency (posts per week)  
- Hashtag efficiency (top-performing hashtags)  
- Best posting windows (by hour and weekday)  
- Caption length vs. engagement correlation  
- Content category lift (based on hashtag/caption themes)  
- Country/region guess (based on profile bio text)  

---

## Features
- Fetches the last **N posts** per username (default = 25)  
- Uses Selenium + ChromeDriver for scraping TikTok’s frontend  
- Exports results to `<username>_summary.csv`  
- Prints per-post snapshot (views, likes, comments, shares, ER, caption preview)  
- Compatible with TikTok schema fields (e.g., `tiktok_profile_name`, `username`)  

---

## Installation

### 1. Clone the repository
```bash
git clone https://github.com/your-username/tiktok-insights-scraper.git
cd tiktok-insights-scraper
2. Install Python dependencies
It’s recommended to use Python 3.9+.

bash
Copy code
python -m pip install --upgrade pip
pip install selenium webdriver-manager
Usage
Edit the USERNAMES list in social_media_data_collection.py to include the TikTok handles you want to analyze (without the @ symbol).

Example:

python
Copy code
USERNAMES = [
    "all.american.eng",
    "englishwiththisguy",
    "eslkate",
]
Run the script:

bash
Copy code
python social_media_data_collection.py
This will:

Scrape up to 25 recent posts per username

Analyze engagement, hashtags, and posting patterns

Save a summary CSV file for each profile

Example Output
Console Summary:

yaml
Copy code
===== @all.american.eng =====
Followers:              123,456
Following:              1,234
Analyzed posts:         25
Avg Likes:              4,567.89
Avg Comments:           123.45
View-adjusted ER:       mean=0.0523, median=0.0487
Post frequency:         3.21 posts/week
Content type:           Video (TikTok)
Content theme:          vocabulary
Avg shares / saves:     67.89 / 45.67
Country/Region:         United States
CSV Columns:

tiktok_profile_name (TikTok display name)

username

posts_analyzed

avg_likes, avg_comments, avg_shares, avg_saves

engagement_rate_view_adj_mean

post_frequency_per_week

content_type, content_theme, country_region

hashtags_used

hashtag_efficiency_top

posting_window_performance

caption_length_vs_er

content_category_lift_top

Notes
TikTok’s frontend may update over time; CSS selectors may need adjusting.

Script uses Selenium with ChromeDriver managed automatically by webdriver-manager.

For large-scale use, consider respecting TikTok’s Terms of Service.

Runs in desktop mode by default (mobile layout scraping is supported but less stable).

License
This project is open source under the MIT License.

