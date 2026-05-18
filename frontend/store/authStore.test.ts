import { describe, expect, it } from "vitest";
import { useAuthStore } from "./authStore";

describe("authStore", () => {
  it("stores Supabase session fields", () => {
    useAuthStore.getState().setSession({ accessToken: "token-123", email: "researcher@example.com" });

    expect(useAuthStore.getState().accessToken).toBe("token-123");
    expect(useAuthStore.getState().email).toBe("researcher@example.com");
  });

  it("clears email when setting a manual token", () => {
    useAuthStore.getState().setSession({ accessToken: "token-123", email: "researcher@example.com" });
    useAuthStore.getState().setAccessToken("manual-token");

    expect(useAuthStore.getState().accessToken).toBe("manual-token");
    expect(useAuthStore.getState().email).toBeNull();
  });
});

