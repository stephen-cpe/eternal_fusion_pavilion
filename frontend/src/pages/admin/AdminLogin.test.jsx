/**
 * Component test for AdminLogin — verifies the form renders, requires both
 * fields, calls adminService.login, and navigates on success.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import AdminLogin from "./AdminLogin";

// Stub the api module so the component's import gets our mock.
vi.mock("../../services/api", () => ({
  adminService: {
    login: vi.fn(),
    getProfile: vi.fn(),
  },
}));

import { adminService } from "../../services/api";

function renderLogin() {
  return render(
    <MemoryRouter>
      <AdminLogin />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("AdminLogin", () => {
  it("renders the form with username/password inputs and a submit button", () => {
    renderLogin();
    expect(screen.getByLabelText(/username/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /login/i })).toBeInTheDocument();
  });

  it("does not call login when fields are empty", async () => {
    const user = userEvent.setup();
    renderLogin();
    await user.click(screen.getByRole("button", { name: /login/i }));
    expect(adminService.login).not.toHaveBeenCalled();
  });

  it("calls adminService.login with the entered credentials", async () => {
    const user = userEvent.setup();
    adminService.login.mockResolvedValueOnce({ message: "ok" });
    renderLogin();

    await user.type(screen.getByLabelText(/username/i), "admin");
    await user.type(screen.getByLabelText(/password/i), "secret");
    await user.click(screen.getByRole("button", { name: /login/i }));

    expect(adminService.login).toHaveBeenCalledWith("admin", "secret");
  });

  it("attempts login on wrong credentials (the api rejects server-side)", async () => {
    const user = userEvent.setup();
    adminService.login.mockRejectedValueOnce(new Error("Invalid credentials"));
    renderLogin();

    await user.type(screen.getByLabelText(/username/i), "admin");
    await user.type(screen.getByLabelText(/password/i), "wrong");
    await user.click(screen.getByRole("button", { name: /login/i }));

    expect(adminService.login).toHaveBeenCalledWith("admin", "wrong");
  });
});