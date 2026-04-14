"""
候选人自助服务门户（外部独立网站）
External Candidate Self-Service Portal — Fortune 500 Enterprise Edition
运行命令：streamlit run candidate_portal.py --server.port 8504
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import uuid, re, io
from datetime import datetime
import data_manager as dm

# ── Page config ──────────────────────────────────────────────
st.set_page_config(
    page_title="某公司内部竞聘服务中心",
    page_icon="🏢",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ── Session ───────────────────────────────────────────────────
if "sid" not in st.session_state:
    st.session_state.sid = str(uuid.uuid4())[:8]

if "visited_this_session" not in st.session_state:
    dm.record_visit(st.session_state.sid, "访问候选人门户")
    st.session_state.visited_this_session = True
 
# ── Constants ─────────────────────────────────────────────────
DEPTS = ["产品部", "技术部", "运营部", "市场部", "数据部", "设计部", "商业化部", "用研部"]
APPEAL_CATS = ["AI评分偏差", "绩效数据滞后", "笔试题目歧义", "材料未被识别", "其他"]

# ── CSS ───────────────────────────────────────────────────────
st.markdown("""
<style>
/* ── Base ─────────────────────────────────────────────────── */
html, body, [class*="css"] {
    font-family: "PingFang SC", "Microsoft YaHei", "Segoe UI",
                 -apple-system, BlinkMacSystemFont, sans-serif;
}
.stApp { background: #f5f7fa; }

p, li, .stMarkdown p, .stMarkdown li {
    font-size: 14px !important;
    line-height: 1.9 !important;
    color: #262626;
}
h1 { font-size: 22px !important; font-weight: 700 !important;
     letter-spacing: -0.3px; color: #141414 !important; }
h2 { font-size: 18px !important; font-weight: 600 !important; color: #1f1f1f !important; }
h3 { font-size: 15px !important; font-weight: 600 !important; color: #333 !important; }
h4 { font-size: 13.5px !important; font-weight: 600 !important; }

/* ── Portal Header ────────────────────────────────────────── */
.portal-header {
    background: linear-gradient(135deg, #001d6c 0%, #0050b3 45%, #1890ff 100%);
    padding: 28px 36px 24px;
    border-radius: 16px;
    margin-bottom: 24px;
    box-shadow: 0 8px 32px rgba(0,29,108,.28);
    position: relative;
    overflow: hidden;
}
.portal-header::before {
    content: "";
    position: absolute;
    top: -40px; right: -40px;
    width: 200px; height: 200px;
    background: rgba(255,255,255,.06);
    border-radius: 50%;
}
.portal-header::after {
    content: "";
    position: absolute;
    bottom: -60px; left: 20px;
    width: 150px; height: 150px;
    background: rgba(255,255,255,.04);
    border-radius: 50%;
}
.nav-brand {
    color: white !important;
    font-size: 22px !important;
    font-weight: 700 !important;
    letter-spacing: 0.5px;
    margin: 0 0 4px;
    text-shadow: 0 1px 4px rgba(0,0,0,.3);
}
.nav-sub {
    color: rgba(255,255,255,.82) !important;
    font-size: 13px !important;
    letter-spacing: 0.3px;
    margin: 0 0 16px;
}
.nav-tag {
    display: inline-block;
    background: rgba(255,255,255,.18);
    color: white;
    font-size: 11px;
    padding: 3px 10px;
    border-radius: 20px;
    margin-right: 6px;
    border: 1px solid rgba(255,255,255,.25);
}

/* ── Hero card ────────────────────────────────────────────── */
.hero-card {
    background: white;
    border-radius: 16px;
    padding: 32px;
    box-shadow: 0 2px 16px rgba(0,0,0,.08);
    margin-bottom: 20px;
    border: 1px solid #eaeef4;
}

/* ── Stat pills ───────────────────────────────────────────── */
.stat-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: #f0f5ff;
    border: 1px solid #adc6ff;
    color: #003eb3;
    font-size: 12px;
    font-weight: 600;
    padding: 4px 12px;
    border-radius: 20px;
    margin-right: 8px;
    margin-bottom: 6px;
}

/* ── Quick action cards ───────────────────────────────────── */
.quick-card {
    background: white;
    border-radius: 14px;
    padding: 22px 20px;
    box-shadow: 0 2px 12px rgba(0,0,0,.07);
    border: 1px solid #eaeef4;
    text-align: center;
    transition: all .25s ease;
    cursor: pointer;
    height: 100%;
}
.quick-card:hover {
    box-shadow: 0 6px 24px rgba(0,0,0,.12);
    transform: translateY(-2px);
}
.quick-card.blue  { border-top: 4px solid #1890ff; }
.quick-card.green { border-top: 4px solid #52c41a; }
.quick-card.orange { border-top: 4px solid #fa8c16; }
.quick-card .qc-icon { font-size: 32px; margin-bottom: 10px; }
.quick-card .qc-title {
    font-size: 15px; font-weight: 600;
    color: #1a1a1a; margin-bottom: 6px;
}
.quick-card .qc-desc { font-size: 12px; color: #8c8c8c; line-height: 1.6; }

/* ── Notice box ───────────────────────────────────────────── */
.notice-box {
    background: #f0f7ff;
    border-left: 4px solid #1890ff;
    border-radius: 0 10px 10px 0;
    padding: 16px 20px;
    margin: 20px 0;
}
.notice-box .nb-title {
    font-size: 14px; font-weight: 600;
    color: #003eb3; margin-bottom: 8px;
}
.notice-box ul {
    margin: 0; padding-left: 18px;
}
.notice-box li {
    font-size: 13px !important;
    color: #3a3a3a !important;
    line-height: 1.8 !important;
}

/* ── Timeline steps ───────────────────────────────────────── */
.timeline-wrap { padding: 8px 0; }
.timeline-step {
    display: flex;
    align-items: flex-start;
    gap: 14px;
    margin-bottom: 4px;
    padding: 12px 0;
    border-bottom: 1px dashed #e8ecf1;
}
.timeline-step:last-child { border-bottom: none; }
.tl-circle {
    width: 32px; height: 32px;
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 13px; font-weight: 700;
    flex-shrink: 0;
    color: white;
}
.tl-circle.blue   { background: #1890ff; }
.tl-circle.green  { background: #52c41a; }
.tl-circle.gold   { background: #faad14; }
.tl-body { flex: 1; }
.tl-title { font-size: 14px; font-weight: 600; color: #1a1a1a; margin-bottom: 2px; }
.tl-days  { font-size: 12px; color: #8c8c8c; }

/* ── Contact card ─────────────────────────────────────────── */
.contact-card {
    background: linear-gradient(135deg, #f0f5ff, #e6f4ff);
    border: 1px solid #adc6ff;
    border-radius: 12px;
    padding: 18px 22px;
    margin-top: 20px;
}

/* ── Form sections ────────────────────────────────────────── */
.form-section {
    background: white;
    border-radius: 12px;
    padding: 22px 24px;
    margin-bottom: 16px;
    border: 1px solid #eaeef4;
    box-shadow: 0 1px 6px rgba(0,0,0,.05);
}
.form-section-title {
    font-size: 14px;
    font-weight: 600;
    color: #003eb3;
    border-bottom: 2px solid #e6f0ff;
    padding-bottom: 8px;
    margin-bottom: 16px;
    display: flex;
    align-items: center;
    gap: 6px;
}

/* ── Privacy box ──────────────────────────────────────────── */
.privacy-box {
    background: #fafafa;
    border: 1px solid #d9d9d9;
    border-radius: 8px;
    padding: 14px 18px;
    margin: 12px 0;
    font-size: 12px !important;
    color: #595959 !important;
    line-height: 1.8 !important;
}

/* ── Status track (appeal progress) ───────────────────────── */
.status-track {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0;
    padding: 24px 0;
    margin: 16px 0;
}
.st-node {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
    flex: 1;
    position: relative;
}
.st-dot {
    width: 36px; height: 36px;
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 16px; z-index: 2;
    border: 3px solid transparent;
}
.st-dot.done    { background: #52c41a; border-color: #b7eb8f; color: white; }
.st-dot.active  { background: #1890ff; border-color: #91caff; color: white;
                  box-shadow: 0 0 0 4px rgba(24,144,255,.2); }
.st-dot.pending { background: #f0f0f0; border-color: #d9d9d9; color: #bfbfbf; }
.st-label {
    font-size: 12px; font-weight: 600;
    color: #595959; text-align: center;
    white-space: nowrap;
}
.st-line {
    height: 3px; flex: 1;
    background: #f0f0f0;
    margin-top: -28px; z-index: 1;
}
.st-line.done { background: #52c41a; }

/* ── Submit success card ──────────────────────────────────── */
.submit-success {
    background: #f6ffed;
    border: 1px solid #b7eb8f;
    border-radius: 12px;
    padding: 24px 28px;
    margin: 16px 0;
    text-align: center;
}
.submit-success .ss-icon  { font-size: 40px; margin-bottom: 8px; }
.submit-success .ss-title { font-size: 17px; font-weight: 700; color: #135200; }
.submit-success .ss-id    {
    display: inline-block;
    background: #52c41a;
    color: white;
    font-size: 15px; font-weight: 700;
    padding: 4px 16px; border-radius: 20px;
    margin: 8px 0;
    letter-spacing: 1px;
}
.submit-success .ss-note  { font-size: 13px; color: #389e0d; margin-top: 8px; }

/* ── Badges ───────────────────────────────────────────────── */
.badge-green  { display:inline-block; background:#f6ffed; color:#135200;
                border:1px solid #b7eb8f; border-radius:20px;
                padding:2px 12px; font-size:12px; font-weight:600; }
.badge-yellow { display:inline-block; background:#fffbe6; color:#874d00;
                border:1px solid #ffe58f; border-radius:20px;
                padding:2px 12px; font-size:12px; font-weight:600; }
.badge-red    { display:inline-block; background:#fff1f0; color:#820014;
                border:1px solid #ffa39e; border-radius:20px;
                padding:2px 12px; font-size:12px; font-weight:600; }
.badge-blue   { display:inline-block; background:#e6f4ff; color:#003eb3;
                border:1px solid #91caff; border-radius:20px;
                padding:2px 12px; font-size:12px; font-weight:600; }
.badge-gray   { display:inline-block; background:#f5f5f5; color:#595959;
                border:1px solid #d9d9d9; border-radius:20px;
                padding:2px 12px; font-size:12px; font-weight:600; }

/* ── Rules box ────────────────────────────────────────────── */
.rules-box {
    background: white;
    border-radius: 12px;
    padding: 20px 24px;
    border: 1px solid #eaeef4;
    box-shadow: 0 1px 6px rgba(0,0,0,.05);
}
.rules-item {
    display: flex;
    gap: 12px;
    padding: 10px 0;
    border-bottom: 1px solid #f0f0f0;
    align-items: flex-start;
}
.rules-item:last-child { border-bottom: none; }
.rules-num {
    width: 24px; height: 24px;
    background: #003eb3; color: white;
    border-radius: 50%; font-size: 12px; font-weight: 700;
    display: flex; align-items: center; justify-content: center;
    flex-shrink: 0; margin-top: 2px;
}
.rules-text { font-size: 13.5px; color: #3a3a3a; line-height: 1.7; }
.rules-label { font-weight: 600; }

/* ── Appeal info box ──────────────────────────────────────── */
.appeal-info-box {
    background: white;
    border-radius: 12px;
    padding: 22px 26px;
    border: 1px solid #eaeef4;
    box-shadow: 0 1px 6px rgba(0,0,0,.05);
    margin-bottom: 20px;
}
.appeal-info-title {
    font-size: 15px; font-weight: 700;
    color: #0050b3; margin-bottom: 14px;
    padding-bottom: 10px;
    border-bottom: 2px solid #e6f0ff;
}
.appeal-row {
    display: flex; gap: 10px; margin-bottom: 8px;
    align-items: flex-start;
}
.appeal-tag {
    font-size: 11px; font-weight: 700;
    padding: 2px 8px; border-radius: 4px;
    white-space: nowrap; flex-shrink: 0; margin-top: 2px;
}
.appeal-tag.valid   { background: #f6ffed; color: #135200; border: 1px solid #b7eb8f; }
.appeal-tag.invalid { background: #fff1f0; color: #820014; border: 1px solid #ffa39e; }
.appeal-tag.info    { background: #e6f4ff; color: #003eb3; border: 1px solid #91caff; }
.appeal-row-text { font-size: 13px; color: #595959; line-height: 1.8; }

/* ── HR comment box ───────────────────────────────────────── */
.hr-comment {
    background: #f9f0ff;
    border-left: 4px solid #722ed1;
    border-radius: 0 10px 10px 0;
    padding: 14px 18px;
    margin-top: 12px;
}
.hr-comment-title { font-size: 12px; font-weight: 600; color: #722ed1; margin-bottom: 6px; }
.hr-comment-text  { font-size: 13px; color: #3a3a3a; line-height: 1.7; }

/* ── Footer ───────────────────────────────────────────────── */
.footer-bar {
    background: white;
    border-top: 1px solid #eaeef4;
    border-radius: 12px;
    padding: 18px 24px;
    margin-top: 40px;
    text-align: center;
    box-shadow: 0 -1px 8px rgba(0,0,0,.04);
}
.footer-bar p {
    font-size: 12px !important;
    color: #8c8c8c !important;
    line-height: 1.8 !important;
    margin: 2px 0 !important;
}
.footer-link {
    color: #1890ff !important;
    text-decoration: none;
}

/* ── Metric containers ────────────────────────────────────── */
div[data-testid="metric-container"] {
    background: white;
    border: 1px solid #e6eaf0;
    border-radius: 12px;
    padding: 16px 20px;
    box-shadow: 0 1px 6px rgba(0,0,0,.06);
}
[data-testid="stMetricValue"] { font-size: 26px !important; font-weight: 700 !important; }
[data-testid="stMetricLabel"] { font-size: 12px !important; color: #595959 !important; }

/* ── Tabs ─────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
    gap: 4px;
    background: white;
    border-radius: 12px 12px 0 0;
    padding: 6px 6px 0;
    border-bottom: 2px solid #e8ecf4;
}
.stTabs [data-baseweb="tab"] {
    font-size: 13px !important;
    font-weight: 500;
    border-radius: 8px 8px 0 0;
    padding: 8px 14px;
    color: #595959;
}
.stTabs [aria-selected="true"] {
    background: #e6f4ff !important;
    color: #0050b3 !important;
    font-weight: 600 !important;
}
.stTabs [data-baseweb="tab-panel"] {
    background: white;
    border-radius: 0 0 12px 12px;
    padding: 20px;
    border: 1px solid #e8ecf4;
    border-top: none;
}

/* ── Expander ─────────────────────────────────────────────── */
.streamlit-expanderHeader {
    font-size: 14px !important;
    font-weight: 600 !important;
    color: #1a1a1a !important;
}

/* ── Buttons ──────────────────────────────────────────────── */
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #0050b3, #1890ff) !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
}
.stButton > button[kind="primary"]:hover {
    box-shadow: 0 4px 16px rgba(24,144,255,.4) !important;
    transform: translateY(-1px);
}

/* ── Search input ─────────────────────────────────────────── */
.search-wrap {
    position: relative;
}
</style>
""", unsafe_allow_html=True)

# ── Header ─────────────────────────────────────────────────────
st.markdown("""
<div class="portal-header">
    <p class="nav-brand">🏢 某公司内部竞聘服务中心</p>
    <p class="nav-sub">XXX Company Internal Talent Competition Portal</p>
    <span class="nav-tag">2025竞聘季</span>
    <span class="nav-tag">产品经理 · 50个名额</span>
    <span class="nav-tag">结果公示中</span>
</div>
""", unsafe_allow_html=True)

# ── Navigation Tabs ─────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "🏠 服务中心",
    "📤 在线投递",
    "🔍 查询报告",
    "📣 提交申诉",
    "📌 申诉进度",
    "📖 须知与政策",
])

# ══════════════════════════════════════════════════════════════════
# TAB 1 · 服务中心
# ══════════════════════════════════════════════════════════════════
with tab1:
    

    # Stats
    df_c = dm.load_candidates()
    total_cands = len(df_c) if df_c is not None else 0
    subs        = dm.load_submissions()
    total_subs  = len(subs)

    # Welcome hero
    st.markdown(f"""
<div class="hero-card">
    <h2 style="color:#001d6c;margin-top:0;">👋 欢迎使用某公司内部竞聘服务中心</h2>
    <p style="color:#595959;font-size:14px;">
        本平台为 2025 年内部产品经理竞聘提供全流程自助服务，包括在线投递、报告查询、申诉提交及进度跟踪。
        所有数据均经加密处理，严格保护您的个人隐私。
    </p>
    <div style="margin-top:16px;">
        <span class="stat-pill">👥 参与人数 {total_cands + total_subs}</span>
        <span class="stat-pill">📋 开放名额 50</span>
        <span class="stat-pill">📅 截止日期 2025-07-14</span>
        <span class="stat-pill">⚡ 申诉窗口 48h</span>
    </div>
</div>
""", unsafe_allow_html=True)

    # Quick action cards
    st.markdown("#### 🚀 快速入口")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("""
<div class="quick-card blue">
    <div class="qc-icon">📊</div>
    <div class="qc-title">查询竞聘报告</div>
    <div class="qc-desc">输入员工编号，即时获取您的 AI 综合评分与能力发展报告</div>
</div>
""", unsafe_allow_html=True)
    with c2:
        st.markdown("""
<div class="quick-card green">
    <div class="qc-icon">📤</div>
    <div class="qc-title">在线投递简历</div>
    <div class="qc-desc">填写竞聘信息并上传简历，HR 将在 3 个工作日内完成审核</div>
</div>
""", unsafe_allow_html=True)
    with c3:
        st.markdown("""
<div class="quick-card orange">
    <div class="qc-icon">📣</div>
    <div class="qc-title">提交竞聘申诉</div>
    <div class="qc-desc">如对评分结果有异议，可在公示后 48 小时内通过本平台提交申诉</div>
</div>
""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Important notices
    st.markdown("""
<div class="notice-box">
    <div class="nb-title">📢 重要公告</div>
    <ul>
        <li>竞聘结果已于 2025-07-13 正式公示，请及时登录查询您的评审报告</li>
        <li>申诉受理窗口为公示后 <strong>48 小时内</strong>（截止 2025-07-15 18:00）</li>
        <li>本平台严格遵守《个人信息保护法》，所有信息仅用于本次竞聘</li>
        <li>如遇技术问题，请联系 <strong>hr-ai@XXX Company.com</strong>（工作日 9:00–18:00）</li>
        <li>评审区间说明：绿区 ≥73分自动通过 / 黄区 67-73分人工复核 / 红区 &lt;67分淘汰</li>
    </ul>
</div>
""", unsafe_allow_html=True)

    # Timeline
    st.markdown("#### 📅 竞聘流程时间轴")
    st.markdown("""
<div class="timeline-wrap">
    <div class="timeline-step">
        <div class="tl-circle blue">AI</div>
        <div class="tl-body">
            <div class="tl-title">第 1–7 天 · AI 智能初筛</div>
            <div class="tl-days">
                系统自动计算综合得分（岗位匹配40% + 绩效30% + 笔试30%），生成能力发展报告，完成绿/黄/红区划定
            </div>
        </div>
    </div>
    <div class="timeline-step">
        <div class="tl-circle gold">HR</div>
        <div class="tl-body">
            <div class="tl-title">第 8–12 天 · HR 人工复核</div>
            <div class="tl-days">
                黄区候选人由 HR 逐一审阅，综合考量情境因素，可调整评审结论；申诉案件同步处理
            </div>
        </div>
    </div>
    <div class="timeline-step">
        <div class="tl-circle green">✓</div>
        <div class="tl-body">
            <div class="tl-title">第 13–14 天 · 结果公示</div>
            <div class="tl-days">
                在本平台发布最终竞聘结果，48 小时内受理申诉，通过申诉者可进入下一轮评审
            </div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

    # Contact footer card
    st.markdown("""
<div class="contact-card">
    <strong style="color:#003eb3;font-size:14px;">📞 联系我们</strong>
    <p style="margin:8px 0 0;font-size:13px;color:#595959;">
        邮箱：<strong>hr-ai@XXX Company.com</strong> &nbsp;|&nbsp;
        工作时间：<strong>周一至周五 9:00–18:00</strong> &nbsp;|&nbsp;
        某公司科技（深圳）有限公司 人力资源部
    </p>
</div>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════
# TAB 2 · 在线投递
# ══════════════════════════════════════════════════════════════════
with tab2:
    

    st.markdown("### 📤 在线投递竞聘申请")
    st.markdown('<p style="color:#8c8c8c;font-size:13px;">请如实填写以下信息，HR 将在 3 个工作日内完成审核并发送结果通知。</p>', unsafe_allow_html=True)

    # Check for existing submission (preview check — before full form)
    with st.container():
        st.markdown('<div class="form-section">', unsafe_allow_html=True)
        st.markdown('<div class="form-section-title">👤 基本信息</div>', unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        name_input   = col1.text_input("姓名 *", placeholder="请输入真实姓名", key="sub_name")
        emp_id_input = col2.text_input("员工编号 *", placeholder="EMP10001", key="sub_empid")

        col3, col4 = st.columns(2)
        dept_input  = col3.selectbox("当前部门 *", DEPTS, key="sub_dept")
        years_input = col4.number_input("司龄（年）*", min_value=0.5, max_value=20.0,
                                         value=3.0, step=0.5, key="sub_years")
        st.markdown('</div>', unsafe_allow_html=True)

    # Check if already submitted
    _existing_subs = dm.load_submissions()
    _already_submitted = emp_id_input and any(
        s.get("emp_id") == emp_id_input for s in _existing_subs.values()
    )

    if _already_submitted:
        _my_sub_id = next(
            (sid for sid, s in _existing_subs.items() if s.get("emp_id") == emp_id_input), None
        )
        st.markdown(f"""
<div style="background:#e6f4ff;border:1px solid #91caff;border-radius:12px;
     padding:20px 24px;margin:16px 0;text-align:center;">
    <div style="font-size:28px;margin-bottom:8px;">ℹ️</div>
    <div style="font-size:16px;font-weight:700;color:#003eb3;">您已成功投递</div>
    <div style="margin:10px 0;">
        <span style="background:#1890ff;color:white;font-size:14px;font-weight:700;
              padding:4px 16px;border-radius:20px;letter-spacing:1px;">{_my_sub_id}</span>
    </div>
    <div style="font-size:13px;color:#0050b3;margin-top:8px;">
        请耐心等待 HR 审核，通常在 <strong>3 个工作日</strong>内完成。如有疑问请联系 hr-ai@XXX Company.com
    </div>
</div>
""", unsafe_allow_html=True)
    else:
        # Full form
        st.markdown('<div class="form-section">', unsafe_allow_html=True)
        st.markdown('<div class="form-section-title">✍️ 竞聘自述（300字以内）</div>', unsafe_allow_html=True)
        statement_input = st.text_area(
            "请简述您的竞聘优势和职业规划",
            placeholder="请描述您申请该岗位的核心竞争力、过往相关经验及未来发展规划（300字以内）…",
            max_chars=300,
            height=140,
            key="sub_statement",
            label_visibility="collapsed"
        )
        char_count = len(statement_input) if statement_input else 0
        st.caption(f"已输入 {char_count} / 300 字")
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="form-section">', unsafe_allow_html=True)
        st.markdown('<div class="form-section-title">📎 简历上传</div>', unsafe_allow_html=True)
        resume_file = st.file_uploader(
            "上传简历文件（支持 PDF / DOCX / TXT，建议不超过 5MB）",
            type=["pdf", "docx", "txt"],
            key="sub_resume"
        )
        if resume_file:
            st.success(f"已选择：{resume_file.name}（{resume_file.size // 1024} KB）")
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="form-section">', unsafe_allow_html=True)
        st.markdown('<div class="form-section-title">📊 自评分（供参考）</div>', unsafe_allow_html=True)
        st.caption("以下分数仅供 HR 参考，最终评分以系统数据为准。")
        ss1, ss2, ss3 = st.columns(3)
        pm_score = ss1.slider("岗位匹配度", 0, 100, 70, key="sub_pm")
        pe_score = ss2.slider("历史绩效", 0, 100, 75, key="sub_pe")
        wt_score = ss3.slider("笔试成绩", 0, 100, 68, key="sub_wt")
        st.markdown('</div>', unsafe_allow_html=True)

        # Privacy & consent
        st.markdown('<div class="privacy-box">', unsafe_allow_html=True)
        st.markdown("""
**《个人信息收集与使用声明》摘要**

某公司科技（深圳）有限公司将收集您的姓名、员工编号、部门、工龄、评分数据、简历文件及竞聘自述，
仅用于本次内部竞聘评审、能力报告生成及申诉处理。数据加密存储于公司内部服务器，
不对外共享，竞聘结束后 6 个月依法删除。完整声明请查阅「须知与政策」页面。
""")
        st.markdown('</div>', unsafe_allow_html=True)

        consent_privacy  = st.checkbox("我已阅读并同意《个人信息收集与使用声明》", key="sub_consent1")
        consent_accurate = st.checkbox("我确认以上信息真实准确，如有虚假将承担相应后果", key="sub_consent2")

        # Validate
        _can_submit = (
            bool(name_input.strip()) and
            bool(emp_id_input.strip()) and
            consent_privacy and
            consent_accurate
        )

        if not _can_submit:
            _hint = []
            if not name_input.strip():   _hint.append("姓名")
            if not emp_id_input.strip(): _hint.append("员工编号")
            if not consent_privacy:      _hint.append("隐私声明同意")
            if not consent_accurate:     _hint.append("信息准确确认")
            if _hint:
                st.caption(f"请完善以下必填项：{'、'.join(_hint)}")

        if st.button("📤 提交竞聘申请", type="primary",
                     disabled=not _can_submit, use_container_width=True):
            _subs = dm.load_submissions()
            _sub_id = f"SUB{len(_subs) + 2001}"
            _subs[_sub_id] = {
                "name":        name_input.strip(),
                "emp_id":      emp_id_input.strip(),
                "dept":        dept_input,
                "years":       years_input,
                "statement":   statement_input,
                "resume_file": resume_file.name if resume_file else "",
                "pm_score":    pm_score,
                "pe_score":    pe_score,
                "wt_score":    wt_score,
                "submitted":   datetime.now().strftime("%Y-%m-%d %H:%M"),
                "status":      "待审核",
            }
            dm.save_submissions(_subs)
            
            st.markdown(f"""
<div class="submit-success">
    <div class="ss-icon">🎉</div>
    <div class="ss-title">投递成功！</div>
    <div><span class="ss-id">{_sub_id}</span></div>
    <div class="ss-note">请保存您的投递编号，HR 将在 3 个工作日内完成审核并通知您结果。</div>
</div>
""", unsafe_allow_html=True)
            st.balloons()
            st.rerun()

# ══════════════════════════════════════════════════════════════════
# TAB 3 · 查询报告
# ══════════════════════════════════════════════════════════════════
with tab3:
    

    st.markdown("### 🔍 竞聘评审报告查询")
    st.markdown('<p style="color:#8c8c8c;font-size:13px;">请输入员工编号或姓名以查询您的竞聘评审报告。</p>', unsafe_allow_html=True)

    _df = dm.load_candidates()

    if _df is None:
        st.warning("⚠️ 竞聘数据尚未发布，请关注官方公告。")
    else:
        # Search box
        st.markdown("""
<div style="position:relative;margin-bottom:4px;">
    <span style="position:absolute;left:12px;top:50%;transform:translateY(-50%);
                 font-size:16px;z-index:10;pointer-events:none;margin-top:4px;">🔍</span>
</div>
""", unsafe_allow_html=True)
        query = st.text_input("搜索员工编号或姓名",
                              placeholder="请输入员工编号（如 EMP10001）或真实姓名…",
                              key="report_query",
                              label_visibility="collapsed")

        if query:
            _mask = (
                _df.get("候选人", pd.Series(dtype=str)).astype(str).str.contains(query, na=False) |
                _df.get("员工编号", pd.Series(dtype=str)).astype(str).str.contains(query, na=False)
            )
            _results = _df[_mask]
        else:
            _results = pd.DataFrame()

        if query and _results.empty:
            st.markdown("""
<div style="background:#fff1f0;border:1px solid #ffa39e;border-radius:10px;
     padding:16px 20px;margin:12px 0;text-align:center;">
    <div style="font-size:24px;margin-bottom:6px;">🔍</div>
    <div style="font-size:14px;font-weight:600;color:#820014;">未找到匹配记录</div>
    <div style="font-size:12px;color:#cf1322;margin-top:4px;">
        请核对员工编号或姓名是否正确，如有疑问请联系 hr-ai@XXX Company.com
    </div>
</div>
""", unsafe_allow_html=True)

        elif not _results.empty:
            for _, row in _results.iterrows():
                score_cols = [c for c in ["岗位匹配度","历史绩效","笔试成绩"] if c in row.index]
                _weights = [0.4, 0.3, 0.3]
                total_score = sum(
                    float(row.get(c, 0)) * w for c, w in zip(["岗位匹配度","历史绩效","笔试成绩"], _weights)
                    if c in row.index
                ) if score_cols else 0

                zone = row.get("评审区间", "")
                if not zone:
                    zone = "绿区" if total_score >= 73 else ("黄区" if total_score >= 67 else "红区")

                badge_cls = {"绿区": "badge-green", "黄区": "badge-yellow", "红区": "badge-red"}.get(zone, "badge-gray")
                zone_icon = {"绿区": "✅", "黄区": "⚠️", "红区": "❌"}.get(zone, "⚪")

                st.markdown(f"""
<div class="hero-card" style="margin-top:12px;">
    <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:12px;">
        <div>
            <div style="font-size:18px;font-weight:700;color:#1a1a1a;">{row.get('候选人','—')}</div>
            <div style="font-size:13px;color:#8c8c8c;margin-top:2px;">{row.get('员工编号','—')} · {row.get('当前部门','—')} · 工龄 {row.get('工龄(年)','?')} 年</div>
        </div>
        <div style="text-align:right;">
            <div style="font-size:28px;font-weight:800;color:#1890ff;">{total_score:.1f}</div>
            <div style="font-size:11px;color:#8c8c8c;">综合得分</div>
            <span class="{badge_cls}" style="margin-top:4px;">{zone_icon} {zone}</span>
        </div>
    </div>
    <hr style="border:none;border-top:1px solid #f0f0f0;margin:16px 0;">
    <div style="display:flex;gap:20px;flex-wrap:wrap;">
        <div style="text-align:center;flex:1;min-width:80px;">
            <div style="font-size:20px;font-weight:700;color:#0050b3;">{float(row.get('岗位匹配度',0)):.0f}</div>
            <div style="font-size:11px;color:#8c8c8c;">岗位匹配度<br><span style="color:#003eb3;font-weight:600;">×40%</span></div>
        </div>
        <div style="text-align:center;flex:1;min-width:80px;">
            <div style="font-size:20px;font-weight:700;color:#389e0d;">{float(row.get('历史绩效',0)):.0f}</div>
            <div style="font-size:11px;color:#8c8c8c;">历史绩效<br><span style="color:#389e0d;font-weight:600;">×30%</span></div>
        </div>
        <div style="text-align:center;flex:1;min-width:80px;">
            <div style="font-size:20px;font-weight:700;color:#d46b08;">{float(row.get('笔试成绩',0)):.0f}</div>
            <div style="font-size:11px;color:#8c8c8c;">笔试成绩<br><span style="color:#d46b08;font-weight:600;">×30%</span></div>
        </div>
        <div style="text-align:center;flex:1;min-width:80px;">
            <div style="font-size:20px;font-weight:700;color:#595959;">第 {int(row.get('排名', 0)) if '排名' in row.index else '—'} 名</div>
            <div style="font-size:11px;color:#8c8c8c;">全体排名</div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

                # Radar chart
                if score_cols:
                    with st.expander("📊 能力雷达图", expanded=True):
                        cats = ["岗位匹配度", "历史绩效", "笔试成绩"]
                        vals = [float(row.get(c, 0)) for c in cats]
                        fig = go.Figure(go.Scatterpolar(
                            r=vals + [vals[0]],
                            theta=cats + [cats[0]],
                            fill="toself",
                            fillcolor="rgba(24,144,255,0.15)",
                            line=dict(color="#1890ff", width=2),
                            marker=dict(size=6, color="#1890ff"),
                            name=str(row.get("候选人", ""))
                        ))
                        fig.update_layout(
                            polar=dict(
                                radialaxis=dict(visible=True, range=[0, 100],
                                                tickfont=dict(size=10), gridcolor="#e8ecf4"),
                                angularaxis=dict(tickfont=dict(size=12))
                            ),
                            showlegend=False,
                            margin=dict(l=40, r=40, t=20, b=20),
                            height=280
                        )
                        st.plotly_chart(fig, use_container_width=True)

                # Report section
                _reports = dm.load_reports()
                _emp_id  = str(row.get("员工编号", ""))
                _report_txt = _reports.get(_emp_id, {}).get("report", "")

                if _report_txt:
                    with st.expander("📄 查看完整能力发展报告"):
                        st.markdown(f"""
<div style="background:white;border:1px solid #eaeef4;border-radius:10px;
     padding:24px;line-height:2.0;font-size:13.5px;color:#2a2a2a;">
{_report_txt}
</div>
""", unsafe_allow_html=True)
                        _buf = io.BytesIO(_report_txt.encode("utf-8"))
                        st.download_button(
                            "⬇️ 下载报告（TXT）",
                            data=_buf,
                            file_name=f"竞聘报告_{row.get('候选人','candidate')}.txt",
                            mime="text/plain"
                        )
                else:
                    st.info("📋 您的个性化能力发展报告尚未生成，请稍后再次查询。")

        else:
            st.markdown("""
<div style="background:#fafafa;border:1px dashed #d9d9d9;border-radius:12px;
     padding:32px;text-align:center;margin-top:12px;">
    <div style="font-size:36px;margin-bottom:8px;">🔎</div>
    <div style="font-size:14px;color:#8c8c8c;">请在上方搜索框输入您的员工编号或姓名</div>
</div>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════
# TAB 4 · 提交申诉
# ══════════════════════════════════════════════════════════════════
with tab4:
   

    st.markdown("### 📣 提交竞聘申诉")

    # Appeal rules notice
    st.info("""
**📝 申诉须知与规则**：

1. **申诉时效**：申诉结果将在提交后的 3-5 个工作日内反馈。
2. **申诉范围**：本次竞聘评审结果由**某公司**人力资源部最终核准，申诉仅针对流程合规性及数据统计错误，不涉及评分标准的重新裁定。
3. **信息核实**：请务必填写真实有效的联系方式与详细申诉理由，以便工作人员快速定位问题并核实。
""")

    # Appeal form
    st.markdown('<div class="form-section">', unsafe_allow_html=True)
    st.markdown('<div class="form-section-title">📝 申诉信息填写</div>', unsafe_allow_html=True)

    a_col1, a_col2 = st.columns(2)
    a_name   = a_col1.text_input("姓名 *", key="ap_name", placeholder="真实姓名")
    a_emp_id = a_col2.text_input("员工编号 *", key="ap_empid", placeholder="EMP10001")
    a_cat    = st.selectbox("申诉类型 *", APPEAL_CATS, key="ap_cat")
    a_detail = st.text_area(
        "申诉详情 *",
        placeholder="请详细描述您的申诉理由，说明具体的分项、数据或材料问题（建议200字以上）…",
        height=160, key="ap_detail"
    )
    a_evidence = st.text_area(
        "支持证据（可选）",
        placeholder="如有相关数据截图说明、文档参考等，请在此补充描述…",
        height=80, key="ap_evidence"
    )
    st.markdown('</div>', unsafe_allow_html=True)

    _can_appeal = bool(a_name.strip()) and bool(a_emp_id.strip()) and bool(a_detail.strip())

    if st.button("📩 提交申诉", type="primary",
                 disabled=not _can_appeal, use_container_width=True):
        _appeals = dm.load_appeals()
        _ap_id   = f"AP{len(_appeals) + 3001}"
        _appeals[_ap_id] = {
            "name":     a_name.strip(),
            "emp_id":   a_emp_id.strip(),
            "category": a_cat,
            "detail":   a_detail.strip(),
            "evidence": a_evidence.strip(),
            "submitted": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "status":   "待受理",
            "hr_comment": "",
        }
        dm.save_appeals(_appeals)
    
        st.markdown(f"""
<div class="submit-success">
    <div class="ss-icon">✉️</div>
    <div class="ss-title">申诉已成功提交！</div>
    <div><span class="ss-id">{_ap_id}</span></div>
    <div class="ss-note">HR 将在 3 个工作日内书面回复，请保存您的申诉编号。</div>
</div>
""", unsafe_allow_html=True)

    if not _can_appeal and (a_name or a_emp_id or a_detail):
        _hint = []
        if not a_name.strip():   _hint.append("姓名")
        if not a_emp_id.strip(): _hint.append("员工编号")
        if not a_detail.strip(): _hint.append("申诉详情")
        st.caption(f"请完善必填项：{'、'.join(_hint)}")

# ══════════════════════════════════════════════════════════════════
# TAB 5 · 申诉进度
# ══════════════════════════════════════════════════════════════════
with tab5:
    

    st.markdown("### 📌 申诉进度查询")
    st.markdown('<p style="color:#8c8c8c;font-size:13px;">请输入员工编号以查询您的申诉处理进度。</p>', unsafe_allow_html=True)

    prog_query = st.text_input(
        "员工编号",
        placeholder="EMP10001",
        key="prog_query",
        label_visibility="collapsed"
    )

    if prog_query:
        _appeals = dm.load_appeals()
        _my_appeals = {k: v for k, v in _appeals.items()
                       if v.get("emp_id") == prog_query.strip()}

        if not _my_appeals:
            st.markdown("""
<div style="background:#fffbe6;border:1px solid #ffe58f;border-radius:10px;
     padding:18px 22px;text-align:center;margin:12px 0;">
    <div style="font-size:24px;margin-bottom:6px;">📭</div>
    <div style="font-size:14px;font-weight:600;color:#874d00;">未找到申诉记录</div>
    <div style="font-size:12px;color:#ad6800;margin-top:4px;">
        请核对员工编号，或确认您是否已提交过申诉
    </div>
</div>
""", unsafe_allow_html=True)
        else:
            for ap_id, ap in sorted(_my_appeals.items(),
                                    key=lambda x: x[1]["submitted"], reverse=True):
                status = ap.get("status", "待受理")

                # Determine step
                step_map = {"待受理": 0, "受理中": 1, "已结案": 2}
                cur_step = step_map.get(status, 0)

                def _dot_cls(i, cur=cur_step):
                    if i < cur: return "done"
                    if i == cur: return "active"
                    return "pending"

                def _dot_icon(i, cur=cur_step):
                    if i < cur: return "✓"
                    if i == cur: return str(i+1)
                    return str(i+1)

                def _line_cls(i, cur=cur_step):
                    return "done" if i < cur else ""

                st.markdown(f"""
<div class="hero-card" style="margin-top:12px;">
    <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
        <div>
            <span class="badge-blue" style="font-size:13px;padding:3px 14px;">{ap_id}</span>
            <span style="margin-left:10px;font-size:14px;font-weight:600;color:#1a1a1a;">{ap.get('category','—')}</span>
        </div>
        <div style="font-size:12px;color:#8c8c8c;">{ap.get('submitted','—')}</div>
    </div>
    <div class="status-track">
        <div class="st-node">
            <div class="st-dot {_dot_cls(0)}">{_dot_icon(0)}</div>
            <div class="st-label">已提交</div>
        </div>
        <div class="st-line {_line_cls(0)}"></div>
        <div class="st-node">
            <div class="st-dot {_dot_cls(1)}">{_dot_icon(1)}</div>
            <div class="st-label">受理中</div>
        </div>
        <div class="st-line {_line_cls(1)}"></div>
        <div class="st-node">
            <div class="st-dot {_dot_cls(2)}">{_dot_icon(2)}</div>
            <div class="st-label">已结案</div>
        </div>
    </div>
    <div style="font-size:13px;color:#595959;margin-top:4px;">
        <strong>申诉详情：</strong>{ap.get('detail','—')[:150]}{'…' if len(ap.get('detail',''))>150 else ''}
    </div>
""", unsafe_allow_html=True)

                if ap.get("hr_comment"):
                    st.markdown(f"""
    <div class="hr-comment">
        <div class="hr-comment-title">🗒️ HR 处理意见</div>
        <div class="hr-comment-text">{ap.get('hr_comment','')}</div>
    </div>
""", unsafe_allow_html=True)
                else:
                    st.markdown("""
    <div style="font-size:12px;color:#bfbfbf;margin-top:10px;font-style:italic;">
        ⏳ HR 尚未填写处理意见，请耐心等待（3 个工作日内）
    </div>
""", unsafe_allow_html=True)

                st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.markdown("""
<div style="background:#fafafa;border:1px dashed #d9d9d9;border-radius:12px;
     padding:32px;text-align:center;margin-top:12px;">
    <div style="font-size:36px;margin-bottom:8px;">📌</div>
    <div style="font-size:14px;color:#8c8c8c;">请输入员工编号以查询您的申诉进度</div>
</div>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════
# TAB 6 · 须知与政策
# ══════════════════════════════════════════════════════════════════
with tab6:
    

    st.markdown("### 📖 须知与政策")

    with st.expander("📋 竞聘规则与须知", expanded=True):
        st.markdown("""
<div class="rules-box">
    <div class="rules-item">
        <div class="rules-num">1</div>
        <div class="rules-text">
            <span class="rules-label">竞聘岗位：</span>
            产品经理（PM），共 <strong>50 个名额</strong>，面向全公司内部员工开放
        </div>
    </div>
    <div class="rules-item">
        <div class="rules-num">2</div>
        <div class="rules-text">
            <span class="rules-label">报名资格：</span>
            司龄满 <strong>1 年</strong>、近两期绩效不低于 <strong>3 星（L3.3 以上）</strong>
        </div>
    </div>
    <div class="rules-item">
        <div class="rules-num">3</div>
        <div class="rules-text">
            <span class="rules-label">评审流程：</span>
            第 1–7 天 AI 初筛 → 第 8–12 天 HR 人工复核 → 第 13–14 天结果公示
        </div>
    </div>
    <div class="rules-item">
        <div class="rules-num">4</div>
        <div class="rules-text">
            <span class="rules-label">评分维度：</span>
            岗位匹配度（<strong>40%</strong>）+ 历史绩效（<strong>30%</strong>）+ 笔试成绩（<strong>30%</strong>）
        </div>
    </div>
    <div class="rules-item">
        <div class="rules-num">5</div>
        <div class="rules-text">
            <span class="rules-label">区间定义：</span>
            <span style="color:#135200;font-weight:600;">绿区 ≥73分</span> 自动通过 ·
            <span style="color:#874d00;font-weight:600;">黄区 67–73分</span> 人工复核 ·
            <span style="color:#820014;font-weight:600;">红区 &lt;67分</span> 淘汰
        </div>
    </div>
    <div class="rules-item">
        <div class="rules-num">6</div>
        <div class="rules-text">
            <span class="rules-label">注意事项：</span>
            不得提供虚假材料，否则<strong>取消竞聘资格</strong>且记录人事档案
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

    with st.expander("📣 申诉流程与规则"):
        st.markdown("""
<div class="rules-box">
    <div class="rules-item">
        <div class="rules-num">1</div>
        <div class="rules-text">
            <span class="rules-label">申诉窗口：</span>
            结果公示后 <strong>48 小时内</strong>（2025-07-15 18:00 截止）
        </div>
    </div>
    <div class="rules-item">
        <div class="rules-num">2</div>
        <div class="rules-text">
            <span class="rules-label">受理范围：</span>
            AI评分偏差 · 绩效数据滞后 · 笔试题目歧义 · 材料未被识别（共四类）
        </div>
    </div>
    <div class="rules-item">
        <div class="rules-num">3</div>
        <div class="rules-text">
            <span class="rules-label">申诉步骤：</span>
            填写申诉表单 → AI 自动分类 → HR 受理 → 3 个工作日内书面回复
        </div>
    </div>
    <div class="rules-item">
        <div class="rules-num">4</div>
        <div class="rules-text">
            <span class="rules-label">申诉结果：</span>
            维持原判 / 通过申诉（进入下一轮评审环节）
        </div>
    </div>
    <div class="rules-item">
        <div class="rules-num">5</div>
        <div class="rules-text">
            <span class="rules-label">重要提示：</span>
            每人<strong>仅限提交一次申诉</strong>，请确保信息完整准确，重复提交无效
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

    with st.expander("🔒 个人信息收集与使用声明"):
        st.markdown("""
<div class="privacy-box" style="font-size:13px!important;">
<strong>某公司科技（深圳）有限公司 · 个人信息收集与使用声明</strong>
<br><br>
<strong>数据控制方：</strong>某公司科技（深圳）有限公司（以下简称"公司"）
<br><br>
<strong>收集目的：</strong>仅用于本次内部竞聘评审、能力发展报告生成及申诉处理，不用于任何其他商业目的。
<br><br>
<strong>收集范围：</strong>姓名、员工编号、部门、工龄、评分数据、简历文件、竞聘自述、申诉内容及处理记录。
<br><br>
<strong>存储方式：</strong>数据经加密处理后存储于公司内部服务器，严格遵守公司数据安全规范，不对外共享、出售或转让。
<br><br>
<strong>保存期限：</strong>本次竞聘结束后 <strong>6 个月</strong>，届时将按照《个人信息保护法》相关规定予以删除。
<br><br>
<strong>您的权利：</strong>您有权随时查询、更正、删除您的个人信息，或撤回同意授权。如需行使上述权利，请联系 <strong>hr-ai@XXX Company.com</strong>。
<br><br>
<strong>同意方式：</strong>使用本平台即视为您已阅读、理解并同意本声明。如您不同意，请停止使用本平台。
<br><br>
<em style="color:#8c8c8c;">本声明最后更新日期：2025年7月1日。公司保留根据法律法规变化修订本声明的权利，修订后将在本平台公告。</em>
</div>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════
# FOOTER (always shown)
# ══════════════════════════════════════════════════════════════════
st.markdown("""
<div class="footer-bar">
    <p><strong>某公司科技（深圳）有限公司</strong> · 人力资源部 · 内部竞聘管理平台</p>
    <p>© 2025 XXX Company. All rights reserved. &nbsp;|&nbsp;
       技术支持：<strong>hr-ai@XXX Company.com</strong> &nbsp;|&nbsp;
       工作时间：周一至周五 09:00–18:00</p>
    <p style="color:#bfbfbf!important;">隐私政策 &nbsp;|&nbsp; 使用条款 &nbsp;|&nbsp; 无障碍声明</p>
</div>
""", unsafe_allow_html=True)
