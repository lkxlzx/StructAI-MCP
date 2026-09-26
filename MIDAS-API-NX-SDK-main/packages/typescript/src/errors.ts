import type { HttpMethod, JsonValue } from "./types";

export interface MidasErrorOptions {
  statusCode?: number;
  method?: HttpMethod;
  endpoint?: string;
  responseBody?: JsonValue | string;
  cause?: unknown;
}

export class MidasAPIError extends Error {
  readonly statusCode: number | undefined;
  readonly method: HttpMethod | undefined;
  readonly endpoint: string | undefined;
  readonly responseBody: JsonValue | string | undefined;

  constructor(message: string, options: MidasErrorOptions = {}) {
    super(message, { cause: options.cause });
    this.name = new.target.name;
    this.statusCode = options.statusCode;
    this.method = options.method;
    this.endpoint = options.endpoint;
    this.responseBody = options.responseBody;
  }
}

export class MidasAuthError extends MidasAPIError {}
export class MidasNotFoundError extends MidasAPIError {}
export class MidasRequestError extends MidasAPIError {}
export class MidasServerError extends MidasAPIError {}
export class MidasConnectionError extends MidasAPIError {}
export class MidasResultError extends MidasAPIError {}
export class ProductMismatchError extends MidasAPIError {}
export class UnsupportedMethodError extends MidasAPIError {}
export class DestructiveOperationError extends MidasAPIError {}

export function errorForStatus(status: number): typeof MidasAPIError {
  if (status === 401 || status === 403) return MidasAuthError;
  if (status === 404) return MidasNotFoundError;
  if (status >= 500) return MidasServerError;
  return MidasRequestError;
}
