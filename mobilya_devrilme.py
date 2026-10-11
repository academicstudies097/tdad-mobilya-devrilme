# -*- coding: utf-8 -*-
"""
Konut ve otel iç mekânlarında serbest duran mobilyaların deprem etkisinde
devrilme ve kayma riski: hesaplamalı (statik + dinamik + mekânsal) analiz.

Yazarlar : Ayşan Ilgın Polat, Hakan Bal, Ferhat Koyuncu
Dergi    : Türk Deprem Araştırma Dergisi (TDAD) gönderimi için hazırlanmıştır.
Lisans   : CC BY 4.0 (kod ve veri)

Çalıştırma:  python3 mobilya_devrilme.py
Çıktılar  :  ./ciktilar/ klasörüne CSV tablolar ve PNG şekiller yazılır.

Modüller
  1. Mobilya kataloğu ve rijit blok geometrisi
  2. Statik eşikler (sallanma başlangıcı ve kayma) – Housner (1963), Shenton (1996)
  3. Kat ivmesi talebi – PFA(z) = 0,4 S_DS (1 + 2 z/H)  (ASCE/SEI 7-16, Bölüm 13)
  4. Dinamik sallanma (Housner denklemi) + stokastik kat hareketleri
     (Kanai–Tajimi / Clough–Penzien spektrumu, tek modlu kat tepkisi)
     -> Monte Carlo kırılganlık eğrileri (lognormal)
  5. Mekânsal analiz: devrilme etki alanı ile yatağın baş-gövde bölgesinin
     çakışması (konut yatak odası ve otel odası, Monte Carlo yerleşimler)
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyArrowPatch, Arc
from scipy.optimize import minimize
from scipy.stats import norm

G = 9.81
SEED = 20261011
OUT = Path(__file__).resolve().parent / "ciktilar"
OUT.mkdir(exist_ok=True)

plt.rcParams.update({
    "font.family": ["Liberation Sans", "DejaVu Sans"], "font.size": 9, "axes.titlesize": 10,
    "axes.labelsize": 9, "legend.fontsize": 8, "figure.dpi": 150,
    "savefig.dpi": 600, "axes.spines.top": False, "axes.spines.right": False,
})

# ---------------------------------------------------------------------------
# 1. MOBİLYA KATALOĞU  (temsilî boyutlar, m;  W: genişlik, D: derinlik, H: yükseklik)
# ---------------------------------------------------------------------------
CATALOG = [
    ("K01", "Gardırop, 2 kapaklı",        "Konut", 0.90, 0.58, 2.00),
    ("K02", "Gardırop, 3 kapaklı",        "Konut", 1.35, 0.58, 2.10),
    ("K03", "Gardırop, sürgülü 4 kapaklı", "Konut", 2.00, 0.62, 2.40),
    ("K04", "Kitaplık, dar",              "Konut", 0.40, 0.30, 1.80),
    ("K05", "Kitaplık, geniş",            "Konut", 0.80, 0.30, 2.00),
    ("K06", "Açık raf ünitesi",           "Konut", 0.80, 0.38, 1.50),
    ("K07", "Vitrin (camlı dolap)",       "Konut", 0.80, 0.40, 1.90),
    ("K08", "Mutfak boy dolabı",          "Konut", 0.60, 0.60, 2.10),
    ("K09", "Buzdolabı (kombi)",          "Konut", 0.70, 0.70, 1.85),
    ("K10", "Ayakkabılık / portmanto",    "Konut", 0.80, 0.35, 1.20),
    ("K11", "Şifonyer",                   "Konut", 1.00, 0.45, 1.10),
    ("K12", "Çamaşır makinesi",           "Konut", 0.60, 0.60, 0.85),
    ("K13", "Komodin",                    "Konut", 0.45, 0.40, 0.50),
    ("K14", "TV ünitesi (alçak)",         "Konut", 1.80, 0.45, 0.50),
    ("O01", "Otel gardırobu",             "Otel",  1.00, 0.60, 2.20),
    ("O02", "Otel bölücü raf",            "Otel",  1.00, 0.35, 2.00),
    ("O03", "Otel bagaj-minibar ünitesi", "Otel",  0.90, 0.50, 0.90),
    ("O04", "Otel çalışma konsolu",       "Otel",  1.20, 0.50, 0.78),
]
MU_BASE = 0.40                 # temel sürtünme katsayısı (varsayım)
MU_RANGE = (0.25, 0.60)        # duyarlılık aralığı (varsayım)
HC_RATIOS = (0.40, 0.50, 0.60) # ağırlık merkezi yüksekliği / H : alt-ağır, homojen, üst-ağır

N_STOREY = 5                   # temsilî konut binası: 5 kat, kat yüksekliği 3 m
ZR_FLOORS = np.array([0.0, 0.2, 0.4, 0.6, 0.8])  # k'ıncı kat döşemesinin z/H oranı
FLOOR_LABELS = ["Zemin kat", "1. kat", "2. kat", "3. kat", "4. kat (en üst)"]
T1 = 0.10 * N_STOREY           # temel periyot (s), T ≈ 0,1N yaklaşımı
ZETA_B = 0.05                  # bina sönüm oranı
SDS_BANDS = {                  # TBDY 2018 Deprem Tasarım Sınıfı aralıklarını temsil eden S_DS değerleri
    "DTS-4 (S_DS=0.25)": 0.25,
    "DTS-3 (S_DS=0.42)": 0.42,
    "DTS-2 (S_DS=0.63)": 0.63,
    "DTS-1 (S_DS=1.00)": 1.00,
    "DTS-1 yüksek (S_DS=1.50)": 1.50,
}


def catalog_df(hc_ratio=0.5, mu=MU_BASE):
    rows = []
    for code, name, space, W, D, H in CATALOG:
        b, hc = D / 2.0, hc_ratio * H
        tan_a = b / hc
        alpha = np.arctan(tan_a)
        R = np.hypot(b, hc)
        p = np.sqrt(3 * G / (4 * R))                    # homojen dikdörtgen blok
        r = 1 - 1.5 * np.sin(alpha) ** 2                # Housner açısal hız oranı
        mode = "Kayma" if mu < tan_a else "Sallanma"
        rows.append(dict(kod=code, mobilya=name, mekan=space, W=W, D=D, H=H,
                         narinlik_HD=H / D, tan_alpha=tan_a, alpha_rad=alpha,
                         R=R, p=p, r=r, mod=mode,
                         esik_sallanma_g=tan_a, esik_kayma_g=mu,
                         etki_alani_m2=W * H))
    return pd.DataFrame(rows)


def pfa_demand(sds, zr):
    """Tasarım düzeyi kat ivmesi (g): 0,4 S_DS (1 + 2 z/H)."""
    return 0.4 * sds * (1 + 2 * zr)


# ---------------------------------------------------------------------------
# 2. STOKASTİK YER VE KAT HAREKETLERİ
# ---------------------------------------------------------------------------
def kt_cp_psd(w, wg=15.0, zg=0.6, wf=1.5, zf=0.6):
    """Kanai–Tajimi spektrumu, Clough–Penzien yüksek geçiren düzeltmesiyle."""
    w2 = w ** 2
    kt = (wg ** 4 + 4 * zg ** 2 * wg ** 2 * w2) / ((wg ** 2 - w2) ** 2 + 4 * zg ** 2 * wg ** 2 * w2)
    cp = w2 ** 2 / ((wf ** 2 - w2) ** 2 + 4 * zf ** 2 * wf ** 2 * w2)
    return kt * cp


def envelope(t, t1=2.0, t2=10.0, c=0.30):
    """Jennings vd. (1968) tipi zarf: parabolik artış, sabit faz, üstel sönüm."""
    return np.where(t < t1, (t / t1) ** 2, np.where(t <= t2, 1.0, np.exp(-c * (t - t2))))


def simulate_ground(n, dur=25.0, dt=0.002, rng=None):
    N = int(round(dur / dt))
    t = np.arange(N) * dt
    w = 2 * np.pi * np.fft.rfftfreq(N, dt)
    F = np.fft.rfft(rng.standard_normal((n, N)), axis=1)
    F *= np.sqrt(kt_cp_psd(np.maximum(w, 1e-6)))
    x = np.fft.irfft(F, N, axis=1) * envelope(t)
    return t, x / np.abs(x).max(axis=1, keepdims=True)    # PGA = 1 (birimsiz)


def floor_motion(ag, dt, zr, T=T1, zeta=ZETA_B, n_storey=N_STOREY):
    """Tek modlu (doğrusal mod şekli) kat mutlak ivmesi: a_f = a_g + Γ φ(z) q̈."""
    if zr == 0:
        return ag.copy()
    n, N = ag.shape
    M = 2 * N                                            # sıfır dolgulu FFT
    w = 2 * np.pi * np.fft.rfftfreq(M, dt)
    wn = 2 * np.pi / T
    Ag = np.fft.rfft(ag, M, axis=1)
    Q = -Ag / (wn ** 2 - w ** 2 + 2j * zeta * wn * w)
    qdd = np.fft.irfft(-(w ** 2) * Q, M, axis=1)[:, :N]
    gamma = 3 * n_storey / (2 * n_storey + 1)
    return ag + gamma * zr * qdd


# ---------------------------------------------------------------------------
# 3. DİNAMİK SALLANMA (Housner denklemi) – vektörleştirilmiş Monte Carlo
# ---------------------------------------------------------------------------
def rocking_overturn(alpha, p, acc, levels, dt):
    """
    alpha, p : (I,) blok parametreleri
    acc      : (n, N) PFA=1 olacak şekilde ölçeklenmiş kat ivmesi kayıtları (g)
    levels   : (L,) hedef PFA düzeyleri (g)
    Dönen    : (I, L, n) bool – devrildi mi
    """
    I, L = len(alpha), len(levels)
    n, N = acc.shape
    a = alpha[:, None, None] * np.ones((I, L, n))
    pp = (p[:, None, None] ** 2) * np.ones((I, L, n))
    ta = np.tan(a)
    rcoef = 1 - 1.5 * np.sin(a) ** 2
    th = np.zeros((I, L, n)); om = np.zeros((I, L, n))
    rock = np.zeros((I, L, n), bool); over = np.zeros((I, L, n), bool)
    lv = levels[None, :, None]
    for k in range(N):
        ug = lv * acc[None, None, :, k]                   # (1,L,n) -> g cinsinden
        rest = ~rock & ~over
        start_pos = rest & (ug < -ta)
        start_neg = rest & (ug > ta)
        th[start_pos] = 1e-7; th[start_neg] = -1e-7
        rock |= start_pos | start_neg
        act = rock & ~over
        if not act.any():
            continue
        s = np.sign(th)
        arg = a * s - th
        thdd = -pp * (np.sin(arg) + ug * np.cos(arg))
        om_new = om + thdd * dt
        th_new = th + om_new * dt
        cross = act & (th * th_new < 0)                   # zemine çarpma
        om_new = np.where(cross, om_new * rcoef, om_new)
        th = np.where(act, th_new, th); om = np.where(act, om_new, om)
        settle = cross & (np.abs(om) < 1e-3)
        th[settle] = 0.0; om[settle] = 0.0; rock[settle] = False
        newly = act & (np.abs(th) > a)
        over |= newly
    return over


def fit_lognormal(levels, k, n):
    """Binom olabilirliğiyle lognormal kırılganlık: (medyan, beta)."""
    if k.sum() == 0:
        return np.nan, np.nan
    def nll(x):
        m, b = np.exp(x)
        P = np.clip(norm.cdf(np.log(levels / m) / b), 1e-9, 1 - 1e-9)
        return -(k * np.log(P) + (n - k) * np.log(1 - P)).sum()
    i50 = np.argmin(np.abs(k / n - 0.5))
    res = minimize(nll, x0=np.log([levels[i50], 0.4]), method="Nelder-Mead",
                   options=dict(xatol=1e-6, fatol=1e-8, maxiter=4000))
    return tuple(np.exp(res.x))


# ---------------------------------------------------------------------------
# 4. MEKÂNSAL ANALİZ – devrilme etki alanı / baş-gövde bölgesi çakışması
# ---------------------------------------------------------------------------
def wall_rect(wall, s, along, depth, Lx, Ly):
    """Duvara sırtı dayalı dikdörtgen (x0,y0,x1,y1); duvar 0:y=0, 1:x=Lx, 2:y=Ly, 3:x=0."""
    if wall == 0: return (s, 0.0, s + along, depth)
    if wall == 2: return (s, Ly - depth, s + along, Ly)
    if wall == 3: return (0.0, s, depth, s + along)
    return (Lx - depth, s, Lx, s + along)


def front_rect(wall, s, along, d0, d1, Lx, Ly):
    """Duvardan d0–d1 uzaklığındaki ön şerit (devrilme alanı, baş bölgesi vb.)."""
    if wall == 0: return (s, d0, s + along, d1)
    if wall == 2: return (s, Ly - d1, s + along, Ly - d0)
    if wall == 3: return (d0, s, d1, s + along)
    return (Lx - d1, s, Lx - d0, s + along)


def overlap(a, b, tol=1e-9):
    return (min(a[2], b[2]) - max(a[0], b[0]) > tol) and (min(a[3], b[3]) - max(a[1], b[1]) > tol)


def clip(r, Lx, Ly):
    return (max(r[0], 0), max(r[1], 0), min(r[2], Lx), min(r[3], Ly))


def wall_len(w, Lx, Ly):
    return Lx if w in (0, 2) else Ly


def layout_room(Lx, Ly, door_wall, door_s, win_wall, win_w, bed_w, bed_l,
                tall_items, step=0.10, head_depth=0.90, side_clear=0.45,
                foot_clear=0.60, front_clear=0.60):
    """Bir oda için tüm uygun (yatak, yüksek mobilya) yerleşimlerini sayar."""
    door_zone = wall_rect(door_wall, door_s, 0.90, 0.90, Lx, Ly)
    wl = wall_len(win_wall, Lx, Ly)
    win_zone = wall_rect(win_wall, (wl - win_w) / 2, win_w, 0.70, Lx, Ly)
    beds = []
    for wb in range(4):
        L = wall_len(wb, Lx, Ly)
        for s in np.arange(side_clear, L - bed_w - side_clear + 1e-9, step):
            fp = wall_rect(wb, s, bed_w, bed_l, Lx, Ly)
            if fp[2] > Lx + 1e-9 or fp[3] > Ly + 1e-9:
                continue
            depth_avail = wall_len((wb + 1) % 4, Lx, Ly)  # yatağın uzandığı doğrultudaki oda boyu
            if depth_avail - bed_l < foot_clear:
                continue
            if overlap(fp, door_zone):
                continue
            head = front_rect(wb, s, bed_w, 0.0, head_depth, Lx, Ly)
            beds.append((wb, s, fp, head))
    results = []
    for (wb, sb, bfp, head) in beds:
        for item in tall_items:
            name, W, D, H = item
            for wt in range(4):
                L = wall_len(wt, Lx, Ly)
                for s in np.arange(0.0, L - W + 1e-9, step):
                    fp = wall_rect(wt, s, W, D, Lx, Ly)
                    if overlap(fp, bfp) or overlap(fp, door_zone) or overlap(fp, win_zone):
                        continue
                    acc_zone = front_rect(wt, s, W, D, D + front_clear, Lx, Ly)
                    if overlap(acc_zone, bfp):
                        continue
                    fall = clip(front_rect(wt, s, W, D, D + H, Lx, Ly), Lx, Ly)
                    hit = overlap(fall, head)
                    results.append((wb, sb, name, wt, s, hit))
    return beds, results


def monte_carlo_layouts(scn, n_rooms, rng):
    recs = []
    examples = []
    for i in range(n_rooms):
        Lx = rng.uniform(*scn["Lx"]); Ly = rng.uniform(*scn["Ly"])
        Lx, Ly = round(Lx, 2), round(Ly, 2)
        door_wall = scn["door_wall"] if scn["door_wall"] is not None else int(rng.integers(4))
        dl = wall_len(door_wall, Lx, Ly)
        door_s = 0.10 if rng.random() < 0.5 else dl - 1.00
        win_wall = (door_wall + 2) % 4
        beds, res = layout_room(Lx, Ly, door_wall, door_s, win_wall, scn["win_w"],
                                scn["bed_w"], scn["bed_l"], scn["items"])
        if not res:
            recs.append(dict(oda=i, Lx=Lx, Ly=Ly, alan=Lx * Ly, uygun=False))
            continue
        df = pd.DataFrame(res, columns=["wb", "sb", "item", "wt", "s", "hit"])
        # her yatak konumu için: rastgele seçilen mobilya konumunun çakışma olasılığı
        per_bed = df.groupby(["wb", "sb", "item"])["hit"].agg(["mean", "min", "size"]).reset_index()
        for it, g in per_bed.groupby("item"):
            recs.append(dict(oda=i, Lx=Lx, Ly=Ly, alan=Lx * Ly, uygun=True, item=it,
                             p_cakisma=g["mean"].mean(),                       # rastgele yerleşim
                             guvenli_alternatif=(g["min"] == 0).mean(),         # güvenli konum var mı
                             n_yerlesim=int(g["size"].sum())))
        if len(examples) < 2 and i % 7 == 0:
            examples.append(dict(Lx=Lx, Ly=Ly, door_wall=door_wall, door_s=door_s,
                                 win_wall=win_wall, df=df.sample(min(len(df), 400), random_state=1)))
    return pd.DataFrame(recs), examples


SCENARIOS = {
    "Konut yatak odası": dict(Lx=(2.8, 3.8), Ly=(3.0, 4.6), door_wall=None, win_w=1.5,
                              bed_w=1.60, bed_l=2.00,
                              items=[("K01", 0.90, 0.58, 2.00), ("K02", 1.35, 0.58, 2.10),
                                     ("K03", 2.00, 0.62, 2.40)]),
    "Otel odası": dict(Lx=(3.3, 4.1), Ly=(4.0, 5.2), door_wall=0, win_w=2.4,
                       bed_w=1.80, bed_l=2.00,
                       items=[("O01", 1.00, 0.60, 2.20), ("O02", 1.00, 0.35, 2.00)]),
}


# ---------------------------------------------------------------------------
# ÇALIŞTIRMA
# ---------------------------------------------------------------------------
def main(n_records=40, n_rooms=600):
    rng = np.random.default_rng(SEED)
    summary = {}

    # --- 1-2. Katalog ve statik eşikler ------------------------------------
    cat = catalog_df()
    cat.to_csv(OUT / "tablo1_katalog_statik.csv", index=False, encoding="utf-8-sig")
    summary["n_mobilya"] = len(cat)
    summary["n_sallanma_modu"] = int((cat["mod"] == "Sallanma").sum())

    # Ağırlık merkezi ve sürtünme duyarlılığı
    sens = []
    for hr in HC_RATIOS:
        for mu in (MU_RANGE[0], MU_BASE, MU_RANGE[1]):
            c = catalog_df(hr, mu)
            sens.append(dict(hc_H=hr, mu=mu, n_sallanma=int((c["mod"] == "Sallanma").sum()),
                             medyan_tan_alpha=float(c["tan_alpha"].median())))
    pd.DataFrame(sens).to_csv(OUT / "tablo_duyarlilik_hc_mu.csv", index=False, encoding="utf-8-sig")

    # Statik aşılma matrisi: mobilya × DTS × kat
    stat_rows = []
    for _, m in cat.iterrows():
        thr = min(m.esik_sallanma_g, m.esik_kayma_g)
        for band, sds in SDS_BANDS.items():
            for zr, fl in zip(ZR_FLOORS, FLOOR_LABELS):
                d = pfa_demand(sds, zr)
                stat_rows.append(dict(kod=m.kod, mobilya=m.mobilya, dts=band, sds=sds, kat=fl, zr=zr,
                                      pfa_g=d, sallanma_baslar=d > m.esik_sallanma_g,
                                      kayma_baslar=d > m.esik_kayma_g, hareket_baslar=d > thr))
    stat = pd.DataFrame(stat_rows)
    stat.to_csv(OUT / "tablo_statik_asilma.csv", index=False, encoding="utf-8-sig")

    # --- 3. Dinamik analiz -------------------------------------------------
    dt = 0.001
    t, ag = simulate_ground(n_records, dt=dt, rng=rng)
    levels = np.round(np.arange(0.1, 2.01, 0.1), 2)
    alpha = cat["alpha_rad"].values; p = cat["p"].values
    frag_rows, frag_curves, amp = [], {}, {}
    for zr, fl in zip(ZR_FLOORS, FLOOR_LABELS):
        af = floor_motion(ag, dt, zr)
        amp[fl] = float(np.mean(np.abs(af).max(axis=1)))       # PGA=1 için kat/zemin oranı
        af = af / np.abs(af).max(axis=1, keepdims=True)           # PFA = 1
        over = rocking_overturn(alpha, p, af, levels, dt)          # (I, L, n)
        k = over.sum(axis=2)
        for i, m in cat.iterrows():
            med, beta = fit_lognormal(levels, k[i], n_records)
            frag_rows.append(dict(kod=m.kod, mobilya=m.mobilya, kat=fl, zr=zr,
                                  tan_alpha=m.tan_alpha, medyan_pfa_g=med, beta=beta,
                                  dinamik_statik_orani=med / m.tan_alpha if med == med else np.nan,
                                  devrilme_orani_max=k[i].max() / n_records))
            frag_curves[(m.kod, fl)] = (k[i] / n_records).tolist()
    frag = pd.DataFrame(frag_rows)
    frag.to_csv(OUT / "tablo2_kirilganlik.csv", index=False, encoding="utf-8-sig")
    summary["kat_ivme_buyutmesi_simulasyon"] = amp
    summary["kat_ivme_buyutmesi_formul"] = {fl: 1 + 2 * zr for zr, fl in zip(ZR_FLOORS, FLOOR_LABELS)}
    json.dump({f"{k_[0]}|{k_[1]}": v for k_, v in frag_curves.items()},
              open(OUT / "kirilganlik_noktalari.json", "w", encoding="utf-8"), ensure_ascii=False)

    # Zaman adımı yakınsama kontrolü: kırılganlık medyanları dt ve dt/2 ile
    t2, ag2 = simulate_ground(n_records, dt=dt / 2, rng=np.random.default_rng(SEED + 1))
    af2 = floor_motion(ag2, dt / 2, 0.8); af2 /= np.abs(af2).max(axis=1, keepdims=True)
    sel = cat.index[cat.kod.isin(["K01", "K03", "K05", "K08"])].values
    conv = []
    for arr, d_ in [(af2[:, ::2], dt), (af2, dt / 2)]:
        kk = rocking_overturn(alpha[sel], p[sel], arr, levels, d_).sum(axis=2)
        conv.append([fit_lognormal(levels, kk[i], n_records)[0] for i in range(len(sel))])
    conv = np.array(conv)
    summary["dt_yakinsama_medyan_max_bagil_fark"] = float(np.nanmax(np.abs(conv[0] - conv[1]) / conv[1]))
    summary["dt_yakinsama_medyanlar"] = {cat.kod[sel[i]]: [float(conv[0, i]), float(conv[1, i])] for i in range(len(sel))}

    # Devrilme olasılığı: mobilya × DTS × kat
    risk_rows = []
    for _, f in frag.iterrows():
        for band, sds in SDS_BANDS.items():
            d = pfa_demand(sds, f.zr)
            P = 0.0 if not f.medyan_pfa_g == f.medyan_pfa_g else norm.cdf(np.log(d / f.medyan_pfa_g) / f.beta)
            risk_rows.append(dict(kod=f.kod, mobilya=f.mobilya, kat=f.kat, zr=f.zr, dts=band, sds=sds,
                                  pfa_g=d, P_devrilme=P))
    risk = pd.DataFrame(risk_rows)
    risk.to_csv(OUT / "tablo3_devrilme_olasiligi.csv", index=False, encoding="utf-8-sig")

    # --- 4. Mekânsal analiz -----------------------------------------------
    lay_all = []
    examples_all = {}
    for scn_name, scn in SCENARIOS.items():
        df, ex = monte_carlo_layouts(scn, n_rooms, rng)
        df["senaryo"] = scn_name
        lay_all.append(df); examples_all[scn_name] = ex
    lay = pd.concat(lay_all, ignore_index=True)
    lay.to_csv(OUT / "tablo4_yerlesim_montecarlo.csv", index=False, encoding="utf-8-sig")

    # --- Şekiller ---------------------------------------------------------
    fig_model()
    fig_static_map(cat)
    fig_fragility(frag, frag_curves, levels)
    fig_risk_heatmap(risk, cat)
    fig_layout(lay, examples_all)
    json.dump(summary, open(OUT / "ozet.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    return cat, stat, frag, risk, lay, summary


# ---------------------------------------------------------------------------
# ŞEKİLLER
# ---------------------------------------------------------------------------
INK = "#1f2a36"; C1 = "#2f6b9a"; C2 = "#c8553d"; C3 = "#7a9e7e"; GRAY = "#8a8f96"
from matplotlib.ticker import FuncFormatter
DEC = "."  # TDAD: ondalık ayırıcı nokta
_TR = FuncFormatter(lambda v, _: (f"{v:g}").replace(".", DEC))


def tr_axis(*axes):
    for ax in axes:
        ax.xaxis.set_major_formatter(_TR); ax.yaxis.set_major_formatter(_TR)


def fig_model():
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.2), gridspec_kw=dict(width_ratios=[1, 1.35]))
    ax = axes[0]
    D, H = 0.6, 2.0
    ax.add_patch(Rectangle((0, 0), D, H, fc="#e9eef3", ec=INK, lw=1.2))
    ax.plot([-0.4, 1.4], [0, 0], color=INK, lw=1.2)
    for x in np.arange(-0.4, 1.4, 0.08):
        ax.plot([x, x - 0.06], [0, -0.06], color=INK, lw=0.6)
    ax.plot(D / 2, H / 2, "o", color=C2, ms=5)
    ax.plot([D, D / 2], [0, H / 2], "--", color=C2, lw=1)
    ax.plot([D, D], [0, 0.75], ":", color=C2, lw=0.9)
    ax.text(D / 2 + 0.05, H / 2 + 0.06, "AM", color=C2)
    ax.text(D * 0.58, H * 0.36, "R", color=C2, ha="right")
    ax.add_patch(Arc((D, 0), 1.1, 1.1, theta1=90, theta2=90 + np.degrees(np.arctan(D / H)), color=C2, lw=1))
    ax.text(D - 0.03, 0.66, "α", color=C2, ha="right", fontsize=9)
    ax.annotate("", xy=(0, -0.22), xytext=(D, -0.22), arrowprops=dict(arrowstyle="<->", color=INK, lw=0.8))
    ax.text(D / 2, -0.38, "D = 2b", ha="center")
    ax.annotate("", xy=(-0.18, 0), xytext=(-0.18, H / 2), arrowprops=dict(arrowstyle="<->", color=INK, lw=0.8))
    ax.text(-0.22, H / 4, "$h_c$", ha="right", va="center")
    ax.annotate("", xy=(1.3, 0.25), xytext=(0.85, 0.25), arrowprops=dict(arrowstyle="->", color=C1, lw=1.4))
    ax.text(1.08, 0.36, "$\\ddot{u}_f(t)$", color=C1, ha="center")
    ax.text(0.95, 1.55, "tan α = b / $h_c$\nR = √(b² + $h_c^2$)\np = √(3g / 4R)", fontsize=7.5, color=INK)
    ax.set_xlim(-0.6, 1.9); ax.set_ylim(-0.5, 2.3); ax.set_aspect("equal"); ax.axis("off")
    ax.set_title("(a) Rijit blok modeli", loc="left")

    ax = axes[1]
    ax.plot([-0.2, 3.5], [0, 0], color=INK, lw=1.2)
    ax.plot([0, 0], [0, 2.3], color=INK, lw=2.2)
    ax.add_patch(Rectangle((2.0, 0.0), 1.35, 0.45, fc=C3, ec=INK, lw=0.8, alpha=0.55, zorder=1))
    ax.add_patch(Rectangle((0, 0), 0.6, 2.0, fc="#e9eef3", ec=INK, lw=1.1, zorder=2))
    ax.add_patch(Rectangle((0.6, 0), 2.0, 0.6, fc="none", ec=C2, lw=1.1, ls="--", zorder=3))
    ax.annotate("", xy=(2.55, 0.68), xytext=(0.62, 2.0),
                arrowprops=dict(arrowstyle="->", color=C2, lw=1, connectionstyle="arc3,rad=-0.35"))
    ax.annotate("", xy=(0.6, -0.25), xytext=(2.6, -0.25), arrowprops=dict(arrowstyle="<->", color=C2, lw=0.9))
    ax.text(1.6, -0.45, "devrilme etki derinliği ≈ H", ha="center", color=C2)
    ax.text(2.95, 0.12, "yatak", ha="center", fontsize=8)
    ax.text(1.35, 0.25, "devrilmiş konum", ha="center", fontsize=7, color=C2)
    ax.text(0.05, 2.15, "duvar", fontsize=8)
    ax.text(0.3, 1.0, "mobilya", rotation=90, ha="center", va="center", fontsize=7.5)
    ax.set_xlim(-0.3, 3.6); ax.set_ylim(-0.6, 2.4); ax.set_aspect("equal"); ax.axis("off")
    ax.set_title("(b) Devrilme etki alanı (kesit)", loc="left")
    fig.tight_layout()
    fig.savefig(OUT / "sekil1_model.png", bbox_inches="tight"); plt.close(fig)


def fig_static_map(cat):
    fig, ax = plt.subplots(figsize=(7.0, 4.0))
    sds = np.linspace(0.1, 2.0, 200)
    styles = [(0.0, "-", C1), (0.4, "--", C3), (0.8, "-.", C2)]
    for zr, ls, col in styles:
        lab = {0.0: "zemin kat", 0.4: "orta kat ($z/H_b$=0.4)", 0.8: "en üst kat ($z/H_b$=0.8)"}[zr]
        ax.plot(sds, 1 / pfa_demand(sds, zr), ls=ls, color=col, lw=1.6,
                label=f"Kritik narinlik H/D, {lab}")
    for x0, x1, lab in [(0, 0.33, "DTS-4"), (0.33, 0.5, "DTS-3"), (0.5, 0.75, "DTS-2"), (0.75, 2.0, "DTS-1")]:
        ax.axvspan(x0, x1, color=GRAY, alpha=0.06 if lab in ("DTS-4", "DTS-2") else 0.0)
        ax.text((x0 + x1) / 2 if lab != "DTS-1" else 1.0, 0.15, lab, ha="center", fontsize=7.5, color=GRAY)
    srt = cat.sort_values("narinlik_HD")
    groups, cur = [], []
    for _, m in srt.iterrows():
        if cur and m.narinlik_HD - cur[0].narinlik_HD > 0.55:
            groups.append(cur); cur = []
        cur.append(m)
    groups.append(cur)
    for g in groups:
        for m in g:
            ax.plot(2.03, m.narinlik_HD, "s" if m.mekan == "Otel" else "o", color=INK, ms=3.5, clip_on=False)
            ax.axhline(m.narinlik_HD, color=INK, lw=0.3, alpha=0.2)
        ymid = np.mean([m.narinlik_HD for m in g])
        lab = ", ".join(m.kod for m in g)
        ax.text(2.08, ymid, lab, fontsize=6.3, va="center", clip_on=False)
    ax.set_xlim(0.1, 2.0); ax.set_ylim(0, 9)
    ax.set_xlabel("Kısa periyot tasarım spektral ivme katsayısı, $S_{DS}$")
    ax.set_ylabel("Mobilya narinliği, H/D")
    ax.text(1.15, 6.6, "Eğrinin üstü: statik ölçüte göre\nsallanma başlar", fontsize=8, color=INK)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.15), ncol=2, frameon=False)
    tr_axis(ax)
    fig.tight_layout()
    fig.savefig(OUT / "sekil2_statik_harita.png", bbox_inches="tight"); plt.close(fig)


def fig_fragility(frag, curves, levels):
    sel = ["K01", "K03", "K05", "K07", "K08", "O02"]
    fig, axes = plt.subplots(2, 3, figsize=(7.2, 4.6), sharex=True, sharey=True)
    xs = np.linspace(0.05, 2.0, 200)
    for ax, code in zip(axes.flat, sel):
        for fl, col, mk in [("Zemin kat", C1, "o"), ("4. kat (en üst)", C2, "s")]:
            f = frag[(frag.kod == code) & (frag.kat == fl)].iloc[0]
            ax.plot(levels, curves[(code, fl)], mk, color=col, ms=2.8, alpha=0.8)
            if f.medyan_pfa_g == f.medyan_pfa_g:
                ax.plot(xs, norm.cdf(np.log(xs / f.medyan_pfa_g) / f.beta), color=col, lw=1.3,
                        label=(f"{'Z' if fl.startswith('Zemin') else 'Ü'}: $\\theta_m$={f.medyan_pfa_g:.2f} g, β={f.beta:.2f}"))
        ta = frag[frag.kod == code].iloc[0].tan_alpha
        ax.axvline(ta, color=INK, lw=0.8, ls=":")
        name = frag[frag.kod == code].iloc[0].mobilya
        ax.set_title(f"{code} – {name}", fontsize=8, loc="left")
        ax.legend(fontsize=6.3, loc="lower right", bbox_to_anchor=(1.0, 0.07), frameon=False,
                  handlelength=1.2)
        tr_axis(ax)
    for ax in axes[1]: ax.set_xlabel("Kat ivmesi PFA (g)")
    for ax in axes[:, 0]: ax.set_ylabel("Devrilme olasılığı")
    from matplotlib.lines import Line2D
    hd = [Line2D([], [], color=C1, marker="o", ms=3, label="Z: zemin kat (simülasyon + lognormal uyum)"),
          Line2D([], [], color=C2, marker="s", ms=3, label="Ü: en üst kat döşemesi ($z/H_b$ = 0.8)"),
          Line2D([], [], color=INK, ls=":", label="statik sallanma eşiği, tan α")]
    fig.legend(handles=hd, loc="lower center", ncol=3, frameon=False, fontsize=7, bbox_to_anchor=(0.5, -0.02))
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig.savefig(OUT / "sekil3_kirilganlik.png", bbox_inches="tight"); plt.close(fig)


def fig_risk_heatmap(risk, cat):
    slender = cat[cat["mod"] == "Sallanma"].kod.tolist()
    bands = list(SDS_BANDS.keys())
    floors = ["Zemin kat", "2. kat", "4. kat (en üst)"]
    cols = [(b, f) for b in bands for f in floors]
    M = np.zeros((len(slender), len(cols)))
    for i, code in enumerate(slender):
        for j, (b, f) in enumerate(cols):
            M[i, j] = risk[(risk.kod == code) & np.isclose(risk.sds, SDS_BANDS[b]) & (risk.kat == f)].P_devrilme.iloc[0]
    fig, ax = plt.subplots(figsize=(7.2, 0.32 * len(slender) + 1.6))
    im = ax.imshow(M, cmap="Reds", vmin=0, vmax=1, aspect="auto")
    names = [f"{c} {cat.set_index('kod').loc[c, 'mobilya']}" for c in slender]
    ax.set_yticks(range(len(slender))); ax.set_yticklabels(names, fontsize=7)
    ax.set_xticks(range(len(cols)))
    ax.set_xticklabels([{"Zemin kat": "Z", "2. kat": "2", "4. kat (en üst)": "4"}[f] for b, f in cols], fontsize=7)
    for j, b in enumerate(bands):
        ax.text(j * 3 + 1, -0.9, b.replace(" (", "\n(").replace("S_DS", "$S_{DS}$"), ha="center", va="bottom", fontsize=6.5)
        if j: ax.axvline(j * 3 - 0.5, color="white", lw=2)
    for i in range(M.shape[0]):
        for j in range(M.shape[1]):
            v = M[i, j]
            ax.text(j, i, f"{v:.2f}".replace(".", DEC), ha="center", va="center", fontsize=5.6,
                    color="white" if v > 0.6 else INK)
    ax.set_xlabel("Kat (Z: zemin, 2: ikinci, 4: en üst kat döşemesi)")
    cb = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.01); cb.set_label("Devrilme olasılığı")
    cb.ax.yaxis.set_major_formatter(_TR)
    ax.spines[:].set_visible(False)
    fig.tight_layout()
    fig.savefig(OUT / "sekil4_risk_isi_haritasi.png", bbox_inches="tight"); plt.close(fig)


def fig_layout(lay, examples):
    fig = plt.figure(figsize=(7.2, 3.3))
    gs = fig.add_gridspec(1, 2, width_ratios=[1, 1.4])
    ax = fig.add_subplot(gs[0])
    # örnek oda: konut yatak odası (yatak başı sol duvarda)
    Lx, Ly = 3.2, 3.8
    ax.add_patch(Rectangle((0, 0), Lx, Ly, fc="none", ec=INK, lw=2))
    bed = wall_rect(3, 1.4, 1.6, 2.0, Lx, Ly)
    head = front_rect(3, 1.4, 1.6, 0, 0.9, Lx, Ly)
    ward = wall_rect(0, 0.10, 1.35, 0.58, Lx, Ly)
    fall = clip(front_rect(0, 0.10, 1.35, 0.58, 0.58 + 2.10, Lx, Ly), Lx, Ly)
    ward2 = wall_rect(2, 2.20, 0.90, 0.58, Lx, Ly)
    fall2 = clip(front_rect(2, 2.20, 0.90, 0.58, 0.58 + 2.0, Lx, Ly), Lx, Ly)
    def rr(r, **kw): ax.add_patch(Rectangle((r[0], r[1]), r[2] - r[0], r[3] - r[1], **kw))
    rr(bed, fc=C3, alpha=0.5, ec=INK); rr(head, fc="none", ec=INK, hatch="////", lw=0.6)
    rr(fall, fc=C2, alpha=0.20, ec=C2, ls="--")
    rr(fall2, fc=C1, alpha=0.14, ec=C1, ls="--")
    rr(ward, fc="#d5dbe1", ec=INK); rr(ward2, fc="#d5dbe1", ec=INK)
    ax.text((ward[0] + ward[2]) / 2, 0.29, "G-3", ha="center", va="center", fontsize=7)
    ax.text((ward2[0] + ward2[2]) / 2, Ly - 0.29, "G-2", ha="center", va="center", fontsize=7)
    ax.text(1.5, 2.2, "yatak", ha="center", fontsize=7)
    ax.text(0.45, 3.2, "baş-gövde\nbölgesi", ha="center", fontsize=6.3)
    ax.text(0.78, 0.95, "G-3 devrilme\nalanı (çakışma)", ha="center", fontsize=6.2, color=C2)
    ax.text(2.65, 1.75, "G-2\ndevrilme\nalanı\n(güvenli)", ha="center", fontsize=6.2, color=C1)
    ax.set_xlim(-0.1, Lx + 0.1); ax.set_ylim(-0.1, Ly + 0.1); ax.set_aspect("equal"); ax.axis("off")
    ax.set_title("(a) Örnek yerleşim (3.2 × 3.8 m)", loc="left", fontsize=8.5)

    ax = fig.add_subplot(gs[1])
    ok = lay[lay.uygun]
    bins = {"Konut yatak odası": [8, 10, 12, 14, 18], "Otel odası": [13, 16, 18, 20, 22]}
    for scn, col in [("Konut yatak odası", C1), ("Otel odası", C2)]:
        d = ok[ok.senaryo == scn].copy()
        d["alan_bin"] = pd.cut(d.alan, bins[scn])
        g = d.groupby("alan_bin", observed=True).agg(p=("p_cakisma", "mean"), s=("guvenli_alternatif", "mean"))
        x = [iv.mid for iv in g.index]
        ax.plot(x, g.p, "-o", color=col, ms=3.5, label=f"{scn}: rastgele yerleşimde çakışma")
        ax.plot(x, 1 - g.s, "--s", color=col, ms=3, alpha=0.8,
                label=f"{scn}: güvenli konum bulunamama")
    ax.set_xlabel("Oda alanı (m²)"); ax.set_ylabel("Olasılık"); ax.set_ylim(0, 1); tr_axis(ax)
    ax.legend(fontsize=6.3, frameon=False, loc="upper right")
    ax.set_title("(b) Monte Carlo yerleşim sonuçları", loc="left", fontsize=8.5)
    fig.tight_layout()
    fig.savefig(OUT / "sekil5_yerlesim.png", bbox_inches="tight"); plt.close(fig)


if __name__ == "__main__":
    import sys, time
    t0 = time.time()
    quick = "--hizli" in sys.argv
    res = main(n_records=12 if quick else 40, n_rooms=60 if quick else 600)
    print(f"Tamamlandı: {time.time() - t0:.1f} s  ->  {OUT}")
