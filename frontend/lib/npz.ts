import { unzipSync } from "fflate";

export type NpzActivationMatrix = {
  activations: Float32Array;
  shape: [number, number];
};

const NPY_MAGIC = [0x93, 0x4e, 0x55, 0x4d, 0x50, 0x59];

/** Parse the small, explicit subset of NumPy archives Cortex Lab writes for results. */
export function parseActivationNpz(bytes: ArrayBuffer): NpzActivationMatrix {
  const files = unzipSync(new Uint8Array(bytes));
  const activationFile = files["activations.npy"];
  if (!activationFile) throw new Error("Result archive does not contain activations.npy");
  return parseFloat32Npy(activationFile);
}

export function parseFloat32Npy(bytes: Uint8Array): NpzActivationMatrix {
  if (bytes.length < 12 || !NPY_MAGIC.every((value, index) => bytes[index] === value)) {
    throw new Error("Activation file is not a NumPy array");
  }
  const version = bytes[6];
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const headerLength = version === 1 ? view.getUint16(8, true) : view.getUint32(8, true);
  const headerOffset = version === 1 ? 10 : 12;
  const dataOffset = headerOffset + headerLength;
  if (dataOffset >= bytes.byteLength) throw new Error("Activation NumPy header is truncated");

  const header = new TextDecoder("latin1").decode(bytes.slice(headerOffset, dataOffset));
  const descriptor = /['"]descr['"]\s*:\s*['"]([^'"]+)['"]/.exec(header)?.[1];
  const fortranOrder = /['"]fortran_order['"]\s*:\s*(True|False)/.exec(header)?.[1];
  const shapeMatch = /['"]shape['"]\s*:\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)/.exec(header);
  if (descriptor !== "<f4" || fortranOrder !== "False" || !shapeMatch) {
    throw new Error("Activation array must be a C-order little-endian float32 matrix");
  }

  const shape: [number, number] = [Number(shapeMatch[1]), Number(shapeMatch[2])];
  const expectedBytes = shape[0] * shape[1] * Float32Array.BYTES_PER_ELEMENT;
  if (bytes.byteLength - dataOffset !== expectedBytes) throw new Error("Activation array byte length does not match its shape");
  const activationBytes = bytes.slice(dataOffset);
  return { activations: new Float32Array(activationBytes.buffer), shape };
}
