"""Build the static site: src/*.md -> site/*.html (no server needed, relative links only).

Chapter file: front matter (title, part, summary), then Markdown.
Custom fenced blocks ```flow / ```tables / ```seq become animated diagrams (assets/viz.js).
Fences ```sql-error and ```sql-skip are shown as plain sql.
"""
import glob, html, json, os, re
import markdown

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SRC = os.path.join(ROOT, "src")
OUT = os.path.join(ROOT, "site")
SITE_TITLE = "Postgres and Event-Driven Backends for Android Developers"
VIZ = re.compile(r"^```(flow|tables|seq)\n(.*?)^```", re.S | re.M)
FRONT = re.compile(r"\A---\n(.*?)\n---\n", re.S)


def parse(path):
    text = open(path, encoding="utf-8").read()
    m = FRONT.match(text)
    meta = dict(l.split(": ", 1) for l in m.group(1).splitlines() if ": " in l)
    return os.path.basename(path)[:-3], meta, text[m.end():]


def render_body(body):
    stash = []

    def viz(m):
        spec = json.loads(m.group(2))  # fails loudly on bad JSON
        stash.append(f'<div class="viz" data-type="{m.group(1)}" '
                     f'data-spec="{html.escape(json.dumps(spec), quote=True)}"></div>')
        return f"\n\nVIZ{len(stash) - 1}TOKEN\n\n"

    body = VIZ.sub(viz, body)
    body = re.sub(r"^```sql-(error|skip)$", "```sql", body, flags=re.M)
    out = markdown.markdown(body, extensions=["fenced_code", "tables", "admonition"])
    for i, div in enumerate(stash):
        out = out.replace(f"<p>VIZ{i}TOKEN</p>", div)
    return out


def sidebar(chapters, current):
    items, part = [], None
    for slug, meta, _ in chapters:
        if meta["part"] != part:
            part = meta["part"]
            items.append(f'<li class="part">{html.escape(part)}</li>')
        cur = ' class="cur"' if slug == current else ""
        num = slug.split("-")[0]
        items.append(f'<li><a href="{slug}.html"{cur}><span>{num}</span>{html.escape(meta["title"])}</a></li>')
    return "".join(items)


def page(title, nav, content, pager=""):
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)} · {SITE_TITLE}</title>
<link rel="stylesheet" href="assets/style.css"></head><body>
<div class="layout"><nav class="side"><a class="brand" href="index.html">{SITE_TITLE}
<small>A hands-on course for Android developers</small></a><ol>{nav}</ol></nav>
<main>{content}{pager}</main></div><script src="assets/viz.js"></script></body></html>"""


def main():
    chapters = [parse(p) for p in sorted(glob.glob(os.path.join(SRC, "*.md")))]
    for old in glob.glob(os.path.join(OUT, "*.html")):
        os.remove(old)
    for i, (slug, meta, body) in enumerate(chapters):
        nav = sidebar(chapters, slug)
        head = (f'<div class="crumb">{html.escape(meta["part"])}</div>'
                f'<h1>{html.escape(meta["title"])}</h1>')
        body_html = render_body(body)
        # the bold one-line definition right after the title is the chapter's lead
        body_html = body_html.replace("<p><strong>", '<p class="lead"><strong>', 1)
        prev = (f'<a href="{chapters[i-1][0]}.html"><small>Previous</small>{html.escape(chapters[i-1][1]["title"])}</a>'
                if i else "<span></span>")
        nxt = (f'<a class="next" href="{chapters[i+1][0]}.html"><small>Next</small>{html.escape(chapters[i+1][1]["title"])}</a>'
               if i + 1 < len(chapters) else "")
        open(os.path.join(OUT, slug + ".html"), "w", encoding="utf-8").write(
            page(meta["title"], nav, head + body_html, f'<div class="pager">{prev}{nxt}</div>'))
    cards = "".join(
        f'<a href="{s}.html"><b>{html.escape(m["part"])}</b>{html.escape(m["title"])}'
        f'<br><small>{html.escape(m["summary"])}</small></a>' for s, m, _ in chapters)
    home = (f"<h1>{SITE_TITLE}</h1><p class='lead'><strong>Learn SQL, PostgreSQL and event-driven "
            f"backends from where an Android developer already stands.</strong></p>"
            f'<p>Start with <a href="00-start-here.html">Start here</a>. Diagrams are animated: press Play.</p>'
            f'<div class="cards">{cards}</div>')
    open(os.path.join(OUT, "index.html"), "w", encoding="utf-8").write(page("Home", sidebar(chapters, ""), home))
    print(f"built {len(chapters)} chapters + index")


if __name__ == "__main__":
    main()
