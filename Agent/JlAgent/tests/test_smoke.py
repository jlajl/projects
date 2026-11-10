"""JlAgent 冒烟测试：不需要大模型，不需要网络，不需要 mcp 包。

运行方式：
    python -m unittest discover -s tests -v      # 在 Agent/JlAgent 下执行
    python tests/test_smoke.py
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.tools.base import Tool, ToolRegistry  # noqa: E402
from core.tools.filesystem import build_tools as build_fs_tools  # noqa: E402
from core.tools.system import build_tools as build_sys_tools  # noqa: E402
from core.tools.system import is_leap_year  # noqa: E402


class LeapYearTest(unittest.TestCase):
    """闰年规则：能被 4 整除，整百年必须能被 400 整除。"""

    def test_rule_cases(self):
        cases = {
            4: True,
            1600: True,
            1900: False,  # 整百年但不能被 400 整除
            2000: True,
            2023: False,
            2024: True,
            2100: False,
        }
        for year, expected in cases.items():
            self.assertIs(is_leap_year(year), expected, f"{year} 判定错误")

    def test_tool_contract_and_output(self):
        tools = {tool.name: tool for tool in build_sys_tools(Path("."))}
        self.assertIn("isLeapYear", tools)
        leap = tools["isLeapYear"]
        self.assertTrue(leap.description.strip(), "工具描述不能为空")
        year_schema = leap.parameters["properties"]["year"]
        self.assertEqual(year_schema["type"], "integer")
        self.assertEqual(leap.parameters["required"], ["year"])

        self.assertIn("是闰年", leap.handler(year=2024))
        self.assertIn("不是闰年", leap.handler(year=1900))
        self.assertIn("不是闰年", leap.handler(year=2100))
        self.assertIn("错误", leap.handler(year="abc"))
        self.assertIn("错误", leap.handler(year=0))
        self.assertIn("错误", leap.handler(year=10000))

    def test_get_date_is_not_hardcoded(self):
        tools = {tool.name: tool for tool in build_sys_tools(Path("."))}
        output = tools["getDate"].handler()
        self.assertRegex(output, r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")


class FilesystemToolTest(unittest.TestCase):
    """十个文件/目录语义都必须在磁盘上产生真实副作用。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name).resolve()
        self.tools = {tool.name: tool for tool in build_fs_tools(self.root)}

    def tearDown(self):
        self._tmp.cleanup()

    def test_all_ten_semantics_have_real_effects(self):
        t = self.tools
        self.assertIn("已创建目录", t["createDir"].handler(path="a/b"))
        self.assertTrue((self.root / "a" / "b").is_dir(), "createDir 未真实建目录")

        self.assertIn("已创建文件", t["createFile"].handler(dir="a/b", name="n.txt", content="x"))
        self.assertEqual((self.root / "a" / "b" / "n.txt").read_text(encoding="utf-8"), "x")

        self.assertIn("已更新文件", t["editFile"].handler(path="a/b/n.txt", content="y"))
        self.assertEqual(t["readFile"].handler(path="a/b/n.txt"), "y")

        self.assertIn("纯文本", t["getFileType"].handler(path="a/b/n.txt"))
        self.assertEqual(t["getFileType"].handler(path="a"), "目录")
        self.assertIn("n.txt", t["listDir"].handler(path="a/b"))

        self.assertIn("已重命名", t["rename"].handler(src="a/b/n.txt", dst="a/b/m.txt"))
        self.assertTrue((self.root / "a" / "b" / "m.txt").is_file())

        self.assertIn("已删除文件", t["removeFile"].handler(path="a/b/m.txt"))
        self.assertFalse((self.root / "a" / "b" / "m.txt").exists())

        self.assertIn("已删除目录", t["removeDir"].handler(path="a"))
        self.assertFalse((self.root / "a").exists(), "removeDir 未删除非空目录")

    def test_registry_schema_shape(self):
        schema = self.tools["readFile"].schema()
        self.assertEqual(schema["type"], "function")
        self.assertEqual(schema["function"]["name"], "readFile")
        self.assertIn("parameters", schema["function"])
        self.assertEqual(schema["function"]["parameters"]["required"], ["path"])

    def test_path_escape_is_blocked(self):
        with self.assertRaises(ValueError):
            self.tools["listDir"].handler(path="../")
        with self.assertRaises(ValueError):
            self.tools["readFile"].handler(path=str(self.root.parent / "outside.txt"))

    def test_registry_turns_exception_into_tool_error(self):
        registry = ToolRegistry([self.tools["readFile"]])
        result = registry.execute("readFile", '{"path": "../secret.txt"}')
        self.assertIn("工具执行失败", result)
        self.assertIn("错误：未知工具", registry.execute("noSuchTool", "{}"))

    def test_create_file_refuses_overwrite(self):
        self.assertIn("已创建文件", self.tools["createFile"].handler(dir=".", name="dup.txt"))
        self.assertIn("已存在", self.tools["createFile"].handler(dir=".", name="dup.txt"))

    def test_destructive_ops_are_guarded(self):
        self.assertIn("禁止", self.tools["removeDir"].handler(path="."))
        self.assertIn("禁止", self.tools["rename"].handler(src=".", dst="x"))
        self.assertTrue(self.root.is_dir(), "工作区根目录不应被删除")


class ToolDataclassTest(unittest.TestCase):
    def test_registry_deduplicates_by_name(self):
        tool = Tool("dup", "描述", {"type": "object", "properties": {}}, lambda: "ok")
        registry = ToolRegistry([tool, tool])
        self.assertEqual(len(registry.list()), 1)
        self.assertEqual(registry.execute("dup", "{}"), "ok")


if __name__ == "__main__":
    unittest.main(verbosity=2)
