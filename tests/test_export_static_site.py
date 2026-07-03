# -*- coding: utf-8 -*-
import json
import tempfile
import time
import unittest
from pathlib import Path

from scripts.export_static_site import export_static_site


DISCLAIMER = "仅供研究，不构成投资建议；不自动交易；不连接券商 API。"


class TestExportStaticSite(unittest.TestCase):
    def setUp(self):
        self._tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self._tempdir.name)
        self.reports_dir = self.root / "reports"
        self.logs_dir = self.root / "logs"
        self.output_dir = self.root / "public"
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self._tempdir.cleanup()

    def test_export_generates_placeholder_when_report_missing(self):
        (self.logs_dir / "analysis-error.txt").write_text("analysis failed", encoding="utf-8")

        metadata = export_static_site(
            output_dir=self.output_dir,
            reports_dir=self.reports_dir,
            logs_dir=self.logs_dir,
            stock_list=["600519", "510300"],
        )

        self.assertFalse(metadata["has_report"])
        self.assertEqual(metadata["stock_list"], ["600519", "510300"])
        self.assertEqual(metadata["error_message"], "analysis failed")
        self.assertTrue((self.output_dir / "index.html").exists())
        self.assertTrue((self.output_dir / "reports" / "latest.html").exists())
        self.assertTrue((self.output_dir / "data" / "latest.json").exists())
        self.assertTrue((self.output_dir / "data" / "history.json").exists())

        latest_html = (self.output_dir / "reports" / "latest.html").read_text(encoding="utf-8")
        self.assertIn("暂无正式报告，本次仅生成占位页面", latest_html)
        self.assertIn(DISCLAIMER, latest_html)

        latest_json = json.loads((self.output_dir / "data" / "latest.json").read_text(encoding="utf-8"))
        self.assertFalse(latest_json["has_report"])
        self.assertEqual(latest_json["report_path"], "reports/latest.html")

    def test_export_prefers_latest_html_report_and_sanitizes_absolute_terms(self):
        old_report = self.reports_dir / "old.md"
        old_report.write_text("旧报告", encoding="utf-8")
        time.sleep(0.02)
        latest_report = self.reports_dir / "latest.html"
        latest_report.write_text("<html><body><p>明天一定涨，建议买入。</p></body></html>", encoding="utf-8")

        metadata = export_static_site(
            output_dir=self.output_dir,
            reports_dir=self.reports_dir,
            logs_dir=self.logs_dir,
            stock_list=["600519"],
        )

        self.assertTrue(metadata["has_report"])
        latest_html = (self.output_dir / "reports" / "latest.html").read_text(encoding="utf-8")
        self.assertIn("高风险表述已隐藏", latest_html)
        self.assertNotIn("明天一定涨", latest_html)
        self.assertIn(DISCLAIMER, latest_html)
        self.assertIn("检测到操作相关词", latest_html)

    def test_export_converts_markdown_report(self):
        report = self.reports_dir / "report_20260703.md"
        report.write_text("# 标题\n\n建议买入，但需关注风险点。", encoding="utf-8")

        export_static_site(
            output_dir=self.output_dir,
            reports_dir=self.reports_dir,
            logs_dir=self.logs_dir,
            stock_list=["159915"],
        )

        latest_html = (self.output_dir / "reports" / "latest.html").read_text(encoding="utf-8")
        self.assertIn("<h1>标题</h1>", latest_html)
        self.assertIn("建议买入", latest_html)
        self.assertIn(DISCLAIMER, latest_html)
        self.assertIn("信号来源", latest_html)


if __name__ == "__main__":
    unittest.main()
