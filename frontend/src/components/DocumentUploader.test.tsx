import { act, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AUTO_CLEAR_MS, DocumentUploader, displayName, isSupportedUpload, queueSummary } from "./DocumentUploader";

describe("DocumentUploader helpers", () => {
  it("accepts production natives and rejects system junk", () => {
    for (const name of [
      "memo.pdf",
      "note.TXT",
      "grid.csv",
      "book.xlsx",
      "legacy.xls",
      "page.htm",
      "page.html",
      "matter.xml",
      "deck.pptx",
      "old.ppt",
      "photo.png",
      "scan.JPG",
      "card.vcf",
      "memo.rtf",
      "thread.eml",
      "outlook.msg",
    ]) {
      expect(isSupportedUpload(new File(["a"], name)), name).toBe(true);
    }
    expect(isSupportedUpload(new File(["a"], ".DS_Store"))).toBe(false);
    expect(isSupportedUpload(new File(["a"], "photo.gif"))).toBe(false);
  });

  it("prefers webkitRelativePath for folder picks", () => {
    const file = new File(["x"], "nda.txt");
    Object.defineProperty(file, "webkitRelativePath", { value: "closing/nda.txt" });
    expect(displayName(file)).toBe("closing/nda.txt");
  });

  it("summarizes a mixed queue for the live region", () => {
    const summary = queueSummary([
      { id: "1", file: new File([], "a.txt"), name: "a.txt", status: "done", detail: "" },
      { id: "2", file: new File([], "b.txt"), name: "b.txt", status: "uploading", detail: "" },
      { id: "3", file: new File([], "c.gif"), name: "c.gif", status: "error", detail: "bad" },
    ]);
    expect(summary).toContain("1 of 3 complete");
    expect(summary).toContain("1 in progress");
    expect(summary).toContain("1 failed");
  });
});

describe("DocumentUploader", () => {
  it("exposes Upload files, Upload folder, and a drop target", () => {
    render(<DocumentUploader matterId="m1" onUploaded={() => undefined} />);
    expect(screen.getByRole("button", { name: "Upload files" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Upload folder" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Drop supported files or a folder/i })).toBeInTheDocument();
    expect(screen.getByText("No upload in progress.")).toBeInTheDocument();
  });

  it("clears successful queue rows and keeps failures until dismissed", async () => {
    const { userEvent } = await import("@testing-library/user-event");
    const user = userEvent.setup();
    const items = [
      { id: "1", file: new File(["a"], "ok.txt"), name: "ok.txt", status: "done" as const, detail: "1 page" },
      { id: "2", file: new File(["b"], "bad.gif"), name: "bad.gif", status: "error" as const, detail: "unsupported" },
    ];
    render(<DocumentUploader matterId="m1" onUploaded={() => undefined} initialItems={items} />);
    expect(screen.getByText("ok.txt")).toBeInTheDocument();
    expect(screen.getByText("bad.gif")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Clear completed" }));
    expect(screen.queryByText("ok.txt")).not.toBeInTheDocument();
    expect(screen.getByText("bad.gif")).toBeInTheDocument();
    await user.click(screen.getAllByRole("button", { name: "Dismiss" })[0]);
    expect(screen.getByText("No upload in progress.")).toBeInTheDocument();
  });

  it("auto-clears successful rows after a short delay and keeps failures", () => {
    vi.useFakeTimers();
    const items = [
      { id: "1", file: new File(["a"], "ok.txt"), name: "ok.txt", status: "done" as const, detail: "1 page" },
      { id: "2", file: new File(["b"], "bad.gif"), name: "bad.gif", status: "error" as const, detail: "unsupported" },
    ];
    render(<DocumentUploader matterId="m1" onUploaded={() => undefined} initialItems={items} />);
    expect(screen.getByText("ok.txt")).toBeInTheDocument();
    act(() => {
      vi.advanceTimersByTime(AUTO_CLEAR_MS);
    });
    expect(screen.queryByText("ok.txt")).not.toBeInTheDocument();
    expect(screen.getByText("bad.gif")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Dismiss" })).toBeInTheDocument();
    vi.useRealTimers();
  });
});
