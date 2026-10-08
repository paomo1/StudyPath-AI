# -*- coding: utf-8 -*-
"""
StudyPath 学术驾驶舱（Gradio 界面）。

踩过的几个渲染坑：背景层用 z-index:0 再给 .gradio-container 加 position:relative;
z-index:1，给背景负 z-index 会被 body 白底盖掉；Gradio 4.x 下样式要命中 textarea 本体，
用 elem_id 锁（spQuery / spBtn）而不是依赖 wrapper class；大圆角卡片直接挂在 gr.Row 上
（.hero-row），不要用 gr.HTML 包 Gradio 组件。

界面不编造院校 / 排名 / 录取率数据。

运行：python rag/app_gradio.py，浏览器打开 http://127.0.0.1:7860
"""
import re
import gradio as gr
from agents import ask_multi


# CSS — 学术驾驶舱视觉
#
# 兼容性约束：
#  1. 背景装饰层（世界地图 / 学术网络）用 position:fixed + z-index:0 + pointer-events:none，
#     .gradio-container 自身 position:relative + z-index:1 覆盖背景，否则背景会被吞或挡交互
#  2. 不要用 *{margin:0;padding:0} 这类全局重置，会污染 Gradio 内部组件
#  3. 输入框样式用 elem_id 锁死（#spQuery textarea），不依赖 wrapper class
CABINET_CSS = r"""
:root{
  --bg:#eef2f9;
  --bg2:#e6ecf7;
  --ink:#1a2233;
  --ink2:#2b3445;
  --sub:#5b6678;
  --sub2:#8a93a3;
  --line:rgba(43,76,126,.12);
  --brand:#3b5bdb;
  --brand2:#4263eb;
  --violet:#7048e8;
  --cyan:#0ca678;
  --amber:#e8590c;
  --amber2:#f08c00;
  --glass:rgba(255,255,255,.60);
  --glass-strong:rgba(255,255,255,.82);
  --shadow:0 6px 28px rgba(43,76,126,.10);
  --shadow-lg:0 14px 44px rgba(43,76,126,.16);
  --shadow-sm:0 3px 14px rgba(43,76,126,.08);
  --r:14px;
}
/* 默认 body 底色 —— 防止 JS 未注入时的白闪 */
body{background:linear-gradient(160deg,#eef2f9 0%,#e6ecf7 48%,#ece9fb 100%);color:var(--ink);font-family:'Inter','PingFang SC','Microsoft YaHei',sans-serif}
/* 顶层容器：透明，让 body 渐变 + JS 注入的 #sp-bg 装饰层透出（不挡交互）。 */
.gradio-container{
  color:var(--ink);
  background:transparent !important;
  max-width:100% !important;
  padding-top:0 !important;
}

/* 背景装饰层：fixed 满屏，z-index:0 pointer-events:none —— 不挡交互 */
#sp-bg{position:fixed;inset:0;z-index:0;pointer-events:none;overflow:hidden}
#sp-bg #worldmap{position:absolute;inset:0;opacity:1;pointer-events:none}
#sp-bg #worldmap svg{width:100%;height:100%;display:block}
#sp-bg #network{position:absolute;inset:0;opacity:.45;pointer-events:none}

/* 顶部品牌条（fixed 顶部，不抢文档流） */
#sp-top{
  position:fixed; top:0; left:0; right:0; z-index:4;
  display:flex; align-items:center; justify-content:space-between;
  padding:14px 28px; pointer-events:none;
  background:linear-gradient(180deg, rgba(238,242,249,.85), rgba(238,242,249,0));
  backdrop-filter:blur(8px);
}
#sp-top .brand{display:flex;align-items:center;gap:10px;font-weight:700;font-size:16px;color:var(--ink)}
#sp-top .brand .dot{width:11px;height:11px;border-radius:50%;
  background:linear-gradient(135deg,var(--brand),var(--cyan));
  box-shadow:0 0 0 4px rgba(66,99,235,.15)}
#sp-top .brand small{font-weight:500;font-size:10.5px;color:var(--sub);letter-spacing:1.5px;
  text-transform:uppercase;margin-left:2px}
#sp-top .status{font-size:12.5px;color:var(--sub);display:flex;align-items:center;gap:7px;
  background:var(--glass-strong);padding:6px 14px;border-radius:20px;border:1px solid var(--line)}
#sp-top .status .live-dot{width:7px;height:7px;border-radius:50%;background:var(--cyan);
  box-shadow:0 0 0 3px rgba(12,166,120,.18);animation:pulse 2s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.35}}

/* Hero 标题区（文档流） */
.hero-block{position:relative;z-index:2;text-align:center;padding:80px 24px 16px;max-width:900px;margin:0 auto}
.hero-block .eyebrow{display:inline-block;font-size:11.5px;letter-spacing:2.4px;text-transform:uppercase;color:var(--brand);
  background:rgba(66,99,235,.08);border:1px solid rgba(66,99,235,.18);padding:6px 14px;border-radius:30px;margin-bottom:18px}
.hero-block h1{font-family:'Space Grotesk','Inter',sans-serif;font-weight:700;font-size:50px;line-height:1.08;letter-spacing:-.5px;margin:0;
  background:linear-gradient(110deg,#1a2233 25%,#3b5bdb 50%,#7048e8 70%,#1a2233 95%);
  background-size:220% auto;animation:gradShift 9s linear infinite;
  -webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent}
@keyframes gradShift{0%{background-position:0% 50%}100%{background-position:220% 50%}}
.hero-block p{margin:14px 0 0;font-size:17px;color:var(--sub)}

/* 输入行 —— v1_basic 朴素写法：直接 Textbox + Button 不套 Row，
   绝对不碰 Gradio 4.x .input-container 的 padding（否则 textarea hover/聚焦全废）。
   视觉样式靠 Hero 标题 + LIVE ACTIVITY + 背景渐变撑住，输入区就用 Gradio 默认白条。 */

/* ⌘K 角标 —— 用 gr.HTML 渲染绝对定位在 input 左下 */
.cmdk-badge{
  position:absolute; left:22px; bottom:6px;
  font-size:11px; color:#94a3b8;
  background:rgba(43,76,126,.06); border:1px solid var(--line);
  padding:2px 7px; border-radius:6px; font-family:'Space Grotesk','Inter',monospace;
  pointer-events:none;
}

/* 按钮 —— 只改视觉色，不改 layout（display/margin/padding 不能碰） */
#spBtn button{
  background:linear-gradient(135deg,var(--brand),var(--brand2)) !important;
  color:#fff !important; border:0 !important; cursor:pointer;
  font-weight:600 !important;
  box-shadow:0 6px 18px rgba(66,99,235,.30) !important;
  transition:.18s;
}
#spBtn button:hover{filter:brightness(1.07)}
/* 让按钮居中、最大宽 720px —— 但用 Gradio 容器的 padding 不用 display */
#spBtn{
  max-width:720px !important;
  margin:14px auto 0 !important;
}

/* LIVE ACTIVITY 玻璃条 */
.live-card{
  max-width:680px; margin:14px auto 0;
  background:var(--glass); border:1px solid var(--line); border-radius:14px;
  padding:10px 16px; display:flex; align-items:center; gap:10px;
  font-size:12.5px; color:var(--sub);
  backdrop-filter:blur(10px); box-shadow:var(--shadow-sm);
  position:relative; z-index:2;
}
.live-card .live-dot{width:8px;height:8px;border-radius:50%;background:var(--cyan);
  box-shadow:0 0 0 3px rgba(12,166,120,.18);animation:pulse 2s infinite}
.live-card b{color:var(--brand);font-weight:600;letter-spacing:.2px}

/* 示例 chips —— Gradio 默认 gr.Examples 样式覆盖 */
.examples{margin:18px auto 0 !important;max-width:780px !important;
  display:flex !important;gap:8px !important;flex-wrap:wrap !important;justify-content:center !important}
.examples table, .examples tbody{display:flex !important;flex-wrap:wrap !important;gap:8px !important}
.examples tr{display:inline-block !important}
.examples td{padding:0 !important}
.examples button{
  background:var(--glass) !important;border:1px solid var(--line) !important;
  border-radius:20px !important;padding:7px 14px !important;
  font-size:12.5px !important;color:var(--ink2) !important;
  box-shadow:none !important;cursor:pointer;transition:.2s;
}
.examples button:hover{background:#fff !important;border-color:var(--brand) !important;color:var(--brand) !important}

section.block{position:relative;z-index:1;margin-top:54px}
.sec-head{display:flex;align-items:baseline;justify-content:space-between;margin-bottom:20px;flex-wrap:wrap;gap:8px}
.sec-head h2{font-family:'Space Grotesk','Inter',sans-serif;font-weight:600;font-size:21px;letter-spacing:-.2px}
.sec-head .tag{font-size:11.5px;color:var(--sub);letter-spacing:1px;text-transform:uppercase}
.eyebrow-sec{font-size:11px;letter-spacing:2.5px;text-transform:uppercase;color:var(--brand);font-weight:600;margin-bottom:8px;display:block}

.card{background:var(--glass);border:1px solid var(--line);border-radius:var(--r);box-shadow:var(--shadow-sm);backdrop-filter:blur(10px);
  transition:transform .3s cubic-bezier(.2,.7,.3,1), box-shadow .3s}
.card:hover{transform:translateY(-3px);box-shadow:var(--shadow-lg)}

.dash{display:block}
.overview{padding:22px 26px}
.overview .ttl{font-size:12px;letter-spacing:1.4px;text-transform:uppercase;color:var(--sub);margin-bottom:16px;display:flex;align-items:center;gap:8px}
.ov-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:0}
.ov-row{display:flex;flex-direction:column;gap:5px;padding:13px 22px;border-left:1px dashed var(--line)}
.ov-row:first-child{border-left:0;padding-left:0}
.ov-row .k{font-size:12px;letter-spacing:.8px;text-transform:uppercase;color:var(--sub)}
.ov-row .v{font-family:'Space Grotesk','Inter',sans-serif;font-weight:600;font-size:20px}
.ov-row .v.hl{color:var(--brand)}
.pc{margin-top:20px;padding-top:18px;border-top:1px solid var(--line)}
.pc .pc-top{display:flex;align-items:baseline;justify-content:space-between;margin-bottom:10px}
.pc .pc-top .lab{font-size:12px;letter-spacing:1.2px;text-transform:uppercase;color:var(--sub)}
.pc .pc-top .pct{font-family:'Space Grotesk','Inter',sans-serif;font-weight:700;font-size:20px;color:var(--brand)}
.pc .track{height:10px;border-radius:10px;background:rgba(43,76,126,.10);overflow:hidden;position:relative}
.pc .track i{display:block;height:100%;border-radius:10px;
  background:linear-gradient(90deg,var(--brand),var(--cyan));background-size:200% 100%;
  animation:pcShine 2.4s linear infinite}
@keyframes pcShine{0%{background-position:0% 0}100%{background-position:200% 0}}

.fits{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-top:18px}
.fit{position:relative;overflow:hidden;text-align:center;padding:24px 18px}
.fit .name{font-size:12px;letter-spacing:1.2px;text-transform:uppercase;color:var(--sub);margin-bottom:16px}
.fit .ring{width:108px;height:108px;border-radius:50%;margin:0 auto 15px;display:flex;align-items:center;justify-content:center;position:relative;
  background:conic-gradient(var(--c) calc(var(--p)*1%), rgba(43,76,126,.10) 0)}
.fit .ring::before{content:"";position:absolute;inset:11px;border-radius:50%;background:var(--glass-strong)}
.fit .ring b{position:relative;z-index:1;font-family:'Space Grotesk','Inter',sans-serif;font-weight:700;font-size:30px;color:var(--c)}
.fit .verdict{font-size:13px;font-weight:600;color:var(--c)}
.fit.f1{--c:var(--brand)}
.fit.f2{--c:var(--cyan)}
.fit.f3{--c:var(--amber)}
.fit .glow{position:absolute;top:-40px;right:-30px;width:120px;height:120px;border-radius:50%;
  background:radial-gradient(circle,var(--c),transparent 70%);opacity:.10;pointer-events:none}

.ai-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}
.ai{position:relative;overflow:hidden;padding:22px 22px 20px}
.ai .ai-name{font-size:12px;letter-spacing:1.2px;text-transform:uppercase;color:var(--sub);margin-bottom:14px}
.ai .ai-num{font-family:'Space Grotesk','Inter',sans-serif;font-weight:700;font-size:46px;line-height:1;letter-spacing:-1px}
.ai .ai-num.small{font-size:30px}
.ai .ai-status{display:inline-flex;align-items:center;gap:6px;margin-top:10px;font-size:12.5px;font-weight:600;
  padding:4px 11px;border-radius:20px}
.ai .ai-judge{margin-top:14px;font-size:13px;line-height:1.55;color:var(--ink2)}
.ai .ai-bar{height:5px;border-radius:5px;background:rgba(43,76,126,.10);margin-top:14px;overflow:hidden}
.ai .ai-bar i{display:block;height:100%;border-radius:5px}
.ai.b1 .ai-num{color:var(--brand)}
.ai.b1 .ai-status{background:rgba(66,99,235,.12);color:var(--brand)}
.ai.b1 .ai-bar i{background:var(--brand)}
.ai.b2 .ai-num{color:var(--cyan)}
.ai.b2 .ai-status{background:rgba(12,166,120,.12);color:var(--cyan)}
.ai.b2 .ai-bar i{background:var(--cyan)}
.ai.b3 .ai-num{color:var(--amber)}
.ai.b3 .ai-status{background:rgba(232,89,12,.12);color:var(--amber)}
.ai.b3 .ai-bar i{background:var(--amber)}
.ai .glow{position:absolute;top:-40px;right:-40px;width:120px;height:120px;border-radius:50%;
  background:radial-gradient(circle,rgba(66,99,235,.10),transparent 70%);pointer-events:none}

.rec-wrap{position:relative;padding:26px 28px;overflow:hidden;
  background:linear-gradient(135deg,rgba(59,91,219,.10),rgba(112,72,232,.06));
  border:1px solid rgba(66,99,235,.22)}
.rec-wrap .glow{position:absolute;top:-60px;left:-40px;width:200px;height:200px;border-radius:50%;
  background:radial-gradient(circle,rgba(112,72,232,.12),transparent 70%);pointer-events:none}
.rec-head{display:flex;align-items:center;gap:11px;margin-bottom:6px;position:relative}
.rec-head .badge{font-size:10.5px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:#fff;background:var(--brand);padding:5px 12px;border-radius:20px}
.rec-head .lead{font-size:11px;letter-spacing:1.5px;text-transform:uppercase;color:var(--sub2)}
.rec-main{font-family:'Space Grotesk','Inter',sans-serif;font-weight:600;font-size:23px;line-height:1.35;margin:12px 0 20px;color:var(--ink);position:relative}
.rec-main b{color:var(--brand)}
.rec-cols{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;position:relative}
.rec-col{padding:16px 18px;background:var(--glass-strong);border:1px solid var(--line);border-radius:12px}
.rec-col .h{font-size:11.5px;font-weight:700;letter-spacing:.6px;text-transform:uppercase;margin-bottom:9px;display:flex;align-items:center;gap:7px}
.rec-col.opp .h{color:var(--cyan)}
.rec-col.risk .h{color:var(--amber)}
.rec-col.act .h{color:var(--violet)}
.rec-col .txt{font-size:13.5px;line-height:1.6;color:var(--ink2)}
.rec-col .txt div{padding:3px 0}

.journey{padding:30px 26px 26px;position:relative}
.jl-track{position:relative;display:flex;justify-content:space-between;margin-top:8px}
.jl-prog{position:absolute;top:21px;left:8%;height:3px;border-radius:3px;
  background:linear-gradient(90deg,var(--brand),var(--violet));z-index:1}
.jl-step{position:relative;z-index:2;flex:1;text-align:center;min-width:120px}
.jl-step .jl-dot{width:42px;height:42px;border-radius:50%;margin:0 auto 13px;display:flex;align-items:center;justify-content:center;
  font-family:'Space Grotesk','Inter',sans-serif;font-weight:700;font-size:15px;background:var(--glass-strong);border:2px solid var(--line);
  color:var(--sub2);transition:.3s}
.jl-step .jl-t{font-size:13.5px;font-weight:600;color:var(--ink2)}
.jl-step .jl-d{font-size:11.5px;color:var(--sub2);margin-top:5px}
.jl-step.done .jl-dot{background:linear-gradient(135deg,var(--brand),var(--brand2));border-color:transparent;color:#fff;box-shadow:0 4px 14px rgba(66,99,235,.30)}
.jl-step.done .jl-t{color:var(--ink)}
.jl-step.current .jl-dot{background:#fff;border-color:var(--brand);color:var(--brand);box-shadow:0 0 0 6px rgba(66,99,235,.14);animation:halo 2.4s ease-in-out infinite}
.jl-step.current .jl-t{color:var(--brand)}
.jl-step.future .jl-dot{opacity:.5}
.jl-step.future .jl-t{color:var(--sub2)}
@keyframes halo{0%,100%{box-shadow:0 0 0 6px rgba(66,99,235,.14)}50%{box-shadow:0 0 0 11px rgba(66,99,235,.05)}}

.map-wrap{padding:8px 4px 0;position:relative;min-height:360px}
.map-wrap svg{width:100%;height:360px;display:block}
.legend{display:flex;gap:18px;margin-top:14px;flex-wrap:wrap;justify-content:center}
.legend span{display:flex;align-items:center;gap:7px;font-size:12.5px;color:var(--sub)}
.legend i{width:11px;height:11px;border-radius:50%}

.strat{display:grid;grid-template-columns:1fr auto 1fr auto 1fr;align-items:stretch;gap:0;position:relative}
.strat::after{content:"";position:absolute;left:16.6%;right:16.6%;top:54px;height:2px;z-index:0;
  background:linear-gradient(90deg,var(--brand),var(--cyan));opacity:.45}
.sc{padding:22px 22px;position:relative;z-index:1}
.sc .sc-no{font-family:'Space Grotesk','Inter',sans-serif;font-weight:700;font-size:13px;color:var(--sub2);letter-spacing:1px}
.sc .sc-ic{width:40px;height:40px;border-radius:11px;display:flex;align-items:center;justify-content:center;font-size:18px;margin:12px 0;position:relative;z-index:1}
.sc.s1 .sc-ic{background:rgba(66,99,235,.12);color:var(--brand)}
.sc.s2 .sc-ic{background:rgba(12,166,120,.12);color:var(--cyan)}
.sc.s3 .sc-ic{background:rgba(112,72,232,.12);color:var(--violet)}
.sc .sc-t{font-family:'Space Grotesk','Inter',sans-serif;font-weight:600;font-size:16px;margin-bottom:8px}
.sc .sc-d{font-size:13.5px;line-height:1.6;color:var(--ink2)}
.sc-joint{display:flex;align-items:center;justify-content:center;color:var(--brand);font-size:20px;opacity:.7;position:relative;z-index:1}

.reveal{opacity:0;animation:revealIn .7s ease forwards}
@keyframes revealIn{to{opacity:1;transform:none}}
.dash-root{animation:revealIn .5s ease forwards}
.empty-hint{text-align:center;color:var(--sub);font-size:15px;padding:60px 20px;line-height:1.8}
.empty-hint b{color:var(--brand)}

footer{position:relative;z-index:1;text-align:center;color:#9aa3b2;font-size:12.5px;margin-top:64px;letter-spacing:.3px}
footer b{color:var(--sub)}

.gr-markdown{position:relative;z-index:1;margin-top:40px;background:var(--glass);border:1px solid var(--line);
  border-radius:var(--r);padding:26px 30px;box-shadow:var(--shadow-sm);backdrop-filter:blur(10px)}
.gr-markdown h3{font-family:'Space Grotesk','Inter',sans-serif;color:var(--brand);margin:18px 0 10px}
.gr-markdown a{color:var(--brand);text-decoration:underline}

@media(max-width:880px){
  .ov-grid{grid-template-columns:repeat(2,1fr)}
  .fits,.ai-grid,.rec-cols{grid-template-columns:1fr}
  .strat{grid-template-columns:1fr}
  .sc-joint{transform:rotate(90deg);padding:6px 0}
  .strat::after{display:none}
  .hero-block h1{font-size:38px}
}
"""


# ===================================================================
#  背景装饰层（世界地图 + 学术网络 canvas）—— fixed 满屏 z-index:0 不拦截交互
# ===================================================================
BACKGROUND_HTML = r"""
<div id="sp-bg" aria-hidden="true">
  <div id="worldmap">
    <svg viewBox="0 0 1000 500" preserveAspectRatio="xMidYMid slice">
      <defs>
        <radialGradient id="glow" cx="50%" cy="45%" r="60%">
          <stop offset="0%" stop-color="#4263eb" stop-opacity=".05"/>
          <stop offset="100%" stop-color="#4263eb" stop-opacity="0"/>
        </radialGradient>
      </defs>
      <rect width="1000" height="500" fill="url(#glow)"/>
      <g stroke="#2b4c7e" stroke-opacity=".05" stroke-width="1">
        <line x1="0" y1="100" x2="1000" y2="100"/><line x1="0" y1="200" x2="1000" y2="200"/>
        <line x1="0" y1="300" x2="1000" y2="300"/><line x1="0" y1="400" x2="1000" y2="400"/>
        <line x1="125" y1="0" x2="125" y2="500"/><line x1="250" y1="0" x2="250" y2="500"/>
        <line x1="375" y1="0" x2="375" y2="500"/><line x1="500" y1="0" x2="500" y2="500"/>
        <line x1="625" y1="0" x2="625" y2="500"/><line x1="750" y1="0" x2="750" y2="500"/>
        <line x1="875" y1="0" x2="875" y2="500"/>
      </g>
      <g fill="#2b4c7e" fill-opacity=".04">
        <path d="M120,90 L210,70 L250,110 L240,170 L190,210 L150,180 L110,140 Z"/>
        <path d="M250,250 L300,240 L320,300 L280,360 L250,330 L240,280 Z"/>
        <path d="M450,80 L560,68 L600,108 L580,150 L520,160 L470,140 Z"/>
        <path d="M470,180 L580,170 L620,230 L590,330 L520,360 L490,280 L470,230 Z"/>
        <path d="M620,90 L860,80 L900,150 L840,210 L720,210 L640,170 Z"/>
        <path d="M820,330 L900,320 L910,370 L850,390 L810,360 Z"/>
        <path d="M455,95 L545,80 L560,115 L510,130 L465,120 Z"/>
      </g>
      <g font-family="Inter" font-size="11" font-weight="600" fill="#2b4c7e" fill-opacity=".055">
        <circle cx="210" cy="150" r="26" fill="#4263eb" fill-opacity=".035"/>
        <text x="210" y="154" text-anchor="middle">United States</text>
        <circle cx="170" cy="120" r="20" fill="#4263eb" fill-opacity=".035"/>
        <text x="170" y="124" text-anchor="middle">Canada</text>
        <circle cx="760" cy="170" r="22" fill="#4263eb" fill-opacity=".035"/>
        <text x="760" y="174" text-anchor="middle">China</text>
        <circle cx="505" cy="108" r="16" fill="#4263eb" fill-opacity=".035"/>
        <text x="505" y="112" text-anchor="middle">Europe</text>
      </g>
      <g stroke="#4263eb" stroke-opacity=".05" stroke-width="1">
        <line x1="210" y1="150" x2="760" y2="170"/>
        <line x1="170" y1="120" x2="210" y2="150"/>
        <line x1="210" y1="150" x2="640" y2="140"/>
        <line x1="760" y1="170" x2="640" y2="140"/>
        <line x1="640" y1="140" x2="540" y2="120"/>
        <line x1="505" y1="108" x2="540" y2="120"/>
        <line x1="505" y1="108" x2="210" y2="150"/>
        <line x1="795" y1="205" x2="760" y2="170"/>
      </g>
      <g id="worldUnis">
        <g class="wuni"><circle cx="210" cy="150" r="3" fill="#3b5bdb" fill-opacity=".10"/></g>
        <g class="wuni"><circle cx="170" cy="120" r="3" fill="#3b5bdb" fill-opacity=".10"/></g>
        <g class="wuni"><circle cx="760" cy="170" r="3" fill="#3b5bdb" fill-opacity=".10"/></g>
        <g class="wuni"><circle cx="640" cy="140" r="3" fill="#3b5bdb" fill-opacity=".10"/></g>
        <g class="wuni"><circle cx="540" cy="120" r="3" fill="#3b5bdb" fill-opacity=".10"/></g>
        <g class="wuni"><circle cx="880" cy="150" r="3" fill="#3b5bdb" fill-opacity=".10"/></g>
        <g class="wuni"><circle cx="300" cy="250" r="3" fill="#3b5bdb" fill-opacity=".10"/></g>
        <g class="wuni"><circle cx="150" cy="230" r="3" fill="#3b5bdb" fill-opacity=".10"/></g>
        <g class="wuni"><circle cx="470" cy="95" r="3" fill="#3b5bdb" fill-opacity=".10"/></g>
        <g class="wuni"><circle cx="495" cy="118" r="3" fill="#3b5bdb" fill-opacity=".10"/></g>
        <g class="wuni"><circle cx="795" cy="205" r="3" fill="#3b5bdb" fill-opacity=".10"/></g>
      </g>
    </svg>
  </div>
  <canvas id="network"></canvas>
</div>
"""

# ===================================================================
#  顶部 fixed 品牌条 + Live 状态
# ===================================================================
TOP_BAR_HTML = r"""
<div id="sp-top">
  <div class="brand"><span class="dot"></span><span>StudyPath<small>Academic Planning Platform</small></span></div>
  <div class="status"><span class="live-dot"></span>Live · RAG + LangGraph</div>
</div>
"""

# ===================================================================
#  Hero 标题区
# ===================================================================
HERO_HTML = r"""
<div class="hero-block">
  <span class="eyebrow">Personalized Academic Planning</span>
  <h1>Your Academic Path,<br>Designed Around You.</h1>
  <p>From your academic profile to a personalized university shortlist.</p>
</div>
"""

# ===================================================================
#  ⌘K 角标（绝对定位在输入框左下）
# ===================================================================
CMDK_HTML = r'<span class="cmdk-badge">⌘K</span>'

# ===================================================================
#  LIVE ACTIVITY 玻璃条
# ===================================================================
LIVE_HTML = r"""
<div class="live-card">
  <span class="live-dot"></span>
  <b>LIVE ACTIVITY</b>
  <span id="spFeed">检索耗时 1.2s · 12 sources matched</span>
</div>
"""

# ===================================================================
#  JS — 背景动画 + Live feed 文字滚动
# ===================================================================
# 整段背景 / 顶部状态条 / LIVE 活动都通过 JS 注入到 document.body 末尾，
# 彻底脱离 .gradio-container 的堆叠上下文 —— 不可能挡住任何 Gradio 组件。
def _inject_layer(layer_id: str, html: str) -> str:
    safe = html.replace("\\", "\\\\").replace("`", "\\`").replace("$", "\\$").replace("\n", " ")
    return (
        f"(function(){{var d=document;if(!d.getElementById('{layer_id}')){{"
        f"var b=d.createElement('div');b.id='sp-wrap-{layer_id}';b.innerHTML=`{safe}`;"
        f"d.body.appendChild(b);}}}})();"
    )


JS = (
    "(function(){\n"
    + _inject_layer("sp-bg", BACKGROUND_HTML)
    + _inject_layer("sp-top", TOP_BAR_HTML)
    + _inject_layer("sp-live", LIVE_HTML)
    + _inject_layer("sp-cmdk", CMDK_HTML)
    + "\n"
    # 2) 网络画布背景动画
    + r"""
  function _startNetwork(){
    var c=document.getElementById('network');
    if(!c||c.dataset.run)return;c.dataset.run='1';c.style.pointerEvents='none';
    var x=c.getContext('2d'),w,h,nodes=[];
    function resize(){w=c.width=innerWidth;h=c.height=innerHeight;init();}
    function init(){nodes=[];var N=Math.min(85,Math.floor(w*h/17000));
      for(var i=0;i<N;i++){nodes.push({x:Math.random()*w,y:Math.random()*h,vx:(Math.random()-.5)*.14,vy:(Math.random()-.5)*.14,r:Math.random()*1.6+0.6,big:Math.random()<.12,ph:Math.random()*Math.PI*2});}}
    function draw(t){x.clearRect(0,0,w,h);
      for(var i=0;i<nodes.length;i++){var a=nodes[i];
        for(var j=i+1;j<nodes.length;j++){var b=nodes[j],dx=a.x-b.x,dy=a.y-b.y,d=Math.hypot(dx,dy);
          if(d<140){x.strokeStyle='rgba(66,99,235,'+(0.045*(1-d/140))+')';x.lineWidth=0.6;x.beginPath();x.moveTo(a.x,a.y);x.lineTo(b.x,b.y);x.stroke();}}}
      for(var k=0;k<nodes.length;k++){var n=nodes[k];n.x+=n.vx;n.y+=n.vy;
        if(n.x<0||n.x>w)n.vx*=-1;if(n.y<0||n.y>h)n.vy*=-1;
        var p=0.5+0.5*Math.sin(t/1400+n.ph);
        x.fillStyle=n.big?('rgba(66,99,235,'+(0.14+0.10*p)+')'):('rgba(43,76,126,'+(0.10+0.06*p)+')');
        x.beginPath();x.arc(n.x,n.y,n.r*(0.9+0.3*p),0,7);x.fill();}
      requestAnimationFrame(draw);}
    addEventListener('resize',resize);resize();requestAnimationFrame(draw);
  }
  if(document.readyState==='loading'){document.addEventListener('DOMContentLoaded',_startNetwork);}else{_startNetwork();}
  """
    # 3) Live feed 文字轮播
    + r"""
  function _startFeed(){
    var af=document.getElementById('spFeed');
    if(af&&!af.dataset.run){af.dataset.run='1';
      var acts=['AI 正在解析学术画像 · 命中 3 库','检索耗时 1.2s · 12 sources matched','LangGraph 路由 → School Match 节点','生成 Academic Fit / Research Fit 评估','匹配 Reach / Target / Safety 三档院校'];
      var i=0;function tick(){af.textContent=acts[i];i=(i+1)%acts.length;setTimeout(tick,2400);}tick();}
  }
  if(document.readyState==='loading'){document.addEventListener('DOMContentLoaded',_startFeed);}else{_startFeed();}
  """
    # 4) 世界地图大学点闪烁
    + r"""
  function _startUnis(){
    var us=document.querySelectorAll('#worldUnis .wuni circle');
    if(us.length){var t=0;function loop(){t+=16;us.forEach(function(u,idx){var p=0.5+0.5*Math.sin(t/1600+idx);u.setAttribute('fill-opacity',(0.06+0.06*p).toFixed(3));});requestAnimationFrame(loop);}requestAnimationFrame(loop);}
  }
  if(document.readyState==='loading'){document.addEventListener('DOMContentLoaded',_startUnis);}else{_startUnis();}
  """
    + "\n})();"
)

INITIAL_DASH = (
    '<div class="dash-root"><div class="empty-hint">'
    '输入你的学术画像（如 <b>GPA 3.5 · TOEFL 100 · 目标 CMU MSCS</b>），'
    '下方将生成你的 <b>学术驾驶舱</b>：申请画像、录取智能评估、院校匹配地图与申请策略。</div></div>'
)


# 从用户 query 里结构化提取档案信息，含估算与补全口径。
# 不编造具体分数：GPA 允许按本科档次与提问语义估算，输出时打 * 标记。
# TOEFL / IELTS 同体系，并入「标化分数」槽，按 query 实际提到的二选一显示。
def extract_profile(q: str) -> dict:
    prof = {
        "gpa": None,
        "gpa_is_estimated": False,        # 是否系统按本科档次/百分制估算的
        "toefl": None,                    # int
        "ielts": None,                    # float (7.0)
        "target": None,                   # 用户明确目标 (CMU/MIT/...)
        "target_hint": None,              # 软语义 ("美国 · TOP · CS")
        "research": None,                 # 等级: Strong / Moderate / Building
    }
    ql = q  # 大小写不敏感处理时用 q，原文大写名校时也保留

    # -------- GPA：四层降级匹配 --------
    # 1) 直接给 4.0 制 GPA: "GPA 3.5"
    m = re.search(r'(?:gpa|绩点|gpa均分)[^\d]{0,6}([0-4](?:\.[0-9]+)?)', ql, re.I)
    if m:
        try:
            v = float(m.group(1))
            if 0 < v <= 4.0:
                prof["gpa"] = v
        except ValueError:
            pass

    # 2) 百分制分数: "均分 85" / "GPA 88"
    if prof["gpa"] is None:
        m = re.search(r'(?:均分|平均分|百分制|成绩|均绩|加权|加权均分|分数)[^\d]{0,6}([6-9][0-9](?:\.[0-9]+)?)', ql)
        if m:
            score = float(m.group(1))
            if score >= 90: prof["gpa"] = 3.7
            elif score >= 85: prof["gpa"] = 3.3
            elif score >= 80: prof["gpa"] = 3.0
            elif score >= 75: prof["gpa"] = 2.7
            else: prof["gpa"] = 2.0
            prof["gpa_is_estimated"] = True

    # 3) 中国本科档次估算: 211/985/C9/一本/双非
    if prof["gpa"] is None:
        if re.search(r'(C9|c9|清华|北大|上交大?|复旦|浙大|中科大|南大|南京大学|哈工大|上交复旦)', ql, re.I):
            prof["gpa"] = 3.7; prof["gpa_is_estimated"] = True
        elif re.search(r'(985|211|双一流)', ql, re.I):
            prof["gpa"] = 3.5; prof["gpa_is_estimated"] = True
        elif re.search(r'(一本|一本院校|原一本)', ql, re.I):
            prof["gpa"] = 3.2; prof["gpa_is_estimated"] = True
        elif re.search(r'(双非|二本|普通本科)', ql, re.I):
            prof["gpa"] = 3.0; prof["gpa_is_estimated"] = True

    # 4) 不带任何 GPA 信号 → 留 None（不算 0）

    # -------- TOEFL / IELTS（同一槽） --------
    m = re.search(r'(?:toefl|托福|ibt)[^\d]{0,6}([0-9]{2,3})', ql, re.I)
    if m:
        v = int(m.group(1))
        if 0 < v <= 120: prof["toefl"] = v
    m = re.search(r'(?:ielts|雅思|雅思分数?)[^\d]{0,6}([0-9](?:\.[0-9])?)', ql, re.I)
    if m:
        try:
            v = float(m.group(1))
            if 0 < v <= 9.0: prof["ielts"] = v
        except ValueError:
            pass

    # -------- Target：硬命中 + 软语义 --------
    target_unis = ['CMU', 'MIT', 'Stanford', 'UIUC', 'USC', 'McGill', 'Toronto',
                   'Harvard', 'Berkeley', 'UC\\s?Berkeley',
                   '哈佛', '斯坦福', '卡内基', '卡梅', '牛津', '剑桥', 'ETH',
                   'NUS', 'NTU', '港大', '港中文', '港城', '港理工',
                   '新加坡国立', '南洋理工',
                   'UCL', '帝国理工', 'IC', '伯克利']
    m = re.search(
        r'(?:申[请报]?|target|目标|想去|冲[刺]?|保[底]?)[^\n]{0,24}?(' + '|'.join(target_unis) + ')',
        ql, re.I)
    if m:
        prof["target"] = re.sub(r'\\s', ' ', m.group(1))

    # 软语义: 国家 + 方向 + 档次
    if not prof["target"]:
        soft = []
        if re.search(r'(美国|usa|u\.s\.?|美研|北美)', ql, re.I):
            soft.append("美国")
        elif re.search(r'(英国|uk|英研|英格兰)', ql, re.I):
            soft.append("英国")
        elif re.search(r'(香港|港硕|港校|港中文)', ql, re.I):
            soft.append("香港")
        elif re.search(r'(新加坡|新国立|南洋)', ql, re.I):
            soft.append("新加坡")
        elif re.search(r'(欧洲|欧陆|欧洲大陆|europe|德国|荷兰|法国|瑞士)', ql, re.I):
            soft.append("欧洲")
        elif re.search(r'(加拿大|加拿大|canada)', ql, re.I):
            soft.append("加拿大")
        elif re.search(r'(澳洲|澳大利亚|aus)', ql, re.I):
            soft.append("澳洲")

        tier = ""
        if re.search(r'(top\s*\d+|前\s*\d+|tier\s*1|tier-?1|顶级|顶校)', ql, re.I):
            tier = "Tier-1"
        elif re.search(r'(top\s*30|前\s*30|三十|30名)', ql, re.I):
            tier = "TOP 30"
        elif re.search(r'(top\s*50|前\s*50|五十|50名)', ql, re.I):
            tier = "TOP 50"

        field = ""
        if re.search(r'(cs|计算机|computer science|码)', ql, re.I):
            field = "CS"
        elif re.search(r'(ai|人工智能|machine learning|ml|deep learning|深度学习|nlp|大模型|llm)', ql, re.I):
            field = "AI"
        elif re.search(r'(ds|数据科学|data science)', ql, re.I):
            field = "DS"
        elif re.search(r'(ee|电子工程|electrical engineering)', ql, re.I):
            field = "EE"
        elif re.search(r'(mba|商科|金融|finance)', ql, re.I):
            field = "商科/MBA"
        elif re.search(r'(机械|自动化|me)', ql, re.I):
            field = "工科"

        # 拼接
        if soft or tier or field:
            parts = []
            if soft: parts.append(soft[0])
            if tier: parts.append(tier)
            if field: parts.append(field)
            prof["target_hint"] = " · ".join(parts)

    # -------- Research：分档级匹配 --------
    strong_kw = ['论文', 'publication', '发表', '一作', '第一作者', '顶会', '顶刊',
                 'SCI', '一区', 'CCF-A', 'NeurIPS', 'ICML', 'CVPR', 'ACL', 'EMNLP']
    moderate_kw = ['科研项目', '实验室', 'research', '导师项目', '组里项目', '跟着老师做']
    building_kw = ['大创', '挑战杯', '互联网+', '竞赛', '比赛', '科创', '项目经历',
                   '实习', 'intern', '科研']

    if any(k in ql for k in strong_kw):
        prof["research"] = "Strong"
    elif any(k in ql for k in moderate_kw):
        prof["research"] = "Moderate"
    elif any(k in ql for k in building_kw):
        prof["research"] = "Building"

    return prof


def heuristic_fit(prof: dict) -> dict:
    gpa = prof.get("gpa")
    academic = round((gpa / 4.0) * 100) if gpa else 70
    research = 82 if prof.get("research") else 64
    # 同时看硬命中 target 和软语义 target_hint
    tgt = (prof.get("target") or prof.get("target_hint") or "").upper()
    competition = (
        "HIGH" if any(k in tgt for k in
                      ["CMU", "MIT", "STANFORD", "HARVARD", "斯坦福", "哈佛", "OXFORD",
                       "ETH", "UC BERKELEY", "伯克利", "TIER-1", "TIER 1"])
        else "MEDIUM"
    )
    return {"academic": academic, "research": research, "competition": competition}


def completeness(prof: dict) -> int:
    """Profile Completeness: 4 个槽位有几个有值（含估算）。
       用户感受到"GPA/标化/TARGET/RESEARCH"四个格子不再空，就算上。"""
    n = 0
    if prof.get("gpa") is not None:
        n += 1
    if prof.get("toefl") is not None or prof.get("ielts") is not None:
        n += 1
    if prof.get("target") is not None or prof.get("target_hint") is not None:
        n += 1
    if prof.get("research") is not None:
        n += 1
    return int(n / 4 * 100)


def fit_verdict(fit: dict) -> tuple:
    a, r, c = fit["academic"], fit["research"], fit["competition"]
    va = "Good Match" if a >= 75 else ("Competitive" if a >= 60 else "Stretch")
    vr = "Strong" if r >= 75 else "Building"
    vc = "Top-tier" if c == "HIGH" else "Standard"
    return va, vr, vc


# ===================================================================
#  构建驾驶舱 HTML
# ===================================================================
def _ov_row(k, v, hl=False):
    vcls = 'v hl' if hl else 'v'
    return f'<div class="ov-row"><span class="k">{k}</span><span class="{vcls}">{v}</span></div>'


def build_sources_html(sources: list) -> str:
    """渲染「📚 参考来源」卡片列表（放在答案之后，像论文参考文献）。

    数据 100% 来自召回文档 metadata 的 source_url，不依赖 LLM 复述。
    """
    if not sources:
        return ""
    cards = "".join(
        f'<a href="{s.get("url", "")}" target="_blank" rel="noopener" '
        f'style="display:block;text-decoration:none;border:1px solid var(--line);'
        f'border-radius:10px;padding:12px 16px;margin:8px 0;background:#fff;'
        f'transition:box-shadow .15s,transform .15s" '
        f'onmouseover="this.style.boxShadow=\'var(--shadow-sm)\';this.style.transform=\'translateY(-1px)\'" '
        f'onmouseout="this.style.boxShadow=\'none\';this.style.transform=\'none\'">'
        f'<div style="display:flex;align-items:center;gap:8px;color:var(--ink2);font-weight:600;font-size:14px">'
        f'<span style="color:var(--brand);font-size:15px">⊙</span>'
        f'{s.get("school") or s.get("domain") or "参考来源"}'
        f'</div>'
        f'<div style="color:var(--sub);font-size:13px;margin-top:4px">{s.get("program") or s.get("sheet") or ""}</div>'
        f'<div style="color:var(--sub2);font-size:12px;margin-top:6px">{s.get("domain", "")}</div>'
        f'</a>'
        for s in sources
    )
    return (
        f'<div style="margin-top:16px;padding:16px 20px;background:var(--glass-strong);'
        f'border-radius:14px;border:1px solid var(--line)">'
        f'<div style="display:flex;align-items:center;gap:8px;font-weight:700;color:var(--ink2);margin-bottom:10px;font-size:14px">'
        f'📚 参考来源'
        f'<span style="font-size:12px;color:var(--sub);font-weight:500">共 {len(sources)} 条</span></div>'
        f'<div style="display:flex;flex-direction:column;gap:4px">{cards}</div>'
        f'</div>'
    )


def build_dash(prof: dict, fit: dict, comp: int, route: list) -> str:
    va, vr, vc = fit_verdict(fit)

    # ---- GPA 槽 ----
    gpa_v = prof.get("gpa")
    if gpa_v is not None:
        if prof.get("gpa_is_estimated"):
            gpa_html = (
                f'<b style="font-size:18px">{gpa_v}</b>'
                f'<div style="font-size:10.5px;color:#e8590c;font-weight:600;letter-spacing:.4px;margin-top:3px">估算 ※</div>'
            )
        else:
            gpa_html = (
                f'<b style="font-size:22px">{gpa_v}</b>'
                f'<div style="font-size:10.5px;color:var(--cyan);font-weight:600;letter-spacing:.3px;margin-top:2px">已提供</div>'
            )
    else:
        gpa_html = '<span style="color:var(--sub2);font-size:18px">未提及</span>'

    # ---- 标化槽: TOEFL/IELTS (同体系，按 query 实际说的二选一) ----
    toefl_v = prof.get("toefl")
    ielts_v = prof.get("ielts")
    if toefl_v is not None and ielts_v is not None:
        std_html = (
            f'<b style="font-size:18px;line-height:1">{toefl_v}</b>'
            f'<div style="font-size:10.5px;color:var(--sub);font-weight:500;letter-spacing:.3px">TOEFL</div>'
            f'<b style="font-size:18px;margin-top:6px;display:inline-block;line-height:1">{ielts_v}</b>'
            f'<div style="font-size:10.5px;color:var(--sub);font-weight:500;letter-spacing:.3px">IELTS</div>'
        )
    elif toefl_v is not None:
        std_html = (
            f'<b style="font-size:24px;line-height:1">{toefl_v}</b>'
            f'<div style="font-size:10.5px;color:var(--sub);font-weight:500;letter-spacing:.3px;margin-top:3px">TOEFL / 120</div>'
        )
    elif ielts_v is not None:
        std_html = (
            f'<b style="font-size:24px;line-height:1">{ielts_v}</b>'
            f'<div style="font-size:10.5px;color:var(--sub);font-weight:500;letter-spacing:.3px;margin-top:3px">IELTS / 9.0</div>'
        )
    else:
        std_html = '<span style="color:var(--sub2);font-size:18px">未提及</span>'

    # ---- Target 槽: 软语义 + 硬命中 ----
    tgt_v = prof.get("target")
    tgt_hint_v = prof.get("target_hint")
    if tgt_v:
        tgt_html = (
            f'<b style="font-size:20px">{tgt_v}</b>'
            f'<div style="font-size:10.5px;color:var(--brand);font-weight:600;letter-spacing:.3px;margin-top:3px">● 已指定</div>'
        )
    elif tgt_hint_v:
        tgt_html = (
            f'<b style="font-size:15px;line-height:1.25;display:inline-block">{tgt_hint_v}</b>'
            f'<div style="font-size:10.5px;color:var(--brand2);font-weight:600;letter-spacing:.3px;margin-top:4px">📍 软语义识别</div>'
        )
    else:
        tgt_html = '<span style="color:var(--sub2);font-size:18px">待补充</span>'

    # ---- Research 槽: 三档分级 ----
    res_v = prof.get("research")
    if res_v:
        color = "#0ca678" if res_v == "Strong" else ("#3b5bdb" if res_v == "Moderate" else "#e8590c")
        chinese_lbl = {"Strong": "强", "Moderate": "中", "Building": "起步"}[res_v]
        res_html = (
            f'<b style="font-size:20px;color:{color}">{chinese_lbl}</b>'
            f'<div style="font-size:10.5px;color:{color};font-weight:600;letter-spacing:.3px;margin-top:3px">{res_v}</div>'
        )
    else:
        res_html = '<span style="color:var(--sub2);font-size:18px">未提及</span>'

    overview = (
        f'<div class="card overview">'
        f'<div class="ttl">📊 Profile Snapshot</div>'
        f'<div class="ov-grid">'
        f'<div class="ov-row"><span class="k">GPA</span><span class="v hl">{gpa_html}</span></div>'
        f'<div class="ov-row"><span class="k">📝 语言标化</span><span class="v">{std_html}</span></div>'
        f'<div class="ov-row"><span class="k">Target</span><span class="v hl">{tgt_html}</span></div>'
        f'<div class="ov-row"><span class="k">Research</span><span class="v">{res_html}</span></div>'
        f'</div>'
        f'<div class="pc"><div class="pc-top"><span class="lab">Profile Completeness</span>'
        f'<span class="pct">{comp}%</span></div>'
        f'<div class="track"><i style="width:{comp}%"></i></div></div>'
        f'</div>'
    )

    a, r, c = fit["academic"], fit["research"], fit["competition"]
    c_pct = 90 if c == "HIGH" else 60
    fits = (
        f'<div class="fits">'
        f'<div class="card fit f1"><span class="glow"></span>'
        f'<div class="name">Academic Fit</div>'
        f'<div class="ring" style="--p:{a}"><b>{a}</b></div>'
        f'<div class="verdict">{va}</div></div>'
        f'<div class="card fit f2"><span class="glow"></span>'
        f'<div class="name">Research Fit</div>'
        f'<div class="ring" style="--p:{r}"><b>{r}</b></div>'
        f'<div class="verdict">{vr}</div></div>'
        f'<div class="card fit f3"><span class="glow"></span>'
        f'<div class="name">Competition</div>'
        f'<div class="ring" style="--p:{c_pct}"><b style="font-size:21px">{c}</b></div>'
        f'<div class="verdict">{"Top-tier" if c=="HIGH" else "Standard"}</div></div>'
        f'</div>'
    )

    tgt = prof.get("target") or prof.get("target_hint") or "你的目标院校"
    opp = "Strong academic foundation" if prof.get("gpa") else "Build a clear academic profile"
    risk = "Research experience could be stronger" if not prof.get("research") else "Maintain research momentum"
    actions = []
    if prof.get("toefl") and prof["toefl"] < 105:
        actions.append(f"Target TOEFL 105+ (current {prof['toefl']})")
    elif prof.get("ielts") and prof["ielts"] < 7.0:
        actions.append(f"Target IELTS 7.0+ (current {prof['ielts']})")
    else:
        actions.append("Keep standardized scores competitive")
    actions.append("Strengthen AI / Systems research")
    actions_html = "".join(f"<div>{a}</div>" for a in actions)
    rec = (
        f'<div class="card rec-wrap"><span class="glow"></span>'
        f'<div class="rec-head"><span class="badge">Recommended</span>'
        f'<span class="lead">Target Assessment</span></div>'
        f'<div class="rec-main"><b>{tgt}</b> is a realistic but competitive target.</div>'
        f'<div class="rec-cols">'
        f'<div class="rec-col opp"><div class="h">▲ Key Opportunity</div>'
        f'<div class="txt"><div>{opp}</div></div></div>'
        f'<div class="rec-col risk"><div class="h">▼ Key Risk</div>'
        f'<div class="txt"><div>{risk}</div></div></div>'
        f'<div class="rec-col act"><div class="h">● Next Action</div>'
        f'<div class="txt">{actions_html}</div></div>'
        f'</div></div>'
    )

    journey = (
        '<div class="card journey"><div class="jl-track">'
        '<div class="jl-prog" style="width:55%"></div>'
        '<div class="jl-step done"><div class="jl-dot">✓</div><div class="jl-t">Profile</div><div class="jl-d">GPA · 标化</div></div>'
        '<div class="jl-step done"><div class="jl-dot">✓</div><div class="jl-t">AI Analysis</div><div class="jl-d">智能评估</div></div>'
        '<div class="jl-step done"><div class="jl-dot">✓</div><div class="jl-t">School Match</div><div class="jl-d">选校定位</div></div>'
        '<div class="jl-step current"><div class="jl-dot">4</div><div class="jl-t">Application Strategy</div><div class="jl-d">策略制定</div></div>'
        '<div class="jl-step future"><div class="jl-dot">5</div><div class="jl-t">Application</div><div class="jl-d">投递</div></div>'
        '<div class="jl-step future"><div class="jl-dot">6</div><div class="jl-t">Decision</div><div class="jl-d">录取</div></div>'
        '</div></div>'
    )

    map_svg = (
        '<div class="map-wrap"><svg viewBox="0 0 900 320" preserveAspectRatio="xMidYMid meet">'
        '<g stroke="rgba(43,76,126,.16)" stroke-width="1">'
        '<line x1="180" y1="90" x2="450" y2="150"/><line x1="450" y1="150" x2="720" y2="80"/>'
        '<line x1="450" y1="150" x2="300" y2="250"/><line x1="450" y1="150" x2="640" y2="250"/>'
        '<line x1="180" y1="90" x2="300" y2="250"/><line x1="720" y1="80" x2="640" y2="250"/>'
        '<line x1="300" y1="250" x2="640" y2="250"/><line x1="120" y1="200" x2="300" y2="250"/>'
        '<line x1="800" y1="200" x2="640" y2="250"/></g>'
        '<g text-anchor="middle">'
        '<g><circle cx="450" cy="150" r="22" fill="#3b5bdb"/>'
        '<circle cx="450" cy="150" r="33" fill="none" stroke="#3b5bdb" stroke-width="1.5" opacity=".4"/>'
        '<text x="450" y="155" fill="#fff" class="lbl" font-weight="700" font-size="12.5">CMU</text>'
        '<text x="450" y="188" fill="#3b5bdb" font-size="10" font-weight="700">● TARGET</text></g>'
        '<g><circle cx="180" cy="90" r="14" fill="#e8590c"/>'
        '<text x="180" y="128" fill="#e8590c" font-size="10" font-weight="700">▲ REACH</text>'
        '<text x="180" y="94" fill="#fff" font-weight="700" font-size="12.5">MIT</text></g>'
        '<g><circle cx="720" cy="80" r="14" fill="#e8590c"/>'
        '<text x="720" y="118" fill="#e8590c" font-size="10" font-weight="700">▲ REACH</text>'
        '<text x="720" y="84" fill="#fff" font-weight="700" font-size="12.5">Stanford</text></g>'
        '<g><circle cx="300" cy="250" r="13" fill="#3b5bdb"/>'
        '<text x="300" y="288" fill="#3b5bdb" font-size="10" font-weight="700">● TARGET</text>'
        '<text x="300" y="254" fill="#fff" font-weight="700" font-size="12.5">UIUC</text></g>'
        '<g><circle cx="640" cy="250" r="12" fill="#0ca678"/>'
        '<text x="640" y="288" fill="#0ca678" font-size="10" font-weight="700">● SAFETY</text>'
        '<text x="640" y="254" fill="#fff" font-weight="700" font-size="12.5">USC</text></g>'
        '<g><circle cx="120" cy="200" r="11" fill="#0ca678"/>'
        '<text x="120" y="236" fill="#0ca678" font-size="10" font-weight="700">● SAFETY</text>'
        '<text x="120" y="204" fill="#1a2233" font-weight="600" font-size="11">McGill</text></g>'
        '<g><circle cx="800" cy="200" r="12" fill="#3b5bdb"/>'
        '<text x="800" y="236" fill="#3b5bdb" font-size="10" font-weight="700">● TARGET</text>'
        '<text x="800" y="204" fill="#1a2233" font-weight="600" font-size="11">Toronto</text></g>'
        '</g></svg>'
        '<div class="legend">'
        '<span><i style="background:#e8590c"></i>Reach（冲刺）</span>'
        '<span><i style="background:#3b5bdb"></i>Target（匹配）</span>'
        '<span><i style="background:#0ca678"></i>Safety（保底）</span></div></div>'
    )

    s1 = ("Improve TOEFL to 105+" if (prof.get("toefl") and prof["toefl"] < 105)
          else ("Improve IELTS to 7.0+" if (prof.get("ielts") and prof["ielts"] < 7.0) else "Maintain strong academics"))
    s2 = "Strengthen AI / Systems research" if not prof.get("research") else "Continue research output"
    s3 = "Prepare a stronger SOP highlighting your wins"
    strat = (
        '<div class="card strat">'
        f'<div class="sc s1"><div class="sc-no">01</div><div class="sc-ic">🎓</div>'
        f'<div class="sc-t">Academic</div><div class="sc-d">{s1}。</div></div>'
        '<div class="sc-joint">→</div>'
        f'<div class="sc s2"><div class="sc-no">02</div><div class="sc-ic">🔬</div>'
        f'<div class="sc-t">Research</div><div class="sc-d">{s2}。</div></div>'
        '<div class="sc-joint">→</div>'
        f'<div class="sc s3"><div class="sc-no">03</div><div class="sc-ic">✍</div>'
        f'<div class="sc-t">Application</div><div class="sc-d">{s3}。</div></div>'
        '</div>'
    )

    route_disp = " → ".join(route) if route else "（未路由）"
    # 路由条：只显示 Supervisor 派了哪些 worker（参考来源已拆到答案之后单独展示）
    route_badge = (
        f'<div class="card" style="margin-top:18px;padding:14px 20px;font-size:13px;color:var(--sub)">'
        f'🧭 <b style="color:var(--brand)">Supervisor 路由</b>：{route_disp}'
        f'</div>'
    )

    return (
        f'<div class="dash-root">'
        f'<section class="block reveal"><span class="eyebrow-sec">Applicant Overview</span>'
        f'<div class="sec-head"><h2>Profile Snapshot</h2><span class="tag">Real-time profile</span></div>'
        f'<div class="dash">{overview}{fits}</div></section>'
        f'<section class="block reveal"><span class="eyebrow-sec">Admission Intelligence</span>'
        f'<div class="sec-head"><h2>Fit · Research · Competition</h2><span class="tag">AI-driven assessment</span></div>'
        f'<div class="ai-grid">'
        f'<div class="card ai b1"><span class="glow"></span><div class="ai-name">Academic Fit</div>'
        f'<div class="ai-num">{a}</div><div class="ai-status">● {va}</div>'
        f'<div class="ai-judge">基于你的 GPA 透明换算（GPA/4.0×100），非官方录取概率。</div>'
        f'<div class="ai-bar"><i style="width:{a}%"></i></div></div>'
        f'<div class="card ai b2"><span class="glow"></span><div class="ai-name">Research Fit</div>'
        f'<div class="ai-num">{r}</div><div class="ai-status">● {vr}</div>'
        f'<div class="ai-judge">依据你是否在画像中体现科研/项目经历评估。</div>'
        f'<div class="ai-bar"><i style="width:{r}%"></i></div></div>'
        f'<div class="card ai b3"><span class="glow"></span><div class="ai-name">Competition</div>'
        f'<div class="ai-num small">{c}</div><div class="ai-status">● {"Competitive" if c=="HIGH" else "Standard"}</div>'
        f'<div class="ai-judge">依据目标院校层级（顶尖名校记为 HIGH）。</div>'
        f'<div class="ai-bar"><i style="width:{c_pct}%"></i></div></div>'
        f'</div></section>'
        f'<section class="block reveal"><span class="eyebrow-sec">AI Recommendation</span>'
        f'<div class="sec-head"><h2>What to do next</h2><span class="tag">Generated by StudyPath</span></div>'
        f'{rec}</section>'
        f'<section class="block reveal"><span class="eyebrow-sec">Your Academic Journey</span>'
        f'<div class="sec-head"><h2>From profile to decision</h2><span class="tag">6-stage roadmap</span></div>'
        f'{journey}</section>'
        f'<section class="block reveal"><span class="eyebrow-sec">Global University Network</span>'
        f'<div class="sec-head"><h2>School Match · Academic Map</h2><span class="tag">Reach · Target · Safety</span></div>'
        f'{map_svg}</section>'
        f'<section class="block reveal"><span class="eyebrow-sec">Application Strategy</span>'
        f'<div class="sec-head"><h2>Three moves to strengthen</h2><span class="tag">Action plan</span></div>'
        f'{strat}</section>'
        f'{route_badge}'
        f'</div>'
    )


def consult(query: str, thread_id: str = "demo"):
    """界面入口：调用多智能体，返回 (驾驶舱 HTML, markdown 答复)。

    thread_id 默认 "demo"：整个 Gradio 实例共享一个会话历史，便于现场演示
    连续多轮指代；MemorySaver 为内存级，服务重启后历史清空。
    """
    q = (query or "").strip()
    if not q:
        return INITIAL_DASH, "_请在上方输入你的问题_"
    try:
        out = ask_multi(q, thread_id=thread_id)
        route = out.get("route", [])
        answer = out.get("answer", "")
        prof = extract_profile(q)
        # B 方案：来源直接取自召回文档的 source_url，不依赖 LLM 是否在回答里复述 URL
        sources = out.get("sources", [])
        fit = heuristic_fit(prof)
        comp = completeness(prof)
        src_html = build_sources_html(sources)
        return build_dash(prof, fit, comp, route), answer or "_（未检索到相关资料）_", src_html
    except Exception as e:
        return INITIAL_DASH, f"⚠️ 调用出错：{e}\n\n请检查网络 / DashScope key 后重试。", ""


blocks_kwargs = {"title": "StudyPath · Academic Planning Platform", "css": CABINET_CSS}
if int(gr.__version__.split(".")[0]) >= 4:
    blocks_kwargs["js"] = JS
with gr.Blocks(**blocks_kwargs) as demo:
    # 背景 / 顶部 / ⌘K / LIVE 4 个 fixed 浮动层 —— 由 JS 注入到 document.body 末尾，
    # 完全脱离 .gradio-container 堆叠上下文，绝不挡交互
    gr.HTML(HERO_HTML)        # Hero 标题区（文档流，跟着滚动）

    # 输入行 —— v1_basic 朴素写法（不挂 elem_classes / 不套 gr.Row），靠 elem_id + CSS 锁样式
    # 这样确保 Gradio 4.x 渲染的 textarea/button DOM 不被外层 CSS 破坏，能正常输入/聚焦
    query_box = gr.Textbox(
        label="Describe your profile",
        placeholder="例：GPA 3.5 托福 100 目标 CMU MSCS",
        lines=2,
        elem_id="spQuery",
    )
    submit_btn = gr.Button("Analyze →", elem_id="spBtn", variant="primary")

    dash = gr.HTML(value=INITIAL_DASH)
    answer_box = gr.Markdown(value="_等待提问，下方将显示 StudyPath 的带引用答复…_", elem_classes=["dash-markdown"])
    source_box = gr.HTML(value="")

    submit_btn.click(consult, inputs=query_box, outputs=[dash, answer_box, source_box])
    query_box.submit(consult, inputs=query_box, outputs=[dash, answer_box, source_box])

    gr.Examples(
        examples=[
            "我想申请美国 CS 硕士，GPA 3.5 托福 100，推荐哪些学校？需要准备什么文书？",
            "CMU 的 MSCS 项目申请要求和截止日期是什么？",
            "GPA 3.2 托福 95 能申到哪些英国 CS 硕士？",
        ],
        inputs=query_box,
    )


if __name__ == "__main__":
    demo.launch(server_name="127.0.0.1", server_port=7860, share=False, inbrowser=True)