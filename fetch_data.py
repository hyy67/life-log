#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
私人生活台 · 数据源抓取脚本（GitHub Pages + Actions 版）
- 每日定时运行，产出 data.json 供前端读取
- 指数：新浪（GBK，稳定）
- 新闻：新浪财经滚动（UTF-8，真实）
- 板块：从当日真实新闻里提取「热门行业」热度（东方财富在数据中心IP常被拦，故改用此法）
- 英语：默认内置示例；若配置 ENGLISH_RSS 则自动抓取公众号 RSS 镜像
依赖：标准库即可（urllib）
"""
import json, urllib.request, urllib.error, datetime, re, sys, os

def strip_tags(s):
    return re.sub(r"<[^>]+>", "", s or "").replace("\s+", " ").strip()

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://finance.sina.com.cn",
}

def get(url, timeout=12, encoding="utf-8"):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode(encoding, "ignore")

def today_str():
    return datetime.date.today().strftime("%Y-%m-%d")

def is_trade_day(d=None):
    d = d or datetime.date.today()
    if d.weekday() >= 5:
        return False
    holidays = {"2026-01-01","2026-02-17","2026-02-18","2026-02-19","2026-02-20",
                "2026-04-05","2026-05-01","2026-06-19","2026-10-01","2026-10-02","2026-10-03"}
    return d.strftime("%Y-%m-%d") not in holidays

# ---------- 1. A股指数（新浪 GBK）----------
def fetch_indices():
    codes = {"sh000001":"上证综指","sz399001":"深证成指","sz399006":"创业板指"}
    try:
        url = "https://hq.sinajs.cn/list=" + ",".join(codes.keys())
        txt = get(url, encoding="gb18030")
        out = []
        for line in txt.split(";"):
            m = re.search(r'hq_str_(\w+)="([^"]*)"', line)
            if not m: continue
            code, payload = m.group(1), m.group(2)
            f = payload.split(",")
            if len(f) < 4: continue
            name, prev_close, current = f[0], float(f[2]), float(f[3])
            pct = round((current - prev_close) / prev_close * 100, 2)
            out.append({"name": name, "value": current, "pct": pct})
        return out, False
    except Exception as e:
        print("indices fail:", e, file=sys.stderr)
        return [
            {"name":"上证综指","value":0,"pct":0},
            {"name":"深证成指","value":0,"pct":0},
            {"name":"创业板指","value":0,"pct":0},
        ], True

# ---------- 2. 行业板块：从当日新闻提取热门行业 ----------
SECTORS = ["人工智能","半导体","芯片","集成电路","新能源","光伏","储能","锂电","锂电池",
           "新能源车","汽车","医药","创新药","消费","白酒","食品饮料","银行","地产",
           "房地产","券商","保险","红利","高股息","军工","机器人","算力","数字经济",
           "数据中心","钢铁","煤炭","有色","黄金","化工","农业"]

def fetch_boards(news_raw):
    cnt = {}
    for text in news_raw:
        for s in SECTORS:
            if s in text:
                cnt[s] = cnt.get(s, 0) + 1
    top = sorted(cnt.items(), key=lambda x: -x[1])[:8]
    if top:
        return [{"name": s, "pct": c, "_demo": False} for s, c in top], False
    # 兜底：无新闻时给一个静态关注方向
    return [
        {"name":"人工智能（软硬件）","pct":0,"_demo":True},
        {"name":"红利/高股息","pct":0,"_demo":True},
        {"name":"半导体","pct":0,"_demo":True},
    ], True

# ---------- 3. 股市精简新闻（新浪滚动）----------
def _classify(title):
    if any(k in title for k in ["美联储","央行","降息","加息","货币","汇率","通胀"]):
        return "央行动态"
    if any(k in title for k in ["A股","沪","深","财报","GDP","财政","经济","证监会","交易所","IPO"]):
        return "国内财经"
    return "全球宏观"

def fetch_news():
    key = os.environ.get("NEWS_API_KEY")
    api = (os.environ.get("NEWS_API") or "sina").lower()
    out = {"全球宏观": [], "央行动态": [], "国内财经": []}
    raw = []
    try:
        if key and api == "juhe":
            txt = get("https://v.juhe.cn/toutiao/index?key=%s&type=caijing" % key)
            obj = json.loads(txt)
            lst = (obj.get("result") or {}).get("data") or []
            if lst:
                for x in lst:
                    t = x.get("title", "")
                    c = strip_tags(x.get("content") or x.get("title") or "")
                    raw.append(t + " " + c)
                    out.setdefault(_classify(t), []).append([t[:40], c[:60] or t[:60]])
                _trim(out)
                return out, False, raw
        if key and api == "tianapi":
            txt = get("https://api.tianapi.com/caijing/?key=%s" % key)
            obj = json.loads(txt)
            lst = obj.get("newslist") or []
            if lst:
                for x in lst:
                    t = x.get("title", "")
                    c = strip_tags(x.get("description") or x.get("title") or "")
                    raw.append(t + " " + c)
                    out.setdefault(_classify(t), []).append([t[:40], c[:60] or t[:60]])
                _trim(out)
                return out, False, raw
        # 默认：新浪财经滚动（真实、稳定、UTF-8）
        txt = get("https://feed.mix.sina.com.cn/api/roll/get?pageid=153&lid=2516&num=30&r=0.1")
        obj = json.loads(txt)
        items = (obj.get("result") or {}).get("data") or []
        for it in items:
            t = it.get("title", "")
            if not t:
                continue
            c = it.get("intro") or it.get("summary") or it.get("wapsummary") or ""
            raw.append(t + " " + c)
            out.setdefault(_classify(t), []).append([t[:40], (c or t)[:60]])
        _trim(out)
        if any(out.values()):
            return out, False, raw
        raise ValueError("empty")
    except Exception as e:
        print("news fail:", e, file=sys.stderr)
        return {
            "全球宏观":[["美联储","维持利率不变，点阵图暗示年内或降息1次","_demo"]],
            "央行动态":[["人民银行","开展逆回购呵护流动性，LPR持平","_demo"]],
            "国内财经":[["财政","专项债发行提速，基建链资金面改善","_demo"]],
        }, True, []

def _trim(out, n=8):
    for k in out:
        out[k] = out[k][:n]

# ---------- 4. 英语「每日背三句」----------
def fetch_english():
    feed = os.environ.get("ENGLISH_RSS")
    if feed:
        try:
            xml = get(feed)
            items = re.findall(r"<item[\s\S]*?</item>", xml, re.I)
            arr = []
            for it in items[:3]:
                t = re.search(r"<title>([\s\S]*?)</title>", it, re.I)
                l = re.search(r"<link>([\s\S]*?)</link>", it, re.I)
                d = re.search(r"<description>([\s\S]*?)</description>", it, re.I)
                title = strip_tags(t.group(1) if t else "")
                link = (l.group(1) if l else feed).strip()
                desc = strip_tags(d.group(1) if d else "")[:80]
                arr.append({"en": title or "(无标题)", "cn": desc or title, "link": link})
            if arr:
                return arr, False
        except Exception as e:
            print("english rss fail:", e, file=sys.stderr)
    return [
        {"en":"I really appreciate you taking the time to help me with this.",
         "cn":"非常感谢你抽时间帮我这件事。",
         "link":"https://weixin.qq.com/"},
        {"en":"Let's touch base sometime next week to align on the plan.",
         "cn":"我们下周找个时间对齐下方案。",
         "link":"https://weixin.qq.com/"},
        {"en":"Could you walk me through how this process works?",
         "cn":"你能带我过一遍这个流程是怎么运作的吗？",
         "link":"https://weixin.qq.com/"},
    ], True

def main():
    indices, di = fetch_indices()
    news, dn, raw = fetch_news()
    boards, db = fetch_boards(raw)
    english, de = fetch_english()
    trade = is_trade_day()
    review = None
    if trade:
        review = {
            "isTrade": True,
            "indices": indices,
            "boards": boards,
            "potential": [
                {"name":"人工智能（软硬件）","opp":"产业趋势确定","risk":"估值波动大、业绩兑现节奏"},
                {"name":"红利/高股息","opp":"低利率环境稀缺收益","risk":"风格切换时弹性不足"},
            ],
        }
    else:
        review = {"isTrade": False}
    data = {
        "generatedAt": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "date": today_str(),
        "indices": indices, "_demo_indices": di,
        "news": news, "_demo_news": dn,
        "english": english, "_demo_english": de,
        "review": review,
        "_demo_boards": db,
    }
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("data.json 已生成 | 指数demo=%s 板块demo=%s 新闻demo=%s 英语demo=%s 交易日=%s"
          % (di, db, dn, de, trade))

if __name__ == "__main__":
    main()
