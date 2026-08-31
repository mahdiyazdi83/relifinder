import { z } from "zod";

const apiErrorSchema = z.object({
  error: z.object({
    code: z.string(),
    message: z.string(),
  }),
});

export class ApiRequestError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code: string,
  ) {
    super(message);
    this.name = "ApiRequestError";
  }
}

export async function toApiRequestError(response: Response): Promise<ApiRequestError> {
  try {
    const result = apiErrorSchema.safeParse(await response.json());
    if (result.success) {
      return new ApiRequestError(
        result.data.error.message,
        response.status,
        result.data.error.code,
      );
    }
  } catch {
    // Fall through to the safe generic message.
  }
  return new ApiRequestError(
    "The local ReliFinder API request failed.",
    response.status,
    "api_error",
  );
}

export function toDisplayMessage(error: unknown): string {
  return error instanceof ApiRequestError
    ? error.message
    : "The local ReliFinder service is unavailable.";
}
