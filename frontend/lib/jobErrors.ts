export type JobErrorCode =
  | "upload_failed"
  | "validation_failed"
  | "modal_oom"
  | "timeout"
  | "partial_failure"
  | "cache_corrupt"
  | "result_storage_failed"
  | "model_access_required"
  | "tribe_access_denied"
  | "internal_error"
  | "cancelled"
  | "invalid_media"
  | "atlas_unavailable";

export type JobErrorCopy = {
  message: string;
  retryLabel: string | null;
};

export function formatJobErrorMessage(code: string | null, fallbackMessage: string | null): string {
  switch (code) {
    case "model_access_required":
      return "Model access required. Your Modal or Hugging Face token cannot access the configured model. Approve access for the gated model, update the Modal secret if needed, then retry.";
    case "tribe_access_denied":
      return "TRIBE access denied. The configured Hugging Face token cannot access TRIBE v2 or one of its dependencies.";
    case "timeout":
      return "Inference timed out. The job took longer than the configured limit; retry after shortening the stimulus or increasing the timeout.";
    case "modal_oom":
      return "Inference ran out of GPU memory. Shorten the stimulus or use a smaller workload before retrying.";
    case "partial_failure":
      return "Inference failed after streaming partial results. You can inspect the received frames, but the saved result may be incomplete.";
    case "result_storage_failed":
      return "The streamed result exists in this browser session, but saving the NPZ artifact failed. Download is disabled until the job is rerun successfully.";
    case "upload_failed":
      return "Upload failed. Check your connection and S3 configuration, then retry the file upload.";
    case "invalid_media":
      return "A stimulus file is corrupt, unsupported, or does not match its configured duration.";
    case "validation_failed":
      return fallbackMessage ?? "Run validation failed. Fix the highlighted block fields before running again.";
    case "cancelled":
      return "Job was cancelled by the user.";
    case "cache_corrupt":
      return "Cached result was invalid. The backend will ignore that cache entry and recompute when possible.";
    case "internal_error":
      return fallbackMessage ?? "An internal error occurred. Keep the job ID for debugging and retry if the issue looks transient.";
    default:
      return fallbackMessage ?? "Something went wrong while running inference.";
  }
}

export function getJobErrorCopy(code: string | null, fallbackMessage: string | null, retryable: boolean): JobErrorCopy {
  return {
    message: formatJobErrorMessage(code, fallbackMessage),
    retryLabel: retryable ? "Retry" : null
  };
}

export function formatUploadError(caught: unknown): string {
  if (caught instanceof Error) {
    return `Upload failed. ${caught.message} Retry the upload after checking your connection and S3 settings.`;
  }
  return "Upload failed. Retry the upload after checking your connection and S3 settings.";
}
