import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ColumnBuilder } from "./ColumnBuilder";

describe("ColumnBuilder", () => {
  it("exposes a first-class column form", () => {
    render(
      <ColumnBuilder
        tableId="t1"
        columns={[]}
        onClose={vi.fn()}
        onChanged={vi.fn()}
      />,
    );
    expect(screen.getByRole("heading", { name: "Add column" })).toBeInTheDocument();
    expect(screen.getByLabelText("Label")).toBeInTheDocument();
    expect(screen.getByLabelText("Instruction")).toBeInTheDocument();
    expect(screen.getByLabelText("Output type")).toBeInTheDocument();
    expect(screen.getByLabelText("Citation policy")).toBeInTheDocument();
    expect(screen.getByLabelText("Model role")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Suggest" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Import" })).toBeInTheDocument();
  });
});
