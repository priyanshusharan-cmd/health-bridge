export async function api<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api${path}`, {
      ...options,
      signal: options.signal ?? AbortSignal.timeout(
        path.endsWith("/brief") || path.includes("/records") || path.includes("/upload-jobs")
          ? 180000
          : 30000
      ),
      credentials: "same-origin",
      headers: options.body instanceof FormData
        ? options.headers
        : { "Content-Type": "application/json", ...options.headers },
    });
  } catch (error) {
    if (options.signal?.aborted) throw error;
    const name = error instanceof Error ? error.name : "";
    throw new Error(name === "TimeoutError" || name === "AbortError"
      ? "The request timed out. Check your connection and try again."
      : "Cannot reach the server. Check your connection and try again.");
  }
  const isInitialAnonymousMe = path === "/me" && (!options.method || options.method.toUpperCase() === "GET");
  if (response.status === 401 && typeof window !== "undefined" && path !== "/auth/login" && !isInitialAnonymousMe) {
    window.dispatchEvent(new Event("healthbridge-session-expired"));
  }
  if (!response.ok) {
    let message = `Request failed (${response.status}). Please try again.`;
    try {
      const data = await response.json();
      if (typeof data.detail === "string") message = data.detail;
      else if (Array.isArray(data.detail))
        message = data.detail.map((e: { msg: string }) => e.msg).join(". ");
    } catch {
      /* Non-JSON network gateway response. */
    }
    throw new Error(message);
  }
  return response.json();
}
export const post = <T>(path: string, body?: unknown) =>
  api<T>(path, {
    method: "POST",
    body: body === undefined ? undefined : JSON.stringify(body),
  });
