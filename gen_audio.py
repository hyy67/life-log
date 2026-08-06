#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
为「音频速览」预生成中文 MP3（edge-tts / 微软神经网络语音）。
生成的文件放在 ./audio/ 下，由 index.html 通过 <audio> 播放，
不依赖运行时 TTS，华为/鸿蒙等自带浏览器也能稳定出声。

口播稿来源：优先读取 data.json 的 ai_audio（每日由 fetch_data.py 生成，
随科技新闻每日更新）；若 data.json 缺失则退回内置静态稿。

用法:
  python3 gen_audio.py            # 依据 data.json 生成全部音频速览 MP3
在 GitHub Actions 的每日刷新流程里也会调用本脚本（fetch_data.py 之后）。
"""
import os, sys, asyncio, argparse, json
import edge_tts

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audio")
VOICE = "zh-CN-XiaoxiaoNeural"   # 晓晓神经语音，自然中文女声
RATE = "+0%"                     # 语速
VOL = "+0%"                      # 音量

# 内置静态兜底口播稿（data.json 缺失时使用，顺序对应 ai_audio_0..2）
FALLBACK_TEXTS = [
    "用 AI 做采购比价，先让模型拆出单价结构：原料、加工、物流、税，再抓三家报价做加权均价，最后生成谈判话术，每周三到五小时稳步推进。",
    "今天关注 GitHub Copilot、Claude、OpenAI 的更新，把它们迁移到采购的比价分析、供应商评估与成本拆解环节，让信息真正用在工作里。",
    "大模型本质是在预测下一个词，区别在参数规模、训练数据和对齐方式。理解这点，选型时就不会被营销话术带偏。",
]

def load_ai_audio_texts():
    """返回 [(文件名, 文本), ...]，顺序对应 ai_audio_0.mp3 ..."""
    dj = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.json")
    try:
        with open(dj, encoding="utf-8") as f:
            data = json.load(f)
        items = data.get("ai_audio") or []
        texts = [(f"ai_audio_{i}", it.get("text", "")) for i, it in enumerate(items) if it.get("text")]
        if texts:
            return texts
    except Exception as e:
        print("  读取 data.json 失败，使用内置静态稿:", e, file=sys.stderr)
    return [(f"ai_audio_{i}", t) for i, t in enumerate(FALLBACK_TEXTS)]

async def gen_one(fname, text):
    path = os.path.join(OUT, fname + ".mp3")
    comm = edge_tts.Communicate(text=text, voice=VOICE, rate=RATE, volume=VOL)
    await comm.save(path)
    print(f"  ok   {fname}.mp3  ({os.path.getsize(path)} bytes)")

async def main(only):
    os.makedirs(OUT, exist_ok=True)
    if only in (None, "ai"):
        print("生成 音频速览 MP3:")
        for fid, txt in load_ai_audio_texts():
            await gen_one(fid, txt)
    print("完成。")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None, help="ai")
    args = ap.parse_args()
    asyncio.run(main(args.only))
