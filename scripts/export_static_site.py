# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import markdown2

DISCLAIMER = "仅供研究，不构成投资建议；不自动交易；不连接券商 API。"
PLACEHOLDER_TEXT = "暂无正式报告，本次仅生成占位页面"
ABSOLUTE_RISK_PATTERNS = [
    "必涨",
    "稳赚",
    "无风险",
    "满仓",
    "梭哈",
    "绝对可以买",
    "明天一定涨",
]
OPERATION_TERMS = [
    "买入",
    "卖出",
    "加仓",
    "减仓",
    "建仓",
    "清仓",
    "小仓试错",
    "优先观察",
    "等回调",
    "风险回避",
]
OPERATION_GUARDRAIL_HTML = """
<section class=\"guardrail\"> 
  <h2>操作倾向说明</h2>
  <p>检测到操作相关词，以下内容为研究框架，不构成直接指令。</p>
  <ul>
    <li>信号来源：请结合原始行情、公告和数据源交叉验证</li>
    <li>技术面依据：均线、量价、趋势强弱与波动结构</li>
    <li>基本面依据：业绩、现金流、行业地位与成长质量</li>
    <li>估值依据：PE、PB、股息率或同业比较</li>
    <li>资金面依据：成交额、主力资金、北向/南向或ETF流向</li>
    <li>新闻/公告依据：财报、指引、监管、产业催化或风险事件</li>
    <li>风险点：宏观、行业、业绩不及预期与流动性风险</li>
    <li>失效条件：趋势破坏、基本面反转、估值失衡或事件证伪</li>
    <li>建议仓位上限：仅限小仓位研究观察</li>
    <li>仅供研究，不构成投资建议</li>
  </ul>
</section>
""".strip()

BASE_STYLE = """
:root {
  color-scheme: light;
  --bg: #f6f0e8;
  --card: #fffdf8;
  --ink: #1f1a17;
  --muted: #6f6258;
  --line: #d9cbbd;
  --accent: #9d2f24;
  --accent-soft: #f3ddd7;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: Georgia, "Noto Serif SC", "Songti SC", serif;
  background:
    radial-gradient(circle at top left, rgba(157,47,36,0.10), transparent 26%),
    linear-gradient(180deg, #fbf7f1 0%, var(--bg) 100%);
  color: var(--ink);
}
main {
  width: min(980px, calc(100vw - 32px));
  margin: 32px auto 48px;
}
.hero, .panel, article.report {
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: 20px;
  box-shadow: 0 14px 40px rgba(31, 26, 23, 0.08);
}
.hero, .panel { padding: 24px; }
.hero h1, article.report h1, article.report h2, article.report h3 { margin-top: 0; }
.hero p, .meta, .disclaimer, .guardrail p, li { line-height: 1.7; }
.hero { margin-bottom: 20px; }
.grid { display: grid; gap: 16px; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); margin: 18px 0; }
.panel { padding: 18px 20px; }
.label { color: var(--muted); font-size: 13px; text-transform: uppercase; letter-spacing: 0.08em; }
.value { font-size: 18px; font-weight: 700; margin-top: 8px; word-break: break-word; }
.actions { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 18px; }
.actions a {
  text-decoration: none;
  color: white;
  background: var(--accent);
  padding: 10px 16px;
  border-radius: 999px;
}
article.report {
  padding: 28px;
}
article.report pre, article.report code {
  font-family: "Consolas", "Courier New", monospace;
}
article.report pre {
  overflow-x: auto;
  padding: 14px;
  background: #f7f1ea;
  border-radius: 12px;
}
article.report blockquote {
  margin: 0;
  padding: 8px 16px;
  border-left: 4px solid var(--accent);
  background: var(--accent-soft);
}
.notice, .disclaimer, .guardrail {
  border-radius: 14px;
  padding: 16px 18px;
  margin: 18px 0;
}
.notice { background: #fff2cc; border: 1px solid #e3c56a; }
.disclaimer, .guardrail { background: var(--accent-soft); border: 1px solid #e3b8af; }
.meta-list { padding-left: 18px; }
@media (max-width: 640px) {
  main { width: min(100vw - 20px, 980px); margin-top: 16px; }
  .hero, .panel, article.report { border-radius: 16px; }
  article.report { padding: 20px; }
}
""".strip()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _discover_latest_report(reports_dir: Path) -> Optional[Path]:
    if not reports_dir.exists():
        return None
    candidates = [
        path for path in reports_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in {".html", ".htm", ".md", ".markdown"}
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda item: item.stat().st_mtime)


def _load_error_message(logs_dir: Path) -> str:
    if not logs_dir.exists():
        return ""
    preferred = logs_dir / "analysis-error.txt"
    if preferred.exists():
        return _read_text(preferred).strip()
    txt_files = sorted(
        [path for path in logs_dir.glob("*.txt") if path.is_file()],
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    if txt_files:
        return _read_text(txt_files[0]).strip()
    return ""


def _sanitize_absolute_terms(text: str) -> Tuple[str, bool]:
    sanitized = text
    flagged = False
    for keyword in ABSOLUTE_RISK_PATTERNS:
        if keyword in sanitized:
            flagged = True
            sanitized = sanitized.replace(keyword, "[高风险表述已隐藏]")
    return sanitized, flagged


def _contains_operation_terms(text: str) -> bool:
    return any(keyword in text for keyword in OPERATION_TERMS)


def _wrap_report_body(body_html: str, *, flagged_absolute: bool, flagged_operation: bool) -> str:
    sections: List[str] = []
    if flagged_absolute:
        sections.append('<div class="notice"><strong>风险提示：</strong>检测到高风险表述已隐藏，请勿将报告视为确定性收益承诺。</div>')
    if flagged_operation:
        sections.append(OPERATION_GUARDRAIL_HTML)
    sections.append(f'<div class="disclaimer"><strong>免责声明：</strong>{escape(DISCLAIMER)}</div>')
    sections.append(body_html)
    return "\n".join(sections)


def _convert_markdown_to_html(markdown_text: str) -> str:
    return markdown2.markdown(markdown_text, extras=["fenced-code-blocks", "tables", "strike", "task_list"])


def _render_report_html(source_path: Optional[Path]) -> Tuple[str, bool, bool, str]:
    if source_path is None:
        body = (
            f'<div class="notice"><strong>占位说明：</strong>{escape(PLACEHOLDER_TEXT)}</div>'
            f'<div class="disclaimer"><strong>免责声明：</strong>{escape(DISCLAIMER)}</div>'
            '<p>数据不足，暂不形成操作倾向。</p>'
        )
        return body, False, False, ""

    raw = _read_text(source_path)
    sanitized, flagged_absolute = _sanitize_absolute_terms(raw)
    flagged_operation = _contains_operation_terms(sanitized)
    if source_path.suffix.lower() in {".md", ".markdown"}:
        report_body = _convert_markdown_to_html(sanitized)
    else:
        report_body = sanitized
    final_body = _wrap_report_body(report_body, flagged_absolute=flagged_absolute, flagged_operation=flagged_operation)
    return final_body, flagged_absolute, flagged_operation, str(source_path.name)


def _render_latest_report_page(report_inner_html: str) -> str:
    return f"""<!doctype html>
<html lang=\"zh-CN\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <title>最新研究报告</title>
  <style>{BASE_STYLE}</style>
</head>
<body>
  <main>
    <article class=\"report\">
      {report_inner_html}
    </article>
  </main>
</body>
</html>
"""


def _render_index_page(*, generated_at: str, stock_list: Sequence[str], has_report: bool, error_message: str) -> str:
    stock_value = ", ".join(stock_list) if stock_list else "未配置"
    report_state = "已生成正式报告" if has_report else PLACEHOLDER_TEXT
    error_panel = f'<div class="notice"><strong>运行备注：</strong>{escape(error_message)}</div>' if error_message else ""
    return f"""<!doctype html>
<html lang=\"zh-CN\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <title>股票/基金筛选看板</title>
  <style>{BASE_STYLE}</style>
</head>
<body>
  <main>
    <section class=\"hero\">
      <p class=\"label\">Daily Research Dashboard</p>
      <h1>股票/基金筛选看板</h1>
      <p>该页面由 GitHub Actions 生成静态研究页面，聚焦每日观察信号、风险提示与辅助分析，不提供自动交易能力。</p>
      <div class=\"grid\">
        <section class=\"panel\"><div class=\"label\">当前运行时间</div><div class=\"value\">{escape(generated_at)}</div></section>
        <section class=\"panel\"><div class=\"label\">STOCK_LIST</div><div class=\"value\">{escape(stock_value)}</div></section>
        <section class=\"panel\"><div class=\"label\">报告状态</div><div class=\"value\">{escape(report_state)}</div></section>
      </div>
      <div class=\"actions\"><a href=\"reports/latest.html\">查看最新报告</a></div>
      {error_panel}
      <div class=\"disclaimer\"><strong>免责声明：</strong>{escape(DISCLAIMER)}</div>
    </section>
  </main>
</body>
</html>
"""


def export_static_site(*, output_dir: Path, reports_dir: Path, logs_dir: Path, stock_list: Sequence[str]) -> Dict[str, Any]:
    output_dir = Path(output_dir)
    reports_dir = Path(reports_dir)
    logs_dir = Path(logs_dir)
    generated_at = _utc_now_iso()
    latest_report_path = _discover_latest_report(reports_dir)
    report_html, _, _, source_name = _render_report_html(latest_report_path)
    latest_page = _render_latest_report_page(report_html)
    error_message = "" if latest_report_path else _load_error_message(logs_dir)

    latest_json = {
        "generated_at": generated_at,
        "stock_list": list(stock_list),
        "has_report": latest_report_path is not None,
        "report_path": "reports/latest.html",
        "source_report": source_name,
        "error_message": error_message,
    }
    history_json = [latest_json]

    _write_text(output_dir / "reports" / "latest.html", latest_page)
    _write_text(
        output_dir / "index.html",
        _render_index_page(
            generated_at=generated_at,
            stock_list=stock_list,
            has_report=latest_report_path is not None,
            error_message=error_message,
        ),
    )
    _write_text(output_dir / "data" / "latest.json", json.dumps(latest_json, ensure_ascii=False, indent=2))
    _write_text(output_dir / "data" / "history.json", json.dumps(history_json, ensure_ascii=False, indent=2))
    return latest_json


def _parse_stock_list(raw: Optional[str]) -> List[str]:
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Export reports into a Netlify-ready static site")
    parser.add_argument("--output", default="public", help="Static output directory, default public")
    parser.add_argument("--reports-dir", default="reports", help="Reports source directory")
    parser.add_argument("--logs-dir", default="logs", help="Logs directory used for placeholder error messages")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    output_dir = (repo_root / args.output).resolve()
    reports_dir = (repo_root / args.reports_dir).resolve()
    logs_dir = (repo_root / args.logs_dir).resolve()
    stock_list = _parse_stock_list(os.getenv("STOCK_LIST") or os.getenv("STOCK_LIST_CONFIG"))

    export_static_site(
        output_dir=output_dir,
        reports_dir=reports_dir,
        logs_dir=logs_dir,
        stock_list=stock_list,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
