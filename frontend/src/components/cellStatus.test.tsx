import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

function Status({ status }: { status: string }) {
  return <span className={`status ${status}`}>{status}</span>;
}

describe("cell status", () => {
  it("renders not_found distinctly from complete", () => {
    const { rerender } = render(<Status status="not_found" />);
    expect(screen.getByText("not_found")).toHaveClass("not_found");
    rerender(<Status status="complete" />);
    expect(screen.getByText("complete")).toHaveClass("complete");
  });
});
