/** model.json artefaktının şekli. Domain katmanı dosyayı import etmez; çağıran verir. */
export type ModelNetwork = { w1: number[][]; b1: number[]; w2: number[][]; b2: number[]; w3: number[][]; b3: number[] };

export type ModelArtifact = {
  fallback?: boolean;
  features: string[];
  horizons: number[];
  xMean: number[]; xStd: number[];
  yMean: number[]; yStd: number[];
  models: ModelNetwork[];
  residual80: number[];
  latest: Record<string, number>;
  latestPrice: number;
  latestDate: string;
  /** Eğitim gözlem sayısı; yalnız gösterim. */
  rows?: number;
  history: [string, number][];
  resistance: { r20: number; r60: number; momentumJumpPct: number };
};

export type FeatureMap = Record<string, number>;

export type Forecast = {
  horizons: number[];
  features: FeatureMap;
  price: number;
  mean: number[];
  err: number[];
  /** Sunucu modelinin ufuk -> parametre -> marjinal getiri etkisi. */
  featureEffects?: Record<string, FeatureMap>;
};

export type PathPoint = {
  day: number; date: string;
  v: number; lo: number; hi: number;
  ret: number; err: number; kind: string;
};
