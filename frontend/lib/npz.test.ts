import { strToU8, zipSync } from "fflate";
import { describe, expect, it } from "vitest";
import { parseActivationNpz, parseFloat32Npy } from "./npz";

function makeNpy(values: number[], shape: [number, number]) {
  const header = `{\'descr\': \'<f4\', \'fortran_order\': False, \'shape\': (${shape[0]}, ${shape[1]}), }`;
  const prefixLength = 10;
  const padding = (16 - ((prefixLength + header.length + 1) % 16)) % 16;
  const headerBytes = strToU8(`${header}${" ".repeat(padding)}\n`);
  const output = new Uint8Array(prefixLength + headerBytes.length + values.length * 4);
  output.set([0x93, 0x4e, 0x55, 0x4d, 0x50, 0x59, 1, 0], 0);
  new DataView(output.buffer).setUint16(8, headerBytes.length, true);
  output.set(headerBytes, prefixLength);
  new Float32Array(output.buffer, prefixLength + headerBytes.length).set(values);
  return output;
}

describe("parseFloat32Npy", () => {
  it("parses Cortex Lab's C-order activation matrix", () => {
    const parsed = parseFloat32Npy(makeNpy([0.25, -1, 2, 0.5], [2, 2]));
    expect(parsed.shape).toEqual([2, 2]);
    expect(Array.from(parsed.activations)).toEqual([0.25, -1, 2, 0.5]);
  });

  it("reads activation arrays from an NPZ archive", () => {
    const archive = zipSync({ "activations.npy": makeNpy([1, 2], [1, 2]) });
    const parsed = parseActivationNpz(archive.buffer.slice(archive.byteOffset, archive.byteOffset + archive.byteLength));
    expect(parsed.shape).toEqual([1, 2]);
  });
});
