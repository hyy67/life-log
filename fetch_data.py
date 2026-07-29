#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
私人生活台 · 数据源抓取脚本
- 定时运行（GitHub Actions 每日 / 沙箱循环），产出 data.json
- 前端(H5/小程序)只读取 data.json，不直接调外部 API
- 取不到的真实源会回退为「示例数据」并在字段标 _demo=true，前端可提示
依赖：标准库即可（urllib）
"""
import json, urllib.request, urllib.error, datetime, re, sys, os

def strip_tags(s):
    return re.sub(r"<[^>]+>", "", s or "").replace("\s+", " ").strip()

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://finance.sina.com.cn",
}

def get(url, timeout=12, binary=False, encoding="utf-8"):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read()
        return data if binary else data.decode(encoding, "ignore")

def today_str():
    return datetime.date.today().strftime("%Y-%m-%d")

def is_trade_day(d=None):
    d = d or datetime.date.today()
    if d.weekday() >= 5:          # 周六日非交易
        return False
    # 简易法定假日表（可按年补充；GitHub Actions 版可接 juhe 交易日接口）
    holidays = {"2026-01-01","2026-02-17","2026-02-18","2026-02-19","2026-02-20",
                "2026-04-05","2026-05-01","2026-06-19","2026-10-01","2026-10-02","2026-10-03"}
    return d.strftime("%Y-%m-%d") not in holidays

# ---------- 1. A股指数 ----------
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

# ---------- 2. 行业板块涨跌 ----------
def fetch_boards():
    try:
        url = ("https://push2.eastmoney.com/api/qt/clist/get?fs=m:90+t:2"
               "&fields=f12,f14,f3&pn=1&pz=8&_=1")
        txt = get(url)
        obj = json.loads(txt)
        items = obj.get("data", {}).get("diff", [])
        out = [{"name": it.get("f14"), "pct": it.get("f3")} for it in items if it.get("f14")]
        return out, False
    except Exception as e:
        print("boards fail:", e, file=sys.stderr)
        return [
            {"name":"半导体","pct":3.1,"_demo":True},
            {"name":"新能源车","pct":-1.4,"_demo":True},
            {"name":"红利低波","pct":0.8,"_demo":True},
        ], True

# ---------- 3. 股市精简新闻 ----------
def fetch_news():
    key = os.environ.get("NEWS_API_KEY")
    api = (os.environ.get("NEWS_API") or "eastmoney").lower()
    try:
        if key and api == "juhe":
            txt = get("https://v.juhe.cn/toutiao/index?key=%s&type=caijing" % key)
            obj = json.loads(txt)
            lst = (obj.get("result") or {}).get("data") or []
            if lst:
                return _categorize([[x.get("title",""), strip_tags(x.get("content") or x.get("title") or "")] for x in lst]), False
        if key and api == "tianapi":
            txt = get("https://api.tianapi.com/caijing/?key=%s" % key)
            obj = json.loads(txt)
            lst = obj.get("newslist") or []
            if lst:
                return _categorize([[x.get("title",""), strip_tags(x.get("description") or x.get("title") or "")] for x in lst]), False
        # 默认：东方财富快讯（免费、稳定）
        url = "https://newsapi.eastmoney.com/kuaixun/v1/getlist?type=1&page_size=15&_=1"
        txt = get(url)
        obj = json.loads(txt)
        raw = obj.get("data", {}).get("list", [])
        def pick(title):
            t = title
            if any(k in t for k in ["美联储","央行","降息","加息","货币"]): return "央行动态"
            if any(k in t for k in ["A股","沪","深","财报","GDP","财政","经济"]): return "国内财经"
            return "全球宏观"
        out = {}
        for it in raw:
            cat = pick(it.get("title",""))
            out.setdefault(cat, []).append([it.get("title","")[:40], it.get("content","").strip()[:60] or it.get("title","")[:60]])
        if out:
            return out, False
        raise ValueError("empty")
    except Exception as e:
        print("news fail:", e, file=sys.stderr)
        return {
            "全球宏观":[["美联储","维持利率不变，点阵图暗示年内或降息1次","_demo"]],
            "央行动态":[["人民银行","开展逆回购呵护流动性，LPR持平","_demo"]],
            "国内财经":[["财政","专项债发行提速，基建链资金面改善","_demo"]],
        }, True

def _categorize(lst):
    out = {}
    for t, c in lst:
        if any(k in t for k in ["美联储","央行","降息","加息","货币"]): cat = "央行动态"
        elif any(k in t for k in ["A股","沪","深","财报","GDP","财政","经济"]): cat = "国内财经"
        else: cat = "全球宏观"
        out.setdefault(cat, []).append([t[:40], (c or t)[:60]])
    return out

# ---------- 4. 英语「每日背三句」----------
def fetch_english():
    # 把 RSS 镜像(WeRSS/RSSHub) 或号主素材接口地址填到环境变量 ENGLISH_RSS 即可自动抓取
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
    # 回退为示例，前端跳转链接指向公众号搜索页
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
    boards, db = fetch_boards()
    news, dn = fetch_news()
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
