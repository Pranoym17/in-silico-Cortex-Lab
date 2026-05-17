import msgpack from "msgpack-lite";

export type ChunkEnvelope = {
  encoding: "base64-msgpack";
  payload: string;
};

export function decodeBase64Msgpack<T>(envelope: ChunkEnvelope): T {
  const bytes = Buffer.from(envelope.payload, "base64");
  return msgpack.decode(bytes) as T;
}

