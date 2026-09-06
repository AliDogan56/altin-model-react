# Önceden kaydedilmiş deneylerin tamamı

PIT ve spot kaynağı doğrulanmamış snapshot; production seçim kanıtı değildir. Hiçbir sonuç gizlenmedi.

## 7 gün

MAE getiri yüzde puanı; yön yalnız sıfırdan farklı tahminlerde. Görüş oranı yanında okunmalı.

| Deney | MAE (yp) | MAE skill | Yön | Görüş oranı | Pozitif skill fold |
|---|---|---|---|---|---|
| persistence | 2.433 | 0.00% | — | 0.00% | 0/3 |
| historical_mean | 2.372 | 2.52% | 61.45% | 100.00% | 3/3 |
| rolling_mean_126 | 2.365 | 2.81% | 59.59% | 100.00% | 2/3 |
| momentum_20d | 2.643 | -8.62% | 54.93% | 100.00% | 0/3 |
| direction_majority | 2.378 | 2.28% | 61.45% | 100.00% | 2/3 |
| linear | 2.455 | -0.89% | 53.07% | 100.00% | 1/3 |
| ridge | 2.395 | 1.58% | 55.31% | 100.00% | 3/3 |
| elasticnet | 2.401 | 1.33% | 55.87% | 100.00% | 2/3 |
| random_forest | 2.419 | 0.59% | 59.78% | 100.00% | 2/3 |
| gradient_boosting | 2.377 | 2.29% | 59.40% | 100.00% | 3/3 |
| mlp_raw | 2.368 | 2.69% | 59.78% | 100.00% | 3/3 |
| mlp_nested | 2.433 | 0.00% | — | 0.00% | 0/3 |
| mlp_serving_replay | 2.406 | 1.13% | 60.34% | 33.33% | 1/3 |
| mlp_log_target | 2.400 | 1.35% | 63.13% | 33.33% | 1/3 |
| mlp_price_target | 2.433 | 0.00% | — | 0.00% | 0/3 |
| mlp_winsor_train_only | 2.392 | 1.69% | 59.22% | 66.67% | 2/3 |
| boosting_huber | 2.392 | 1.71% | 54.75% | 100.00% | 3/3 |
| boosting_mae | 2.382 | 2.09% | 58.85% | 100.00% | 3/3 |
| heterogeneous_calibrated | 2.378 | 2.25% | 59.59% | 100.00% | 3/3 |
| direction_logistic | 2.356 | 3.17% | 61.27% | 100.00% | 3/3 |
| mlp_shrinkage_calibration | 2.433 | 0.00% | — | 0.00% | 0/3 |
| mlp_rolling_calibration | 2.433 | 0.00% | — | 0.00% | 0/3 |
| mlp_rolling3y | 2.433 | 0.00% | — | 0.00% | 0/3 |
| mlp_rolling5y | 2.433 | 0.00% | — | 0.00% | 0/3 |
| mlp_recency_1y | 2.433 | 0.00% | — | 0.00% | 0/3 |
| mlp_technical | 2.433 | 0.00% | — | 0.00% | 0/3 |
| mlp_macro | 2.422 | 0.44% | 59.22% | 33.33% | 1/3 |
| mlp_regime | 2.431 | 0.09% | 56.98% | 33.33% | 1/3 |
| mlp_minus_dollar | 2.401 | 1.31% | 57.26% | 66.67% | 2/3 |
| mlp_minus_real_yield | 2.433 | 0.00% | — | 0.00% | 0/3 |
| mlp_minus_inflation | 2.408 | 1.04% | 53.35% | 66.67% | 2/3 |
| mlp_minus_vix | 2.428 | 0.23% | 52.51% | 33.33% | 1/3 |
| mlp_minus_oil | 2.423 | 0.42% | 55.31% | 66.67% | 2/3 |
| mlp_minus_momentum | 2.409 | 0.98% | 60.06% | 66.67% | 1/3 |
| mlp_minus_volatility | 2.396 | 1.52% | 60.34% | 66.67% | 2/3 |
| mlp_macro_lag_stress | 2.428 | 0.20% | 56.42% | 33.33% | 1/3 |
| mlp_engineered | 2.433 | 0.00% | — | 0.00% | 0/3 |
| mlp_lookback_10_20_40 | 2.433 | 0.00% | — | 0.00% | 0/3 |
| ridge_technical | 2.415 | 0.74% | 56.24% | 100.00% | 1/3 |
| ridge_macro | 2.339 | 3.89% | 61.45% | 100.00% | 3/3 |
| ridge_regime | 2.368 | 2.66% | 55.12% | 100.00% | 3/3 |
| ridge_engineered | 2.520 | -3.58% | 48.23% | 100.00% | 2/3 |
| ridge_lookback_10_20_40 | 2.383 | 2.08% | 56.24% | 100.00% | 3/3 |

## 14 gün

MAE getiri yüzde puanı; yön yalnız sıfırdan farklı tahminlerde. Görüş oranı yanında okunmalı.

| Deney | MAE (yp) | MAE skill | Yön | Görüş oranı | Pozitif skill fold |
|---|---|---|---|---|---|
| persistence | 3.205 | 0.00% | — | 0.00% | 0/3 |
| historical_mean | 3.076 | 4.03% | 62.80% | 100.00% | 2/3 |
| rolling_mean_126 | 3.121 | 2.60% | 59.63% | 100.00% | 2/3 |
| momentum_20d | 3.612 | -12.71% | 58.13% | 100.00% | 0/3 |
| direction_majority | 3.066 | 4.34% | 62.80% | 100.00% | 2/3 |
| linear | 3.370 | -5.17% | 59.07% | 100.00% | 0/3 |
| ridge | 3.223 | -0.57% | 59.25% | 100.00% | 1/3 |
| elasticnet | 3.243 | -1.21% | 59.07% | 100.00% | 1/3 |
| random_forest | 3.275 | -2.20% | 55.70% | 100.00% | 1/3 |
| gradient_boosting | 3.191 | 0.42% | 58.13% | 100.00% | 2/3 |
| mlp_raw | 3.178 | 0.84% | 57.57% | 100.00% | 1/3 |
| mlp_nested | 3.141 | 1.99% | 56.86% | 66.73% | 1/3 |
| mlp_serving_replay | 3.171 | 1.05% | 56.30% | 66.73% | 1/3 |
| mlp_log_target | 3.155 | 1.56% | 57.42% | 66.73% | 1/3 |
| mlp_price_target | 3.205 | 0.00% | — | 0.00% | 0/3 |
| mlp_winsor_train_only | 3.193 | 0.38% | 56.30% | 66.73% | 1/3 |
| boosting_huber | 3.196 | 0.26% | 58.13% | 100.00% | 1/3 |
| boosting_mae | 3.144 | 1.88% | 56.26% | 100.00% | 1/3 |
| heterogeneous_calibrated | 3.209 | -0.15% | 58.13% | 100.00% | 2/3 |
| direction_logistic | 3.136 | 2.16% | 55.70% | 100.00% | 2/3 |
| mlp_shrinkage_calibration | 3.161 | 1.37% | 56.86% | 66.73% | 2/3 |
| mlp_rolling_calibration | 3.205 | 0.00% | — | 0.00% | 0/3 |
| mlp_rolling3y | 3.217 | -0.37% | 57.70% | 66.73% | 1/3 |
| mlp_rolling5y | 3.141 | 1.99% | 56.86% | 66.73% | 1/3 |
| mlp_recency_1y | 3.130 | 2.32% | 69.66% | 33.27% | 1/3 |
| mlp_technical | 3.198 | 0.21% | 53.37% | 33.27% | 1/3 |
| mlp_macro | 3.216 | -0.36% | 49.72% | 33.46% | 0/3 |
| mlp_regime | 3.153 | 1.61% | 57.70% | 66.73% | 1/3 |
| mlp_minus_dollar | 3.143 | 1.93% | 68.54% | 33.27% | 1/3 |
| mlp_minus_real_yield | 3.167 | 1.16% | 57.14% | 66.73% | 1/3 |
| mlp_minus_inflation | 3.213 | -0.27% | 53.78% | 66.73% | 1/3 |
| mlp_minus_vix | 3.212 | -0.22% | 60.50% | 66.73% | 1/3 |
| mlp_minus_oil | 3.111 | 2.92% | 69.10% | 33.27% | 1/3 |
| mlp_minus_momentum | 3.229 | -0.75% | 50.84% | 33.46% | 0/3 |
| mlp_minus_volatility | 3.123 | 2.55% | 69.66% | 33.27% | 1/3 |
| mlp_macro_lag_stress | 3.196 | 0.28% | 58.82% | 66.73% | 1/3 |
| mlp_engineered | 3.163 | 1.29% | 54.34% | 66.73% | 2/3 |
| mlp_lookback_10_20_40 | 3.131 | 2.31% | 67.98% | 33.27% | 1/3 |
| ridge_technical | 3.242 | -1.15% | 56.45% | 100.00% | 1/3 |
| ridge_macro | 3.080 | 3.90% | 62.06% | 100.00% | 2/3 |
| ridge_regime | 3.169 | 1.12% | 61.31% | 100.00% | 2/3 |
| ridge_engineered | 3.713 | -15.85% | 50.28% | 100.00% | 1/3 |
| ridge_lookback_10_20_40 | 3.210 | -0.17% | 61.12% | 100.00% | 1/3 |

## 30 gün

MAE getiri yüzde puanı; yön yalnız sıfırdan farklı tahminlerde. Görüş oranı yanında okunmalı.

| Deney | MAE (yp) | MAE skill | Yön | Görüş oranı | Pozitif skill fold |
|---|---|---|---|---|---|
| persistence | 5.104 | 0.00% | — | 0.00% | 0/3 |
| historical_mean | 4.742 | 7.11% | 69.19% | 100.00% | 2/3 |
| rolling_mean_126 | 4.775 | 6.44% | 65.03% | 100.00% | 2/3 |
| momentum_20d | 6.036 | -18.25% | 65.41% | 100.00% | 0/3 |
| direction_majority | 4.528 | 11.29% | 69.19% | 100.00% | 2/3 |
| linear | 5.661 | -10.91% | 61.25% | 100.00% | 0/3 |
| ridge | 5.154 | -0.98% | 63.71% | 100.00% | 2/3 |
| elasticnet | 5.430 | -6.38% | 61.44% | 100.00% | 0/3 |
| random_forest | 5.345 | -4.71% | 58.41% | 100.00% | 1/3 |
| gradient_boosting | 5.248 | -2.81% | 57.84% | 100.00% | 1/3 |
| mlp_raw | 5.216 | -2.18% | 61.25% | 100.00% | 2/3 |
| mlp_nested | 4.864 | 4.70% | 77.84% | 33.27% | 1/3 |
| mlp_serving_replay | 5.034 | 1.38% | 67.61% | 33.27% | 1/3 |
| mlp_log_target | 5.104 | 0.00% | — | 0.00% | 0/3 |
| mlp_price_target | 5.104 | 0.00% | — | 0.00% | 0/3 |
| mlp_winsor_train_only | 4.817 | 5.63% | 76.70% | 33.27% | 1/3 |
| boosting_huber | 5.240 | -2.65% | 57.47% | 100.00% | 1/3 |
| boosting_mae | 5.203 | -1.94% | 58.03% | 100.00% | 1/3 |
| heterogeneous_calibrated | 4.910 | 3.81% | 60.87% | 100.00% | 3/3 |
| direction_logistic | 4.620 | 9.50% | 69.57% | 100.00% | 2/3 |
| mlp_shrinkage_calibration | 5.004 | 1.96% | 77.84% | 33.27% | 1/3 |
| mlp_rolling_calibration | 5.104 | 0.00% | — | 0.00% | 0/3 |
| mlp_rolling3y | 4.864 | 4.70% | 77.84% | 33.27% | 1/3 |
| mlp_rolling5y | 4.864 | 4.70% | 77.84% | 33.27% | 1/3 |
| mlp_recency_1y | 5.104 | 0.00% | — | 0.00% | 0/3 |
| mlp_technical | 4.896 | 4.09% | 69.97% | 66.73% | 2/3 |
| mlp_macro | 5.115 | -0.21% | 51.70% | 33.27% | 0/3 |
| mlp_regime | 5.104 | 0.00% | — | 0.00% | 0/3 |
| mlp_minus_dollar | 5.104 | 0.00% | — | 0.00% | 0/3 |
| mlp_minus_real_yield | 5.104 | 0.00% | — | 0.00% | 0/3 |
| mlp_minus_inflation | 5.275 | -3.35% | 59.66% | 33.27% | 0/3 |
| mlp_minus_vix | 5.104 | 0.00% | — | 0.00% | 0/3 |
| mlp_minus_oil | 5.104 | 0.00% | — | 0.00% | 0/3 |
| mlp_minus_momentum | 5.097 | 0.15% | 52.54% | 33.46% | 1/3 |
| mlp_minus_volatility | 5.002 | 2.01% | 74.43% | 33.27% | 1/3 |
| mlp_macro_lag_stress | 5.104 | 0.00% | — | 0.00% | 0/3 |
| mlp_engineered | 5.104 | 0.00% | — | 0.00% | 0/3 |
| mlp_lookback_10_20_40 | 5.104 | 0.00% | — | 0.00% | 0/3 |
| ridge_technical | 5.101 | 0.06% | 55.01% | 100.00% | 1/3 |
| ridge_macro | 4.830 | 5.38% | 69.19% | 100.00% | 2/3 |
| ridge_regime | 5.362 | -5.04% | 61.44% | 100.00% | 1/3 |
| ridge_engineered | 6.175 | -20.98% | 48.39% | 100.00% | 1/3 |
| ridge_lookback_10_20_40 | 5.137 | -0.64% | 64.65% | 100.00% | 2/3 |
