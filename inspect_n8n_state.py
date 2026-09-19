from __future__ import annotations

import sqlite3
from pathlib import Path


DATABASE = Path(__file__).resolve().parents[1] / "database.sqlite"
TARGET_IDS = (
    "pQ5W4rwznGxY6zKO",
    "wBVjyD9ks1z6cZTl",
    "fe98643a-74b5-4cbb-b91c-a2adf4a7a06f",
)


def main() -> None:
    connection = sqlite3.connect(f"file:{DATABASE}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        print(f"integrity={integrity}")
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        if "settings" in tables:
            setting_keys = [
                row[0]
                for row in connection.execute('SELECT "key" FROM "settings" ORDER BY "key"')
            ]
            print("setting_keys=" + ",".join(setting_keys))
        workflow_table = "workflow_entity"
        columns = {
            row[1] for row in connection.execute(f'PRAGMA table_info("{workflow_table}")')
        }
        selected = ["id", "name", "active"]
        for optional in ("versionId", "activeVersionId"):
            if optional in columns:
                selected.append(optional)
        placeholders = ",".join("?" for _ in TARGET_IDS)
        rows = connection.execute(
            f'SELECT {",".join(selected)} FROM "{workflow_table}" '
            f"WHERE id IN ({placeholders}) ORDER BY name",
            TARGET_IDS,
        ).fetchall()
        for row in rows:
            details = " ".join(f"{key}={row[key]}" for key in selected)
            print(f"workflow {details}")

        if "webhook_entity" in tables:
            webhook_columns = {
                row[1]
                for row in connection.execute('PRAGMA table_info("webhook_entity")')
            }
            workflow_column = "workflowId" if "workflowId" in webhook_columns else "workflow_id"
            webhooks = connection.execute(
                f'SELECT "{workflow_column}", COUNT(*) AS count '
                f'FROM "webhook_entity" WHERE "{workflow_column}" IN ({placeholders}) '
                f'GROUP BY "{workflow_column}" ORDER BY "{workflow_column}"',
                TARGET_IDS,
            ).fetchall()
            counts = {row[0]: row[1] for row in webhooks}
            for workflow_id in TARGET_IDS:
                print(f"webhooks workflow_id={workflow_id} count={counts.get(workflow_id, 0)}")

        if "execution_entity" in tables:
            execution_columns = {
                row[1]
                for row in connection.execute('PRAGMA table_info("execution_entity")')
            }
            required = {"id", "workflowId", "status"}
            if required.issubset(execution_columns):
                executions = connection.execute(
                    f'SELECT id, "workflowId", status FROM "execution_entity" '
                    f'WHERE "workflowId" IN ({placeholders}) ORDER BY id DESC LIMIT 12',
                    TARGET_IDS,
                ).fetchall()
                for row in executions:
                    print(
                        f"execution id={row['id']} workflow_id={row['workflowId']} "
                        f"status={row['status']}"
                    )
    finally:
        connection.close()


if __name__ == "__main__":
    main()
