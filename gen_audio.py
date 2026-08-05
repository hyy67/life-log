#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
为「音频速览」等内容预生成中文 MP3（edge-tts / 微软神经网络语音）。
生成的文件放在 ./audio/ 下，由 index.html 通过 <audio> 播放，
不依赖运行时 TTS，华为/鸿蒙等自带浏览器也能稳定出声。

用法:
  python3 gen_audio.py            # 生成全部
  python3 gen_audio.py --only ai  # 仅音频速览
在 GitHub Actions 的每日刷新流程里也可调用本脚本。
"""
import os, sys, asyncio, argparse
import edge_tts

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audio")
VOICE = "zh-CN-XiaoxiaoNeural"   # 晓晓神经语音，自然中文女声
RATE = "+0%"                     # 语速
VOL = "+0%"

# 音频速览条目：与 index.html 中 AI_AUDIO 的 text 保持一致（按顺序）
AI_AUDIO_TEXTS = [
    ("ai_audio_0", "用 AI 做采购比价，先让模型拆出单价结构：原料、加工、物流、税，再抓三家报价做加权均价，最后生成谈判话术，每周三到五小时稳步推进。"),
    ("ai_audio_1", "今天关注 GitHub Copilot、Claude、OpenAI 的更新，把它们迁移到采购的比价分析、供应商评估与成本拆解环节，让信息真正用在工作里。"),
    ("ai_audio_2", "大模型本质是在预测下一个词，区别在参数规模、训练数据和对齐方式。理解这点，选型时就不会被营销话术带偏。"),
]

async def gen_one(fname, text):
    path = os.path.join(OUT, fname + ".mp3")
    if os.path.exists(path) and os.path.getsize(path) > 1000:
        print(f"  skip (exists) {fname}.mp3")
        return
    comm = edge_tts.Communicate(text=text, voice=VOICE, rate=RATE, volume=VOL)
    await comm.save(path)
    print(f"  ok   {fname}.mp3  ({os.path.getsize(path)} bytes)")

async def main(only):
    os.makedirs(OUT, exist_ok=True)
    if only in (None, "ai"):
        print("生成 音频速览 MP3:")
        for fid, txt in AI_AUDIO_TEXTS:
            await gen_one(fid, txt)
    print("完成。")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None, help="ai")
    args = ap.parse_args()
    asyncio.run(main(args.only))
