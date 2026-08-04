#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
壹壹工作台 · 数据源抓取脚本（GitHub Pages + Actions 版）
- 指数：新浪（GBK，稳定真实）
- 新闻：新浪财经滚动（UTF-8，真实）→ 分类为 hot/macro/livelihood/finance
- 板块：从当日真实新闻提取热门行业热度
- 天气：Open-Meteo（免密钥，真实）
依赖：标准库即可（urllib）
"""
import json, urllib.request, urllib.error, urllib.parse, datetime, re, sys, os

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
        return [{"name":"上证综指","value":0,"pct":0},
                {"name":"深证成指","value":0,"pct":0},
                {"name":"创业板指","value":0,"pct":0}], True

# ---------- 2. 行业板块：从当日新闻提取热门行业热度 ----------
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
    return [{"name":"人工智能（软硬件）","pct":0,"_demo":True},
            {"name":"红利/高股息","pct":0,"_demo":True},
            {"name":"半导体","pct":0,"_demo":True}], True

# ---------- 3. 新闻分类（新浪滚动）----------
def _bucket(title):
    if any(k in title for k in ["美联储","央行","降息","加息","货币","汇率","通胀","地缘"]):
        return "macro"
    if any(k in title for k in ["A股","沪","深","财报","GDP","财政","证监会","交易所","IPO","股市","基金"]):
        return "finance"
    if any(k in title for k in ["民生","教育","医疗","就业","消费","房价","养老","社保","菜价"]):
        return "livelihood"
    return "hot"

def fetch_news():
    out = {"hot": [], "macro": [], "livelihood": [], "finance": []}
    raw = []
    try:
        txt = get("https://feed.mix.sina.com.cn/api/roll/get?pageid=153&lid=2516&num=30&r=0.1")
        obj = json.loads(txt)
        items = (obj.get("result") or {}).get("data") or []
        for it in items:
            t = it.get("title", "")
            if not t: continue
            c = it.get("intro") or it.get("summary") or it.get("wapsummary") or ""
            u = it.get("url") or it.get("wapurl") or ""
            src = it.get("media_name") or ""
            ctime = it.get("ctime") or 0
            raw.append(t + " " + c)
            b = _bucket(t)
            out[b].append([t, (c or t)[:120], u, src, ctime])
        for k in out: out[k] = out[k][:10]
        if any(out.values()):
            return out, False, raw
        raise ValueError("empty")
    except Exception as e:
        print("news fail:", e, file=sys.stderr)
        return {"hot":[["国常会","研究部署稳增长一揽子增量政策"]],
                "macro":[["美联储","维持利率不变，点阵图暗示年内或降息1次"]],
                "livelihood":[["多地","推出促消费举措，家电以旧换新扩围"]],
                "finance":[["证监会","强调保护中小投资者，严打违规"]]}, True, []

# ---------- 4. 每日天气（Open-Meteo，免密钥）----------
WMO = {0:"晴",1:"大致晴朗",2:"局部多云",3:"阴",45:"雾",48:"雾凇",
 51:"毛毛雨",53:"小雨",55:"中雨",56:"冻雨",57:"冻雨",61:"小雨",63:"中雨",65:"大雨",
 66:"冻雨",67:"冻雨",71:"小雪",73:"中雪",75:"大雪",77:"雪粒",80:"阵雨",81:"阵雨",82:"强阵雨",
 85:"阵雪",86:"强阵雪",95:"雷阵雨",96:"雷阵雨伴冰雹",99:"强雷暴冰雹"}
def wmo_text(c):
    try: return WMO.get(int(float(c)), "未知")
    except: return "未知"

def fetch_weather():
    city = (os.environ.get("WEATHER_CITY") or "深圳").strip()
    try:
        g = get("https://geocoding-api.open-meteo.com/v1/search?name=%s&count=1&language=zh" % urllib.parse.quote(city))
        res = json.loads(g).get("results") or [{}]
        lat = res[0].get("latitude"); lon = res[0].get("longitude")
        if lat is None or lon is None: raise ValueError("geo")
        furl = ("https://api.open-meteo.com/v1/forecast?latitude=%s&longitude=%s"
                "&current_weather=true&daily=weathercode,temperature_2m_max,temperature_2m_min"
                "&timezone=Asia%%2FShanghai&forecast_days=2") % (lat, lon)
        o = json.loads(get(furl))
        cw = o.get("current_weather", {})
        d = o.get("daily", {})
        def day(i):
            return {"tmax": (d.get("temperature_2m_max") or [None,None])[i],
                    "tmin": (d.get("temperature_2m_min") or [None,None])[i],
                    "code": (d.get("weathercode") or [None,None])[i],
                    "text": wmo_text((d.get("weathercode") or [None,None])[i])}
        return {"city": city,
                "updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                "today": {"temp": cw.get("temperature"), **day(0)},
                "tomorrow": day(1)}, False
    except Exception as e:
        print("weather fail:", e, file=sys.stderr)
        return {"city": city, "updated": "",
                "today": {"temp": None, "tmax": 30, "tmin": 20, "code": 0, "text": "晴"},
                "tomorrow": {"tmax": 30, "tmin": 20, "code": 0, "text": "晴"},
                "_demo": True}, True

def main():
    indices, di = fetch_indices()
    news, dn, raw = fetch_news()
    boards, db = fetch_boards(raw)
    weather, dw = fetch_weather()
    trade = is_trade_day()
    data = {
        "generatedAt": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "date": today_str(),
        "indices": indices, "_demo_indices": di,
        "news": news, "_demo_news": dn,
        "boards": boards, "_demo_boards": db,
        "weather": weather, "_demo_weather": dw,
        "review": {"isTrade": trade},
    }
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("data.json 已生成 | 指数demo=%s 新闻demo=%s 板块demo=%s 天气demo=%s 交易日=%s"
          % (di, dn, db, dw, trade))

if __name__ == "__main__":
    main()
