from fastapi.testclient import TestClient


def _reviewer_headers(client: TestClient) -> dict[str, str]:
    token = client.post(
        "/api/auth/login", json={"email": "reviewer@rockhawk.local", "password": "ReviewerDemo1!"}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_admin_registry_forbidden_for_reviewer(client: TestClient) -> None:
    denied = client.get("/api/admin/registry", headers=_reviewer_headers(client))
    assert denied.status_code == 403


def test_vertical_slice_apply_audit_rollback(client: TestClient, auth_headers: dict) -> None:
    registry = client.get("/api/admin/registry", headers=auth_headers)
    assert registry.status_code == 200
    keys = {item["key"] for item in registry.json()["settings"]}
    assert "app.support_email" in keys
    assert "review.preserve_verified_cells" in keys

    before = client.get("/api/admin/effective", headers=auth_headers)
    assert before.status_code == 200
    revision_id = before.json()["active_revision_id"]
    support = next(item for item in before.json()["values"] if item["key"] == "app.support_email")
    assert support["source"] in {"default", "global_admin"}
    assert support["value"] != "ops@rockhawk.local" or support["source"] == "default"

    draft = client.post(
        "/api/admin/drafts",
        headers=auth_headers,
        json={"changes": {"app.support_email": "ops@rockhawk.local"}, "expected_revision_id": revision_id},
    )
    assert draft.status_code == 201, draft.text
    draft_id = draft.json()["id"]

    validated = client.post(f"/api/admin/drafts/{draft_id}/validate", headers=auth_headers)
    assert validated.status_code == 200
    assert validated.json()["validation"]["ok"] is True

    preview = client.post(f"/api/admin/drafts/{draft_id}/preview", headers=auth_headers)
    assert preview.status_code == 200
    diffs = preview.json()["preview"]["diffs"]
    assert any(item["key"] == "app.support_email" and item["after"] == "ops@rockhawk.local" for item in diffs)

    refused = client.post(
        f"/api/admin/drafts/{draft_id}/apply",
        headers=auth_headers,
        json={"reason": "short", "confirm": False, "expected_revision_id": revision_id},
    )
    assert refused.status_code == 400

    applied = client.post(
        f"/api/admin/drafts/{draft_id}/apply",
        headers=auth_headers,
        json={"reason": "Set support mailbox for operators", "confirm": True, "expected_revision_id": revision_id},
    )
    assert applied.status_code == 200, applied.text
    new_number = applied.json()["number"]
    assert new_number >= 2

    after = client.get("/api/admin/effective", headers=auth_headers).json()
    support = next(item for item in after["values"] if item["key"] == "app.support_email")
    assert support["value"] == "ops@rockhawk.local"
    assert support["source"] == "global_admin"

    audit = client.get("/api/audit", headers=auth_headers).json()
    assert any(event["action"] == "config.revision.applied" for event in audit)
    applied_event = next(event for event in audit if event["action"] == "config.revision.applied")
    assert "ops@rockhawk.local" in str(applied_event["payload"])

    rollback = client.post(
        f"/api/admin/revisions/{revision_id}/rollback",
        headers=auth_headers,
        json={"reason": "Restore previous support mailbox"},
    )
    assert rollback.status_code == 200, rollback.text
    restored = client.get("/api/admin/effective", headers=auth_headers).json()
    support = next(item for item in restored["values"] if item["key"] == "app.support_email")
    assert support["value"] != "ops@rockhawk.local"


def test_verified_cell_floor_cannot_be_weakened(client: TestClient, auth_headers: dict) -> None:
    effective = client.get("/api/admin/effective", headers=auth_headers).json()
    floor = next(item for item in effective["values"] if item["key"] == "review.preserve_verified_cells")
    assert floor["value"] is True
    draft = client.post(
        "/api/admin/drafts",
        headers=auth_headers,
        json={"changes": {"review.preserve_verified_cells": False}, "expected_revision_id": effective["active_revision_id"]},
    )
    assert draft.status_code == 201
    validated = client.post(f"/api/admin/drafts/{draft.json()['id']}/validate", headers=auth_headers)
    assert validated.json()["validation"]["ok"] is False
    assert any("floor" in err.lower() or "readonly" in err.lower() for err in validated.json()["validation"]["errors"])


def test_secrets_never_exported_or_echoed(client: TestClient, auth_headers: dict) -> None:
    effective = client.get("/api/admin/effective", headers=auth_headers).json()
    draft = client.post(
        "/api/admin/drafts",
        headers=auth_headers,
        json={
            "changes": {"ai.openai_compatible.api_key": "sk-super-secret-demo-key"},
            "expected_revision_id": effective["active_revision_id"],
        },
    )
    assert draft.status_code == 201
    body = draft.json()
    assert "sk-super-secret-demo-key" not in str(body)
    assert body["proposed"]["ai.openai_compatible.api_key"].get("redacted") is True

    draft_id = body["id"]
    client.post(f"/api/admin/drafts/{draft_id}/validate", headers=auth_headers)
    client.post(f"/api/admin/drafts/{draft_id}/preview", headers=auth_headers)
    applied = client.post(
        f"/api/admin/drafts/{draft_id}/apply",
        headers=auth_headers,
        json={"reason": "Store provider key as a reference", "confirm": True, "expected_revision_id": effective["active_revision_id"]},
    )
    assert applied.status_code == 200, applied.text

    exported = client.get("/api/admin/export", headers=auth_headers)
    assert exported.status_code == 200
    assert "sk-super-secret-demo-key" not in exported.text
    secrets = client.get("/api/admin/secrets", headers=auth_headers).json()
    assert secrets
    assert all("ciphertext" not in row and "sk-super" not in str(row) for row in secrets)
    audit = client.get("/api/audit", headers=auth_headers).json()
    assert "sk-super-secret-demo-key" not in str(audit)


def test_ai_test_connection_and_prompt_lineage(client: TestClient, auth_headers: dict) -> None:
    ping = client.post("/api/admin/ai/test-connection", headers=auth_headers)
    assert ping.status_code == 200
    assert ping.json()["ok"] is True
    assert "documents" in ping.json()["detail"].lower()
    models = client.get("/api/admin/ai/models", headers=auth_headers)
    assert models.status_code == 200
    assert "mock-extractor" in models.json()["models"]
    roles = client.get("/api/admin/ai/roles", headers=auth_headers).json()["roles"]
    names = {row["role"] for row in roles}
    assert names == {"orchestrator", "triage", "extraction", "qc", "synthesis", "embeddings"}

    created = client.post(
        "/api/admin/prompts",
        headers=auth_headers,
        json={"prompt_key": "column.extract", "body": "Updated extractor lineage body for tests.", "note": "v-next"},
    )
    assert created.status_code == 201, created.text
    listed = client.get("/api/admin/prompts", headers=auth_headers).json()
    versions = [row for row in listed if row["prompt_key"] == "column.extract"]
    assert len(versions) >= 2
    latest = max(versions, key=lambda row: int(row["version"]))
    assert latest["parent_version"] is not None


def test_import_dry_run_and_env_pin(client: TestClient, auth_headers: dict) -> None:
    effective = client.get("/api/admin/effective", headers=auth_headers).json()
    provider = next(item for item in effective["values"] if item["key"] == "ai.provider")
    assert provider["source"] == "bootstrap"

    draft = client.post(
        "/api/admin/drafts",
        headers=auth_headers,
        json={"changes": {"ai.provider": "openai_compatible"}, "expected_revision_id": effective["active_revision_id"]},
    )
    validated = client.post(f"/api/admin/drafts/{draft.json()['id']}/validate", headers=auth_headers)
    assert validated.json()["validation"]["ok"] is False

    exported = client.get("/api/admin/export", headers=auth_headers).json()
    dry = client.post("/api/admin/import", headers=auth_headers, json={"bundle": exported, "dry_run": True})
    assert dry.status_code == 200
    assert dry.json()["dry_run"] is True
    live = client.post("/api/admin/import", headers=auth_headers, json={"bundle": exported, "dry_run": False})
    assert live.status_code == 400
