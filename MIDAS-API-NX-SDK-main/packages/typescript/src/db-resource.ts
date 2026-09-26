import {
  DestructiveOperationError,
  MidasRequestError,
  UnsupportedMethodError,
} from "./errors";
import { getDefaultClient, type MidasClient } from "./client";
import type {
  HttpMethod,
  ItemId,
  ItemMap,
  JsonObject,
  NumericItemMap,
  Product,
} from "./types";

export interface DbResourceMetadata {
  className: string;
  endpoint: string;
  name: string;
  products: readonly Product[];
  methods: readonly HttpMethod[];
  /**
   * The official manual chapter documenting this endpoint, e.g.
   * `03_DB_Node_Element.md` in `Dennis5882/MIDAS-API`.
   *
   * This replaced a `pythonModule` field that shipped the PyPI package's module
   * path to JavaScript users - nothing they could act on, and a standing
   * advertisement that one language surface was generated from the other. Both
   * are now generated from `contracts/`.
   */
  manualChapter?: string;
  /**
   * Field values this endpoint's contract requires be sent explicitly, filled
   * in on `create()` and `update()` for any record that omits them.
   *
   * These are never invented defaults. Each one is the value the official
   * manual already documents, made explicit on the wire because omitting it
   * has been observed to break the product. `/db/NMAS` is the case that
   * motivated it: leaving `rmX`/`rmY`/`rmZ` out of the payload hung the call
   * and killed the NX session across 15+ reproductions on both Gen NX and
   * Civil NX, while sending them as `0.0` - their own documented default - did
   * not. A caller should not have to know that to use the endpoint safely.
   *
   * Generated from `contracts/endpoints/*.yaml`; see `contracts/README.md`.
   */
  payloadDefaults?: Readonly<Record<string, unknown>>;
  /**
   * Payload fields this endpoint's contract refuses to send as an empty
   * object, checked on `create()` and `update()`.
   *
   * `/db/MVHL`'s `VEH_DEFAULT` is the case that motivated it: the server
   * accepts `VEH_DEFAULT: {}`, answers `{"message": ""}` with no error object,
   * and stores nothing - a following `get()` shows the vehicle was never
   * created. Every member of that object is documented Optional, so an empty
   * one reads as "all defaults", and nothing in the response says otherwise.
   *
   * Only an explicitly empty object is refused. Omitting the field is a
   * different request and is left alone.
   *
   * Generated from `contracts/endpoints/*.yaml`; see `contracts/README.md`.
   */
  rejectEmptyFields?: readonly string[];
  /**
   * Payload fields this endpoint's contract requires be present, checked on
   * `create()` and `update()`. A path may name an array's entries -
   * `ITEMS[].DIRECTION` - in which case every entry is checked.
   *
   * The opposite of `payloadDefaults`, and it exists for the case that one
   * cannot cover: a documented default the product refuses. `/db/PRES`'s
   * `DIRECTION` is the case that motivated it. The manual marks it Optional
   * with the default `"NORMAL"`, and on a `PLATE` with `FACE_EDGE_TYPE`
   * `"FACE"` - the commonest pressure load there is - the server refuses both
   * the omission and that value, with the same message. Filling the default in
   * would send a value known to fail; there is no other value an SDK could
   * supply without deciding which way the pressure acts. So the caller is
   * asked, before the request goes out.
   *
   * Sending the documented value explicitly is left alone: it is legitimate
   * for the other element-type combinations the manual's own availability
   * matrix lists.
   *
   * Generated from `contracts/endpoints/*.yaml`; see `contracts/README.md`.
   */
  requiredExplicitFields?: readonly string[];
}

export class DbResource<TPayload extends object = JsonObject> {
  readonly metadata: DbResourceMetadata;

  constructor(metadata: DbResourceMetadata) {
    this.metadata = metadata;
  }

  private check(client: MidasClient, method: HttpMethod): void {
    client.checkProduct(this.metadata.products, this.metadata.name || this.metadata.className);
    if (!this.metadata.methods.includes(method)) {
      throw new UnsupportedMethodError(
        `${this.metadata.name || this.metadata.className} (${this.metadata.endpoint}) does not support ${method}; supported methods: ${this.metadata.methods.join(", ")}`,
        { method, endpoint: this.metadata.endpoint },
      );
    }
  }

  async get(client: MidasClient = getDefaultClient()): Promise<JsonObject> {
    this.check(client, "GET");
    return client.request("GET", this.metadata.endpoint);
  }

  async items(client: MidasClient = getDefaultClient()): Promise<NumericItemMap<TPayload>> {
    const response = await this.get(client);
    const table = Object.values(response).find(
      (value): value is JsonObject => typeof value === "object" && value !== null && !Array.isArray(value),
    );
    if (!table) return {};
    return Object.fromEntries(
      Object.entries(table).map(([key, value]) => [Number(key), value as TPayload]),
    ) as NumericItemMap<TPayload>;
  }

  async info(client: MidasClient = getDefaultClient()): Promise<JsonObject> {
    client.checkProduct(this.metadata.products, this.metadata.name || this.metadata.className);
    return client.request("GET", `/info${this.metadata.endpoint}`);
  }

  /**
   * Apply the contract's required-explicit field values to every record,
   * without overriding anything the caller supplied.
   */
  /** Refuse the payload shapes the contract records as silently discarded. */
  private rejectEmpty(items: ItemMap<TPayload>, method: HttpMethod): void {
    const fields = this.metadata.rejectEmptyFields;
    if (!fields?.length) return;
    for (const [id, payload] of Object.entries(items)) {
      const values = payload as Record<string, unknown>;
      for (const field of fields) {
        const value = values[field];
        if (
          typeof value === "object" &&
          value !== null &&
          !Array.isArray(value) &&
          Object.keys(value).length === 0
        ) {
          throw new MidasRequestError(
            `${field} must not be empty for ${this.metadata.endpoint}: the server accepts the request and saves nothing (record ${id})`,
            { method, endpoint: this.metadata.endpoint },
          );
        }
      }
    }
  }

  /**
   * Refuse a record that leaves a contract-required field to a default the
   * product does not accept. See `requiredExplicitFields`.
   */
  private requireExplicit(items: ItemMap<TPayload>, method: HttpMethod): void {
    const paths = this.metadata.requiredExplicitFields;
    if (!paths?.length) return;
    for (const [id, payload] of Object.entries(items)) {
      for (const path of paths) {
        for (const [where, holder] of this.resolve(payload as Record<string, unknown>, path, id)) {
          const field = path.slice(path.lastIndexOf(".") + 1);
          if (holder[field] === undefined) {
            throw new MidasRequestError(
              `${field} must be sent explicitly for ${this.metadata.endpoint}: its documented default is one the product refuses (${where})`,
              { method, endpoint: this.metadata.endpoint },
            );
          }
        }
      }
    }
  }

  /**
   * Every object a dotted path addresses, with a label naming where it sits.
   * `A[].B` yields one entry per element of `A`; a missing or wrongly typed
   * step yields none, because a field cannot be absent from a place the
   * caller never sent.
   */
  private resolve(
    payload: Record<string, unknown>,
    path: string,
    id: string,
  ): [string, Record<string, unknown>][] {
    const steps = path.split(".").slice(0, -1);
    let holders: [string, Record<string, unknown>][] = [[`record ${id}`, payload]];
    for (const step of steps) {
      const array = step.endsWith("[]");
      const key = array ? step.slice(0, -2) : step;
      const next: [string, Record<string, unknown>][] = [];
      for (const [where, holder] of holders) {
        const value = holder[key];
        if (array) {
          if (!Array.isArray(value)) continue;
          value.forEach((entry, index) => {
            if (entry && typeof entry === "object" && !Array.isArray(entry)) {
              next.push([`${where}, ${key}[${index}]`, entry as Record<string, unknown>]);
            }
          });
        } else if (value && typeof value === "object" && !Array.isArray(value)) {
          next.push([`${where}, ${key}`, value as Record<string, unknown>]);
        }
      }
      holders = next;
    }
    return holders;
  }

  private normalize(items: ItemMap<TPayload>): ItemMap<TPayload> {
    const defaults = this.metadata.payloadDefaults;
    if (!defaults) return items;
    return Object.fromEntries(
      Object.entries(items).map(([id, payload]) => [id, { ...defaults, ...payload }]),
    ) as ItemMap<TPayload>;
  }

  async create(items: ItemMap<TPayload>, client: MidasClient = getDefaultClient()): Promise<JsonObject> {
    this.check(client, "POST");
    this.rejectEmpty(items, "POST");
    this.requireExplicit(items, "POST");
    return client.request("POST", this.metadata.endpoint, {
      Assign: stringifyKeys(this.normalize(items)),
    });
  }

  async update(items: ItemMap<TPayload>, client: MidasClient = getDefaultClient()): Promise<JsonObject> {
    this.check(client, "PUT");
    this.rejectEmpty(items, "PUT");
    this.requireExplicit(items, "PUT");
    return client.request("PUT", this.metadata.endpoint, {
      Assign: stringifyKeys(this.normalize(items)),
    });
  }

  /**
   * Delete only the requested IDs, one request at a time. Processing stops at
   * the first error so later destructive requests are never left running in
   * the background after this promise rejects.
   */
  async delete(ids: readonly ItemId[], client: MidasClient = getDefaultClient()): Promise<Record<string, JsonObject>> {
    this.check(client, "DELETE");
    const responses: Record<string, JsonObject> = {};
    // MIDAS NX sessions are stateful and several operations can block the
    // product UI. Keep destructive calls ordered and stop at the first error;
    // launching every DELETE with Promise.all would let later mutations keep
    // running after the caller has already received a rejection.
    for (const id of ids) {
      responses[String(id)] = await client.request<JsonObject>(
        "DELETE",
        `${this.metadata.endpoint}/${id}`,
      );
    }
    return responses;
  }

  /**
   * Empty the entire resource table.
   *
   * @warning This cannot be undone through the API. For `/db/NODE`, attached
   * elements are removed as well. Use `delete(ids)` for selected records.
   */
  async deleteAll(
    options: { confirm: true; client?: MidasClient } | { confirm?: false; client?: MidasClient },
  ): Promise<JsonObject> {
    if (options.confirm !== true) {
      throw new DestructiveOperationError(
        `${this.metadata.name || this.metadata.className} (${this.metadata.endpoint}): deleteAll() would delete every record in this table and cannot be undone.`,
        { method: "DELETE", endpoint: this.metadata.endpoint },
      );
    }
    const client = options.client ?? getDefaultClient();
    this.check(client, "DELETE");
    return client.request("DELETE", this.metadata.endpoint, { Assign: {} });
  }
}

function stringifyKeys<T extends object>(items: ItemMap<T>): JsonObject {
  return Object.fromEntries(Object.entries(items)) as JsonObject;
}

export function defineDbResource<TPayload extends object = JsonObject>(
  metadata: DbResourceMetadata,
): DbResource<TPayload> {
  return new DbResource<TPayload>(metadata);
}
