import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ActivityIndicator } from "./activity-indicator";

describe("ActivityIndicator", () => {
  it("animates by default and stops under reduced-motion preference", () => {
    render(<ActivityIndicator label="Loading metadata" />);
    const icon = screen.getByText("Loading metadata").previousElementSibling;
    expect(icon).toHaveClass("animate-spin");
    expect(icon).toHaveClass("motion-reduce:animate-none");
  });
});
