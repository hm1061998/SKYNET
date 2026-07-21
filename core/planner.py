"""Lập kế hoạch cho một tác vụ và render ra file HTML trong plans/."""
from __future__ import annotations
import html
import time

from . import PLANS_DIR


def new_plan_path() -> "os.PathLike":
    PLANS_DIR.mkdir(exist_ok=True)
    return PLANS_DIR / f"plan_{time.strftime('%Y%m%d_%H%M%S')}.html"


def render_plan_html(task: str, steps: list[str], path=None):
    path = path or new_plan_path()
    items = "\n".join(
        f'      <li><span class="num">{i+1}</span><span class="txt">{html.escape(str(s))}</span></li>'
        for i, s in enumerate(steps)
    )
    doc = _TEMPLATE.format(task=html.escape(task), items=items,
                           ts=time.strftime("%H:%M:%S %d/%m/%Y"))
    path.write_text(doc, encoding="utf-8")
    return path


_TEMPLATE = """<!DOCTYPE html>
<html lang="vi"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Kế hoạch — Javis</title>
<style>
  body{{ margin:0; font-family:"Segoe UI",system-ui,sans-serif; background:#05070f; color:#dCEBFF; padding:26px; }}
  .card{{ max-width:680px; margin:auto; background:rgba(12,18,34,.6);
    border:1px solid rgba(90,180,220,.18); border-radius:16px; padding:22px 26px; }}
  .tag{{ font-size:11px; letter-spacing:.24em; text-transform:uppercase; color:#50f6c8; }}
  h1{{ font-size:20px; margin:6px 0 2px; color:#eaf6ff; }}
  .ts{{ font-size:12px; color:#7ea0c8; margin-bottom:18px; }}
  ol{{ list-style:none; margin:0; padding:0; }}
  li{{ display:flex; gap:14px; align-items:flex-start; padding:11px 0; border-top:1px solid rgba(90,180,220,.10); }}
  .num{{ flex:none; width:26px; height:26px; border-radius:50%; display:grid; place-items:center;
    font-size:13px; font-weight:700; color:#05070f; background:linear-gradient(135deg,#50f6c8,#4fe3ff); }}
  .txt{{ padding-top:3px; font-size:14.5px; line-height:1.45; }}
</style></head>
<body><div class="card">
  <div class="tag">Kế hoạch thực thi</div>
  <h1>{task}</h1>
  <div class="ts">Tạo lúc {ts}</div>
  <ol>
{items}
  </ol>
</div></body></html>
"""
