from io import BytesIO

from fastapi.testclient import TestClient


def _matter_and_table(client: TestClient, headers: dict) -> tuple[str, str]:
    matters = client.get("/api/matters", headers=headers).json()
    assert matters, "demo matter should be seeded"
    matter_id = matters[0]["id"]
    tables = client.get(f"/api/matters/{matter_id}/tables", headers=headers).json()
    assert tables
    return matter_id, tables[0]["id"]


def test_login_and_demo_seed(client: TestClient, auth_headers: dict) -> None:
    me = client.get("/api/auth/me", headers=auth_headers)
    assert me.status_code == 200
    assert me.json()["role"] == "admin"
    matters = client.get("/api/matters", headers=auth_headers).json()
    assert any("Northwind" in m["name"] for m in matters)


def test_ethical_wall_hides_matter(client: TestClient) -> None:
    walled = client.post("/api/auth/login", json={"email": "walled@rockhawk.local", "password": "WalledDemo1!"})
    assert walled.status_code == 200
    headers = {"Authorization": f"Bearer {walled.json()['access_token']}"}
    matters = client.get("/api/matters", headers=headers).json()
    assert matters == []


def test_viewer_cannot_run(client: TestClient) -> None:
    token = client.post("/api/auth/login", json={"email": "viewer@rockhawk.local", "password": "ViewerDemo1!"}).json()[
        "access_token"
    ]
    headers = {"Authorization": f"Bearer {token}"}
    matters = client.get("/api/matters", headers=headers).json()
    assert matters
    tables = client.get(f"/api/matters/{matters[0]['id']}/tables", headers=headers).json()
    run = client.post(f"/api/tables/{tables[0]['id']}/run-sync", json={}, headers=headers)
    assert run.status_code == 403


def test_batch_upload_partial_success_and_duplicates(client: TestClient, auth_headers: dict) -> None:
    matter_id, _table_id = _matter_and_table(client, auth_headers)
    good_a = ("batch_a.txt", BytesIO(b"Party A agrees to venue in Oregon.\n"), "text/plain")
    good_b = ("batch_b.txt", BytesIO(b"This letter has no dollar cap.\n"), "text/plain")
    bad = ("notes.png", BytesIO(b"not-a-document"), "image/png")
    batch = client.post(
        f"/api/matters/{matter_id}/documents/batch",
        headers=auth_headers,
        files=[("files", good_a), ("files", good_b), ("files", bad)],
    )
    assert batch.status_code == 200, batch.text
    body = batch.json()
    assert body["accepted"] == 2
    assert body["failed"] == 1
    statuses = {row["filename"]: row["status"] for row in body["results"]}
    assert statuses["batch_a.txt"] == "created"
    assert statuses["batch_b.txt"] == "created"
    assert statuses["notes.png"] == "error"
    assert any(row["document"] and row["document"]["id"] for row in body["results"] if row["status"] == "created")

    again = client.post(
        f"/api/matters/{matter_id}/documents/batch",
        headers=auth_headers,
        files=[("files", ("batch_a.txt", BytesIO(b"Party A agrees to venue in Oregon.\n"), "text/plain"))],
    )
    assert again.status_code == 200
    assert again.json()["duplicates"] == 1
    assert again.json()["results"][0]["status"] == "duplicate"

    listed = client.get(f"/api/matters/{matter_id}/documents", headers=auth_headers).json()
    names = {doc["filename"] for doc in listed}
    assert "batch_a.txt" in names
    assert "batch_b.txt" in names
    assert "notes.png" not in names

    audit = client.get(f"/api/audit?matter_id={matter_id}", headers=auth_headers).json()
    uploaded = [event for event in audit if event["action"] == "document.uploaded"]
    assert len(uploaded) >= 2


def test_single_upload_duplicate_is_conflict(client: TestClient, auth_headers: dict) -> None:
    matter_id, _table_id = _matter_and_table(client, auth_headers)
    payload = ("once.txt", BytesIO(b"Unique side letter about Idaho venue.\n"), "text/plain")
    first = client.post(f"/api/matters/{matter_id}/documents", headers=auth_headers, files={"file": payload})
    assert first.status_code == 201, first.text
    second = client.post(
        f"/api/matters/{matter_id}/documents",
        headers=auth_headers,
        files={"file": ("once.txt", BytesIO(b"Unique side letter about Idaho venue.\n"), "text/plain")},
    )
    assert second.status_code == 409


def test_viewer_cannot_upload(client: TestClient) -> None:
    token = client.post("/api/auth/login", json={"email": "viewer@rockhawk.local", "password": "ViewerDemo1!"}).json()[
        "access_token"
    ]
    headers = {"Authorization": f"Bearer {token}"}
    matters = client.get("/api/matters", headers=headers).json()
    matter_id = matters[0]["id"]
    single = client.post(
        f"/api/matters/{matter_id}/documents",
        headers=headers,
        files={"file": ("nope.txt", BytesIO(b"secret"), "text/plain")},
    )
    assert single.status_code == 403
    batch = client.post(
        f"/api/matters/{matter_id}/documents/batch",
        headers=headers,
        files=[("files", ("nope.txt", BytesIO(b"secret"), "text/plain"))],
    )
    assert batch.status_code == 403


def test_upload_txt_and_page_citations(client: TestClient, auth_headers: dict) -> None:
    matter_id, _table_id = _matter_and_table(client, auth_headers)
    content = b"Governing law. This side letter is governed by the laws of the State of Oregon.\n"
    upload = client.post(
        f"/api/matters/{matter_id}/documents",
        headers=auth_headers,
        files={"file": ("side_letter.txt", BytesIO(content), "text/plain")},
    )
    assert upload.status_code == 201, upload.text
    doc_id = upload.json()["id"]
    pages = client.get(f"/api/documents/{doc_id}/pages", headers=auth_headers).json()
    assert pages[0]["page_number"] == 1
    assert "Oregon" in pages[0]["text"]


def test_typed_columns_grounded_and_not_found(client: TestClient, auth_headers: dict) -> None:
    _matter_id, table_id = _matter_and_table(client, auth_headers)
    run = client.post(f"/api/tables/{table_id}/run-sync", json={"include_verified": False}, headers=auth_headers)
    assert run.status_code == 200, run.text
    table = client.get(f"/api/tables/{table_id}", headers=auth_headers).json()
    assert len(table["columns"]) >= 5
    types = {col["value_type"] for col in table["columns"]}
    assert {"text", "boolean", "date", "money", "enum"} <= types

    rows = {row["document"]["filename"]: row for row in table["rows"]}
    msa = rows["Contoso_MSA.pdf"]
    sow = rows["SOW_1_Overflow.docx"]
    nda = rows["Mutual_NDA.txt"]

    def cell(row, name: str) -> dict:
        col = next(c for c in table["columns"] if c["name"] == name)
        return next(c for c in row["cells"] if c["column_id"] == col["id"])

    gov = cell(msa, "Governing law")
    assert "Delaware" in gov["value"]
    assert gov["status"] == "complete"
    assert gov["citations"]
    assert gov["citations"][0]["page"] >= 1

    sow_gov = cell(sow, "Governing law")
    assert sow_gov["value"] == "Not found"
    assert sow_gov["status"] == "not_found"

    assert cell(msa, "Termination for convenience")["value"] == "true"
    assert cell(nda, "Termination for convenience")["value"] == "false"

    # Conditional: NDA has no convenience termination, so notice period is skipped / not found
    assert cell(nda, "Termination notice period")["value"] == "Not found"
    assert "30" in cell(msa, "Termination notice period")["value"]

    assert "$500,000" in cell(msa, "Liability cap")["value"]
    assert cell(sow, "Liability cap")["value"] == "Not found"


def test_verified_cells_survive_rerun(client: TestClient, auth_headers: dict) -> None:
    _matter_id, table_id = _matter_and_table(client, auth_headers)
    client.post(f"/api/tables/{table_id}/run-sync", json={}, headers=auth_headers)
    table = client.get(f"/api/tables/{table_id}", headers=auth_headers).json()
    target = table["rows"][0]["cells"][0]
    patched = client.patch(
        f"/api/cells/{target['id']}",
        headers=auth_headers,
        json={"value": "Human verified value", "verified": True},
    )
    assert patched.status_code == 200
    client.post(f"/api/tables/{table_id}/run-sync", json={"include_verified": False}, headers=auth_headers)
    again = client.get(f"/api/cells/{target['id']}", headers=auth_headers).json()
    assert again["value"] == "Human verified value"
    assert again["verified"] is True


def test_flag_comment_assign_hot_ask_export_audit(client: TestClient, auth_headers: dict) -> None:
    matter_id, table_id = _matter_and_table(client, auth_headers)
    client.post(f"/api/tables/{table_id}/run-sync", json={}, headers=auth_headers)
    table = client.get(f"/api/tables/{table_id}", headers=auth_headers).json()
    cell = table["rows"][0]["cells"][0]
    me = client.get("/api/auth/me", headers=auth_headers).json()
    patch = client.patch(
        f"/api/cells/{cell['id']}",
        headers=auth_headers,
        json={"flagged": True, "assigned_to_id": me["id"]},
    )
    assert patch.status_code == 200
    comment = client.post(f"/api/cells/{cell['id']}/comments", headers=auth_headers, json={"body": "Please confirm venue."})
    assert comment.status_code == 201

    hot = client.post(f"/api/rows/{table['rows'][0]['id']}/hot", headers=auth_headers)
    assert hot.status_code == 200
    queue = client.get(f"/api/matters/{matter_id}/hot", headers=auth_headers).json()
    assert queue

    asked = client.post(
        f"/api/tables/{table_id}/ask",
        headers=auth_headers,
        json={"question": "Which documents have a Delaware governing law?"},
    )
    assert asked.status_code == 200
    messages = asked.json()["messages"]
    assert any(m["role"] == "assistant" for m in messages)
    assistant = next(m for m in messages if m["role"] == "assistant")
    assert "Delaware" in assistant["body"] or assistant["citations"]

    csv_resp = client.get(f"/api/tables/{table_id}/export.csv", headers=auth_headers)
    assert csv_resp.status_code == 200
    assert "Governing law" in csv_resp.text
    xlsx = client.get(f"/api/tables/{table_id}/export.xlsx", headers=auth_headers)
    assert xlsx.status_code == 200
    assert xlsx.content[:2] == b"PK"

    audit = client.get(f"/api/audit?matter_id={matter_id}", headers=auth_headers).json()
    assert any(event["action"] == "demo.seeded" for event in audit)
    assert any(event["action"] == "cell.updated" for event in audit)
