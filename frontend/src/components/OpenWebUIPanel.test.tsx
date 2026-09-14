import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { OpenWebUIPanel, secretStatus } from "./OpenWebUIPanel";
import { EffectiveSetting } from "../api/client";

describe("secretStatus", () => {
  it("shows configured vs not configured without a raw key", () => {
    expect(
      secretStatus({
        key: "ai.openai_compatible.api_key",
        value: { configured: true, hint: "••••demo" },
        source: "global_admin",
        overridden: true,
        restart_required: false,
        secret: true,
        editability: "confirm",
        risk: "high",
      }),
    ).toBe("Configured (••••demo)");
    expect(
      secretStatus({
        key: "ai.openai_compatible.api_key",
        value: { configured: false, hint: null },
        source: "default",
        overridden: false,
        restart_required: false,
        secret: true,
        editability: "confirm",
        risk: "high",
      }),
    ).toBe("Not configured");
  });
});

describe("OpenWebUIPanel", () => {
  it("exposes key, URL, test, discover, and six role pickers", () => {
    const values: EffectiveSetting[] = [
      setting("ai.provider", "mock", false),
      setting("ai.openai_compatible.base_url", "http://host.docker.internal:8080/v1", false),
      {
        ...setting("ai.openai_compatible.api_key", { configured: false }, true),
        secret: true,
      },
      setting("ai.openai_compatible.model", "llama3.1", false),
      setting("ai.role.extraction", "", false),
    ];
    render(
      <OpenWebUIPanel
        values={values}
        pending={{}}
        setPending={vi.fn()}
        models={["llama3.1", "nomic-embed"]}
        setModels={vi.fn()}
        aiResult=""
        setAiResult={vi.fn()}
        onError={vi.fn()}
      />,
    );
    expect(screen.getByLabelText("API key")).toBeInTheDocument();
    expect(screen.getByLabelText("Base URL")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Test Connection" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Discover models" })).toBeInTheDocument();
    expect(screen.getByLabelText("Coding / extraction")).toBeInTheDocument();
    expect(screen.getByLabelText("Orchestrator")).toBeInTheDocument();
    expect(screen.getByLabelText("Embeddings")).toBeInTheDocument();
    expect(screen.getByLabelText("Linux Docker help")).toBeInTheDocument();
  });
});

function setting(key: string, value: unknown, secret: boolean): EffectiveSetting {
  return {
    key,
    value,
    source: "default",
    overridden: false,
    restart_required: false,
    secret,
    editability: "editable",
    risk: "medium",
  };
}
