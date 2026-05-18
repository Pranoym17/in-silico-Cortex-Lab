import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(() => {
  vi.resetModules();
  vi.unstubAllEnvs();
});

describe("isSupabaseConfigured", () => {
  it("is false when env vars are missing", async () => {
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_URL", "");
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_ANON_KEY", "");
    const { isSupabaseConfigured } = await import("./supabase");

    expect(isSupabaseConfigured()).toBe(false);
  });

  it("is true when both public env vars are present", async () => {
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_URL", "https://example.supabase.co");
    vi.stubEnv("NEXT_PUBLIC_SUPABASE_ANON_KEY", "anon-key");
    const { isSupabaseConfigured } = await import("./supabase");

    expect(isSupabaseConfigured()).toBe(true);
  });
});

