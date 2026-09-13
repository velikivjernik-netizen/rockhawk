from io import BytesIO

from fastapi.testclient import TestClient


def _matter_and_table(client: TestClient, headers: dict) -> tuple[str, str]:
    matters = client.get("/api/matters", headers=headers).json()
    matter_id = matters[0]["id"]
    tables = client.get(f"/api/matters/{matter_id}/tables", headers=headers).json()
    return matter_id, tables[0]["id"]


def test_create_blank_table_and_add_full_column(client: TestClient, auth_headers: dict) -> None:
    matter_id, _ = _matter_and_table(client, auth_headers)
    blank = client.post(
        f"/api/matters/{matter_id}/tables",
        headers=auth_headers,
        json={"name": "Custom grid", "columns": [], "include_all_documents": True},
    )
    assert blank.status_code == 201, blank.text
    assert blank.json()["columns"] == []
    table_id = blank.json()["id"]
    created = client.post(
        f"/api/tables/{table_id}/columns",
        headers=auth_headers,
        json={
            "name": "Venue",
            "value_type": "text",
            "instruction": "Extract exclusive venue. If absent, Not found.",
            "citation_policy": "always",
            "model_role": "extraction",
            "prompt_key": "column.extract",
            "overwrite_policy": "skip_verified",
            "required": True,
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["citation_policy"] == "always"
    assert created.json()["model_role"] == "extraction"
    patched = client.patch(
        f"/api/columns/{created.json()['id']}",
        headers=auth_headers,
        json={"instruction": "Extract exclusive venue or forum. If absent, Not found."},
    )
    assert patched.status_code == 200
    assert "forum" in patched.json()["instruction"]


def test_suggest_and_import_are_proposals_until_approved(client: TestClient, auth_headers: dict) -> None:
    _matter_id, table_id = _matter_and_table(client, auth_headers)
    before = client.get(f"/api/tables/{table_id}", headers=auth_headers).json()
    count = len(before["columns"])
    suggested = client.post(
        f"/api/tables/{table_id}/columns/suggest",
        headers=auth_headers,
        json={"description": "Extract governing law, venue, and whether there is a jury waiver"},
    )
    assert suggested.status_code == 200, suggested.text
    assert suggested.json()["persisted"] is False
    names = {item["name"] for item in suggested.json()["proposed"]}
    assert "Governing law" in names
    assert "Jury waiver" in names
    after_suggest = client.get(f"/api/tables/{table_id}", headers=auth_headers).json()
    assert len(after_suggest["columns"]) == count

    imported = client.post(
        f"/api/tables/{table_id}/columns/import",
        headers=auth_headers,
        files={"file": ("checklist.csv", BytesIO(b"Assignment restriction,Data protection\n"), "text/csv")},
    )
    assert imported.status_code == 200
    assert imported.json()["persisted"] is False
    after_import = client.get(f"/api/tables/{table_id}", headers=auth_headers).json()
    assert len(after_import["columns"]) == count

    approved = client.post(
        f"/api/tables/{table_id}/columns/bulk",
        headers=auth_headers,
        json={"columns": imported.json()["proposed"]},
    )
    assert approved.status_code == 201
    final = client.get(f"/api/tables/{table_id}", headers=auth_headers).json()
    assert len(final["columns"]) == count + len(imported.json()["proposed"])


def test_table_hot_criteria_and_enum_validation(client: TestClient, auth_headers: dict) -> None:
    _matter_id, table_id = _matter_and_table(client, auth_headers)
    patched = client.patch(
        f"/api/tables/{table_id}",
        headers=auth_headers,
        json={"hot_include_flagged": True, "hot_include_manual": True, "hot_min_flagged": 2},
    )
    assert patched.status_code == 200
    assert patched.json()["hot_min_flagged"] == 2
    bad = client.post(
        f"/api/tables/{table_id}/columns",
        headers=auth_headers,
        json={"name": "Broken enum", "value_type": "enum", "instruction": "x"},
    )
    assert bad.status_code == 400
