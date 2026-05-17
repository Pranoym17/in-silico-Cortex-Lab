declare module "msgpack-lite" {
  export function encode(input: unknown): Buffer;
  export function decode<T = unknown>(input: Uint8Array | Buffer): T;

  const msgpack: {
    encode: typeof encode;
    decode: typeof decode;
  };

  export default msgpack;
}

