# Serbest Duran Mobilyaların Deprem Kaynaklı Devrilme Riski


## Çalıştırma

```
pip install numpy scipy pandas matplotlib
python3 mobilya_devrilme.py          # tam analiz, yaklaşık 2 dakika
python3 mobilya_devrilme.py --hizli  # hızlı deneme (12 kayıt, 60 oda)
```

Rastgele sayı tohumu sabittir (20261011); aynı sürümlerle sonuçlar birebir yeniden üretilir.

## Çıktılar (`ciktilar/`)

| Dosya | İçerik |
| --- | --- |
| `tablo1_katalog_statik.csv` | 18 mobilya, rijit blok parametreleri, başlangıç modu (Tablo 1) |
| `tablo_duyarlilik_hc_mu.csv` | Ağırlık merkezi ve sürtünme duyarlılığı |
| `tablo_statik_asilma.csv` | Mobilya × DTS × kat statik eşik aşılması |
| `tablo2_kirilganlik.csv` | Lognormal kırılganlık parametreleri, 5 kat düzeyi (Tablo 2) |
| `kirilganlik_noktalari.json` | Simülasyondan devrilme oranları (Şekil 3 noktaları) |
| `tablo3_devrilme_olasiligi.csv` | Mobilya × DTS × kat devrilme olasılığı (Şekil 4) |
| `tablo4_yerlesim_montecarlo.csv` | Oda bazında yerleşim sonuçları (Tablo 3, Şekil 5) |
| `ozet.json`, `makale_sayilari.json` | Makalede geçen özet sayılar |
| `sekil1_model.png` … `sekil5_yerlesim.png` | Makale şekilleri (300 dpi) |

`hesaplayici/devrilme-hesaplayici.html` tek dosyalık web hesaplayıcıdır; GitHub Pages gibi bir adreste yayımlanabilir.

## Lisans

Kod ve veriler CC BY 4.0 lisanslıdır.
