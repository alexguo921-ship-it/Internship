"""
AI内部竞聘评审系统 v2.1
腾讯AIHR面试作品 · 项目运营方视角
新增：简历批量导入 | 员工信息与多人对比 | 细化能力报告+PDF/Word下载 | 申诉通道
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import io, json, re
from datetime import datetime
from anthropic import Anthropic

# ── Optional dependencies ────────────────────────────────────────────────────
try:
    import pdfplumber;  HAS_PDF = True
except ImportError:
    HAS_PDF = False

try:
    from docx import Document as DocxDoc
    from docx.shared import Pt, RGBColor, Cm
    from docx.oxml.ns import qn as _qn
    HAS_DOCX = True
except ImportError:
    HAS_DOCX = False

try:
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.lib.colors import HexColor, black
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AI内部竞聘评审系统",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
.stApp { background-color: #f5f7fa; }
div[data-testid="metric-container"] {
    background: white; border: 1px solid #e8ecf0;
    border-radius: 12px; padding: 16px 20px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.05);
}
.card {
    background: white; border: 1px solid #e8ecf0;
    border-radius: 12px; padding: 22px 26px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.05); margin-bottom: 12px;
}
.report-box {
    background: white; border: 1px solid #e8ecf0;
    border-radius: 12px; padding: 28px 32px;
    line-height: 1.95; font-size: 14px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.05);
}
.badge-green  { background:#f6ffed; color:#389e0d; border:1px solid #b7eb8f;
                padding:2px 10px; border-radius:20px; font-size:12px; font-weight:600;}
.badge-yellow { background:#fffbe6; color:#d48806; border:1px solid #ffe58f;
                padding:2px 10px; border-radius:20px; font-size:12px; font-weight:600;}
.badge-red    { background:#fff2f0; color:#cf1322; border:1px solid #ffa39e;
                padding:2px 10px; border-radius:20px; font-size:12px; font-weight:600;}
</style>
""", unsafe_allow_html=True)

# ── Constants ────────────────────────────────────────────────────────────────
SURNAMES = list("张李王刘陈杨黄赵周吴徐孙马朱胡林郭何高罗")
GIVEN    = ["伟","芳","娜","敏","静","丽","强","磊","洋","艳","勇","军","杰","涛",
            "明","超","霞","平","刚","玲","华","辉","飞","云","红","建","宇","鑫","斌","梅"]
DEPTS    = ["产品部","技术部","运营部","市场部","数据部","设计部","商业化部","用研部"]
DEPT_P   = [0.10,0.22,0.18,0.14,0.13,0.08,0.08,0.07]

RESOURCES = {
    "岗位匹配度": [
        ("腾讯内部·PM成长路径手册（必读）",        "https://iwiki.woa.com/p/pm-growth-path"),
        ("腾讯课堂·产品经理核心技能训练营（6h）",    "https://ke.qq.com/course/5982909"),
        ("极客时间·产品思维与产品管理实战专栏",      "https://time.geekbang.org/column/intro/100003101"),
        ("人人都是产品经理·需求分析与功能设计指南",   "https://www.woshipm.com/pmd/5847200.html"),
    ],
    "历史绩效": [
        ("腾讯内部·OKR设定与绩效复盘方法论",        "https://km.woa.com/articles/show/okr-guide"),
        ("腾讯内部·绩效提升工作坊（每季度开放报名）", "https://talent.tencent.com/training/performance"),
        ("极客时间·高效工作法与个人效能提升专栏",    "https://time.geekbang.org/column/intro/100018401"),
    ],
    "笔试成绩": [
        ("腾讯内部·PM笔试历年题库与详解",           "https://km.woa.com/group/product/exam-prep"),
        ("极客时间·数据分析实战 45 讲",             "https://time.geekbang.org/column/intro/100093501"),
        ("产品经理之家·案例题在线练习库",            "https://www.pmcaff.com/tools/exam"),
        ("腾讯数据平台·数据思维与分析入门课",        "https://data.qq.com/article/data-thinking"),
    ],
}

# ── Base data ────────────────────────────────────────────────────────────────
@st.cache_data
def _gen_base() -> pd.DataFrame:
    rng = np.random.default_rng(42)
    n   = 360
    lat = rng.normal(0, 1, n)
    pm  = np.clip(60 + 10*lat + 10*rng.normal(0,1,n), 0, 100)
    pe  = np.clip(65 +  8*lat +  7*rng.normal(0,1,n), 0, 100)
    wt  = np.clip(58 +  6*lat + 14*rng.normal(0,1,n), 0, 100)
    r2  = np.random.default_rng(123)
    names = [SURNAMES[r2.integers(0,20)] + GIVEN[r2.integers(0,30)] for _ in range(n)]
    depts = [DEPTS[i] for i in r2.choice(len(DEPTS), n, p=DEPT_P)]
    years = r2.uniform(1.0, 12.0, n)
    return pd.DataFrame({
        "候选人":    names,
        "员工编号":  [f"EMP{10001+i}" for i in range(n)],
        "当前部门":  depts,
        "工龄(年)":  np.round(years, 1),
        "岗位匹配度": np.round(pm, 1),
        "历史绩效":   np.round(pe, 1),
        "笔试成绩":   np.round(wt, 1),
        "来源":       ["系统导入"] * n,
    })

# ── Core helpers ─────────────────────────────────────────────────────────────
def apply_weights(base: pd.DataFrame, wm: float, wp: float, wt_: float,
                  g_thr: int, r_thr: int) -> pd.DataFrame:
    df = base.copy()
    df["AI综合评分"] = (df["岗位匹配度"]*wm + df["历史绩效"]*wp + df["笔试成绩"]*wt_).round(1)
    def zone(s):
        return "绿区" if s >= g_thr else ("黄区" if s >= r_thr else "红区")
    STATUS = {"绿区":"✅ AI通过","黄区":"⏳ 待人工复核","红区":"❌ AI淘汰"}
    df["评审区间"] = df["AI综合评分"].apply(zone)
    df["状态"]     = df["评审区间"].map(STATUS)
    df = df.sort_values("AI综合评分", ascending=False).reset_index(drop=True)
    df["排名"] = df.index + 1
    return df

def extract_text(f) -> str:
    name = f.name.lower()
    raw  = f.getvalue()
    if name.endswith(".pdf") and HAS_PDF:
        with pdfplumber.open(io.BytesIO(raw)) as pdf:
            return "\n".join(p.extract_text() or "" for p in pdf.pages)
    if name.endswith(".docx") and HAS_DOCX:
        doc = DocxDoc(io.BytesIO(raw))
        return "\n".join(p.text for p in doc.paragraphs)
    if name.endswith(".txt"):
        return raw.decode("utf-8", errors="ignore")
    return f"[不支持格式: {f.name}]"

def ai_parse(client, text: str, fname: str) -> dict:
    prompt = f"""从以下简历文本提取候选人信息，返回纯JSON（无注释无markdown）。
文本：\n{text[:3000]}
格式：
{{"name":"姓名","department":"当前部门","years":工作年限数字,
  "education":"学历","skills":["技能1","技能2"],
  "position_match_estimate":0-100,"performance_estimate":0-100,
  "written_test_estimate":0-100,"highlights":"一句话核心亮点"}}"""
    try:
        r = client.messages.create(model="claude-sonnet-4-6", max_tokens=500,
                                    messages=[{"role":"user","content":prompt}])
        m = re.search(r'\{.*\}', r.content[0].text, re.DOTALL)
        return json.loads(m.group()) if m else {}
    except:
        return {}

def heuristic_parse(text: str, fname: str) -> dict:
    nm = re.search(r'姓名[：:]\s*(\S+)', text)
    yr = re.search(r'(\d+)\s*年.*?工作', text)
    return {
        "name": nm.group(1) if nm else fname.rsplit(".",1)[0],
        "department": "待补充", "years": float(yr.group(1)) if yr else 3.0,
        "education": "待补充", "skills": [],
        "position_match_estimate": 60.0,
        "performance_estimate": 65.0,
        "written_test_estimate": 58.0,
        "highlights": "请手动补充候选人核心亮点",
    }

# ── Report builder ───────────────────────────────────────────────────────────
def build_report(row: pd.Series, df_all: pd.DataFrame,
                 g_thr: int, wm: float, wp: float, wt_: float) -> str:
    name  = row["候选人"]
    dept  = row["当前部门"]
    yrs   = row["工龄(年)"]
    score = row["AI综合评分"]
    pm    = row["岗位匹配度"]
    pe    = row["历史绩效"]
    wt    = row["笔试成绩"]
    gap   = g_thr - score
    now   = datetime.now().strftime("%Y-%m-%d %H:%M")

    def pct(col, val):
        return (df_all[col] <= val).mean() * 100

    pm_pct  = pct("岗位匹配度", pm)
    pe_pct  = pct("历史绩效",   pe)
    wt_pct  = pct("笔试成绩",   wt)
    all_pct = pct("AI综合评分", score)

    dims = [("岗位匹配度", pm, pm_pct, wm),
            ("历史绩效",   pe, pe_pct, wp),
            ("笔试成绩",   wt, wt_pct, wt_)]
    lo = min(dims, key=lambda x: x[1])
    hi = max(dims, key=lambda x: x[1])

    gap_desc = {
        "岗位匹配度": "产品视角与PM岗位契合度有待提升，需加强需求分析、用户研究和产品方法论的系统掌握",
        "历史绩效":   "历史项目量化成果的呈现与OKR完成度记录需进一步完善，建议与直属上级重新梳理可量化的贡献",
        "笔试成绩":   "PM专业知识的结构化表达与案例推导能力尚需强化，可通过刷题和案例练习在短期内快速提升",
    }
    res_md = "\n".join(
        f"  - [{t}]({u})" for t, u in RESOURCES.get(lo[0], [])
    )

    return f"""## {name} · 能力发展报告

**评审日期**：{now}　　**竞聘岗位**：产品经理　　**当前部门**：{dept}　　**工龄**：{yrs} 年

---

### 一、综合评价

感谢您积极参与本次产品经理内部竞聘。您的 AI 综合评分为 **{score:.1f} 分**，超越了全体 {len(df_all)} 名报名员工中 **{all_pct:.0f}%** 的候选人，与通过线（{g_thr} 分）仅差 **{gap:.1f} 分**——差距并不遥远。本报告将为您精准定位短板，并提供一条可立即执行的提升路径。

---

### 二、能力亮点

**▶ {hi[0]}（{hi[1]:.1f} 分 · 权重 {hi[3]:.0%} · 超越全体 {hi[2]:.0f}%）**
得分高于全体均值 {df_all[hi[0]].mean():.1f} 分，处于所有报名者前列，是您目前最显著的竞争优势。建议在下次竞聘材料中将相关项目成果量化呈现（如：主导 XX 功能上线，DAU 提升 X%）。

**▶ 内部跨团队协作经验（工龄 {yrs} 年）**
丰富的内部工作经验意味着您已熟悉公司文化与协作机制，转岗后的适应成本极低——这是外部候选人无法复制的优势，在人工复核阶段可作为重要加分项重点陈述。

**▶ 主动进取意识**
在 360 名报名者中，能够主动迈出参与竞聘这一步，本身即证明了您的职业成长驱动力，这是 PM 团队最看重的软性特质之一。

---

### 三、成长重点

**▶ {lo[0]}（{lo[1]:.1f} 分 · 权重 {lo[3]:.0%} · 超越全体 {lo[2]:.0f}%）——⚡ 优先突破项**
与全体均值（{df_all[lo[0]].mean():.1f} 分）差距 **{df_all[lo[0]].mean() - lo[1]:.1f} 分**，是本次评分与通过线差距的核心来源。{gap_desc[lo[0]]}。

**量化目标**：将该维度提升 **{gap * 1.3:.0f}–{gap * 1.6:.0f} 分**，即可在下次竞聘中越过通过线。

**▶ 笔试专项（{wt:.1f} 分 · 超越全体 {wt_pct:.0f}%）**
笔试考察产品案例推理、数据分析与用户体验判断。此类能力提升效率高——通过专项刷题与案例练习，**3–4 周内**可看到 5–10 分的明显提升。

**▶ 结构化表达与书面沟通**
PM 岗位要求清晰的 PRD 撰写与跨部门方案传递能力。建议通过持续输出产品分析文章来锻炼，每篇 500–800 字即可产生积累效果。

---

### 四、🎯 行动建议与学习资源

#### 第一步：{lo[0]} 专项突破（本月内 · 预计提升 {gap * 1.3:.0f}+ 分）

{res_md}

> 💡 **建议**：选取上方 1–2 门资源系统学习（约 6–12 小时），同时每周输出 1 篇 500 字产品分析作为练习记录，可直接积累为下次竞聘的补充材料。

#### 第二步：实践积累（第 2–4 周）

- 主动申请参与产品部门虚拟项目组：[腾讯内部·开放项目列表](https://km.woa.com/group/product-open-projects)
- 在现部门承接需求对接角色，留存可量化案例（示例格式：「主导 XX 需求落地，上线后 XX 指标提升 X%」）
- 对每次跨部门协作进行结构化复盘（参考模板：[协作复盘记录模板](https://iwiki.woa.com/p/collab-review-template)）

#### 第三步：系统认证与综合提升（第 5–12 周）

- 完成腾讯 PM 成长认证课程：[腾讯产品经理认证体系](https://talent.tencent.com/certification/pm)（结业证书可直接附于下次竞聘材料）
- 建立个人 PM 知识框架：[知识地图参考模板](https://iwiki.woa.com/p/pm-knowledge-map)
- 模拟笔试演练（建议在下次竞聘前 4 周完成）：[PM 能力在线模拟考](https://talent.tencent.com/mock-test/pm)

#### 下次竞聘 Checklist

- [ ] **{lo[0]}** 提升至 **{lo[1] + gap * 1.5:.0f} 分以上**
- [ ] 积累至少 **2 个** 可量化的产品实践案例（STAR 格式）
- [ ] 完成腾讯 PM 认证课程并取得结业证明
- [ ] 提前 2 周与直属上级确认绩效数据已更新至 HR 系统
- [ ] 准备 3 分钟结构化自我介绍（聚焦与 PM 岗的能力匹配）

---

### 五、发展寄语

{gap:.0f} 分的差距，是方向，不是终点。您今天种下的每一份努力，都将在下次竞聘中成为真实可见的优势。组织珍视的不只是最终通过的 50 人，更珍视每一位主动求变、敢于突破的成长者——期待在下次竞聘中看到更好的您。

---

> 📣 **对本次评分有异议？** 如认为 AI 评分未能充分反映您的实际能力，可在结果公示后 **48 小时内**通过系统「申诉通道」标签页提交补充材料，HR 将在 **3 个工作日内**完成人工复核并给出书面回复。
>
> *本报告由腾讯 AI 竞聘评审系统自动生成 · {now} · 咨询请联系 hr-ai@tencent.com*"""

# ── PDF & Word export ────────────────────────────────────────────────────────
def to_pdf_bytes(md: str) -> bytes | None:
    if not HAS_REPORTLAB:
        return None
    try:
        pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))
    except Exception:
        pass
    BLUE  = HexColor('#1890ff')
    GRAY  = HexColor('#595959')
    LGRAY = HexColor('#8c8c8c')
    sN = ParagraphStyle('n',  fontName='STSong-Light', fontSize=10.5, leading=20)
    sH1= ParagraphStyle('h1', fontName='STSong-Light', fontSize=15,   leading=26,
                         textColor=BLUE, spaceBefore=4, spaceAfter=4)
    sH2= ParagraphStyle('h2', fontName='STSong-Light', fontSize=12.5, leading=22,
                         textColor=HexColor('#222'), spaceBefore=10, spaceAfter=4)
    sH3= ParagraphStyle('h3', fontName='STSong-Light', fontSize=11,   leading=20,
                         textColor=HexColor('#13c2c2'), spaceBefore=6, spaceAfter=2)
    sB = ParagraphStyle('b',  fontName='STSong-Light', fontSize=10,   leading=18, leftIndent=14)
    sQ = ParagraphStyle('q',  fontName='STSong-Light', fontSize=9.5,  leading=17,
                         leftIndent=20, textColor=GRAY)
    sC = ParagraphStyle('c',  fontName='STSong-Light', fontSize=9,    leading=15, textColor=LGRAY)

    def clean(s):
        s = re.sub(r'\*\*(.+?)\*\*', r'\1', s)
        s = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', s)
        return s.strip()

    story = []
    for line in md.split('\n'):
        s = line.strip()
        if not s:
            story.append(Spacer(1, 0.2*cm)); continue
        if s == '---':
            story.append(HRFlowable(width="100%", thickness=0.5,
                                     color=HexColor('#d9d9d9'), spaceAfter=4)); continue
        c = clean(s)
        if   s.startswith('## '):
            story += [Paragraph(c, sH1),
                      HRFlowable(width="100%", thickness=1.5, color=BLUE, spaceAfter=6)]
        elif s.startswith('### '):  story.append(Paragraph(c, sH2))
        elif s.startswith('#### '): story.append(Paragraph(c, sH3))
        elif s.startswith('  - '):  story.append(Paragraph('  · ' + clean(s[4:]), sB))
        elif s.startswith('- [ ]'): story.append(Paragraph('☐ ' + clean(s[5:]), sB))
        elif s.startswith('- ') or s.startswith('▶'):
            story.append(Paragraph('• ' + clean(s.lstrip('-▶ ')), sB))
        elif s.startswith('> '):    story.append(Paragraph(clean(s[2:]), sQ))
        elif s.startswith('*') and s.endswith('*'):
            story.append(Paragraph(clean(s), sC))
        else:
            story.append(Paragraph(c, sN))

    buf = io.BytesIO()
    SimpleDocTemplate(buf, pagesize=A4,
                      rightMargin=2.5*cm, leftMargin=2.5*cm,
                      topMargin=2.5*cm,  bottomMargin=2*cm).build(story)
    buf.seek(0)
    return buf.getvalue()


def to_word_bytes(md: str) -> bytes | None:
    if not HAS_DOCX:
        return None
    doc = DocxDoc()
    sty = doc.styles['Normal']
    sty.font.name = '微软雅黑'
    sty.element.rPr.rFonts.set(_qn('w:eastAsia'), '微软雅黑')

    def add_run(para, text, bold=False, color=None, size=10.5):
        r = para.add_run(text)
        r.font.name = '微软雅黑'
        r.font.size = Pt(size)
        if bold:  r.font.bold = True
        if color: r.font.color.rgb = RGBColor(*color)
        r.element.rPr.rFonts.set(_qn('w:eastAsia'), '微软雅黑')
        return r

    def clean(s):
        s = re.sub(r'\*\*(.+?)\*\*', r'\1', s)
        s = re.sub(r'\[(.+?)\]\((.+?)\)', r'\1 → \2', s)
        return s.strip()

    for line in md.split('\n'):
        s = line.strip()
        if not s:
            doc.add_paragraph(); continue
        if s == '---':
            doc.add_paragraph('─' * 45); continue
        c = clean(s)
        if s.startswith('## '):
            p = doc.add_heading(level=1); add_run(p, s[3:], bold=True, color=(0x18,0x90,0xFF), size=15)
        elif s.startswith('### '):
            p = doc.add_heading(level=2); add_run(p, s[4:], bold=True, size=12)
        elif s.startswith('#### '):
            p = doc.add_heading(level=3); add_run(p, s[5:], bold=True, color=(0x13,0xC2,0xC2), size=11)
        elif s.startswith('  - '):
            p = doc.add_paragraph(style='List Bullet 2'); add_run(p, clean(s[4:]))
        elif s.startswith('- [ ]'):
            p = doc.add_paragraph(style='List Bullet'); add_run(p, '☐ ' + clean(s[5:]))
        elif s.startswith('- ') or s.startswith('▶'):
            p = doc.add_paragraph(style='List Bullet'); add_run(p, clean(s.lstrip('-▶ ')))
        elif s.startswith('> '):
            p = doc.add_paragraph(); p.paragraph_format.left_indent = Cm(1)
            add_run(p, clean(s[2:]), color=(0x59,0x59,0x59))
        else:
            p = doc.add_paragraph(); add_run(p, c)

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf.getvalue()

# ── Session state ────────────────────────────────────────────────────────────
for k, v in [("base_df", None), ("human_reviews", {}), ("generated_reports", {}),
             ("appeals", {}), ("client", None), ("upload_parsed", [])]:
    if k not in st.session_state:
        st.session_state[k] = v

if st.session_state.base_df is None:
    st.session_state.base_df = _gen_base()

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ 系统配置")
    st.divider()
    st.markdown("**评分权重**")
    wm  = st.slider("岗位匹配度", 0.20, 0.60, 0.40, 0.05)
    wp  = st.slider("历史绩效",   0.10, 0.50, 0.30, 0.05)
    wt_ = st.slider("笔试成绩",   0.10, 0.50, 0.30, 0.05)
    tot = wm + wp + wt_
    if abs(tot - 1.0) > 0.01:
        st.warning(f"权重合计 {tot:.2f}，已归一化")
        wm /= tot; wp /= tot; wt_ /= tot
    fig_w = go.Figure(go.Bar(
        x=[wm, wp, wt_], y=["岗位匹配", "历史绩效", "笔试成绩"], orientation="h",
        marker_color=["#1890ff","#52c41a","#722ed1"],
        text=[f"{v:.0%}" for v in [wm, wp, wt_]], textposition="inside",
    ))
    fig_w.update_layout(height=120, margin=dict(l=0,r=0,t=4,b=4), showlegend=False,
                         plot_bgcolor="rgba(0,0,0,0)",
                         xaxis=dict(showticklabels=False,showgrid=False),
                         yaxis=dict(showgrid=False))
    st.plotly_chart(fig_w, use_container_width=True)
    st.divider()
    st.markdown("**复核阈值**")
    g_thr = int(st.number_input("绿区下限（自动通过）", 65, 85, 73))
    r_thr = int(st.number_input("红区上限（自动淘汰）", 50, 70, 67))
    st.divider()
    st.markdown("**Claude API**")
    api_key = st.text_input("API Key", type="password", placeholder="sk-ant-...")
    if api_key:
        try:
            st.session_state.client = Anthropic(api_key=api_key)
            st.success("✅ API 已连接")
        except Exception as e:
            st.error(str(e))
    else:
        st.caption("未配置 → 使用智能模板")
    st.divider()
    total_cands = len(st.session_state.base_df)
    uploaded_n  = (st.session_state.base_df["来源"] == "简历上传").sum()
    st.caption(f"AI竞聘评审系统 v2.1")
    st.caption(f"系统候选人：{total_cands} 人（含上传 {uploaded_n} 人）")

# ── Live df ──────────────────────────────────────────────────────────────────
df      = apply_weights(st.session_state.base_df, wm, wp, wt_, g_thr, r_thr)
green_n = (df["评审区间"] == "绿区").sum()
yellow_n= (df["评审区间"] == "黄区").sum()
red_n   = (df["评审区间"] == "红区").sum()

# ── Header ───────────────────────────────────────────────────────────────────
st.markdown(f"""<div style="background:linear-gradient(135deg,#1890ff,#722ed1);
  color:white;padding:22px 32px;border-radius:16px;margin-bottom:20px;">
  <h1 style="margin:0;font-size:24px;font-weight:700;">🎯 AI内部竞聘评审系统</h1>
  <p style="margin:6px 0 0;opacity:.85;font-size:13px;">
    产品经理岗位 · 50个名额 · {len(df)} 名候选人 · 两周双轨制高效评审
  </p>
</div>""", unsafe_allow_html=True)

# ── TABS ─────────────────────────────────────────────────────────────────────
tab1,tab2,tab3,tab4,tab5,tab6,tab7 = st.tabs([
    "📊 总览仪表板",
    "📤 简历导入",
    "👤 员工信息与对比",
    "🔍 人工复核",
    "📋 能力发展报告",
    "📣 申诉通道",
    "📈 效果评估",
])

# ════════════════════════════════════════════════════════════════════════════
# TAB 1 · 总览仪表板
# ════════════════════════════════════════════════════════════════════════════
with tab1:
    c1,c2,c3,c4,c5 = st.columns(5)
    review_rate = yellow_n / len(df)
    c1.metric("报名总人数", str(len(df)))
    c2.metric("开放名额", "50")
    c3.metric("✅ AI通过", str(green_n), f"{green_n/len(df):.1%}")
    c4.metric("⏳ 待复核",  str(yellow_n), f"{yellow_n/len(df):.1%}")
    c5.metric("人工复核率", f"{review_rate:.1%}",
              delta="达标 ✓" if review_rate<=0.15 else "超标 ✗",
              delta_color="normal" if review_rate<=0.15 else "inverse")

    st.divider()
    col_l, col_r = st.columns([3,2])

    with col_l:
        st.subheader("AI综合评分分布")
        fig_h = go.Figure()
        fig_h.add_trace(go.Histogram(x=df["AI综合评分"], nbinsx=40,
                                      marker_color="#1890ff", opacity=0.75))
        for x0, x1, col, ann, apos in [
            (g_thr,100,"#52c41a","绿区·自动通过","top right"),
            (r_thr,g_thr,"#faad14","黄区·人工复核","top"),
            (0,r_thr,"#ff4d4f","红区·自动淘汰","top left"),
        ]:
            fig_h.add_vrect(x0=x0, x1=x1, fillcolor=col, opacity=0.07, line_width=0,
                             annotation_text=ann, annotation_position=apos)
        fig_h.add_vline(x=g_thr, line_dash="dash", line_color="#52c41a", line_width=1.5)
        fig_h.add_vline(x=r_thr, line_dash="dash", line_color="#ff4d4f", line_width=1.5)
        fig_h.update_layout(height=300, margin=dict(l=20,r=20,t=40,b=20),
                             plot_bgcolor="rgba(0,0,0,0)",
                             xaxis_title="AI综合评分", yaxis_title="人数",
                             showlegend=False)
        st.plotly_chart(fig_h, use_container_width=True)

    with col_r:
        st.subheader("评审区间占比")
        fig_p = px.pie(values=[green_n,yellow_n,red_n],
                        names=["绿区（AI通过）","黄区（复核）","红区（AI淘汰）"],
                        color_discrete_sequence=["#52c41a","#faad14","#ff4d4f"],
                        hole=0.52)
        fig_p.update_traces(textposition="outside", textinfo="percent+label+value")
        fig_p.update_layout(height=300, margin=dict(l=0,r=0,t=10,b=10), showlegend=False)
        st.plotly_chart(fig_p, use_container_width=True)

    st.subheader("各部门报名与通过情况")
    dept_s = (df.groupby("当前部门")
               .agg(报名=("候选人","count"),
                    AI通过=("评审区间", lambda x:(x=="绿区").sum()),
                    待复核=("评审区间", lambda x:(x=="黄区").sum()))
               .reset_index())
    fig_d = go.Figure()
    fig_d.add_trace(go.Bar(name="AI通过",    x=dept_s["当前部门"], y=dept_s["AI通过"],
                            marker_color="#52c41a", opacity=0.85))
    fig_d.add_trace(go.Bar(name="待人工复核", x=dept_s["当前部门"], y=dept_s["待复核"],
                            marker_color="#faad14", opacity=0.85))
    fig_d.update_layout(barmode="stack", height=250, margin=dict(l=20,r=20,t=10,b=20),
                         plot_bgcolor="rgba(0,0,0,0)",
                         legend=dict(orientation="h",y=1.1), yaxis_title="人数")
    st.plotly_chart(fig_d, use_container_width=True)

    st.subheader("📅 两周评审流程")
    gantt_data = [
        dict(Task="AI解析项目经历与绩效",   Start="2025-01-01",Finish="2025-01-04",Phase="第一周·AI初筛"),
        dict(Task="AI批改笔试·生成综合评分",Start="2025-01-04",Finish="2025-01-07",Phase="第一周·AI初筛"),
        dict(Task="区间划分·黄区推送HR",    Start="2025-01-07",Finish="2025-01-08",Phase="衔接"),
        dict(Task="HR人工精判黄区（约54人）",Start="2025-01-08",Finish="2025-01-12",Phase="第二周·精判"),
        dict(Task="最终名单审核与公示",      Start="2025-01-12",Finish="2025-01-14",Phase="第二周·精判"),
        dict(Task="能力发展报告推送+申诉窗口",Start="2025-01-13",Finish="2025-01-14",Phase="第二周·精判"),
    ]
    fig_g = px.timeline(gantt_data, x_start="Start", x_end="Finish", y="Task", color="Phase",
                         color_discrete_map={"第一周·AI初筛":"#1890ff","衔接":"#722ed1","第二周·精判":"#13c2c2"})
    fig_g.update_yaxes(autorange="reversed", title="")
    fig_g.update_layout(height=250, margin=dict(l=20,r=20,t=10,b=20),
                         plot_bgcolor="rgba(0,0,0,0)",
                         legend=dict(orientation="h", y=-0.3))
    st.plotly_chart(fig_g, use_container_width=True)


# ════════════════════════════════════════════════════════════════════════════
# TAB 2 · 简历导入
# ════════════════════════════════════════════════════════════════════════════
with tab2:
    st.subheader("📤 批量简历导入")
    st.markdown(
        "> 支持批量上传 **PDF / DOCX / TXT** 格式简历，AI 自动解析结构化信息并导入评审池。"
        "数据持久保存于系统，支持持续迭代使用。"
    )

    uploaded = st.file_uploader(
        "拖拽或点击上传简历文件（支持多选）",
        type=["pdf","docx","txt"],
        accept_multiple_files=True,
        label_visibility="collapsed",
    )

    if uploaded:
        if st.button("🤖 开始解析所有简历", type="primary"):
            st.session_state.upload_parsed = []
            prog = st.progress(0, text="正在解析…")
            for i, f in enumerate(uploaded):
                text = extract_text(f)
                if st.session_state.client:
                    info = ai_parse(st.session_state.client, text, f.name)
                    if not info:
                        info = heuristic_parse(text, f.name)
                    info["_source"] = "Claude AI解析"
                else:
                    info = heuristic_parse(text, f.name)
                    info["_source"] = "规则解析"
                info["_filename"] = f.name
                info["_text_preview"] = text[:300]
                st.session_state.upload_parsed.append(info)
                prog.progress((i+1)/len(uploaded), text=f"已解析 {i+1}/{len(uploaded)}")
            prog.empty()
            st.success(f"✅ 成功解析 {len(uploaded)} 份简历！请在下方确认信息后导入系统。")

    if st.session_state.upload_parsed:
        st.divider()
        st.subheader("解析结果预览与编辑")
        st.caption("请核对以下信息，支持手动修改后批量导入系统")

        confirmed = []
        for i, info in enumerate(st.session_state.upload_parsed):
            with st.expander(f"📄 {info.get('_filename','文件'+str(i+1))}  ·  解析方式：{info.get('_source','—')}", expanded=i==0):
                ec1, ec2, ec3 = st.columns(3)
                name_  = ec1.text_input("姓名",       info.get("name",""), key=f"n{i}")
                dept_  = ec2.selectbox("当前部门",    DEPTS,
                                        index=DEPTS.index(info.get("department","技术部"))
                                        if info.get("department") in DEPTS else 0, key=f"d{i}")
                years_ = ec3.number_input("工龄(年)", 0.5, 20.0,
                                           float(info.get("years",3.0)), 0.5, key=f"y{i}")

                sc1, sc2, sc3 = st.columns(3)
                pm_  = sc1.slider("岗位匹配度", 0, 100,
                                   int(info.get("position_match_estimate",60)), key=f"pm{i}")
                pe_  = sc2.slider("历史绩效",   0, 100,
                                   int(info.get("performance_estimate",65)),    key=f"pe{i}")
                wt__ = sc3.slider("笔试成绩",   0, 100,
                                   int(info.get("written_test_estimate",58)),   key=f"wt{i}")

                hl = st.text_input("核心亮点（补充说明）",
                                    info.get("highlights",""), key=f"hl{i}")

                st.caption(f"**简历摘要**：{info.get('_text_preview','')[:200]}…")

                if st.checkbox(f"✅ 确认导入", key=f"cb{i}"):
                    confirmed.append({
                        "候选人": name_, "员工编号": f"UPL{1000+i}",
                        "当前部门": dept_, "工龄(年)": years_,
                        "岗位匹配度": float(pm_), "历史绩效": float(pe_),
                        "笔试成绩": float(wt__), "来源": "简历上传",
                    })

        if confirmed:
            if st.button(f"⬆️ 将 {len(confirmed)} 名候选人导入系统", type="primary"):
                new_rows = pd.DataFrame(confirmed)
                st.session_state.base_df = pd.concat(
                    [st.session_state.base_df, new_rows], ignore_index=True
                )
                st.session_state.upload_parsed = []
                st.success(f"🎉 已成功导入 {len(confirmed)} 名候选人！请切换到其他标签页查看。")
                st.rerun()

    st.divider()
    st.subheader("📊 已导入数据概况")
    src_counts = st.session_state.base_df["来源"].value_counts().reset_index()
    src_counts.columns = ["来源", "人数"]
    st.dataframe(src_counts, use_container_width=True, hide_index=True)


# ════════════════════════════════════════════════════════════════════════════
# TAB 3 · 员工信息与对比
# ════════════════════════════════════════════════════════════════════════════
with tab3:
    st.subheader("👤 员工信息查询与横向对比")
    mode = st.radio("查看模式", ["单人详情", "多人横向对比"],
                     horizontal=True, label_visibility="collapsed")

    ZONE_ICON = {"绿区":"🟢","黄区":"🟡","红区":"🔴"}
    ALL_NAMES = df["候选人"].tolist()   # ← 全部 360+ 人

    # ── 单人详情 ─────────────────────────────────────────────
    if mode == "单人详情":
        search_q = st.text_input("🔍 输入姓名或工号搜索", placeholder="张伟 / EMP10001")
        if search_q:
            mask = (df["候选人"].str.contains(search_q) |
                    df["员工编号"].str.contains(search_q))
            cands = df[mask]["候选人"].tolist()
        else:
            cands = ALL_NAMES

        if not cands:
            st.warning("未找到匹配候选人")
        else:
            pick = st.selectbox("选择候选人", cands)
            row  = df[df["候选人"] == pick].iloc[0]

            left, right = st.columns([1, 2])
            with left:
                zone_badge = {"绿区":"badge-green","黄区":"badge-yellow","红区":"badge-red"}
                st.markdown(f'<div class="card">', unsafe_allow_html=True)
                st.markdown(f"### {row['候选人']}")
                st.markdown(f"`{row['员工编号']}`")
                st.markdown(f"""
| 项目 | 信息 |
|------|------|
| 当前部门 | {row['当前部门']} |
| 工龄 | {row['工龄(年)']} 年 |
| 来源 | {row['来源']} |
| 全体排名 | **第 {row['排名']} 名** / {len(df)} |
| 评审区间 | {ZONE_ICON.get(row['评审区间'],'⚪')} **{row['评审区间']}** |
| 当前状态 | {row['状态']} |
""")
                st.metric("AI综合评分", f"{row['AI综合评分']:.1f}",
                          delta=f"距通过线 {row['AI综合评分']-g_thr:+.1f}分")
                st.markdown('</div>', unsafe_allow_html=True)

                # Score bars
                st.markdown("**分项得分**")
                for metric, color, weight in [
                    ("岗位匹配度","#1890ff", wm),
                    ("历史绩效",  "#52c41a", wp),
                    ("笔试成绩",  "#722ed1", wt_),
                ]:
                    score_v = row[metric]
                    avg_v   = df[metric].mean()
                    st.markdown(f"<small>{metric}（权重{weight:.0%}）：**{score_v:.1f}** / 均值 {avg_v:.1f}</small>",
                                unsafe_allow_html=True)
                    st.progress(int(score_v)/100)

            with right:
                cats = ["岗位匹配度","历史绩效","笔试成绩"]
                vals = [row["岗位匹配度"], row["历史绩效"], row["笔试成绩"]]
                avgs = [df[c].mean() for c in cats]
                fig_r = go.Figure()
                fig_r.add_trace(go.Scatterpolar(
                    r=vals+[vals[0]], theta=cats+[cats[0]], fill="toself",
                    name=row["候选人"], line_color="#1890ff",
                    fillcolor="rgba(24,144,255,0.18)"))
                fig_r.add_trace(go.Scatterpolar(
                    r=avgs+[avgs[0]], theta=cats+[cats[0]],
                    name="全体均值", line_color="#faad14", line_dash="dash"))
                fig_r.update_layout(
                    polar=dict(radialaxis=dict(visible=True, range=[0,100])),
                    height=340, margin=dict(l=40,r=40,t=40,b=40),
                    legend=dict(orientation="h", y=-0.1))
                st.plotly_chart(fig_r, use_container_width=True)

                # Percentile table
                pct_df = pd.DataFrame({
                    "维度": ["岗位匹配度","历史绩效","笔试成绩","综合评分"],
                    "得分": [row["岗位匹配度"], row["历史绩效"],
                             row["笔试成绩"], row["AI综合评分"]],
                    "超越全体%": [
                        f"{(df['岗位匹配度']<=row['岗位匹配度']).mean()*100:.0f}%",
                        f"{(df['历史绩效']<=row['历史绩效']).mean()*100:.0f}%",
                        f"{(df['笔试成绩']<=row['笔试成绩']).mean()*100:.0f}%",
                        f"{(df['AI综合评分']<=row['AI综合评分']).mean()*100:.0f}%",
                    ],
                    "与均值差": [
                        f"{row['岗位匹配度']-df['岗位匹配度'].mean():+.1f}",
                        f"{row['历史绩效']-df['历史绩效'].mean():+.1f}",
                        f"{row['笔试成绩']-df['笔试成绩'].mean():+.1f}",
                        f"{row['AI综合评分']-df['AI综合评分'].mean():+.1f}",
                    ],
                })
                st.dataframe(pct_df, use_container_width=True, hide_index=True)

    # ── 多人横向对比 ──────────────────────────────────────────
    else:
        st.markdown("选择 **2–4 名**候选人进行横向对比（适用于人工复核决策）")
        compare_names = st.multiselect(
            "选择候选人（支持搜索）", ALL_NAMES,
            default=ALL_NAMES[:2], max_selections=4
        )

        if len(compare_names) < 2:
            st.info("请至少选择 2 名候选人")
        else:
            compare_rows = [df[df["候选人"]==n].iloc[0] for n in compare_names]
            COLORS = ["#1890ff","#52c41a","#722ed1","#fa8c16"]

            # ── Score cards ─────
            cols = st.columns(len(compare_rows))
            for col, row, color in zip(cols, compare_rows, COLORS):
                with col:
                    z = row["评审区间"]
                    badge_cls = {"绿区":"badge-green","黄区":"badge-yellow","红区":"badge-red"}[z]
                    st.markdown(
                        f'<div class="card" style="border-top:4px solid {color}">'
                        f'<h4 style="margin:0;color:{color}">{row["候选人"]}</h4>'
                        f'<p style="margin:4px 0;font-size:12px;color:#888">'
                        f'{row["当前部门"]} · {row["工龄(年)"]}年</p>'
                        f'<p style="font-size:28px;font-weight:700;margin:8px 0;color:{color}">'
                        f'{row["AI综合评分"]:.1f}</p>'
                        f'<span class="{badge_cls}">{z}</span>&nbsp;'
                        f'<small>第{row["排名"]}名</small>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

            # ── Overlay radar ────
            st.subheader("能力雷达图对比")
            cats = ["岗位匹配度","历史绩效","笔试成绩"]
            fig_cmp = go.Figure()
            for row, color in zip(compare_rows, COLORS):
                vals = [row["岗位匹配度"], row["历史绩效"], row["笔试成绩"]]
                fig_cmp.add_trace(go.Scatterpolar(
                    r=vals+[vals[0]], theta=cats+[cats[0]],
                    fill="toself", name=row["候选人"],
                    line_color=color, fillcolor=color.replace("#","rgba(")+",.15)" if False else color,
                    opacity=0.75,
                ))
            fig_cmp.update_layout(
                polar=dict(radialaxis=dict(visible=True, range=[0,100])),
                height=380, margin=dict(l=40,r=40,t=40,b=40),
                legend=dict(orientation="h", y=-0.15))
            st.plotly_chart(fig_cmp, use_container_width=True)

            # ── Comparison table ─
            st.subheader("分项得分对比表")
            tbl = {"指标": ["岗位匹配度","历史绩效","笔试成绩","AI综合评分","排名","评审区间","工龄(年)"]}
            for row in compare_rows:
                tbl[row["候选人"]] = [
                    f"{row['岗位匹配度']:.1f}",
                    f"{row['历史绩效']:.1f}",
                    f"{row['笔试成绩']:.1f}",
                    f"{row['AI综合评分']:.1f}",
                    f"第{row['排名']}名",
                    row["评审区间"],
                    str(row["工龄(年)"]),
                ]
            st.dataframe(pd.DataFrame(tbl), use_container_width=True, hide_index=True)

            # ── Bar chart comparison ─
            st.subheader("分项得分柱状对比")
            bar_data = []
            for row in compare_rows:
                for metric in ["岗位匹配度","历史绩效","笔试成绩"]:
                    bar_data.append({"候选人": row["候选人"], "维度": metric, "分数": row[metric]})
            fig_bar = px.bar(
                pd.DataFrame(bar_data), x="维度", y="分数", color="候选人",
                barmode="group", color_discrete_sequence=COLORS,
                range_y=[0,100], height=280,
            )
            fig_bar.update_layout(margin=dict(l=20,r=20,t=10,b=20),
                                   plot_bgcolor="rgba(0,0,0,0)",
                                   legend=dict(orientation="h", y=1.1))
            st.plotly_chart(fig_bar, use_container_width=True)

            # ── HR recommendation ─
            st.subheader("🤔 AI辅助复核建议")
            best = max(compare_rows, key=lambda r: r["AI综合评分"])
            st.info(
                f"根据当前权重配置，**{best['候选人']}** 综合得分最高（{best['AI综合评分']:.1f}分），"
                f"如仅有 1 个名额建议优先通过。若多人处于黄区，请结合工龄、部门匹配度与面谈印象综合判断。"
            )


# ════════════════════════════════════════════════════════════════════════════
# TAB 4 · 人工复核
# ════════════════════════════════════════════════════════════════════════════
with tab4:
    yellow_df  = df[df["评审区间"] == "黄区"].copy()
    done_count = len(st.session_state.human_reviews)

    h1,h2,h3 = st.columns(3)
    h1.metric("黄区总人数", str(yellow_n))
    h2.metric("已完成复核", str(done_count))
    h3.metric("待复核",     str(yellow_n - done_count))
    prog_val = done_count / yellow_n if yellow_n > 0 else 0
    st.progress(prog_val, text=f"复核进度：{done_count}/{yellow_n}（{prog_val:.0%}）")

    st.divider()
    pending   = yellow_df[~yellow_df["员工编号"].isin(st.session_state.human_reviews)]
    completed = yellow_df[yellow_df["员工编号"].isin(st.session_state.human_reviews)]

    if len(pending) > 0:
        st.subheader("待复核候选人")
        rev_name = st.selectbox("选择候选人", pending["候选人"].tolist())
        rev = yellow_df[yellow_df["候选人"] == rev_name].iloc[0]

        left, right = st.columns([1,1])
        with left:
            st.markdown(f"#### {rev['候选人']} · 评分详情")
            for metric, weight, color in [
                ("岗位匹配度", wm,  "#1890ff"),
                ("历史绩效",   wp,  "#52c41a"),
                ("笔试成绩",   wt_, "#722ed1"),
            ]:
                sc = rev[metric]; avg = df[metric].mean()
                st.markdown(f"**{metric}**（权重 {weight:.0%}）— "
                            f"{sc:.1f}分 {'↑' if sc>avg else '↓'} 均值 {avg:.1f}")
                st.progress(int(sc)/100)
            gap = rev["AI综合评分"] - g_thr
            st.metric("AI综合评分", f"{rev['AI综合评分']:.1f}分",
                      delta=f"距通过线 {gap:+.1f}分",
                      delta_color="normal" if gap>=0 else "inverse")
        with right:
            st.markdown("#### HR 复核决策")
            st.info(f"该候选人评分 **{rev['AI综合评分']:.1f}分**，位于临界区间（{r_thr}–{g_thr}分）。")
            notes = st.text_area("复核备注（必填）",
                                  placeholder="如：面谈后确认候选人有丰富B端PM经验，项目与岗位高度契合…",
                                  height=110, key=f"notes_{rev['员工编号']}")
            b1,b2 = st.columns(2)
            with b1:
                if st.button("✅ 通过", type="primary", use_container_width=True, disabled=not notes):
                    st.session_state.human_reviews[rev["员工编号"]] = {
                        "decision":"通过","notes":notes,"candidate":rev["候选人"]}
                    st.success(f"已确认 {rev['候选人']} 通过！"); st.rerun()
            with b2:
                if st.button("❌ 淘汰", use_container_width=True, disabled=not notes):
                    st.session_state.human_reviews[rev["员工编号"]] = {
                        "decision":"淘汰","notes":notes,"candidate":rev["候选人"]}
                    st.warning(f"已确认 {rev['候选人']} 淘汰。"); st.rerun()
    else:
        st.success("🎉 所有黄区候选人已完成人工复核！")

    if len(completed) > 0:
        st.divider()
        st.subheader("已完成复核记录")
        records = []
        for _, row in completed.iterrows():
            rv = st.session_state.human_reviews.get(row["员工编号"])
            if rv:
                records.append({
                    "候选人": row["候选人"], "AI评分": row["AI综合评分"],
                    "HR决策": rv["decision"],
                    "备注": rv["notes"][:40]+"…" if len(rv["notes"])>40 else rv["notes"],
                })
        st.dataframe(pd.DataFrame(records), use_container_width=True, hide_index=True)


# ════════════════════════════════════════════════════════════════════════════
# TAB 5 · 能力发展报告
# ════════════════════════════════════════════════════════════════════════════
with tab5:
    st.subheader("📋 能力发展报告")
    st.markdown("> 为每位参与者生成**个性化、带学习超链接**的能力发展报告，支持下载 **PDF / Word** 双格式。")

    rpt_pool = df[df["评审区间"].isin(["红区","黄区"])].head(80)

    col_pick, col_report = st.columns([1,2])
    with col_pick:
        rpt_search = st.text_input("搜索候选人", placeholder="输入姓名…", key="rpt_search")
        if rpt_search:
            rpt_pool = rpt_pool[rpt_pool["候选人"].str.contains(rpt_search)]
        rpt_name = st.selectbox("选择候选人（落榜/待复核）",
                                 rpt_pool["候选人"].tolist(), key="rpt_sel")
        rc = df[df["候选人"] == rpt_name].iloc[0]

        zi = {"绿区":"🟢","黄区":"🟡","红区":"🔴"}.get(rc["评审区间"],"⚪")
        st.markdown(f"**{rc['候选人']}** {zi} {rc['评审区间']}")
        st.caption(f"{rc['当前部门']} · 工龄 {rc['工龄(年)']}年")

        for metric, col_c in [("岗位匹配度","#1890ff"),("历史绩效","#52c41a"),("笔试成绩","#722ed1")]:
            sc = rc[metric]; avg = df[metric].mean()
            st.markdown(f"<small>{metric}：**{sc:.1f}** / 均值 {avg:.1f}</small>",
                         unsafe_allow_html=True)
            st.progress(int(sc)/100)

        gen_btn = st.button("🤖 生成能力发展报告", type="primary", use_container_width=True)

    with col_report:
        emp_id = rc["员工编号"]

        if gen_btn:
            if st.session_state.client:
                with st.spinner("Claude 正在生成个性化报告…"):
                    try:
                        base_rpt = build_report(rc, df, g_thr, wm, wp, wt_)
                        prompt = f"""请在以下报告模板基础上，用更自然流畅的中文语气改写，
保留所有数据、链接和结构，字数控制在600字以内：

{base_rpt}"""
                        resp = st.session_state.client.messages.create(
                            model="claude-sonnet-4-6", max_tokens=2000,
                            system="你是腾讯人才发展顾问，报告温和、专业、激励性强。",
                            messages=[{"role":"user","content":prompt}])
                        st.session_state.generated_reports[emp_id] = resp.content[0].text
                    except Exception as e:
                        st.error(f"AI生成失败：{e}，已改用模板")
                        st.session_state.generated_reports[emp_id] = build_report(rc, df, g_thr, wm, wp, wt_)
            else:
                st.session_state.generated_reports[emp_id] = build_report(rc, df, g_thr, wm, wp, wt_)

        if emp_id in st.session_state.generated_reports:
            rpt_text = st.session_state.generated_reports[emp_id]
            st.markdown('<div class="report-box">', unsafe_allow_html=True)
            st.markdown(rpt_text)
            st.markdown('</div>', unsafe_allow_html=True)

            st.markdown("**下载报告**")
            dl1, dl2 = st.columns(2)

            # Word
            with dl1:
                word_bytes = to_word_bytes(rpt_text)
                if word_bytes:
                    st.download_button("📄 下载 Word (.docx)", data=word_bytes,
                                        file_name=f"{rpt_name}_能力发展报告.docx",
                                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                        use_container_width=True)
                else:
                    st.warning("python-docx 未安装")

            # PDF
            with dl2:
                pdf_bytes = to_pdf_bytes(rpt_text)
                if pdf_bytes:
                    st.download_button("📑 下载 PDF (.pdf)", data=pdf_bytes,
                                        file_name=f"{rpt_name}_能力发展报告.pdf",
                                        mime="application/pdf",
                                        use_container_width=True)
                else:
                    st.warning("reportlab 未安装")
        else:
            st.markdown(
                '<div style="text-align:center;padding:60px 20px;color:#8c8c8c;'
                'border:2px dashed #d9d9d9;border-radius:12px;margin-top:16px;">'
                '<div style="font-size:48px">📋</div>'
                '<div style="margin-top:12px;font-size:15px">点击左侧按钮生成能力发展报告</div>'
                '<div style="margin-top:8px;font-size:12px;color:#bfbfbf">'
                '包含学习资源超链接 · 支持 PDF / Word 双格式下载</div>'
                '</div>', unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════
# TAB 6 · 申诉通道
# ════════════════════════════════════════════════════════════════════════════
with tab6:
    st.subheader("📣 申诉通道")
    st.markdown(
        "> 候选人可在竞聘结果公示后 **48 小时内**提交申诉，附上补充材料说明 AI 评分未能反映的能力。"
        "HR 将在 **3 个工作日**内完成人工复核并书面回复，进一步保障评审公平性。"
    )

    sub_tab, status_tab = st.tabs(["📝 提交申诉", "📋 申诉状态查询"])

    with sub_tab:
        st.markdown("#### 填写申诉信息")
        ap1, ap2 = st.columns([1,1])
        with ap1:
            ap_name = st.selectbox("申诉候选人", df["候选人"].tolist(),
                                    key="ap_name")
            ap_cand = df[df["候选人"]==ap_name].iloc[0]
            st.info(f"当前评分：**{ap_cand['AI综合评分']:.1f}分** · {ap_cand['评审区间']}")

        with ap2:
            ap_cat = st.selectbox("申诉类型", [
                "AI评分偏差（项目经历未被正确识别）",
                "绩效数据更新滞后",
                "笔试题目存在歧义",
                "其他（请在下方说明）",
            ])

        ap_reason = st.text_area(
            "详细说明（必填，请描述具体情况）",
            placeholder="例如：我在 XX 项目中担任产品负责人，主导了 XX 功能的设计与上线，"
                        "该项目 GMV 提升了 25%，但简历中的表述未能被 AI 准确识别…",
            height=130,
        )
        ap_files = st.file_uploader(
            "上传补充材料（可选，支持 PDF/DOCX/图片）",
            type=["pdf","docx","png","jpg","jpeg"],
            accept_multiple_files=True,
        )
        ap_contact = st.text_input("联系方式（工号/邮箱）",
                                    placeholder="EMP10001 / yourname@tencent.com")

        if st.button("📤 提交申诉", type="primary", disabled=not (ap_reason and ap_contact)):
            appeal_id = f"AP{len(st.session_state.appeals)+1001}"
            st.session_state.appeals[appeal_id] = {
                "candidate":  ap_name,
                "emp_id":     ap_cand["员工编号"],
                "score":      ap_cand["AI综合评分"],
                "category":   ap_cat,
                "reason":     ap_reason,
                "contact":    ap_contact,
                "files":      [f.name for f in ap_files] if ap_files else [],
                "status":     "⏳ 待审核",
                "submitted":  datetime.now().strftime("%Y-%m-%d %H:%M"),
                "hr_comment": "",
                "deadline":   "结果公示后 48 小时内有效",
            }
            st.success(f"✅ 申诉已提交！申诉编号：**{appeal_id}**  \n"
                       f"HR 将在 3 个工作日内联系 {ap_contact} 给出书面回复。")
            st.balloons()

    with status_tab:
        st.markdown("#### 申诉记录")
        if not st.session_state.appeals:
            st.info("暂无申诉记录")
        else:
            # HR side: manage appeals
            st.caption("（以下为 HR 管理视图，可更新处理状态）")
            for aid, ap in st.session_state.appeals.items():
                with st.expander(f"**{aid}** · {ap['candidate']} · {ap['status']} · {ap['submitted']}"):
                    st.markdown(f"""
| 字段 | 内容 |
|------|------|
| 申诉人 | {ap['candidate']}（{ap['emp_id']}） |
| 原始评分 | {ap['score']:.1f} 分 |
| 申诉类型 | {ap['category']} |
| 联系方式 | {ap['contact']} |
| 提交时间 | {ap['submitted']} |
| 附件 | {', '.join(ap['files']) if ap['files'] else '无'} |
""")
                    st.markdown(f"**申诉内容**：{ap['reason']}")
                    st.divider()

                    # HR process
                    new_status = st.selectbox("更新状态", ["⏳ 待审核","🔍 审核中","✅ 通过申诉","❌ 维持原判"],
                                               index=["⏳ 待审核","🔍 审核中","✅ 通过申诉","❌ 维持原判"].index(ap["status"]),
                                               key=f"st_{aid}")
                    hr_cmt = st.text_area("HR 回复意见", ap.get("hr_comment",""),
                                           key=f"cmt_{aid}", height=80)
                    if st.button("更新处理结果", key=f"upd_{aid}"):
                        st.session_state.appeals[aid]["status"]     = new_status
                        st.session_state.appeals[aid]["hr_comment"] = hr_cmt
                        st.success("已更新"); st.rerun()

            # Summary metrics
            st.divider()
            total_ap  = len(st.session_state.appeals)
            passed_ap = sum(1 for a in st.session_state.appeals.values() if "通过" in a["status"])
            rejected  = sum(1 for a in st.session_state.appeals.values() if "维持" in a["status"])
            pending   = total_ap - passed_ap - rejected
            aa,ab,ac = st.columns(3)
            aa.metric("申诉总数", str(total_ap))
            ab.metric("通过申诉", str(passed_ap))
            ac.metric("待处理",   str(pending))


# ════════════════════════════════════════════════════════════════════════════
# TAB 7 · 效果评估
# ════════════════════════════════════════════════════════════════════════════
with tab7:
    st.subheader("📈 运营效果预测评估")

    kpis = [
        ("评审时长(天)",  12,        14,  "越小越好"),
        ("人工复核率",    round(yellow_n/len(df)*100,1), 15, "越小越好"),
        ("预估投诉率",    3.5,        5,  "越小越好"),
        ("1年内离职率",  7.2,        10, "越小越好"),
    ]
    gcols = st.columns(4)
    for col, (name, actual, target, direction) in zip(gcols, kpis):
        with col:
            good  = actual < target
            color = "#52c41a" if good else "#ff4d4f"
            fig_g = go.Figure(go.Indicator(
                mode="gauge+number+delta", value=actual,
                number={"font":{"size":26,"color":color}},
                delta={"reference":target,"valueformat":".1f",
                       "decreasing":{"color":"#52c41a"},"increasing":{"color":"#ff4d4f"}},
                gauge={"axis":{"range":[0,target*1.5]},
                       "bar":{"color":color},
                       "steps":[{"range":[0,target*0.7],"color":"#f6ffed"},
                                 {"range":[target*0.7,target],"color":"#fffbe6"},
                                 {"range":[target,target*1.5],"color":"#fff2f0"}],
                       "threshold":{"line":{"color":"#ff4d4f","width":2},"value":target}},
                title={"text":f"{name}<br><span style='font-size:11px;color:gray'>目标≤{target}</span>"},
            ))
            fig_g.update_layout(height=220, margin=dict(l=20,r=20,t=60,b=20))
            st.plotly_chart(fig_g, use_container_width=True)

    st.divider()
    st.subheader("AI赋能前后对比")
    cmp_df = pd.DataFrame({
        "指标":     ["评审时长(天)","人工工作量(人天)","投诉率(%)","员工满意度(分)"],
        "AI赋能前": [30, 180, 22, 60],
        "AI赋能后": [12,  45,  3.5, 86],
        "目标值":   [14,  60,  5,  80],
    })
    fig_c = go.Figure()
    fig_c.add_trace(go.Bar(name="AI赋能前",    x=cmp_df["指标"], y=cmp_df["AI赋能前"],
                            marker_color="#ff7875", opacity=0.8))
    fig_c.add_trace(go.Bar(name="AI赋能后（预测）", x=cmp_df["指标"], y=cmp_df["AI赋能后"],
                            marker_color="#73d13d", opacity=0.8))
    fig_c.add_trace(go.Scatter(name="目标值", x=cmp_df["指标"], y=cmp_df["目标值"],
                                mode="markers+lines",
                                marker=dict(symbol="diamond",size=10,color="#1890ff"),
                                line=dict(dash="dash",color="#1890ff")))
    fig_c.update_layout(barmode="group", height=300,
                         margin=dict(l=20,r=20,t=20,b=20),
                         plot_bgcolor="rgba(0,0,0,0)",
                         legend=dict(orientation="h",y=1.1),
                         yaxis_title="数值")
    st.plotly_chart(fig_c, use_container_width=True)

    st.divider()
    st.subheader("三大降投诉/降离职路径")
    p1,p2,p3 = st.columns(3)
    with p1:
        st.markdown("""
#### 🎯 精准匹配
AI 岗位匹配度评估（40%权重）确保转岗员工与新岗高度契合，减少"入职后不适"导致的早期离职。

**AI匹配准确率 82%** → 通过人才满意度↑
        """)
    with p2:
        st.markdown("""
#### 📋 发展报告
落榜者收到含超链接学习资源的个性化报告，将"被淘汰"转化为"被看见+被指引"，提升组织归属感。

**报告覆盖率 100%** → 离职冲动↓
        """)
    with p3:
        st.markdown("""
#### 📣 申诉通道
48h申诉窗口+3个工作日回复机制，让候选人感受到"有异议可以说"，从根本上降低投诉意愿。

**申诉通道公开** → 投诉率从22%降至≤5%
        """)
