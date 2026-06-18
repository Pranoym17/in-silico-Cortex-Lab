import { describe, expect, it } from "vitest";
import { formatJobErrorMessage, formatUploadError, getJobErrorCopy } from "./jobErrors";

describe("jobErrors", () => {
  it("formats Hugging Face and TRIBE access errors without stack traces", () => {
    expect(formatJobErrorMessage("model_access_required", "403 gated stack")).toContain("Model access required");
    expect(formatJobErrorMessage("model_access_required", "403 gated stack")).toContain("token cannot access");
    expect(formatJobErrorMessage("tribe_access_denied", null)).toContain("TRIBE access denied");
  });

  it("formats retryable timeout and partial/result-storage states", () => {
    expect(getJobErrorCopy("timeout", "raw timeout", true)).toEqual({
      message: "Inference timed out. The job took longer than the configured limit; retry after shortening the stimulus or increasing the timeout.",
      retryLabel: "Retry"
    });
    expect(formatJobErrorMessage("partial_failure", null)).toContain("partial results");
    expect(formatJobErrorMessage("result_storage_failed", null)).toContain("Download is disabled");
  });

  it("only exposes retry labels for retryable errors", () => {
    expect(getJobErrorCopy("validation_failed", "bad block", false).retryLabel).toBeNull();
    expect(getJobErrorCopy("internal_error", "try again", true).retryLabel).toBe("Retry");
  });

  it("formats upload failures with retry guidance", () => {
    expect(formatUploadError(new Error("S3 presign failed"))).toBe(
      "Upload failed. S3 presign failed Retry the upload after checking your connection and S3 settings."
    );
  });
});
