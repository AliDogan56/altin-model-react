import type { ModelNetwork } from './types';

const matVec = (x: number[], w: number[][]): number[] =>
  w[0].map((_, j) => x.reduce((s, v, i) => s + v * w[i][j], 0));

const add = (a: number[], b: number[]): number[] => a.map((v, i) => v + b[i]);
const relu = (a: number[]): number[] => a.map(v => Math.max(0, v));

/** Tek ağın ileri beslemesi; çıktı y ölçeğinden gerçek getiriye döndürülür. */
export const forward = (x: number[], net: ModelNetwork, yMean: number[], yStd: number[]): number[] => {
  const a1 = relu(add(matVec(x, net.w1), net.b1));
  const a2 = relu(add(matVec(a1, net.w2), net.b2));
  return add(matVec(a2, net.w3), net.b3).map((v, i) => v * yStd[i] + yMean[i]);
};
