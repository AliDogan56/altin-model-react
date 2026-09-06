#!/usr/bin/env python3
"""Render the recorded audit, without fitting or choosing a model."""
import argparse
import csv
import html
import json
import math
from pathlib import Path

import numpy as np


def p(value): return "—" if value is None else f"{100*value:.2f}%"
def n(value): return "—" if value is None else f"{value:.4f}"
def table(headers,rows):
    return "| "+" | ".join(headers)+" |\n|"+"|".join("---" for _ in headers)+"|\n"+"\n".join("| "+" | ".join(map(str,row))+" |" for row in rows)+"\n"


def paired_ci(y,a,b):
    rng=np.random.default_rng(735)
    differences=np.abs(y-a)-np.abs(y-b);length=len(y);block=30
    boot=[]
    for _ in range(1000):
        starts=rng.integers(0,length-block+1,size=math.ceil(length/block))
        indexes=np.concatenate([np.arange(s,s+block) for s in starts])[:length]
        boot.append(float(differences[indexes].mean()))
    return {"mean_mae_difference":float(differences.mean()),"ci95":np.quantile(boot,[.025,.975]).tolist(),
            "interpretation":"negative favors model; paired moving blocks30, exploratory, not corrected for multiple comparisons"}


def svg_frame(width,height,title,body):
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img"><title>{html.escape(title)}</title><rect width="100%" height="100%" fill="#faf9f6"/><g font-family="Arial,sans-serif" fill="#292c2b">{body}</g></svg>'


def main(directory):
    results=json.loads((directory/"results.json").read_text());manifest=json.loads((directory/"manifest.json").read_text())
    overview=[];full=[];comparisons={}
    predicted={}
    with (directory/"oos_predictions.csv").open() as handle:
        for row in csv.DictReader(handle):predicted.setdefault((row["horizon"],row["experiment"]),[]).append(row)
    for horizon,experiments in results.items():
        full.append(f"## {horizon} gün\n\nMAE getiri yüzde puanı; yön yalnız sıfırdan farklı tahminlerde. Görüş oranı yanında okunmalı.\n")
        full.append(table(["Deney","MAE (yp)","MAE skill","Yön","Görüş oranı","Pozitif skill fold"],[
            [name,f'{v["metrics"]["mae"]*100:.3f}',p(v["metrics"]["mae_skill"]),p(v["metrics"]["direction"]),p(v["metrics"]["active_fraction"]),f'{v["positive_skill_folds"]}/3']
            for name,v in experiments.items()]))
        for name in ("persistence","historical_mean","direction_majority","ridge","elasticnet","random_forest","gradient_boosting","mlp_raw","mlp_nested","direction_logistic","heterogeneous_calibrated"):
            v=experiments[name];m=v["metrics"]
            overview.append({"horizon":horizon,"experiment":name,**m})
        base=predicted[(horizon,"direction_majority")]
        for name in ("ridge_macro","mlp_raw","mlp_nested","direction_logistic","heterogeneous_calibrated"):
            other=predicted[(horizon,name)]
            assert [r["date"] for r in base]==[r["date"] for r in other]
            comparisons[f"{horizon}:{name}:vs_direction_majority"]=paired_ci(
                np.array([float(r["actual_return"]) for r in base]),np.array([float(r["predicted_return"]) for r in other]),np.array([float(r["predicted_return"]) for r in base]))
    (directory/"EXPERIMENTS.md").write_text("# Önceden kaydedilmiş deneylerin tamamı\n\nPIT ve spot kaynağı doğrulanmamış snapshot; production seçim kanıtı değildir. Hiçbir sonuç gizlenmedi.\n\n"+"\n".join(full),encoding="utf-8")
    with (directory/"summary.csv").open("w",newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=list(overview[0]),lineterminator="\n");writer.writeheader();writer.writerows(overview)
    (directory/"paired_comparisons.json").write_text(json.dumps(comparisons,indent=2))
    body='<text x="32" y="28" font-size="18">Nominal → gerçekleşen bant kapsamı / nested MLP</text>'
    colors={"split":"#9c7652","rolling":"#307477","adaptive":"#86588c"}
    for j,(horizon,experiments) in enumerate(results.items()):
        left=50+j*320;top=70;size=250
        body+=f'<text x="{left}" y="53" font-size="15">{horizon} gün</text>'
        for percent in (0,25,50,75,100):
            yy=top+size*(1-percent/100)
            body+=f'<path d="M{left},{yy}h{size}" stroke="#ddd"/><text x="{left-6}" y="{yy+4}" text-anchor="end" font-size="10">{percent}</text>'
        body+=f'<path d="M{left},{top+size}L{left+size},{top}" stroke="#777" stroke-dasharray="4 4"/>'
        for method,color in colors.items():
            points=[]
            for c in (.5,.7,.8,.9):
                value=experiments["mlp_nested"]["intervals"][method+"_"+str(c)]["empirical"]
                xx=left+size*c;yy=top+size*(1-value);points.append(f"{xx},{yy}")
                body+=f'<circle cx="{xx}" cy="{yy}" r="3" fill="{color}"><title>{method} nominal {c:.0%}, actual {value:.1%}</title></circle>'
            body+=f'<polyline points="{" ".join(points)}" fill="none" stroke="{color}" stroke-width="2"/>'
        body+=f'<text x="{left+size/2}" y="345" text-anchor="middle" font-size="11">Nominal kapsam: 0–100%</text>'
    for j,(method,color) in enumerate(colors.items()):body+=f'<text x="{100+j*260}" y="380" fill="{color}" font-size="13">● {method}</text>'
    body+='<text x="32" y="415" font-size="12">Deneysel ölçüm. Makro vintage/provenance yok; zaman bağımlı veride dağılımdan bağımsız garanti değildir.</text>'
    (directory/"calibration.svg").write_text(svg_frame(1010,440,"Calibration curves",body))
    redundancy=json.loads((directory/"feature_redundancy.json").read_text());names=redundancy["features"]
    matrix=np.asarray(redundancy["spearman"]);body='<text x="18" y="26" font-size="18">Spearman feature korelasyonu (betimleyici)</text>'
    for i,name in enumerate(names):
        body+=f'<text x="210" y="{59+i*24}" text-anchor="end" font-size="10">{html.escape(name)}</text>'
        body+=f'<text x="{228+i*24}" y="42" font-size="10">{i+1}</text>'
        for j,value in enumerate(matrix[i]):
            hue="25,90,130" if value>=0 else "161,65,55"
            body+=f'<rect x="{220+j*24}" y="{45+i*24}" width="23" height="23" fill="rgb({hue})" fill-opacity="{abs(value):.3f}"><title>{names[i]} / {names[j]}: {value:.3f}</title></rect>'
    (directory/"correlation.svg").write_text(svg_frame(710,525,"Spearman correlation",body))
    with (directory/"dataset_snapshot.csv").open() as handle:rows=list(csv.DictReader(handle))
    body='<text x="30" y="30" font-size="18">Hedef dağılımları / basit getiri</text>'
    for j,h in enumerate((7,14,30)):
        vals=np.array([float(r[f"target_return_{h}d"]) for r in rows if r[f"target_return_{h}d"]])
        counts,bins=np.histogram(vals,bins=np.linspace(-.2,.24,41));left=50+j*320;top=75;width=270;height=190
        body+=f'<text x="{left}" y="60" font-size="14">{h} gün · n={len(vals)}</text>'
        for i,count in enumerate(counts):
            barheight=height*count/max(counts)
            body+=f'<rect x="{left+i*width/40}" y="{top+height-barheight}" width="{width/40-1}" height="{barheight}" fill="#8f7545"/>'
        for value in (-.2,0,.2):
            xx=left+(value+.2)/.44*width
            body+=f'<text x="{xx}" y="285" text-anchor="middle" font-size="11">{value:.0%}</text>'
    (directory/"target_distribution.svg").write_text(svg_frame(1010,310,"Return target distributions",body))
    (directory/"index.html").write_text('<!doctype html><html lang="tr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Model audit — ölçüm çıktıları</title><style>body{max-width:1100px;margin:32px auto;padding:0 16px;background:#faf9f6;color:#292c2b;font:16px/1.6 system-ui}img{width:100%;height:auto}aside{border-left:4px solid #9c7652;padding:12px 20px;background:#eee9de}a{color:#386b74}code{overflow-wrap:anywhere}section{margin:40px 0}table{border-collapse:collapse}td,th{padding:8px;border-bottom:1px solid #ccc}</style><h1>Ons altın · model inceleme ölçümleri</h1><aside>Bu snapshot’ın makro yayın/vintage ve spot kaynak geçmişi doğrulanmamıştır. Sonuçlar deneysel denetimdir; yeni model production’a alınmadı.</aside><p>Snapshot SHA256: <code>'+manifest["dataset_hash"]+'</code></p><p>43 deney × 3 vade · 3 purged expanding fold. <a href="EXPERIMENTS.md">Tüm deneyler</a> · <a href="summary.csv">Özet CSV</a> · <a href="results.json">Tam metrikler</a></p><section><img src="target_distribution.svg" alt="7,14,30 gün hedef dağılımları"></section><section><img src="calibration.svg" alt="Nominal ve gerçekleşen kapsam karşılaştırması"></section><section><img src="correlation.svg" alt="19 feature Spearman korelasyon matrisi"></section></html>',encoding="utf-8")
    print(f"Rendered {len(overview)} summary rows, 3 SVG figures, all experiment tables and paired bootstrap comparisons")


if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("directory",type=Path);main(parser.parse_args().directory)
