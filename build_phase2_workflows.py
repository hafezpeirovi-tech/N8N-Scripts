from __future__ import annotations

import copy
import json
from pathlib import Path
import secrets
import uuid


WORKSPACE = Path(__file__).resolve().parents[1]
BACKUP = WORKSPACE / "backups" / "phase2" / "20260819-130349"
OUTPUT = WORKSPACE / "workflows" / "phase2-prepared"
CONFIG_PATH = WORKSPACE / "trading" / "reporting" / "config.local.json"


def load_workflow(filename: str) -> dict:
    return json.loads((BACKUP / filename).read_text(encoding="utf-8-sig"))


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def new_version(workflow: dict, name: str, description: str) -> None:
    version_id = str(uuid.uuid4())
    workflow["versionId"] = version_id
    workflow["activeVersionId"] = version_id if workflow.get("active") else None
    workflow["versionMetadata"] = {"name": name, "description": description}


def load_or_create_config(webhook_path: str) -> dict:
    if CONFIG_PATH.exists():
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))
    else:
        config = {
            "notification_key": secrets.token_hex(32),
            "magic": 1001,
            "timezone": "Asia/Tehran",
            "report_port": 5001,
            "terminal_path": "C:\\Program Files\\MetaTrader 5\\terminal64.exe",
        }
    config["notification_url"] = f"http://127.0.0.1:5678/webhook/{webhook_path}"
    write_json(CONFIG_PATH, config)
    return config


def build_notification(workflow: dict, event_key: str) -> dict:
    workflow = copy.deepcopy(workflow)
    workflow["active"] = True
    workflow["description"] = (
        "Authenticated fail-safe Telegram notifications for Hermes trading events."
    )
    normalize_node = {
        "parameters": {
            "jsCode": (
                "return $input.all().map((item) => ({\n"
                "  json: item.json?.body ?? item.json ?? {},\n"
                "}));"
            )
        },
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [-336, -112],
        "id": "efea4034-301b-47b2-8d31-2089f1531454",
        "name": "Normalize Internal Event",
    }
    validate_code = f"""const expectedKey = {json.dumps(event_key)};

return $input.all().map((item) => {{
  const headers = item.json?.headers ?? {{}};
  const receivedKey = String(
    headers['x-hermes-event-key'] ?? headers['X-Hermes-Event-Key'] ?? ''
  );
  if (!expectedKey || receivedKey !== expectedKey) {{
    throw new Error('Unauthorized Hermes event');
  }}
  const payload = item.json?.body ?? {{}};
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {{
    throw new Error('Hermes event body must be a JSON object');
  }}
  return {{ json: payload }};
}});"""
    validate_node = {
        "parameters": {"jsCode": validate_code},
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [-336, 112],
        "id": "791a4ce9-0fc1-4cb8-a880-d64410cb8c03",
        "name": "Validate Webhook Event",
    }
    workflow["nodes"].extend([normalize_node, validate_node])
    workflow["connections"]["When Executed by Another Workflow"] = {
        "main": [[{"node": "Normalize Internal Event", "type": "main", "index": 0}]]
    }
    workflow["connections"]["MT5 Events Webhook"] = {
        "main": [[{"node": "Validate Webhook Event", "type": "main", "index": 0}]]
    }
    workflow["connections"]["Normalize Internal Event"] = {
        "main": [[{"node": "Format Notification", "type": "main", "index": 0}]]
    }
    workflow["connections"]["Validate Webhook Event"] = {
        "main": [[{"node": "Format Notification", "type": "main", "index": 0}]]
    }
    workflow["meta"] = {**(workflow.get("meta") or {}), "phase": "realtime-notifications"}
    new_version(
        workflow,
        "Phase 2: authenticated real-time notifications",
        "Validates local event calls and sends signal/open/close messages to Telegram.",
    )
    return workflow


def build_main(workflow: dict) -> dict:
    workflow = copy.deepcopy(workflow)
    telegram_template = next(
        node for node in workflow["nodes"] if node["name"] == "Send a text message"
    )
    pnl_if = {
        "parameters": {
            "conditions": {
                "options": {
                    "caseSensitive": False,
                    "leftValue": "",
                    "typeValidation": "strict",
                    "version": 3,
                },
                "conditions": [
                    {
                        "id": "3159b560-ff45-41b3-850b-e68891151337",
                        "leftValue": (
                            "={{ ($json.message?.text ?? '').trim().toLowerCase()"
                            ".split(/\\s+/)[0].split('@')[0] }}"
                        ),
                        "rightValue": "/pnl",
                        "operator": {"type": "string", "operation": "equals"},
                    }
                ],
                "combinator": "and",
            },
            "options": {},
        },
        "type": "n8n-nodes-base.if",
        "typeVersion": 2.3,
        "position": [-80, -256],
        "id": "6a9dd34a-7dc8-47af-825a-fe1aa7dfca43",
        "name": "If - PnL Command",
    }
    parse_pnl = {
        "parameters": {
            "jsCode": """const item = $input.first().json;
const text = String(item.message?.text ?? '').trim().toLowerCase();
const argument = text.split(/\\s+/)[1] ?? 'today';
const aliases = {
  today: 'today', 'امروز': 'today',
  week: 'week', 'هفته': 'week', 'هفتگی': 'week',
  month: 'month', 'ماه': 'month', 'ماهانه': 'month',
};
return [{ json: { ...item, pnl_period: aliases[argument] ?? 'today' } }];"""
        },
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [144, -352],
        "id": "db0bea67-4865-4b48-8a14-12925b0233cc",
        "name": "Parse PnL Command",
    }
    get_pnl = {
        "parameters": {
            "method": "POST",
            "url": "http://127.0.0.1:5001/v1/pnl",
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": "={{ { period: $json.pnl_period } }}",
            "options": {"timeout": 10000},
        },
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.4,
        "position": [368, -352],
        "id": "502453c0-993f-46e8-b0c8-576dc8b32fd8",
        "name": "Get PnL Report",
        "onError": "continueRegularOutput",
    }
    send_pnl = {
        "parameters": {
            "resource": "message",
            "operation": "sendMessage",
            "chatId": telegram_template["parameters"]["chatId"],
            "text": (
                "={{ $json.message || "
                "'⚠️ سرویس گزارش‌گیری در دسترس نیست. لطفاً دوباره تلاش کنید.' }}"
            ),
            "additionalFields": {},
        },
        "type": "n8n-nodes-base.telegram",
        "typeVersion": 1.2,
        "position": [592, -352],
        "id": "30d96019-3556-441b-a078-daeb7644a216",
        "name": "Send PnL Report",
        "credentials": copy.deepcopy(telegram_template["credentials"]),
        "onError": "continueRegularOutput",
    }
    workflow["nodes"].extend([pnl_if, parse_pnl, get_pnl, send_pnl])
    workflow["connections"]["Merge - Preserve Telegram Update"] = {
        "main": [[{"node": "If - PnL Command", "type": "main", "index": 0}]]
    }
    workflow["connections"]["If - PnL Command"] = {
        "main": [
            [{"node": "Parse PnL Command", "type": "main", "index": 0}],
            [{"node": "If", "type": "main", "index": 0}],
        ]
    }
    workflow["connections"]["Parse PnL Command"] = {
        "main": [[{"node": "Get PnL Report", "type": "main", "index": 0}]]
    }
    workflow["connections"]["Get PnL Report"] = {
        "main": [[{"node": "Send PnL Report", "type": "main", "index": 0}]]
    }
    new_version(
        workflow,
        "Phase 2: Telegram PnL command",
        "Routes /pnl today|week|month to the isolated read-only reporting service.",
    )
    return workflow


def build_trading(workflow: dict, notification_url: str, event_key: str) -> dict:
    workflow = copy.deepcopy(workflow)
    signal_node = {
        "parameters": {
            "method": "POST",
            "url": notification_url,
            "sendHeaders": True,
            "headerParameters": {
                "parameters": [{"name": "X-Hermes-Event-Key", "value": event_key}]
            },
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": "={{ { event_type: 'signal_received' } }}",
            "options": {"timeout": 1000},
        },
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.4,
        "position": [208, -176],
        "id": "de9d8790-f690-4194-8924-302af3ad294f",
        "name": "Notify Signal Received",
        "onError": "continueRegularOutput",
    }
    workflow["nodes"].append(signal_node)
    original_edge = {"node": "HTTP Request", "type": "main", "index": 0}
    workflow["connections"]["Webhook"] = {
        "main": [[
            {"node": "Notify Signal Received", "type": "main", "index": 0},
            original_edge,
        ]]
    }
    new_version(
        workflow,
        "Phase 2: signal received notification",
        "Adds an isolated fail-open notification branch; the Webhook-to-trade edge is preserved.",
    )
    return workflow


def main() -> None:
    notification_base = load_workflow("hermes---telegram-notifications.json")
    webhook_node = next(
        node for node in notification_base["nodes"] if node["name"] == "MT5 Events Webhook"
    )
    webhook_path = webhook_node["parameters"]["path"]
    config = load_or_create_config(webhook_path)

    workflows = [
        build_main(load_workflow("my-workflow.json")),
        build_trading(
            load_workflow("trading.json"),
            config["notification_url"],
            config["notification_key"],
        ),
        build_notification(notification_base, config["notification_key"]),
    ]
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for workflow in workflows:
        write_json(OUTPUT / f"{workflow['id']}.json", workflow)
    write_json(WORKSPACE / "workflows" / "phase2-import.json", workflows)
    print("Prepared 3 workflows and local reporting configuration.")


if __name__ == "__main__":
    main()
