from __future__ import annotations

import ast
import argparse
import json
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[1]
BACKUP = WORKSPACE / "backups" / "phase2" / "20260819-130349"
PREPARED = WORKSPACE / "workflows" / "phase2-prepared"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def nodes_by_id(workflow: dict) -> dict[str, dict]:
    return {node["id"]: node for node in workflow["nodes"]}


def assert_original_nodes_unchanged(base: dict, prepared: dict) -> None:
    prepared_nodes = nodes_by_id(prepared)
    for node_id, node in nodes_by_id(base).items():
        assert prepared_nodes[node_id] == node, f"Original node changed: {node['name']}"


def function(tree: ast.Module, name: str) -> ast.FunctionDef:
    return next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    )


def is_emit_call(statement: ast.stmt) -> bool:
    return (
        isinstance(statement, ast.Expr)
        and isinstance(statement.value, ast.Call)
        and isinstance(statement.value.func, ast.Name)
        and statement.value.func.id == "emit_notification_async"
    )


def verify_hermes(candidate_path: Path) -> None:
    base_tree = ast.parse((BACKUP / "hermes.py").read_text(encoding="utf-8-sig"))
    candidate_tree = ast.parse(candidate_path.read_text(encoding="utf-8-sig"))

    for name in ("trade", "handle_exit_signal"):
        assert ast.dump(function(base_tree, name)) == ast.dump(function(candidate_tree, name)), (
            f"Protected function changed: {name}"
        )

    base_entry = function(base_tree, "handle_entry_signal")
    candidate_entry = function(candidate_tree, "handle_entry_signal")
    candidate_core = [statement for statement in candidate_entry.body if not is_emit_call(statement)]
    assert len(candidate_core) + 1 == len(candidate_entry.body), "Expected one notification hook"
    assert ast.dump(ast.Module(body=base_entry.body, type_ignores=[])) == ast.dump(
        ast.Module(body=candidate_core, type_ignores=[])
    ), "Protected entry logic changed"


def verify_reporting_read_only() -> None:
    for path in (WORKSPACE / "trading" / "reporting").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                assert node.func.attr not in {"order_send", "order_check"}, (
                    f"Write-capable MT5 call found in {path.name}: {node.func.attr}"
                )


def verify_workflows() -> None:
    files = {
        "main": ("my-workflow.json", "pQ5W4rwznGxY6zKO.json"),
        "trading": ("trading.json", "wBVjyD9ks1z6cZTl.json"),
        "notification": (
            "hermes---telegram-notifications.json",
            "fe98643a-74b5-4cbb-b91c-a2adf4a7a06f.json",
        ),
    }
    loaded = {}
    for name, (base_name, prepared_name) in files.items():
        base = load(BACKUP / base_name)
        prepared = load(PREPARED / prepared_name)
        assert_original_nodes_unchanged(base, prepared)
        loaded[name] = (base, prepared)

    main_base, main = loaded["main"]
    for key, value in main_base["connections"].items():
        if key != "Merge - Preserve Telegram Update":
            assert main["connections"][key] == value, f"Main connection changed: {key}"
    assert len(main["nodes"]) == len(main_base["nodes"]) + 4

    trading_base, trading = loaded["trading"]
    assert len(trading["nodes"]) == len(trading_base["nodes"]) + 1
    protected_edge = {"node": "HTTP Request", "type": "main", "index": 0}
    trading_edges = trading["connections"]["Webhook"]["main"][0]
    assert trading_edges.count(protected_edge) == 1, "Protected Webhook-to-trade edge missing"
    assert nodes_by_id(trading)["4fb6bacd-9263-4a87-a6be-ced2e4a80c62"] == (
        nodes_by_id(trading_base)["4fb6bacd-9263-4a87-a6be-ced2e4a80c62"]
    )

    notification_base, notification = loaded["notification"]
    assert len(notification["nodes"]) == len(notification_base["nodes"]) + 2
    assert notification["active"] is True

    config = load(WORKSPACE / "trading" / "reporting" / "config.local.json")
    assert config["notification_url"].startswith("http://127.0.0.1:5678/webhook/")
    assert len(config["notification_key"]) >= 64
    webhook = next(
        node for node in notification["nodes"] if node["name"] == "MT5 Events Webhook"
    )
    assert config["notification_url"].endswith(webhook["parameters"]["path"])


def verify_exported_workflows(export_path: Path) -> None:
    exported = load(export_path)
    assert isinstance(exported, list), "n8n export must contain a workflow list"
    exported_by_id = {workflow["id"]: workflow for workflow in exported}
    for prepared_path in PREPARED.glob("*.json"):
        prepared = load(prepared_path)
        actual = exported_by_id[prepared["id"]]
        for key in ("name", "nodes", "connections", "settings"):
            assert actual[key] == prepared[key], f"Imported workflow mismatch: {prepared['name']}:{key}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--deployed-hermes", type=Path)
    parser.add_argument("--workflow-export", type=Path)
    args = parser.parse_args()
    verify_workflows()
    verify_reporting_read_only()
    verify_hermes(WORKSPACE / "trading" / "port5000" / "hermes.py")
    if args.deployed_hermes:
        verify_hermes(args.deployed_hermes)
    if args.workflow_export:
        verify_exported_workflows(args.workflow_export)
    print("Phase 2 safety verification: OK")


if __name__ == "__main__":
    main()
