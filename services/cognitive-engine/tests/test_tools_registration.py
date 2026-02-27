"""Tests for tool registration — all built-in tools discoverable with correct shapes.

Run:
    cd services/cognitive-engine
    uv run pytest tests/test_tools_registration.py -v
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.graph.tools import (
    get_all_tools,
    search_codebase,
    read_file,
    list_directory,
    glob_find,
    propose_command,
    propose_file_creation,
    propose_file_edit,
    analyze_screen,
    scan_vulnerabilities,
    generate_and_preview_mvp,
    update_sandbox_preview,
    github_read_issue,
    github_create_pr,
)


@pytest.fixture(autouse=True)
def _mock_tavily():
    """Mock TavilySearch so tests don't need TAVILY_API_KEY."""
    mock_tool = MagicMock()
    mock_tool.name = "tavily_search"
    mock_tool.description = "Search the web for current documentation and knowledge."
    with patch("src.graph.tools.get_web_search", return_value=mock_tool):
        # Reset the cached instance so our mock is picked up
        import src.graph.tools as _tools_mod
        _tools_mod._web_search_instance = None
        yield
        _tools_mod._web_search_instance = None


# ---------------------------------------------------------------------------
# 1. All 14 built-in tools registered in get_all_tools()
# ---------------------------------------------------------------------------


class TestToolRegistration:
    def test_builtin_tools_count(self):
        tools = get_all_tools()
        # 13 built-in tools + tavily mock + any dynamic MCP tools from registry
        builtin_names = {
            "search_codebase",
            "read_file",
            "list_directory",
            "glob_find",
            "propose_command",
            "github_read_issue",
            "github_create_pr",
            "propose_file_creation",
            "propose_file_edit",
            "analyze_screen",
            "scan_vulnerabilities",
            "generate_and_preview_mvp",
            "update_sandbox_preview",
            "tavily_search",
        }
        tool_names = {t.name for t in tools}
        missing = builtin_names - tool_names
        assert not missing, f"Missing tools: {missing}"

    def test_each_tool_has_description(self):
        tools = get_all_tools()
        for t in tools:
            assert t.description, f"Tool {t.name} has empty description"
            assert len(t.description) > 10, f"Tool {t.name} description too short"


# ---------------------------------------------------------------------------
# 2. search_codebase → valid JSON-RPC shape
# ---------------------------------------------------------------------------


class TestSearchCodebaseTool:
    def test_returns_jsonrpc_shape(self):
        result = search_codebase.invoke({"pattern": "auth", "project_path": "/project"})
        assert result["jsonrpc"] == "2.0"
        assert result["method"] == "search_project"
        assert result["params"]["pattern"] == "auth"
        assert result["params"]["project_path"] == "/project"


# ---------------------------------------------------------------------------
# 3. propose_command → dict with command_id
# ---------------------------------------------------------------------------


class TestProposeCommandTool:
    def test_returns_command_id(self):
        result = propose_command.invoke({
            "command": "npm test",
            "description": "Run tests",
            "project_path": "/project",
        })
        assert "command_id" in result
        assert len(result["command_id"]) == 8  # hex[:8]
        assert result["command"] == "npm test"
        assert result["description"] == "Run tests"
        assert result["project_path"] == "/project"


# ---------------------------------------------------------------------------
# 4. generate_and_preview_mvp → correct signal dict
# ---------------------------------------------------------------------------


class TestGenerateAndPreviewMVP:
    def test_returns_sandbox_signal(self):
        result = generate_and_preview_mvp.invoke({
            "app_description": "task tracker",
            "html_code": "<html>test</html>",
        })
        assert result["method"] == "local/sandbox_preview"
        assert result["params"]["app_description"] == "task tracker"
        assert result["params"]["html_code"] == "<html>test</html>"


# ---------------------------------------------------------------------------
# 5. Other tool shape validations
# ---------------------------------------------------------------------------


class TestOtherToolShapes:
    def test_propose_file_creation_shape(self):
        result = propose_file_creation.invoke({
            "file_path": "src/new.ts",
            "content": "export const x = 1;",
            "description": "New file",
        })
        assert "proposal_id" in result
        assert result["action"] == "create_file"
        assert result["file_path"] == "src/new.ts"

    def test_propose_file_edit_shape(self):
        result = propose_file_edit.invoke({
            "file_path": "src/old.ts",
            "diff": "- old\n+ new",
            "description": "Edit file",
        })
        assert "proposal_id" in result
        assert result["action"] == "edit_file"

    def test_propose_file_edit_cowork_ready_default(self):
        result = propose_file_edit.invoke({
            "file_path": "src/old.ts",
            "diff": "- old\n+ new",
            "description": "Edit file",
        })
        assert result.get("cowork_ready") is False

    def test_propose_file_edit_cowork_ready_true(self):
        result = propose_file_edit.invoke({
            "file_path": "src/old.ts",
            "diff": "- old\n+ new",
            "description": "Edit file",
            "cowork_ready": True,
        })
        assert result["cowork_ready"] is True

    def test_analyze_screen_shape(self):
        result = analyze_screen.invoke({"user_description": "check this bug"})
        assert result["method"] == "local/get_recent_frames"

    def test_scan_vulnerabilities_shape(self):
        result = scan_vulnerabilities.invoke({"project_path": "/project"})
        assert result["method"] == "local/scan_security"

    def test_update_sandbox_preview_shape(self):
        result = update_sandbox_preview.invoke({"html_code": "<html>updated</html>"})
        assert result["method"] == "local/sandbox_preview"


# ---------------------------------------------------------------------------
# 6. New search primitive tool shapes
# ---------------------------------------------------------------------------


class TestNewSearchPrimitives:
    def test_read_file_shape(self):
        result = read_file.invoke({"file_path": "/project/src/main.ts", "project_path": "/project"})
        assert result["jsonrpc"] == "2.0"
        assert result["method"] == "local/read_file"
        assert result["params"]["file_path"] == "/project/src/main.ts"
        assert result["params"]["project_root"] == "/project"

    def test_read_file_with_line_range(self):
        result = read_file.invoke({
            "file_path": "/project/src/main.ts",
            "project_path": "/project",
            "start_line": 10,
            "end_line": 25,
        })
        assert result["params"]["start_line"] == 10
        assert result["params"]["end_line"] == 25

    def test_list_directory_shape(self):
        result = list_directory.invoke({"path": "/project/src", "project_path": "/project"})
        assert result["jsonrpc"] == "2.0"
        assert result["method"] == "local/list_directory"
        assert result["params"]["dir_path"] == "/project/src"
        assert result["params"]["project_root"] == "/project"
        assert result["params"]["max_depth"] == 3

    def test_glob_find_shape(self):
        result = glob_find.invoke({"pattern": "*.test.ts", "project_path": "/project"})
        assert result["jsonrpc"] == "2.0"
        assert result["method"] == "local/glob_find"
        assert result["params"]["pattern"] == "*.test.ts"
        assert result["params"]["project_path"] == "/project"
        assert result["params"]["file_type"] == "file"
        assert result["params"]["max_results"] == 50
