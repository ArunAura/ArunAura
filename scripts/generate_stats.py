#!/usr/bin/env python3
"""Generates assets/stats-dashboard.svg and assets/spent-time.svg from live GitHub data.
Run daily by .github/workflows/stats.yml. Standard library only."""
import json, os, re, sys, urllib.request, urllib.error
from datetime import date, datetime, timedelta

USER = os.environ.get("GH_USER", "ArunAura")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
OUT = os.environ.get("ASSETS_DIR", os.path.join(os.path.dirname(__file__), "..", "assets"))

MONO = "'JetBrains Mono','Fira Code','SF Mono',Consolas,'Courier New',monospace"
BG, PANEL, LINE, INK, MUTED = "#0d1117", "#111722", "#222b3a", "#e6edf3", "#8b98ad"
LANG_COLORS = {"Java": "#f89820", "JavaScript": "#f7df1e", "TypeScript": "#3178c6", "HTML": "#e34c26", "CSS": "#8b5cf6",
               "Python": "#4b8bbe", "C": "#9aa7b8", "C++": "#f34b7d", "SCSS": "#c6538c", "Shell": "#89e051", "PLpgSQL": "#336790",
               "Jupyter Notebook": "#da5b0b", "Dockerfile": "#384d54", "Kotlin": "#a97bff", "Go": "#00add8", "PHP": "#4f5d95"}
PALETTE = ["#58a6ff", "#a78bfa", "#f472b6", "#4ade80", "#fbbf24", "#22d3ee"]

def esc(s): return str(s).replace("&", "&amp;").replace("<", "&lt;")
def lcolor(n, i=0): return LANG_COLORS.get(n, PALETTE[i % len(PALETTE)])

def http(url, api=False):
    h = {"User-Agent": "profile-readme-stats"}
    if api:
        h["Accept"] = "application/vnd.github+json"
        if TOKEN: h["Authorization"] = f"Bearer {TOKEN}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=30) as r:
        return r.read().decode("utf-8", "replace")

# ---------------- data ----------------
def fetch_calendar():
    html = http(f"https://github.com/users/{USER}/contributions")
    tips = {}
    for m in re.finditer(r'for="(contribution-day-component-\d+-\d+)"[^>]*>\s*(No|\d+) contributions?', html):
        tips[m.group(1)] = 0 if m.group(2) == "No" else int(m.group(2))
    days = {}
    for m in re.finditer(r'<td[^>]*data-date="(\d{4}-\d{2}-\d{2})"[^>]*id="(contribution-day-component-\d+-\d+)"', html):
        days[date.fromisoformat(m.group(1))] = tips.get(m.group(2), 0)
    if not days: raise RuntimeError("could not parse contribution calendar")
    return dict(sorted(days.items()))

def fetch_profile_api():
    u = json.loads(http(f"https://api.github.com/users/{USER}", True))
    repos, page = [], 1
    while True:
        chunk = json.loads(http(f"https://api.github.com/users/{USER}/repos?per_page=100&page={page}&type=owner", True))
        repos += chunk
        if len(chunk) < 100: break
        page += 1
    repos = [r for r in repos if not r["fork"]]
    by_repo, by_size = {}, {}
    for r in repos:
        if r.get("language"): by_repo[r["language"]] = by_repo.get(r["language"], 0) + 1
        try:
            for k, v in json.loads(http(r["languages_url"], True)).items(): by_size[k] = by_size.get(k, 0) + v
        except Exception: pass
    return dict(repos=u["public_repos"], followers=u["followers"], stars=sum(r["stargazers_count"] for r in repos),
                by_repo=by_repo, by_size=by_size)

def fetch_profile_scrape():
    p = http(f"https://github.com/{USER}")
    rt = http(f"https://github.com/{USER}?tab=repositories")
    langs = {}
    for l in re.findall(r'itemprop="programmingLanguage">([^<]+)', rt): langs[l] = langs.get(l, 0) + 1
    nrepos = len(re.findall(r'itemprop="name codeRepository"', rt))
    fm = re.search(r'text-bold color-fg-default">([\d.,kK]+)</span>\s*followers', p)
    return dict(repos=nrepos, followers=int(fm.group(1)) if fm and fm.group(1).isdigit() else 0, stars=0,
                by_repo=langs, by_size=None)

# ---------------- analysis ----------------
def streaks(days):
    ds = sorted(days)
    longest, run, best_end, start = 0, 0, None, None
    prev = None
    for d in ds:
        if days[d] > 0:
            run = run + 1 if prev and (d - prev).days == 1 and days[prev] > 0 else 1
            if run > longest: longest, best_end = run, d
        else: run = 0
        prev = d
    rng = ""
    if longest:
        s = best_end - timedelta(days=longest - 1)
        rng = f"{s.strftime('%b')} {s.day} - {best_end.strftime('%b')} {best_end.day}"
    today = ds[-1]
    d = today if days[today] > 0 else today - timedelta(days=1)
    cur = 0
    while d in days and days[d] > 0: cur += 1; d -= timedelta(days=1)
    return cur, longest, rng

def human(n):
    return f"{n/1_000_000:.1f}M" if n >= 1_000_000 else f"{n/1000:.0f}K" if n >= 10_000 else f"{n/1000:.1f}K" if n >= 1000 else str(n)

# ---------------- svg helpers ----------------
DEFS = f'''<linearGradient id="fr" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#58a6ff"/><stop offset=".5" stop-color="#a78bfa"/><stop offset="1" stop-color="#f472b6"/></linearGradient>
<linearGradient id="bar" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#f472b6"/><stop offset="1" stop-color="#58a6ff"/></linearGradient>
<linearGradient id="gt" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#bef264"/><stop offset="1" stop-color="#4ade80"/></linearGradient>
<linearGradient id="bt" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#67e8f9"/><stop offset="1" stop-color="#60a5fa"/></linearGradient>
<linearGradient id="hl" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff" stop-opacity=".05"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>
<filter id="bl" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="40"/></filter>'''

def frame(w, h, body, extra=""):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" font-family="{MONO}">
<defs>{DEFS}{extra}<clipPath id="cp"><rect width="{w}" height="{h}" rx="20"/></clipPath></defs>
<g clip-path="url(#cp)"><rect width="{w}" height="{h}" fill="{BG}"/>
<g filter="url(#bl)" opacity=".16"><circle cx="90" cy="60" r="110" fill="#58a6ff"><animate attributeName="cx" values="90;220;90" dur="16s" repeatCount="indefinite"/></circle><circle cx="{w-90}" cy="{h-40}" r="120" fill="#a78bfa"><animate attributeName="cx" values="{w-90};{w-240};{w-90}" dur="19s" repeatCount="indefinite"/></circle></g>
<rect width="{w}" height="{h*0.3:.0f}" fill="url(#hl)"/>{body}</g>
<rect x="1" y="1" width="{w-2}" height="{h-2}" rx="19" fill="none" stroke="url(#fr)" stroke-width="1.6"/></svg>'''

def panel(x, y, w, h, body):
    return f'<g transform="translate({x} {y})"><rect width="{w}" height="{h}" rx="14" fill="{PANEL}" stroke="{LINE}"/>{body}</g>'

def donut(cx, cy, items, total, label, sub, delay=0):
    r, sw = 58, 22
    circ = 2 * 3.14159265 * r
    out = f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#1a2232" stroke-width="{sw}"/>'
    acc = 0
    for i, (name, val) in enumerate(items):
        frac = val / total if total else 0
        seg = max(frac * circ - 2, 0)
        out += (f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{lcolor(name, i)}" stroke-width="{sw}" stroke-dasharray="0 {circ:.2f}" '
                f'stroke-dashoffset="{-acc:.2f}" transform="rotate(-90 {cx} {cy})"><animate attributeName="stroke-dasharray" from="0 {circ:.2f}" to="{seg:.2f} {circ-seg:.2f}" dur=".9s" begin="{delay + i*0.12:.2f}s" fill="freeze"/></circle>')
        acc += frac * circ
    out += f'<text x="{cx}" y="{cy+4}" font-size="26" font-weight="800" fill="{INK}" text-anchor="middle">{esc(label)}</text>'
    out += f'<text x="{cx}" y="{cy+24}" font-size="11" fill="{MUTED}" text-anchor="middle">{esc(sub)}</text>'
    return out

def legend(x, y0, items, total, right):
    out = ""
    for i, (name, val) in enumerate(items):
        y = y0 + i * 32
        c = lcolor(name, i)
        out += (f'<circle cx="{x+6}" cy="{y-5}" r="6" fill="{c}"/><text x="{x+22}" y="{y}" font-size="14" fill="{INK}">{esc(name)}</text>'
                f'<text x="{right}" y="{y}" font-size="14" font-weight="700" fill="{c}" text-anchor="end">{val/total*100:.1f}%</text>')
    return out

def top_n(d, n=5):
    items = sorted(d.items(), key=lambda kv: -kv[1])
    if len(items) > n:
        items = items[:n - 1] + [("Other", sum(v for _, v in items[n - 1:]))]
    return items

# ---------------- dashboard ----------------
def dashboard(days, prof):
    W, H = 1000, 642
    last12 = {d: c for d, c in days.items() if d > max(days) - timedelta(days=365)}
    total = sum(last12.values())
    cur, longest, rng = streaks(days)
    wk = [0] * 7
    for d, c in last12.items(): wk[d.weekday()] += c
    names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    mx = max(wk) or 1
    top_day = names[wk.index(max(wk))] if max(wk) else "-"
    b = f'<text x="34" y="50" font-size="22" font-weight="800" fill="url(#gt)">GitHub Stats</text><text x="966" y="50" font-size="12" fill="{MUTED}" text-anchor="end">live from GitHub - updates every day</text>'
    # row 1
    circ = 2 * 3.14159265 * 44
    prog = min(cur / longest, 1) if longest else 0
    left = (f'<text x="88" y="112" font-size="54" font-weight="800" fill="#58a6ff" text-anchor="middle">{total}</text>'
            f'<text x="88" y="142" font-size="14" fill="{INK}" text-anchor="middle">Contributions</text><text x="88" y="162" font-size="11" fill="{MUTED}" text-anchor="middle">last 12 months</text>'
            f'<path d="M236 22c4 7 9 10 9 17a9 9 0 0 1-18 0c0-4 2-6 4-9 1 3 3 4 4 3 1-4 0-7 1-11z" fill="#fb923c"/>'
            f'<circle cx="236" cy="104" r="44" fill="none" stroke="#1a2232" stroke-width="10"/>'
            f'<circle cx="236" cy="104" r="44" fill="none" stroke="#fb923c" stroke-width="10" stroke-linecap="round" transform="rotate(-90 236 104)" stroke-dasharray="0 {circ:.1f}"><animate attributeName="stroke-dasharray" from="0 {circ:.1f}" to="{prog*circ:.1f} {circ:.1f}" dur="1.1s" fill="freeze"/></circle>'
            f'<text x="236" y="114" font-size="30" font-weight="800" fill="#fb923c" text-anchor="middle">{cur}</text>'
            f'<text x="236" y="178" font-size="14" font-weight="700" fill="#fb923c" text-anchor="middle">Current Streak</text>'
            f'<text x="384" y="112" font-size="54" font-weight="800" fill="#a78bfa" text-anchor="middle">{longest}</text>'
            f'<text x="384" y="142" font-size="14" fill="{INK}" text-anchor="middle">Longest Streak</text><text x="384" y="162" font-size="11" fill="{MUTED}" text-anchor="middle">{esc(rng or "-")}</text>')
    b += panel(28, 76, 472, 196, left)
    bars = f'<text x="22" y="32" font-size="14" font-weight="700" fill="{INK}">Contributions by Weekday</text><text x="436" y="32" font-size="11" fill="{MUTED}" text-anchor="end">most active: {top_day}</text>'
    for i, v in enumerate(wk):
        h = max(v / mx * 84, 6)
        x = 30 + i * 59
        fill = "#f5f5f5" if v == max(wk) and v > 0 else "url(#bar)"
        bars += (f'<rect x="{x}" y="{150-h:.1f}" width="42" height="{h:.1f}" rx="7" fill="{fill}"><animate attributeName="height" from="0" to="{h:.1f}" dur=".8s" begin="{i*0.08:.2f}s" fill="freeze"/><animate attributeName="y" from="150" to="{150-h:.1f}" dur=".8s" begin="{i*0.08:.2f}s" fill="freeze"/></rect>'
                 f'<text x="{x+21}" y="{142-h:.1f}" font-size="13" font-weight="700" fill="{INK}" text-anchor="middle">{v}</text>'
                 f'<text x="{x+21}" y="172" font-size="11" fill="{MUTED}" text-anchor="middle">{names[i]}</text>')
    b += panel(514, 76, 458, 196, bars)
    # row 2
    rl = top_n(prof["by_repo"]) if prof["by_repo"] else []
    rt = sum(v for _, v in rl)
    p1 = f'<text x="24" y="34" font-size="14" font-weight="700" fill="{INK}">Top Languages by Repository</text>'
    if rl:
        p1 += donut(112, 140, rl, rt, str(sum(v for _, v in rl)), "repos") + legend(212, 104, rl, rt, 448)
    else: p1 += f'<text x="236" y="140" font-size="13" fill="{MUTED}" text-anchor="middle">No public repos with a language yet</text>'
    b += panel(28, 290, 472, 250, p1)
    p2 = f'<text x="24" y="34" font-size="14" font-weight="700" fill="{INK}">Top Languages by Code Size</text>'
    if prof["by_size"]:
        sl = top_n(prof["by_size"]); st = sum(v for _, v in sl)
        p2 += donut(112, 140, sl, st, human(st), "code", 0.3) + legend(212, 104, sl, st, 434)
    else:
        p2 += (f'<circle cx="112" cy="140" r="58" fill="none" stroke="#1a2232" stroke-width="22"/><text x="112" y="144" font-size="13" fill="{MUTED}" text-anchor="middle">code</text>'
               f'<text x="212" y="130" font-size="13" fill="{MUTED}">Code size appears after</text><text x="212" y="152" font-size="13" fill="{MUTED}">the first daily update.</text>')
    b += panel(514, 290, 458, 250, p2)
    # row 3
    def pill(x, w, c, label, val):
        return panel(x, 558, w, 56, f'<circle cx="26" cy="28" r="8" fill="{c}"/><text x="46" y="33" font-size="14" fill="{INK}">{label}</text><text x="{w-24}" y="35" font-size="21" font-weight="800" fill="{c}" text-anchor="end">{val}</text>')
    b += pill(28, 300, "#58a6ff", "Public Repos", prof["repos"]) + pill(350, 290, "#fbbf24", "Total Stars", prof["stars"]) + pill(662, 310, "#4ade80", "Followers", prof["followers"])
    return frame(W, H, b)

# ---------------- spent my time ----------------
def spent(days, prof):
    W, H = 1000, 452
    ds = sorted(days)
    start = ds[0] - timedelta(days=(ds[0].weekday() + 1) % 7)  # Sunday on/before first day
    cols = {}
    for d in ds:
        cols.setdefault((d - start).days // 7, {})[(d.weekday() + 1) % 7] = (d, days[d])
    last_cols = sorted(cols)[-26:]
    cells = [(ci, r, cols[c][r][0], cols[c][r][1]) for ci, c in enumerate(last_cols) for r in range(7) if r in cols[c]]
    counts = [c for *_, c in cells]
    mx = max(counts) if counts and max(counts) else 1
    palette = ["#161d29", "#1d6f8a", "#2dd4e0", "#7ee787", "#ffb86b", "#ff79c6"]
    def lvl(c): return 0 if c == 0 else min(1 + int((c - 1) / mx * 5), 5)
    b = f'<text x="34" y="50" font-size="22" font-weight="800" fill="url(#bt)">Spent My Time</text><text x="966" y="50" font-size="12" fill="{MUTED}" text-anchor="end">last 26 weeks - every square is a day</text>'
    # terminal
    lines = [[("const ", "#ff79c6"), ("dev ", "#e6edf3"), ("= {", "#e6edf3")],
             [("  name", "#79c0ff"), (": ", "#e6edf3"), ('"Arun Kumar"', "#7ee787"), (",", "#e6edf3")],
             [("  role", "#79c0ff"), (": ", "#e6edf3"), ('"Full Stack Dev"', "#7ee787"), (",", "#e6edf3")],
             [("  stack", "#79c0ff"), (": [", "#e6edf3"), ('"Java"', "#7ee787"), (", ", "#e6edf3"), ('"Spring"', "#7ee787"), ("],", "#e6edf3")],
             [("};", "#e6edf3")],
             [("build", "#d2a8ff"), ("(dev);  ", "#e6edf3"), ("// ship it", "#6e7a8e")]]
    t = (f'<rect x="34" y="84" width="326" height="196" rx="14" fill="#0a111d" stroke="#2a3548" stroke-width="1.5"/>'
         '<circle cx="56" cy="106" r="5.5" fill="#ff5f56"/><circle cx="76" cy="106" r="5.5" fill="#ffbd2e"/><circle cx="96" cy="106" r="5.5" fill="#27c93f"/>'
         '<rect x="22" y="288" width="350" height="10" rx="5" fill="#161d29" stroke="#222b3a"/>')
    for i, ln in enumerate(lines):
        spans = "".join(f'<tspan fill="{c}">{esc(s).replace(" ", "&#160;")}</tspan>' for s, c in ln)
        a = i / 8
        t += (f'<text x="54" y="{142+i*25}" font-size="13.5" xml:space="preserve" opacity="0">{spans}'
              f'<animate attributeName="opacity" values="0;0;1;1;0" keyTimes="0;{a:.3f};{a+0.05:.3f};0.9;1" dur="11s" repeatCount="indefinite"/></text>')
    t += f'<rect x="{54+19*8.1:.1f}" y="{142+5*25-12}" width="8" height="15" fill="#4ade80" opacity="0"><animate attributeName="opacity" values="0;0;1;0;1;0" keyTimes="0;.55;.56;.7;.8;1" dur="11s" repeatCount="indefinite"/></rect>'
    b += t
    # heatmap
    hx, hy, pitch = 396, 86, 21
    for ci, r, d, c in cells:
        col = palette[lvl(c)]
        b += (f'<rect x="{hx+ci*pitch}" y="{hy+r*pitch}" width="17" height="17" rx="4.5" fill="{col}" opacity="0"><title>{d.isoformat()}: {c}</title>'
              f'<animate attributeName="opacity" from="0" to="1" dur=".35s" begin="{ci*0.03:.2f}s" fill="freeze"/></rect>')
    b += f'<text x="{hx}" y="262" font-size="11" fill="{MUTED}">Less</text>'
    for i, col in enumerate(palette): b += f'<rect x="{hx+34+i*21}" y="251" width="14" height="14" rx="4" fill="{col}"/>'
    b += f'<text x="{hx+34+6*21+4}" y="262" font-size="11" fill="{MUTED}">More</text>'
    # stats
    week_total = sum(c for d, c in days.items() if d >= max(days) - timedelta(days=(max(days).weekday() + 1) % 7))
    active = sum(1 for c in counts if c > 0)
    for i, (n, lab, col) in enumerate([(active, "Active days", "#7ee787"), (max(counts) if counts else 0, "Best day", "#ffb86b"), (week_total, "This week", "#58a6ff")]):
        b += f'<text x="{hx+i*180}" y="322" font-size="32" font-weight="800" fill="{col}">{n}</text><text x="{hx+i*180}" y="344" font-size="12" fill="{MUTED}">{lab}</text>'
    # languages
    b += f'<text x="34" y="384" font-size="14" font-weight="700" fill="{INK}">Where my code goes</text>'
    src = prof["by_size"] or prof["by_repo"]
    tot = sum(src.values()) or 1
    for i, (n, v) in enumerate(sorted(src.items(), key=lambda kv: -kv[1])[:3]):
        x = 34 + i * 322; w = 290; c = lcolor(n, i); pct = v / tot * 100
        b += (f'<text x="{x}" y="414" font-size="13" fill="{INK}">{esc(n)}</text><text x="{x+w}" y="414" font-size="13" font-weight="700" fill="{c}" text-anchor="end">{pct:.1f}%</text>'
              f'<rect x="{x}" y="424" width="{w}" height="12" rx="6" fill="#1a2232"/><rect x="{x}" y="424" width="0" height="12" rx="6" fill="{c}"><animate attributeName="width" from="0" to="{w*pct/100:.1f}" dur=".9s" begin="{i*0.15:.2f}s" fill="freeze"/></rect>')
    return frame(W, H, b)

def main():
    os.makedirs(OUT, exist_ok=True)
    days = fetch_calendar()
    try:
        prof = fetch_profile_api()
        print("profile via API")
    except Exception as e:
        print("API unavailable, using page scrape:", e)
        prof = fetch_profile_scrape()
    open(os.path.join(OUT, "stats-dashboard.svg"), "w").write(dashboard(days, prof))
    open(os.path.join(OUT, "spent-time.svg"), "w").write(spent(days, prof))
    print("written; repos", prof["repos"], "followers", prof["followers"], "days", len(days))

if __name__ == "__main__":
    main()
