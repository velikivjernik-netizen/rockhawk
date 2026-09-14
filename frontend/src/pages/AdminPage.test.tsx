import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AdminPage, formatDiffValue } from "./AdminPage";

const fetchMock = vi.fn();

describe("AdminPage", () => {
  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
    localStorage.setItem("rockhawk.token", "test-token");
    fetchMock.mockImplementation((path: string) => {
      if (String(path).includes("/registry")) {
        return json({
          categories: [{ id: "application", label: "1. Application & branding" }],
          settings: [
            {
              key: "app.support_email",
              category: "application",
              category_label: "1. Application & branding",
              label: "Support contact",
              description: "Low-risk operator contact",
              value_type: "string",
              default: "admin@rockhawk.local",
              risk: "low",
              editability: "editable",
              restart_required: false,
              secret: false,
              enum_options: null,
            },
          ],
        });
      }
      if (String(path).includes("/effective")) {
        return json({
          active_revision_id: "rev-1",
          active_revision_number: 1,
          values: [
            {
              key: "app.support_email",
              value: "admin@rockhawk.local",
              source: "default",
              overridden: false,
              restart_required: false,
              secret: false,
              editability: "editable",
              risk: "low",
            },
          ],
        });
      }
      if (String(path).includes("/revisions")) return json([]);
      if (String(path).includes("/prompts")) return json([]);
      if (String(path).includes("/ai/roles")) return json({ roles: [] });
      return json({});
    });
  });

  it("shows searchable admin settings and the draft action", async () => {
    render(
      <MemoryRouter>
        <AdminPage />
      </MemoryRouter>,
    );
    expect(await screen.findByRole("heading", { name: "Administration Center" })).toBeInTheDocument();
    expect(screen.getByLabelText("Search settings")).toBeInTheDocument();
    expect(screen.getByText("Support contact")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Validate & preview draft" })).toBeInTheDocument();
  });

  it("formats secret diffs as configured / not configured", () => {
    expect(formatDiffValue({ configured: false })).toBe("Not configured");
    expect(formatDiffValue({ configured: true, hint: "••••key1", redacted: true })).toBe("Configured (••••key1)");
    expect(formatDiffValue("llama3.1")).toBe("llama3.1");
  });
});

function json(body: unknown) {
  return Promise.resolve({
    ok: true,
    status: 200,
    headers: { get: () => "application/json" },
    json: async () => body,
  });
}
