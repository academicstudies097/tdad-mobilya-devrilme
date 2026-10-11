# -*- coding: utf-8 -*-
"""TDAD Word şablonuna makaleyi yerleştirir (OMML denklemler, şekiller, tablolar)."""
import re, shutil, struct, zipfile
from pathlib import Path
from xml.sax.saxutils import escape

BASE = Path(__file__).resolve().parent
SRC = BASE / "unpacked"
OUT_DIR = BASE / "build"
FIG = Path("/home/claude/tdad_mobilya/ciktilar")
OUT_DOCX = BASE / "TDAD_Mobilya_Devrilme_Makale.docx"

# ---------------------------------------------------------------- run / paragraph helpers
FONT = '<w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:cs="Arial"/>'
LANG = '<w:lang w:val="tr-TR"/>'


def rpr(b=False, i=False, sz=None, va=None, hl=False):
    x = FONT
    if b: x += '<w:b/><w:bCs/>'
    if i: x += '<w:i/><w:iCs/>'
    if sz: x += f'<w:sz w:val="{sz}"/><w:szCs w:val="{sz}"/>'
    if hl: x += '<w:highlight w:val="yellow"/>'
    if va: x += f'<w:vertAlign w:val="{va}"/>'
    return '<w:rPr>' + x + LANG + '</w:rPr>'


def run(t, **k):
    return f'<w:r>{rpr(**k)}<w:t xml:space="preserve">{escape(t)}</w:t></w:r>'


TOK = re.compile(r'(_\{[^}]*\}|\^\{[^}]*\}|\[\[[ihb]:.*?\]\])')


def runs(text, b=False, i=False, sz=None, hl=False):
    """Mini biçim dili: _{alt} ^{üst} [[i:italik]] [[h:vurgulu]] [[b:kalın]]"""
    out = []
    for part in TOK.split(text):
        if not part:
            continue
        if part.startswith('_{'):
            out.append(run(part[2:-1], b=b, i=i, sz=sz, va='subscript', hl=hl))
        elif part.startswith('^{'):
            out.append(run(part[2:-1], b=b, i=i, sz=sz, va='superscript', hl=hl))
        elif part.startswith('[[i:'):
            out.append(run(part[4:-2], b=b, i=True, sz=sz, hl=hl))
        elif part.startswith('[[h:'):
            out.append(run(part[4:-2], b=b, i=i, sz=sz, hl=True))
        elif part.startswith('[[b:'):
            out.append(run(part[4:-2], b=True, i=i, sz=sz, hl=hl))
        else:
            out.append(run(part, b=b, i=i, sz=sz, hl=hl))
    return ''.join(out)


def ppr(jc='both', keep=False, tabs='', ind='', sz=None, i=False, b=False):
    x = '<w:pPr>'
    if keep: x += '<w:keepNext/>'
    x += tabs
    x += '<w:autoSpaceDE w:val="0"/><w:autoSpaceDN w:val="0"/><w:adjustRightInd w:val="0"/>'
    x += '<w:spacing w:after="0" w:line="240" w:lineRule="auto"/>' + ind
    if jc: x += f'<w:jc w:val="{jc}"/>'
    x += rpr(b=b, i=i, sz=sz) + '</w:pPr>'
    return x


def P(text='', jc='both', b=False, i=False, sz=None, keep=False, hl=False):
    return f'<w:p>{ppr(jc, keep, sz=sz, i=i, b=b)}{runs(text, b=b, i=i, sz=sz, hl=hl) if text else ""}</w:p>'


def blank(n=1, jc='both'):
    return ''.join(P('', jc=jc) for _ in range(n))


# ---------------------------------------------------------------- OMML helpers
MF = '<w:rPr><w:rFonts w:ascii="Cambria Math" w:hAnsi="Cambria Math"/></w:rPr>'


def mr(t, plain=False):
    s = '<m:rPr><m:sty m:val="p"/></m:rPr>' if plain else ''
    return f'<m:r>{s}{MF}<m:t xml:space="preserve">{escape(t)}</m:t></m:r>'


def mf(n, d): return f'<m:f><m:num>{n}</m:num><m:den>{d}</m:den></m:f>'
def msub(e, s): return f'<m:sSub><m:e>{e}</m:e><m:sub>{s}</m:sub></m:sSub>'
def msup(e, s): return f'<m:sSup><m:e>{e}</m:e><m:sup>{s}</m:sup></m:sSup>'
def msubsup(e, b, p): return f'<m:sSubSup><m:e>{e}</m:e><m:sub>{b}</m:sub><m:sup>{p}</m:sup></m:sSubSup>'
def msqrt(e): return f'<m:rad><m:radPr><m:degHide m:val="1"/></m:radPr><m:deg/><m:e>{e}</m:e></m:rad>'
def md(e, a='(', z=')'): return f'<m:d><m:dPr><m:begChr m:val="{a}"/><m:endChr m:val="{z}"/></m:dPr><m:e>{e}</m:e></m:d>'
def mfunc(name, e): return f'<m:func><m:fName>{name}</m:fName><m:e>{e}</m:e></m:func>'
def macc(e, ch): return f'<m:acc><m:accPr><m:chr m:val="{ch}"/></m:accPr><m:e>{e}</m:e></m:acc>'


DDOT, DOT = '̈', '̇'
SEP = f'<m:r><m:rPr><m:nor/></m:rPr>{MF}<m:t xml:space="preserve">,      </m:t></m:r>'


def ud(sub_): return msub(macc(mr('u'), DDOT), mr(sub_))


def eq_para(omml, num):
    tabs = '<w:tabs><w:tab w:val="center" w:pos="4560"/><w:tab w:val="right" w:pos="9120"/></w:tabs>'
    return (f'<w:p>{ppr(jc=None, tabs=tabs)}<w:r>{rpr()}<w:tab/></w:r><m:oMath>{omml}</m:oMath>'
            f'<w:r>{rpr()}<w:tab/><w:t>({num})</w:t></w:r></w:p>')


ga = lambda s: msub(mr('ω'), mr(s))
E = {}
E[1] = (mfunc(mr('tan', True), mr('α')) + mr('=') + mf(mr('b'), msub(mr('h'), mr('c'))) + SEP +
        mr('R=') + msqrt(msup(mr('b'), mr('2')) + mr('+') + msubsup(mr('h'), mr('c'), mr('2'))) + SEP +
        mr('p=') + msqrt(mf(mr('3g'), mr('4R'))))
E[2] = (mr('PFA', True) + md(mr('z')) + mr('=0.4') + msub(mr('S'), mr('DS', True)) +
        md(mr('1+2') + mf(mr('z'), msub(mr('H'), mr('b')))))
num1 = msubsup(mr('ω'), mr('g'), mr('4')) + mr('+4') + msubsup(mr('ζ'), mr('g'), mr('2')) + msubsup(mr('ω'), mr('g'), mr('2')) + msup(mr('ω'), mr('2'))
den1 = msup(md(msubsup(mr('ω'), mr('g'), mr('2')) + mr('−') + msup(mr('ω'), mr('2'))), mr('2')) + mr('+4') + msubsup(mr('ζ'), mr('g'), mr('2')) + msubsup(mr('ω'), mr('g'), mr('2')) + msup(mr('ω'), mr('2'))
den2 = msup(md(msubsup(mr('ω'), mr('f'), mr('2')) + mr('−') + msup(mr('ω'), mr('2'))), mr('2')) + mr('+4') + msubsup(mr('ζ'), mr('f'), mr('2')) + msubsup(mr('ω'), mr('f'), mr('2')) + msup(mr('ω'), mr('2'))
E[3] = mr('S') + md(mr('ω')) + mr('=') + msub(mr('S'), mr('0')) + mf(num1, den1) + mr('·') + mf(msup(mr('ω'), mr('4')), den2)
qdd, qd = macc(mr('q'), DDOT), macc(mr('q'), DOT)
E[4] = (ud('f') + md(mr('z,t')) + mr('=') + ud('g') + md(mr('t')) + mr('+Γφ') + md(mr('z')) + qdd + md(mr('t')) + SEP +
        qdd + mr('+2ζ') + msub(mr('ω'), mr('1')) + qd + mr('+') + msubsup(mr('ω'), mr('1'), mr('2')) + mr('q=−') + ud('g') + md(mr('t')))
arg = md(mr('α') + mfunc(mr('sgn', True), mr('θ')) + mr('−θ'))
E[5] = (macc(mr('θ'), DDOT) + mr('=−') + msup(mr('p'), mr('2')) +
        md(mfunc(mr('sin', True), arg) + mr('+') + mf(ud('f'), mr('g')) + mfunc(mr('cos', True), arg), '[', ']') + SEP +
        mr('r=1−') + mf(mr('3'), mr('2')) + mfunc(msup(mr('sin', True), mr('2')), mr('α')))
E[6] = (mr('P') + md(mr('devrilme', True) + mr('∣') + mr('PFA', True)) + mr('=Φ') +
        md(mf(mfunc(mr('ln', True), md(mr('PFA', True) + mr('/') + msub(mr('θ'), mr('m')))), mr('β'))))
E[7] = msub(mr('D'), mr('min', True)) + mr('=2') + msub(mr('h'), mr('c')) + mr('·') + mr('PFA', True)

# ---------------------------------------------------------------- images
IMG_RELS, IMG_COUNTER = [], [100]


def png_size(path):
    with open(path, 'rb') as fh:
        fh.read(16)
        return struct.unpack('>II', fh.read(8))


def figure(fname, width_in, cap_tr, cap_en):
    IMG_COUNTER[0] += 1
    n = IMG_COUNTER[0]
    rid = f'rId{n}'
    target = f'media/fig_{n}.png'
    IMG_RELS.append((rid, target, FIG / fname))
    w, h = png_size(FIG / fname)
    cx = int(width_in * 914400); cy = int(cx * h / w)
    draw = (f'<w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0"><wp:extent cx="{cx}" cy="{cy}"/>'
            f'<wp:effectExtent l="0" t="0" r="0" b="0"/><wp:docPr id="{n}" name="Şekil {n}"/>'
            '<wp:cNvGraphicFramePr><a:graphicFrameLocks xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" noChangeAspect="1"/></wp:cNvGraphicFramePr>'
            '<a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
            f'<pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:nvPicPr><pic:cNvPr id="{n}" name="{fname}"/><pic:cNvPicPr/></pic:nvPicPr>'
            f'<pic:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
            f'<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>'
            '</pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing>')
    img = f'<w:p>{ppr("center", keep=True)}<w:r><w:rPr>{FONT}<w:noProof/>{LANG}</w:rPr>{draw}</w:r></w:p>'
    return (blank(2) + img + P(cap_tr, 'center', i=True, sz=20, keep=True) +
            P(cap_en, 'center', i=True, sz=20) + blank(2))


# ---------------------------------------------------------------- tables
def cell(text, w, jc='center'):
    tc = (f'<w:tc><w:tcPr><w:tcW w:w="{w}" w:type="dxa"/><w:tcBorders>'
          '<w:top w:val="single" w:sz="4" w:space="0" w:color="999999"/>'
          '<w:bottom w:val="single" w:sz="4" w:space="0" w:color="999999"/></w:tcBorders>'
          '<w:shd w:val="clear" w:color="auto" w:fill="auto"/><w:vAlign w:val="center"/></w:tcPr>')
    return tc + f'<w:p>{ppr(jc)}{runs(text)}</w:p></w:tc>'


def table(header, rows, widths, cap_tr, cap_en, left_cols=()):
    total = sum(widths)
    x = (f'<w:tbl><w:tblPr><w:tblW w:w="{total}" w:type="dxa"/><w:jc w:val="center"/>'
         '<w:tblLayout w:type="fixed"/><w:tblCellMar><w:left w:w="57" w:type="dxa"/><w:right w:w="57" w:type="dxa"/></w:tblCellMar>'
         '<w:tblLook w:val="0000" w:firstRow="0" w:lastRow="0" w:firstColumn="0" w:lastColumn="0" w:noHBand="0" w:noVBand="0"/></w:tblPr><w:tblGrid>')
    x += ''.join(f'<w:gridCol w:w="{w}"/>' for w in widths) + '</w:tblGrid>'
    def tr(cells, head=False):
        s = '<w:tr><w:trPr>' + ('<w:tblHeader/>' if head else '') + '<w:trHeight w:val="340"/><w:jc w:val="center"/></w:trPr>'
        for k, (t, w) in enumerate(zip(cells, widths)):
            s += cell(t, w, 'left' if (k in left_cols and not head) else 'center')
        return s + '</w:tr>'
    x += tr(header, True) + ''.join(tr(r) for r in rows) + '</w:tbl>'
    return (blank(2) + P(cap_tr, 'center', i=True, sz=20, keep=True) +
            P(cap_en, 'center', i=True, sz=20, keep=True) + x + blank(2))


# ---------------------------------------------------------------- content
H1 = lambda t: P(t, b=True)            # ana başlık
H2 = lambda t: P(t)                    # 1. kademe alt başlık (düz, sözcük başları büyük)

body = []
add = body.append

# --- Türkçe başlık bloğu
add(P('Konut ve Otel İç Mekânlarında Serbest Duran Mobilyaların Deprem Kaynaklı Devrilme Riski: Rijit Blok Dinamiği ve Yerleşim Analizine Dayalı Hesaplamalı Bir Değerlendirme', 'center', b=True))
add(blank(1, 'center'))
add(P('Ayşan Ilgın Polat^{1,*}, Hakan Bal^{1} ve Ferhat Koyuncu^{1}', 'center', sz=20))
add(blank(1, 'center'))
add(P('^{1} Antalya Bilim Üniversitesi, Güzel Sanatlar ve Mimarlık Fakültesi, İç Mimarlık ve Çevre Tasarımı Bölümü, Döşemealtı 07190 Antalya', 'center', sz=18))
add(P('* Sorumlu Yazar, Eposta: aysanilgin@gmail.com', 'center', i=True, sz=18))
add(P('ORCID: [[h:0000-0000-xxxx-xxx1]], [[h:0000-0000-xxxx-xxx2]], [[h:0000-0000-xxxx-xxx3]]', 'center', sz=18))
add(blank())
add(P('ÖZET', b=True)); add(blank())
OZET = ("Deprem sırasında devrilen mobilyalar, taşıyıcı sistemi ayakta kalan binalarda da önemli bir yaralanma kaynağıdır. "
        "Bu çalışmada konut ve otel iç mekânlarında yaygın 18 serbest duran mobilyanın devrilme riski, rijit blok dinamiği ile yerleşim analizini birleştiren açık kaynaklı bir hesaplamalı çerçeveyle değerlendirilmiştir. "
        "Statik eşikler TBDY 2018 deprem tasarım sınıflarına karşılık gelen kat ivmesi talepleriyle karşılaştırılmış, Housner denklemi 40 stokastik kayıt altında çözülerek kırılganlık eğrileri elde edilmiştir. "
        "S_{DS} = 1.00 düzeyinde 12 narin mobilyanın tamamı her katta statik eşiği aşmaktadır. "
        "Dinamik devrilme ivmeleri statik eşiğin 1.8–4.0 katı olsa da aynı düzeyde en üst kattaki 12 mobilyanın 11'inde devrilme olasılığı 0.5'i geçmektedir. "
        "Rastgele yatak odası yerleşimlerinin %43.4'ünde devrilme alanı yatağın baş-gövde bölgesine ulaşmaktadır.")
add(P(OZET)); add(blank())
add(P('Anahtar Kelimeler: ', b=True))
add(P('Yapısal olmayan elemanlar, Mobilya devrilmesi, Rijit blok sallanması, Kırılganlık eğrisi, İç mekân yerleşimi'))
add(blank())
add(P('Öne Çıkanlar:', b=True))
for t in ['* Narin mobilyalar S_{DS} = 1.00 düzeyinde her katta statik sallanma eşiğini aşmaktadır',
          '* Dinamik devrilme ivmesi statik eşiğin 1.8–4.0 katı olsa da üst katlarda risk yüksektir',
          '* Rastgele yatak odası yerleşimlerinin %43\'ünde devrilme alanı baş bölgesine ulaşmaktadır']:
    add(P(t))
add(blank())

# --- İngilizce başlık bloğu
add(P('Earthquake-Induced Overturning Risk of Freestanding Furniture in Residential and Hotel Interiors: A Computational Assessment Based on Rigid-Block Dynamics and Layout Analysis', 'center', b=True))
add(blank(1, 'center'))
add(P('Ayşan Ilgın Polat^{1,*}, Hakan Bal^{1} and Ferhat Koyuncu^{1}', 'center', sz=20))
add(blank(1, 'center'))
add(P('^{1} Antalya Bilim University, Faculty of Fine Arts and Architecture, Department of Interior Architecture and Environmental Design, Dosemealti 07190 Antalya', 'center', sz=18))
add(P('* Corresponding Author, Email: aysanilgin@gmail.com', 'center', i=True, sz=18))
add(P('ORCID: [[h:0000-0000-xxxx-xxx1]], [[h:0000-0000-xxxx-xxx2]], [[h:0000-0000-xxxx-xxx3]]', 'center', sz=18))
add(blank())
add(P('ABSTRACT', b=True)); add(blank())
ABS = ("Overturning furniture causes many earthquake injuries even when buildings survive. "
       "This study assesses the overturning risk of 18 freestanding furniture types in residential and hotel interiors with an open-source framework coupling rigid-block dynamics and layout analysis. "
       "Static thresholds were compared with floor acceleration demands for the TBDY 2018 seismic design classes, and fragility curves were derived from Housner's equation under 40 stochastic records. "
       "At S_{DS} = 1.00, all 12 slender items exceed the static threshold on every floor. "
       "Dynamic overturning accelerations are 1.8–4.0 times the static threshold, yet 11 of the 12 items on the top floor still exceed an overturning probability of 0.5. "
       "In 43.4% of random bedroom layouts, the fall zone reaches the head-torso zone of the bed.")
add(P(ABS)); add(blank())
add(P('Key Words: ', b=True))
add(P('Nonstructural components, Furniture overturning, Rigid-block rocking, Fragility curve, Interior layout'))
add(blank())
add(P('Highlights:', b=True))
for t in ['* Slender furniture exceeds the static rocking threshold on every floor at S_{DS} = 1.00',
          '* Dynamic overturning accelerations are 1.8–4.0 times the static threshold',
          '* In 43% of random bedroom layouts the fall zone reaches the head zone of the bed']:
    add(P(t))
add(blank(2))


def section(title, paras):
    add(H1(title)); add(blank())
    for k, p in enumerate(paras):
        add(p if p.startswith('<w:') else P(p))
        if not (p.startswith('<w:') or p.startswith('AS') or p.startswith('* ')) or p.startswith('AS3') or p.startswith('* Otel'):
            add(blank())
        elif p.startswith('<w:'):
            pass


def sub(title):
    return P(title)


# ---------------------------------------------------------------- 1. GİRİŞ
add(H1('1. GİRİŞ')); add(blank())
intro = [
 "Türkiye, aktif fay sistemleri nedeniyle yüksek deprem tehlikesine sahiptir. 6 Şubat 2023 Kahramanmaraş depremlerinde ilk ana şokun yatay bileşende 2 g'yi aşan en büyük yer ivmeleri ürettiği bildirilmiştir (Akinci ve diğ. 2025). Deprem güvenliği tartışmaları çoğunlukla taşıyıcı sisteme odaklansa da kullanıcıların sarsıntıyı yaşadığı ortam iç mekândır. Asma tavanlar, bölme duvarlar, tesisat ve mobilya gibi yapısal olmayan elemanlar hem can güvenliğini hem de tahliyeyi doğrudan etkiler ve son yıllarda performansa dayalı tasarım kapsamında ayrıca ele alınmaktadır (FEMA 2012, Filiatrault ve diğ. 2021).",
 "Mobilya kaynaklı yaralanmaların büyüklüğü saha verileriyle ortaya konmuştur. Tokyo İtfaiyesi, son depremlerdeki yaralanmaların yaklaşık %30–50'sinin devrilen, düşen veya kayan mobilyadan kaynaklandığını bildirmektedir (TFD 2017). 2003 Kuzey Miyagi depremi üzerine yapılan bir saha çalışmasında yaralanmaların yarısından fazlası devrilen mobilya ve düşen nesnelerle ilişkilendirilmiştir (Sato ve diğ. 2006). Bu bulgular, binanın göçmediği sarsıntılarda bile tefrişin bağımsız bir yaralanma kaynağı olduğunu göstermektedir.",
 "Türkiye'deki iç mimarlık ve mobilya tasarımı literatürü bu soruna büyük ölçüde nitel ve tasarım odaklı yaklaşmıştır. Konut iç mekânlarının güvenlik analizi (Demirbas 2008), konutlarda yapısal olmayan elemanların yarattığı riskler (Ertas Besir ve Dereci 2021), okul mobilyası önerileri (Kaya ve Sahan 2023), güvenli sığınma alanı sunan mobilya (Buker ve diğ. 2023), devrilmeyi önleyici ürünler (Ozcan 2023), dönüşebilen çift amaçlı mobilyalar (Kurtulus ve Mus Ozmen 2025), risk matrisiyle önceliklendirilen güvenli tefriş önerileri (Uzer ve Uc 2026) ve geçici barınma mekânları için uyarlanabilir mobilya ölçütleri (Yolcu 2026) bu çalışmalar arasındadır. Uluslararası literatürde de hayat kurtaran mobilya stratejileri benzer biçimde tasarım düzeyinde ele alınmıştır (Pietroni ve diğ. 2021). Ancak bu çalışmalar, bir mobilyanın hangi yer hareketi düzeyinde, hangi katta ve odanın neresinde tehlikeli hâle geldiğini sayısal olarak belirlememektedir.",
 "Deprem mühendisliğinde ise serbest duran rijit blokların davranışı uzun süredir incelenmektedir. Housner (1963) sallanma hareketinin temel denklemini ve büyük blokların görece kararlı olduğunu gösteren ölçek etkisini ortaya koymuştur. Sonraki çalışmalar sallanma tepkisini (Yim ve diğ. 1980, Ishiyama 1982), kayma ve sallanma başlangıç modlarını (Shenton 1996), yakın fay atımlarının etkisini (Makris ve Roussos 2000, Zhang ve Makris 2001) ve benzerlik yasalarını (Dimitrakopoulos ve DeJong 2012) incelemiştir. Devrilme kırılganlıkları sayısal ve deneysel olarak (Purvance ve diğ. 2008), laboratuvar ekipmanı için sarsma tablası deneyleriyle (Konstantinidis ve Makris 2009) ve kayma için olasılıksal olarak (Lopez Garcia ve Soong 2003) türetilmiştir. Son çalışmalar, mobilya devrilme kırılganlıklarını bina tepkisi ve tehlike eğrileriyle birleştirerek yıllık devrilme sıklığını tahmin etmektedir (Suzuki ve diğ. 2024). Kat ivmelerinin bina yüksekliği boyunca arttığı da bilinmektedir (Miranda ve Taghavi 2005, ASCE 2017). Ne var ki bu bilgi birikimi iç mimari kararlara, yani hangi mobilyanın hangi katta ve odanın neresinde kullanılacağına nadiren aktarılmakta, TBDY 2018'in tehlike sınıflarıyla da ifade edilmemektedir.",
]
for p in intro:
    add(P(p)); add(blank())
add(P("Bu çalışmanın amacı, konut ve otel iç mekânlarındaki serbest duran mobilyaların deprem kaynaklı devrilme riskini rijit blok dinamiği, yönetmelik tabanlı kat ivmesi talebi ve iç mekân yerleşim analizini birleştirerek nicel olarak değerlendirmektir. Çalışma üç araştırma sorusuna (AS) yanıt aramaktadır:"))
add(blank())
add(P("AS1) Temsilî mobilyalar hangi deprem tasarım sınıfında ve hangi katta statik olarak harekete geçmektedir?"))
add(P("AS2) Dinamik davranış (ölçek etkisi ve katın filtreleme etkisi) bu tabloyu nasıl değiştirmekte ve devrilme olasılıkları ne düzeydedir?"))
add(P("AS3) Tipik yatak odası ve otel odası yerleşimlerinde devrilme etki alanı uyuyan kullanıcıyla ne sıklıkla çakışmakta ve yerleşim kararlarıyla bu risk ne ölçüde azaltılabilmektedir?"))
add(blank())
add(P("Çalışmanın katkısı üç yönlüdür. Birincisi, iç mimari ölçekte mobilya geometrisi, deprem tehlikesi ve yerleşimi aynı çerçevede ele alan bütünleşik bir değerlendirme sunmaktadır. İkincisi, sonuçlar TBDY 2018 deprem tasarım sınıfları ve kat düzeyi üzerinden ifade edilerek tasarımcının doğrudan kullanabileceği biçime getirilmiştir. Üçüncüsü, analiz kodu ve iç mimarlar için geliştirilen web tabanlı bir hesaplayıcı açık erişimle paylaşılmaktadır. Mobilyanın narinlik oranı temel tasarımda bir oran-orantı kararı olarak ele alınır (Ching 2015); bu çalışma aynı oranın bir deprem güvenliği parametresi olduğunu da göstermektedir."))
add(blank())

# ---------------------------------------------------------------- 2. YÖNTEM
add(H1('2. YÖNTEM')); add(blank())
add(H2('2.1) Araştırma Tasarımı')); add(blank())
add(P("Çalışma üç modülden oluşan hesaplamalı bir tasarıma dayanmaktadır: (i) mobilyaların rijit blok olarak modellenmesi ve statik hareket başlangıcı ölçütlerinin yönetmelik tabanlı kat ivmesi talebiyle karşılaştırılması, (ii) stokastik kat hareketleri altında dinamik sallanma analizi ve kırılganlık eğrilerinin türetilmesi, (iii) devrilme etki alanının oda yerleşimleri içinde Monte Carlo yöntemiyle incelenmesi. Rijit blok modeli ve devrilme etki alanı tanımı Şekil 1'de gösterilmiştir. Tüm analizler Python (NumPy, SciPy, pandas, Matplotlib) ile yazılmış tek bir betikte, sabit rastgele sayı tohumuyla (20261011) yeniden üretilebilir biçimde yürütülmüştür."))
add(figure('sekil1_model.png', 5.6,
           'Şekil 1: a) Serbest duran mobilyanın rijit blok modeli (AM: ağırlık merkezi), b) Öne devrilen mobilyanın etki alanı (kesit)',
           'Figure 1: a) Rigid-block model of freestanding furniture (AM: centre of mass), b) Fall zone of furniture overturning forward (section)'))
add(H2('2.2) Mobilya Kataloğu')); add(blank())
add(P("Konut (14) ve otel odası (4) iç mekânlarında yaygın 18 serbest duran mobilya tipi seçilmiştir (Tablo 1). K kodları konut, O kodları otel mobilyalarını göstermektedir. Boyutlar, yaygın ürün aralıkları ile ergonomi ve tasarım başvuru kaynakları (Panero ve Zelnik 1979) dikkate alınarak temsilî değerler olarak belirlenmiştir; W genişliği, D derinliği, H yüksekliği göstermektedir. Mobilyalar homojen kütleli dikdörtgen bloklar olarak kabul edilmiş ve ağırlık merkezi yüksekliği h_{c} = H/2 alınmıştır. İçerik yüklemesinin etkisi h_{c}/H = 0.40 (alt-ağır), 0.50 (homojen) ve 0.60 (üst-ağır) senaryolarıyla duyarlılık analizinde incelenmiştir. Devrilme, en kritik doğrultu olan derinlik doğrultusunda (b = D/2) ele alınmıştır."))
T1 = [
 ("K01", "Gardırop, 2 kapaklı", "0.90 × 0.58 × 2.00", "3.45", "0.290", "1.04", "Sallanma"),
 ("K02", "Gardırop, 3 kapaklı", "1.35 × 0.58 × 2.10", "3.62", "0.276", "1.09", "Sallanma"),
 ("K03", "Gardırop, sürgülü 4 kapaklı", "2.00 × 0.62 × 2.40", "3.87", "0.258", "1.24", "Sallanma"),
 ("K04", "Kitaplık, dar", "0.40 × 0.30 × 1.80", "6.00", "0.167", "0.91", "Sallanma"),
 ("K05", "Kitaplık, geniş", "0.80 × 0.30 × 2.00", "6.67", "0.150", "1.01", "Sallanma"),
 ("K06", "Açık raf ünitesi", "0.80 × 0.38 × 1.50", "3.95", "0.253", "0.77", "Sallanma"),
 ("K07", "Vitrin (camlı dolap)", "0.80 × 0.40 × 1.90", "4.75", "0.211", "0.97", "Sallanma"),
 ("K08", "Mutfak boy dolabı", "0.60 × 0.60 × 2.10", "3.50", "0.286", "1.09", "Sallanma"),
 ("K09", "Buzdolabı (kombi)", "0.70 × 0.70 × 1.85", "2.64", "0.378", "0.99", "Sallanma"),
 ("K10", "Ayakkabılık / portmanto", "0.80 × 0.35 × 1.20", "3.43", "0.292", "0.62", "Sallanma"),
 ("K11", "Şifonyer", "1.00 × 0.45 × 1.10", "2.44", "0.409", "0.59", "Kayma"),
 ("K12", "Çamaşır makinesi", "0.60 × 0.60 × 0.85", "1.42", "0.706", "0.52", "Kayma"),
 ("K13", "Komodin", "0.45 × 0.40 × 0.50", "1.25", "0.800", "0.32", "Kayma"),
 ("K14", "TV ünitesi (alçak)", "1.80 × 0.45 × 0.50", "1.11", "0.900", "0.34", "Kayma"),
 ("O01", "Otel gardırobu", "1.00 × 0.60 × 2.20", "3.67", "0.273", "1.14", "Sallanma"),
 ("O02", "Otel bölücü raf", "1.00 × 0.35 × 2.00", "5.71", "0.175", "1.02", "Sallanma"),
 ("O03", "Otel bagaj-minibar ünitesi", "0.90 × 0.50 × 0.90", "1.80", "0.556", "0.51", "Kayma"),
 ("O04", "Otel çalışma konsolu", "1.20 × 0.50 × 0.78", "1.56", "0.641", "0.46", "Kayma"),
]
add(table(["Kod", "Mobilya", "W × D × H (m)", "H/D", "tan α", "R (m)", "Başlangıç modu"], T1,
          [700, 2750, 2000, 800, 900, 800, 1150],
          'Tablo 1: Mobilya kataloğu ve rijit blok parametreleri (μ = 0.40)',
          'Table 1: Furniture catalogue and rigid-block parameters (μ = 0.40)', left_cols=(1,)))
add(H2('2.3) Statik Hareket Başlangıcı Ölçütleri')); add(blank())
add(P("Yarı genişliği b (m) ve ağırlık merkezi yüksekliği h_{c} (m) olan bir blok için narinlik açısı α (rad), ağırlık merkezinin dönme köşesine uzaklığı R (m) ve frekans parametresi p (rad/s) Eşitlik 1 ile tanımlanır (Housner 1963):"))
add(blank()); add(eq_para(E[1], 1)); add(blank())
add(P("Burada g yerçekimi ivmesidir (9.81 m/s^{2}). Kat ivmesi g·tan α değerini aştığında sallanma, μ·g değerini aştığında kayma başlar. Hangi modun önce başlayacağı μ ile tan α'nın karşılaştırılmasıyla belirlenir: μ > tan α ise sallanma, μ < tan α ise kayma baskındır (Shenton 1996). Mobilya ile döşeme kaplaması arasındaki sürtünme katsayısı için μ = 0.40 temel değer, 0.25–0.60 aralığı ise duyarlılık aralığı olarak varsayılmıştır."))
add(blank())
add(H2('2.4) Kat İvmesi Talebi')); add(blank())
add(P("Döşeme kotu z olan bir kattaki tasarım düzeyi kat ivmesi (PFA, g cinsinden), yapısal olmayan elemanlar için yaygın kullanılan yükseklikle doğrusal büyütme ifadesiyle hesaplanmıştır (ASCE 2017):"))
add(blank()); add(eq_para(E[2], 2)); add(blank())
add(P("Burada S_{DS} kısa periyot tasarım spektral ivme katsayısı (boyutsuz), z döşeme kotu (m) ve H_{b} bina yüksekliğidir (m). S_{DS} değerleri TBDY 2018'deki deprem tasarım sınıflarını (DTS) temsil edecek biçimde 0.25 (DTS-4), 0.42 (DTS-3), 0.63 (DTS-2), 1.00 (DTS-1) ve 1.50 (DTS-1, yüksek tehlike) olarak seçilmiştir (AFAD 2018, TBDY 2018). Temsilî bina, kat yüksekliği 3 m olan 5 katlı (H_{b} = 15 m) bir betonarme konuttur; mobilyaların bulunduğu döşemeler z/H_{b} = 0, 0.2, 0.4, 0.6 ve 0.8 oranlarına karşılık gelir."))
add(blank())
add(H2('2.5) Stokastik Zemin ve Kat Hareketleri')); add(blank())
add(P("Zemin hareketleri, Clough–Penzien yüksek geçiren düzeltmesiyle Kanai–Tajimi spektrumuna (Clough ve Penzien 1993) göre filtrelenmiş beyaz gürültü olarak üretilmiştir:"))
add(blank()); add(eq_para(E[3], 3)); add(blank())
add(P("Burada S(ω) güç spektral yoğunluğu, S_{0} ölçek katsayısı ve ω açısal frekanstır (rad/s). Sert zemini temsil eden ω_{g} = 15 rad/s ve ζ_{g} = 0.6 ile ω_{f} = 1.5 rad/s ve ζ_{f} = 0.6 değerleri kullanılmıştır. Durağan olmayan karakter, Jennings ve diğ. (1968) tipinde parabolik artış (0–2 s), sabit faz (2–10 s) ve üstel sönümden (c = 0.30 s^{−1}) oluşan bir zarfla verilmiştir. Kayıt süresi 25 s, zaman adımı 0.001 s ve kayıt sayısı 40'tır; üretim, spektral gösterim yöntemine eşdeğer biçimde frekans alanında yapılmıştır (Shinozuka ve Deodatis 1991). Kat hareketleri tek modlu bir bina tepkisiyle elde edilmiştir:"))
add(blank()); add(eq_para(E[4], 4)); add(blank())
add(P("Burada ü_{g} zemin ivmesi, ü_{f} kat ivmesi, q modal yer değiştirme, Γ modal katkı çarpanı, φ(z) mod şekli, ζ sönüm oranı ve ω_{1} birinci mod açısal frekansıdır (rad/s). Temel periyot T_{1} ≈ 0.1N = 0.5 s (Chopra 2012), ζ = 0.05, mod şekli doğrusal φ(z) = z/H_{b} ve düzgün kütle dağılımı için Γ = 3N/(2N+1) ≈ 1.36 alınmıştır; N = 5 kat sayısıdır. Her kat kaydı en büyük değeri 1 olacak biçimde normalize edilmiş ve 0.1–2.0 g aralığında 0.1 g adımlarla (20 düzey) ölçeklenmiştir."))
add(blank())
add(H2('2.6) Dinamik Sallanma Analizi')); add(blank())
add(P("Sallanma hareketi Housner denklemiyle çözülmüştür (Housner 1963, Makris ve Roussos 2000):"))
add(blank()); add(eq_para(E[5], 5)); add(blank())
add(P("Burada θ dönme açısı (rad) ve r çarpma sonrası açısal hız oranıdır. Blok, |ü_{f}| > g·tan α koşulunda sallanmaya başlar; θ işaret değiştirdiğinde açısal hız r katsayısıyla azaltılır. |θ| > α olduğunda mobilya devrilmiş sayılmıştır. Denklem yarı kapalı Euler yöntemiyle Δt = 0.001 s adımla çözülmüştür. Zaman adımı yarıya indirildiğinde dört kontrol mobilyasının medyan devrilme ivmelerindeki en büyük bağıl fark %5.2'dir. Mobilyalar serbest duran simetrik bloklar olarak modellenmiş; duvar teması, kapak açılması ve kayma-sallanma etkileşimi ihmal edilmiştir. Bu nedenle dinamik sonuçlar yalnızca sallanma modundaki 12 mobilya için yorumlanmıştır."))
add(blank())
add(H2('2.7) Kırılganlık Eğrileri ve Devrilme Olasılığı')); add(blank())
add(P("Her mobilya ve kat için 20 ivme düzeyi × 40 kayıt = 800 analizden elde edilen devrilme sayıları, binom olabilirlik fonksiyonu en büyüklenerek lognormal dağılıma uydurulmuştur (Baker 2015):"))
add(blank()); add(eq_para(E[6], 6)); add(blank())
add(P("Burada Φ standart normal birikimli dağılım fonksiyonu, θ_{m} medyan devrilme ivmesi (g) ve β logaritmik standart sapmadır. Her DTS ve kat bileşimi için devrilme olasılığı, Eşitlik 2'deki talep Eşitlik 6'da yerine konularak hesaplanmıştır."))
add(blank())
add(H2('2.8) Yerleşim Analizi')); add(blank())
add(P("Devrilme etki alanı, öne devrilen mobilyanın döşemede kapladığı W × H dikdörtgeni olarak tanımlanmıştır (Şekil 1b). Yatağın başlık duvarından itibaren ilk 0.90 m'lik kısmı uyuyan kullanıcının baş-gövde bölgesi kabul edilmiştir. İki senaryo için 600'er oda üretilmiştir: konut yatak odası (2.8–3.8 × 3.0–4.6 m, 160 × 200 cm yatak, K01–K03) ve otel odası (3.3–4.1 × 4.0–5.2 m, 180 × 200 cm yatak, O01–O02). Her odada 0.90 m genişliğinde bir kapı ve 0.90 × 0.90 m kapı açılım alanı, karşı duvarda ise önüne yüksek mobilya konamayan bir pencere (konut 1.5 m, otel 2.4 m) tanımlanmıştır. Yatak başlığı bir duvara dayalı, yan açıklıkları en az 0.45 m ve ayakucu açıklığı en az 0.60 m olacak biçimde; yüksek mobilya ise sırtı duvara dayalı ve önünde 0.60 m kullanım alanı kalacak biçimde 0.10 m'lik ızgarada yerleştirilmiştir."))
add(blank())
add(P("İki gösterge hesaplanmıştır: (i) rastgele yerleşimde çakışma olasılığı, yani uygun mobilya konumlarından baş-gövde bölgesiyle çakışanların payının yatak konumları üzerinden ortalaması; (ii) güvenli konum bulunamama oranı, yani hiçbir güvenli mobilya konumu bulunmayan yatak konumlarının payı."))
add(blank())

# ---------------------------------------------------------------- 3. BULGULAR
add(H1('3. BULGULAR')); add(blank())
add(H2('3.1) Statik Eşikler ve Deprem Tasarım Sınıfları')); add(blank())
add(P("μ = 0.40 için 18 mobilyanın 12'si sallanma, 6'sı (K11–K14, O03, O04) kayma modundadır (Tablo 1). Sallanma modundaki mobilyaların tan α değerleri 0.150–0.378, narinlikleri (H/D) 2.64–6.67 aralığındadır. En narin mobilyalar geniş ve dar kitaplıklar (K05, K04) ile otel bölücü rafıdır (O02)."))
add(blank())
add(P("h_{c} = H/2 kabulüyle statik sallanma, mobilya narinliği g/PFA oranını aştığında başlar (Şekil 2). Örneğin S_{DS} = 1.00 için bu kritik narinlik zemin katta 2.50, en üst katta 0.96'dır. Statik ölçüte göre sallanma eşiğini aşan mobilya sayısı tehlike ve kat düzeyiyle hızla artmaktadır. DTS-4 temsil değerinde (S_{DS} = 0.25) zemin katta hiçbir mobilya eşiği aşmazken en üst katta 12 mobilyanın 6'sı aşmaktadır. DTS-3'te (S_{DS} = 0.42) bu sayı zemin katta 2, ikinci katta 11, en üst katta 12'dir. DTS-2'de (S_{DS} = 0.63) zemin katta 4, birinci katta 11 mobilya eşiği aşar; daha üst katlarda tüm mobilyalar eşiği aşar. DTS-1'de (S_{DS} = 1.00 ve 1.50) 12 mobilyanın tamamı her katta eşiği aşmaktadır."))
add(figure('sekil2_statik_harita.png', 6.0,
           'Şekil 2: Statik sallanma başlangıcı için kritik narinlik (H/D = g/PFA, h_{c} = H/2) ve katalogdaki mobilyaların narinlikleri (gri bantlar TBDY 2018 deprem tasarım sınıflarının S_{DS} aralıklarını göstermektedir)',
           'Figure 2: Critical slenderness for static rocking initiation (H/D = g/PFA, h_{c} = H/2) and slenderness of the catalogue items (grey bands show the S_{DS} ranges of the TBDY 2018 seismic design classes)'))
add(P("Duyarlılık analizi, içerik yüklemesinin belirleyici olduğunu göstermektedir. Alt-ağır yüklemede (h_{c}/H = 0.40) medyan tan α 0.29'dan 0.36'ya yükselirken (%25), üst-ağır yüklemede (h_{c}/H = 0.60) 0.24'e düşmektedir (%17). Sürtünme katsayısı 0.25'e indiğinde sallanma modundaki mobilya sayısı 4'e düşmekte, 0.60'a çıktığında 14'e yükselmektedir; üst-ağır yükleme ve μ = 0.60 bileşiminde bu sayı 16'dır."))
add(blank())
add(H2('3.2) Dinamik Davranış ve Kırılganlık Eğrileri')); add(blank())
add(P("Dinamik analiz, statik ölçütün devrilme için gereken ivmeyi belirgin biçimde düşük tahmin ettiğini göstermektedir (Tablo 2, Şekil 3). Medyan devrilme ivmesinin statik eşiğe oranı zemin katta 1.8–2.7 (medyan 2.1), en üst katta 2.4–4.0 (medyan 3.1) aralığındadır. Zemin kattaki bu oran blok boyutuyla artmaktadır (R ile Spearman ρ = 0.61): örneğin en küçük blok olan ayakkabılıkta (K10, R = 0.62 m) oran 1.9 iken sürgülü gardıropta (K03, R = 1.24 m) 2.4'tür."))
T2 = [
 ("K01", "0.290", "0.68", "0.21", "2.3", "1.01", "0.34", "3.5"),
 ("K02", "0.276", "0.66", "0.23", "2.4", "0.98", "0.35", "3.6"),
 ("K03", "0.258", "0.61", "0.27", "2.4", "0.97", "0.36", "3.7"),
 ("K04", "0.167", "0.31", "0.20", "1.9", "0.39", "0.38", "2.4"),
 ("K05", "0.150", "0.27", "0.29", "1.8", "0.37", "0.38", "2.5"),
 ("K06", "0.253", "0.48", "0.24", "1.9", "0.64", "0.34", "2.5"),
 ("K07", "0.211", "0.41", "0.24", "2.0", "0.59", "0.36", "2.8"),
 ("K08", "0.286", "0.68", "0.21", "2.4", "1.03", "0.34", "3.6"),
 ("K09", "0.378", "1.01", "0.20", "2.7", "1.52", "0.30", "4.0"),
 ("K10", "0.292", "0.54", "0.21", "1.9", "0.70", "0.30", "2.4"),
 ("O01", "0.273", "0.65", "0.20", "2.4", "0.97", "0.34", "3.6"),
 ("O02", "0.175", "0.33", "0.24", "1.9", "0.47", "0.32", "2.7"),
]
add(table(["Kod", "tan α", "Zemin θ_{m} (g)", "Zemin β", "Zemin θ_{m}/tan α", "En üst kat θ_{m} (g)", "En üst kat β", "En üst kat θ_{m}/tan α"], T2,
          [700, 900, 1150, 1000, 1250, 1250, 1100, 1450],
          'Tablo 2: Sallanma modundaki mobilyaların kırılganlık parametreleri (θ_{m}: medyan devrilme ivmesi, β: logaritmik standart sapma)',
          'Table 2: Fragility parameters of rocking-governed furniture (θ_{m}: median overturning acceleration, β: logarithmic standard deviation)'))
add(P("En üst kattaki medyan devrilme ivmeleri zemin kattakilerin 1.26–1.58 katıdır (medyan 1.46). Bunun nedeni, binanın temel periyodu çevresinde dar bantlı hâle gelen kat hareketinin, aynı tepe ivmesinde devrilme için daha az elverişli olmasıdır. Kat ivmesinin kendisi ise yükseklikle artmaktadır: simülasyonlarda ortalama PFA/PGA oranı z/H_{b} = 0.2, 0.4, 0.6 ve 0.8 için sırasıyla 1.03, 1.29, 1.71 ve 2.23 bulunmuştur. Eşitlik 2 aynı katlar için 1.4, 1.8, 2.2 ve 2.6 vermekte, özellikle alt katlarda güvenli tarafta kalmaktadır. Saçılım en üst katta daha yüksektir (β zemin katta 0.20–0.29, en üst katta 0.30–0.38)."))
add(figure('sekil3_kirilganlik.png', 6.0,
           'Şekil 3: Seçili altı mobilyanın zemin kat (Z) ve en üst kat (Ü) kırılganlık eğrileri (noktalar 40 kayıtlık simülasyondaki devrilme oranlarını, eğriler lognormal uyumu, noktalı dikey çizgi statik sallanma eşiğini göstermektedir)',
           'Figure 3: Fragility curves of six selected items on the ground floor (Z) and the top floor (Ü) (dots are overturning rates from 40 records, curves are lognormal fits, dotted vertical lines show the static rocking threshold)'))
add(H2('3.3) Deprem Tasarım Sınıfı ve Kata Göre Devrilme Olasılıkları')); add(blank())
add(P("Kırılganlık eğrileri Eşitlik 2'deki taleple birleştirildiğinde devrilme olasılığı hem tehlike düzeyine hem de kata güçlü biçimde bağlıdır (Şekil 4). DTS-4'te en yüksek olasılık en üst kattaki geniş kitaplıkta 0.17'dir. DTS-3'te dar ve geniş kitaplıklar en üst katta 0.61 ve 0.66, otel bölücü rafı 0.41 olasılıkla devrilmektedir; zemin katta tüm olasılıklar 0.05'in altındadır. DTS-2'de en üst kattaki 12 mobilyanın 5'inde (K04, K05, O02, K07, K06) olasılık 0.5'i geçmekte, gardıroplarda 0.10–0.14 düzeyinde kalmaktadır."))
add(blank())
add(P("S_{DS} = 1.00 düzeyinde devrilme olasılığı zemin katta 3 mobilyada (K04, K05, O02), en üst katta ise buzdolabı dışındaki 11 mobilyada 0.5'i aşmaktadır. Bu düzeyde gardıropların en üst kattaki devrilme olasılığı 0.53–0.58'dir. S_{DS} = 1.50 düzeyinde zemin kattaki 6 mobilyada ve ikinci kattan itibaren tüm mobilyalarda olasılık 0.5'in üzerindedir."))
add(figure('sekil4_risk_isi_haritasi.png', 6.0,
           'Şekil 4: Sallanma modundaki 12 mobilya için deprem tasarım sınıfı ve kat düzeyine göre devrilme olasılıkları (Z: zemin, 2: ikinci kat, 4: en üst kat döşemesi)',
           'Figure 4: Overturning probabilities of the 12 rocking-governed items by seismic design class and floor (Z: ground, 2: second floor, 4: top floor slab)'))
add(H2('3.4) Yerleşim Analizi')); add(blank())
add(P("Konut yatak odası senaryosunda 600 odanın (8.7–17.0 m^{2}, ortalama 12.3 m^{2}) 597'sinde en az bir uygun yerleşim bulunmuştur. Rastgele seçilen bir yerleşimde gardırobun devrilme etki alanı ortalama %43.4 olasılıkla yatağın baş-gövde bölgesine ulaşmaktadır (Tablo 3). Bu oran iki kapaklı gardıropta %22.8, üç kapaklıda %44.2, sürgülü dört kapaklıda %66.3'tür. Sürgülü gardırop için yatak konumlarının %51.7'sinde odada güvenli bir gardırop konumu bulunmamaktadır."))
T3 = [
 ("Konut yatak odası", "K01 Gardırop, 2 kapaklı", "597", "22.8", "0.8"),
 ("Konut yatak odası", "K02 Gardırop, 3 kapaklı", "569", "44.2", "18.8"),
 ("Konut yatak odası", "K03 Gardırop, sürgülü 4 kapaklı", "514", "66.3", "51.7"),
 ("Konut yatak odası", "Tümü (ortalama)", "597", "43.4", "22.5"),
 ("Otel odası", "O01 Otel gardırobu", "600", "25.3", "1.1"),
 ("Otel odası", "O02 Otel bölücü raf", "600", "7.7", "0.0"),
 ("Otel odası", "Tümü (ortalama)", "600", "16.5", "0.6"),
]
add(table(["Senaryo", "Mobilya", "Oda sayısı", "Çakışma olasılığı (%)", "Güvenli konum bulunamama (%)"], T3,
          [1800, 3000, 1100, 1450, 1650],
          'Tablo 3: Monte Carlo yerleşim analizi sonuçları (her senaryo için 600 oda)',
          'Table 3: Results of the Monte Carlo layout analysis (600 rooms per scenario)', left_cols=(0, 1)))
add(P("Oda alanı büyüdükçe risk azalmaktadır (Şekil 5b). Konutta 10 m^{2} ve altındaki odalarda çakışma olasılığı %49.0, güvenli konum bulunamama oranı %37.2'dir. 14–18 m^{2} odalarda bu değerler sırasıyla %31.5 ve %8.5'e düşmektedir. Otel odalarında (13.5–21.2 m^{2}, ortalama 17.1 m^{2}) ortalama çakışma olasılığı %16.5'tir ve hemen her yatak konumu için güvenli bir alternatif bulunmaktadır (%0.6 istisna)."))
add(figure('sekil5_yerlesim.png', 6.0,
           'Şekil 5: a) Örnek yatak odası yerleşiminde çakışan ve güvenli gardırop konumları, b) Oda alanına göre rastgele yerleşimde çakışma ve güvenli konum bulunamama olasılıkları',
           'Figure 5: a) Conflicting and safe wardrobe positions in an example bedroom layout, b) Probabilities of fall-zone conflict in random layouts and of no safe position by room area'))

# ---------------------------------------------------------------- 4. TARTIŞMA
add(H1('4. TARTIŞMA')); add(blank())
add(H2('4.1) Statik Ölçüt, Dinamik Rezerv ve Ölçek Etkisi')); add(blank())
add(P("Statik sallanma eşiğinin aşılması devrilme anlamına gelmemektedir: medyan devrilme ivmeleri statik eşiğin 1.8–4.0 katıdır. Bu sonuç, büyük blokların aynı narinlikte daha kararlı olduğunu gösteren ölçek etkisiyle (Housner 1963) ve devrilmenin hem narinliğe hem de blok boyutuna bağlı olduğunu gösteren sayısal ve deneysel çalışmalarla (Makris ve Roussos 2000, Purvance ve diğ. 2008, Dimitrakopoulos ve DeJong 2012) uyumludur. Statik ölçüt yine de tasarımcı için değerli bir tarama aracıdır, çünkü eşiği aşmayan bir mobilya hiç harekete geçmez."))
add(blank())
add(P("Dinamik rezerv riski ortadan kaldırmamaktadır. S_{DS} = 1.00 düzeyinde en üst katta 12 mobilyanın 11'inde devrilme olasılığı 0.5'i aşmaktadır. 2023 Kahramanmaraş depremlerinde 2 g'yi aşan yer ivmelerinin kaydedilmiş olması (Akinci ve diğ. 2025), dinamik olarak görece kararlı görünen buzdolabı gibi mobilyaların da tasarım düzeyini aşan sarsıntılarda devrilebileceğini düşündürmektedir."))
add(blank())
add(H2('4.2) Kat Etkisi')); add(blank())
add(P("Üst katlarda devrilme için gereken kat ivmesi zemin kata göre 1.26–1.58 kat artarken, Eşitlik 2'ye göre talep en üst katta 2.6 kat artmaktadır. Talepteki artış kapasitedeki artıştan hızlı olduğundan risk yükseklikle belirgin biçimde büyümektedir. Taşıyıcı sistemin kat ivmelerini değiştirerek devrilme riskini etkilediği farklı sistemler için de gösterilmiştir (Suzuki ve diğ. 2024). Orta yükseklikteki apartmanlarda kullanıcıların önemli bir bölümü üst katlarda yaşadığından sabitleme öncelikleri kata göre belirlenmelidir. Simülasyonla elde edilen kat büyütmeleri (1.03–2.23), Eşitlik 2'nin özellikle alt katlarda güvenli tarafta kaldığını göstermekte olup kat ivmesi tahminine yönelik ayrıntılı yöntemlerle (Miranda ve Taghavi 2005) uyumlu bir eğilim sergilemektedir."))
add(blank())
add(H2('4.3) İç Mimari Tasarım İçin Çıkarımlar')); add(blank())
add(P("Bulgular, iç mimarın doğrudan uygulayabileceği beş tasarım kuralına dönüştürülebilir."))
add(blank())
add(P("(1) Oran kuralı. Statik kararlılık için gereken en küçük derinlik D_{min} (m), ağırlık merkezi yüksekliği ve g cinsinden kat ivmesine bağlıdır:"))
add(blank()); add(eq_para(E[7], 7)); add(blank())
add(P("Örneğin S_{DS} = 0.42 olan bir bölgede, 5 katlı binanın en üst katındaki 2.00 m yüksekliğinde homojen bir gardırop için PFA = 0.44 g ve D_{min} = 0.87 m'dir. Bu değer tipik gardırop derinliğinin (0.58–0.62 m) çok üzerindedir; aynı bölgede zemin kat için D_{min} = 0.34 m'dir. Dolayısıyla oran tek başına yeterli değildir, ancak narinliğin azaltılması dinamik riski de düşürmektedir. Temel tasarım eğitiminde bir estetik karar olarak ele alınan oran (Ching 2015), deprem bölgelerinde bir güvenlik parametresi olarak da öğretilmelidir."))
add(blank())
add(P("(2) Yükleme kuralı. Ağır içeriğin alt bölmelere yerleştirilmesi (h_{c}/H = 0.40) tan α değerini %25 artırmaktadır. Bu, maliyetsiz bir kullanıcı önlemidir ve tefriş kılavuzlarında açıkça yer almalıdır."))
add(blank())
add(P("(3) Yerleşim kuralı. Yüksek mobilyanın W × H boyutlu devrilme etki alanı yatağın baş-gövde bölgesi, oturma alanları ve kaçış yolu ile kesişmemelidir. Konut yatak odalarında yatak konumlarının %77.5'inde bu kuralı sağlayan bir gardırop konumu bulunmaktadır; kural çoğu odada ek maliyet olmadan uygulanabilir. 10 m^{2} ve altındaki odalarda ve geniş sürgülü gardıroplarda kural sıklıkla sağlanamadığından bu durumlarda sabitleme zorunlu görülmelidir."))
add(blank())
add(P("(4) Sabitleme önceliği. DTS-3 ve üzeri bölgelerde üst katlardaki kitaplıklar, vitrinler ve bölücü raflar; DTS-1 bölgelerinde ise tüm yüksek mobilyalar zemin kat dâhil sabitlenmelidir. Kayma modundaki alçak mobilya ve cihazlar devrilmese de kayarak kapı ve kaçış yollarını kapatabileceğinden durdurucu ve bağlantı elemanlarıyla tutulmalıdır (FEMA 2012)."))
add(blank())
add(P("(5) Otel odaları. Otel odalarının daha büyük alanı nedeniyle yerleşim kuralı hemen her zaman sağlanabilmektedir. Buna karşın odayı bölmek için kullanılan serbest duran yüksek raflar en kırılgan elemanlar arasındadır (zemin katta θ_{m} = 0.33 g). Odayı tanımayan konukların kullandığı bu mekânlarda bölücü rafların döşemeye ve tavana bağlanması önerilmektedir. Camlı vitrinlerde (K07) devrilme ile cam kırılması tehlikesi birleştiğinden sabitlemeyle birlikte güvenlik camı kullanılmalıdır."))
add(blank())
add(H2('4.4) Açık Kaynak Hesaplayıcı')); add(blank())
add(P("Çalışmanın yöntemi, iç mimarların ve öğrencilerin kullanabileceği web tabanlı bir hesaplayıcıya dönüştürülmüştür. Kullanıcı mobilya boyutlarını, AFAD Türkiye Deprem Tehlike Haritaları'ndan (AFAD 2018) elde edilen S_{DS} değerini ve kat konumunu girerek statik eşiği, kat ivmesi talebini, devrilme etki derinliğini ve sabitleme gereksinimini görebilmektedir. Bu araç, deprem riskinin tasarım stüdyosu aşamasında görünür kılınmasına ve mesleki kapasitenin geliştirilmesine katkı sağlamayı amaçlamaktadır."))
add(blank())
add(H2('4.5) Sınırlılıklar')); add(blank())
add(P("Çalışmanın sınırlılıkları şunlardır: (i) Kayıtlar stokastik olarak üretilmiştir; yakın fay atımları (Makris ve Roussos 2000, Zhang ve Makris 2001) ve 2023 depremlerinin uzun süreli kayıtları ayrıca incelenmelidir. (ii) Mobilyalar homojen, rijit ve simetrik bloklar olarak modellenmiş; esneklik, içerik hareketi, kapak açılması, duvar teması, kayma-sallanma etkileşimi ile üç boyutlu ve düşey etkiler ihmal edilmiştir. (iii) Tek bir 5 katlı bina ve tek mod kullanılmıştır. (iv) Sürtünme katsayısı ve mobilya boyutları temsilî varsayımlardır. (v) Talep deterministik alınmıştır; olasılıklar tasarım düzeyi sarsıntıya koşulludur ve yıllık risk değildir. (vi) Devrilme etki alanı basitleştirilmiş bir dikdörtgendir ve yaralanma şiddeti modellenmemiştir. Sonuçların sarsma tablası deneyleriyle doğrulanması, ofis, okul ve sağlık yapılarına genişletilmesi ve yerleşim kuralının parametrik ya da yapay zekâ destekli tasarım araçlarına entegre edilmesi sonraki çalışmalar için önerilmektedir."))
add(blank())

# ---------------------------------------------------------------- 5. SONUÇLAR
add(H1('5. SONUÇLAR')); add(blank())
add(P("Bu çalışma, konut ve otel iç mekânlarındaki serbest duran mobilyaların deprem kaynaklı devrilme riskini rijit blok dinamiği, yönetmelik tabanlı kat ivmesi talebi ve yerleşim analizini birleştirerek nicel olarak değerlendirmiştir. Birinci araştırma sorusuna yanıt olarak, S_{DS} = 1.00 düzeyinde sallanma modundaki 12 mobilyanın tamamı her katta statik sallanma eşiğini aşmakta, DTS-3'te bile en üst kattaki tüm mobilyalar harekete geçmektedir. İkinci soruya yanıt olarak, dinamik devrilme ivmeleri statik eşiğin 1.8–4.0 katı olmakla birlikte S_{DS} = 1.00 düzeyinde en üst kattaki 12 mobilyanın 11'inde devrilme olasılığı 0.5'i aşmaktadır. Üçüncü soruya yanıt olarak, rastgele konut yatak odası yerleşimlerinin %43.4'ünde gardırobun devrilme etki alanı yatağın baş-gövde bölgesine ulaşmakta, bu oran otel odalarında %16.5'e inmektedir."))
add(blank())
add(P("Bulgular dört uygulama önerisine işaret etmektedir:"))
add(blank())
for t in ["* Afet bilinci ve hazırlık materyallerinde mobilya sabitleme önerileri deprem tasarım sınıfı ve kat düzeyine göre önceliklendirilmeli, devrilme etki alanı kuralı yerleşim önerisi olarak yer almalıdır.",
          "* Yüksek mobilyalar sabitleme elemanlarıyla birlikte sunulmalı, ürün bilgilerinde yükseklik/derinlik oranı ve önerilen yükleme düzeni belirtilmelidir.",
          "* İç mimarlık tasarım stüdyolarında yerleşim kararları devrilme etki alanı kontrolüyle birlikte değerlendirilmeli; oran ve yükleme kararları deprem güvenliği bağlamında öğretilmelidir.",
          "* Otel işletmelerinde gardırop ve bölücü rafların sabitlenmesi düzenli denetim listelerine eklenmelidir."]:
    add(P(t, jc='left'))
add(blank())
add(P("Açık erişimle paylaşılan kod ve hesaplayıcı, bu önerilerin farklı mobilya, bina ve tehlike koşullarında sınanmasına olanak tanımaktadır."))
add(blank())

# ---------------------------------------------------------------- TEŞEKKÜR
add(H1('TEŞEKKÜR')); add(blank())
add(P("Bu çalışma herhangi bir kurum veya proje tarafından desteklenmemiştir. [[h:Analiz kodunun yazılmasında ve metnin taslak aşamasında yapay zekâ destekli bir araçtan (Claude, Anthropic) yararlanılmış; tüm hesaplamalar, içerik ve kaynaklar yazarlar tarafından kontrol edilmiştir.]]"))
add(blank())

# ---------------------------------------------------------------- KAYNAKLAR
add(H1('KAYNAKLAR')); add(blank())
REFS = [
 "AFAD, 2018. Turkey Earthquake Hazard Maps Interactive Web Application (TDTH), Ankara, Erişim adresi: https://tdth.afad.gov.tr",
 "Akinci A., Dindar A.A., Bal I.E., Ertuncay D., Smyrou E., Cheloni D., 2025. Characteristics of strong ground motions and structural damage patterns from the February 6th, 2023 Kahramanmaras earthquakes, Turkiye, [[i:Nat. Hazards]] 121(2), 1209-1239.",
 "ASCE, 2017. Minimum Design Loads and Associated Criteria for Buildings and Other Structures (ASCE/SEI 7-16), American Society of Civil Engineers, Reston, VA, U.S.A.",
 "Baker J.W., 2015. Efficient analytical fragility function fitting using dynamic structural analysis, [[i:Earthq. Spectra]] 31(1), 579-599.",
 "Buker M.B., Pinar E., Sakarya K., Altiparmakoglu Sakarya G., 2023. Yapisal olmayan elemanlarla deprem guvenligi saglamaya yonelik bir mobilya tasarim onerisi, [[i:Journal of Architectural Sciences and Applications]] 8(Ozel Sayi), 615-630.",
 "Ching F.D.K., 2015. Architecture: Form, Space, and Order, 4th Edition, Wiley, Hoboken, NJ, U.S.A., 447 p.",
 "Chopra A.K., 2012. Dynamics of Structures: Theory and Applications to Earthquake Engineering, 4th Edition, Prentice Hall, Upper Saddle River, NJ, U.S.A., 944 p.",
 "Clough R.W., Penzien J., 1993. Dynamics of Structures, 2nd Edition, McGraw-Hill, New York, U.S.A., 738 p.",
 "Demirbas C., 2008. Deprem bolgesi konutlari icin ic mekanlarin guvenlik analizi ve cozum onerileri, Yuksek Lisans Tezi, Karadeniz Teknik Universitesi, Fen Bilimleri Enstitusu, Ic Mimarlik Anabilim Dali, Trabzon, 118 s.",
 "Dimitrakopoulos E.G., DeJong M.J., 2012. Revisiting the rocking block: closed-form solutions and similarity laws, [[i:Proc. R. Soc. A-Math. Phys. Eng. Sci.]] 468(2144), 2294-2318.",
 "Ertas Besir S., Dereci S., 2021. Deprem sirasinda konut ic mekanlarinda yapisal olmayan elemanlarin yarattigi riskler ve alinabilecek onlemler, [[i:International Social Mentality and Researcher Thinkers Journal]] 7(42), 350-360.",
 "FEMA, 2012. Reducing the Risks of Nonstructural Earthquake Damage - A Practical Guide (FEMA E-74), Federal Emergency Management Agency, Washington, DC, U.S.A.",
 "Filiatrault A., Perrone D., Merino R.J., Calvi G.M., 2021. Performance-based seismic design of nonstructural building elements, [[i:J. Earthq. Eng.]] 25(2), 237-269.",
 "Housner G.W., 1963. The behavior of inverted pendulum structures during earthquakes, [[i:Bull. Seismol. Soc. Amer.]] 53(2), 403-417.",
 "Ishiyama Y., 1982. Motions of rigid bodies and criteria for overturning by earthquake excitations, [[i:Earthq. Eng. Struct. Dyn.]] 10(5), 635-650.",
 "Jennings P.C., Housner G.W., Tsai N.C., 1968. Simulated Earthquake Motions, Technical Report, Earthquake Engineering Research Laboratory, California Institute of Technology, Pasadena, CA, U.S.A.",
 "Kaya I., Sahan C., 2023. Depreme karsi okul binalarinda yapisal olmayan tehlikelere alternatif mobilya tasarim onerileri, [[i:ODU Sosyal Bilimler Arastirmalari Dergisi]] 13(2), 1907-1927.",
 "Konstantinidis D., Makris N., 2009. Experimental and analytical studies on the response of freestanding laboratory equipment to earthquake shaking, [[i:Earthq. Eng. Struct. Dyn.]] 38(6), 827-848.",
 "Kurtulus V.B., Mus Ozmen N., 2025. Deprem aninda ve sonrasinda donusebilen tasarim onerileri: gunluk kullanimdan hayat kurtaran birimlere, [[i:Turk Deprem Arastirma Dergisi]] 7(3), 406-431.",
 "Lopez Garcia D., Soong T.T., 2003. Sliding fragility of block-type non-structural components. Part 1: Unrestrained components, [[i:Earthq. Eng. Struct. Dyn.]] 32(1), 111-129.",
 "Makris N., Roussos Y.S., 2000. Rocking response of rigid blocks under near-source ground motions, [[i:Geotechnique]] 50(3), 243-262.",
 "Miranda E., Taghavi S., 2005. Approximate floor acceleration demands in multistory buildings. I: Formulation, [[i:J. Struct. Eng.]] 131(2), 203-211.",
 "Ozcan S., 2023. Ic mekan donatilarinda guvenligin arttirilmasi ve devrilmenin onlenmesi amacli urun tasarimi ve ornek uygulamalar, Doktora Tezi, Karabuk Universitesi, Lisansustu Egitim Enstitusu, Orman Endustri Muhendisligi Anabilim Dali, Karabuk, 111 s.",
 "Panero J., Zelnik M., 1979. Human Dimension and Interior Space: A Source Book of Design Reference Standards, Whitney Library of Design, New York, U.S.A., 320 p.",
 "Pietroni L., Mascitti J., Galloppo D., 2021. Life saving furniture during an earthquake, [[i:International Journal of Architecture, Art and Design]] 10, 218-229.",
 "Purvance M.D., Anooshehpoor A., Brune J.N., 2008. Freestanding block overturning fragilities: numerical simulation and experimental validation, [[i:Earthq. Eng. Struct. Dyn.]] 37(5), 791-808.",
 "Sato T., Motosaka M., Mano A., 2006. Investigation of human injuries during the July 26, 2003 northern Miyagi earthquake with focus on furniture overturning, [[i:Journal of Natural Disaster Science]] 28(1), 15-24.",
 "Shenton H.W., 1996. Criteria for initiation of slide, rock, and slide-rock rigid-body modes, [[i:J. Eng. Mech.]] 122(7), 690-693.",
 "Shinozuka M., Deodatis G., 1991. Simulation of stochastic processes by spectral representation, [[i:Appl. Mech. Rev.]] 44(4), 191-204.",
 "Suzuki A., Ohno S., Kimura Y., 2024. Risk assessment of overturning of freestanding non-structural building contents in buckling-restrained braced frames, [[i:Buildings]] 14(10), 3195.",
 "TBDY, 2018. Turkiye Bina Deprem Yonetmeligi, T.C. Resmi Gazete, 18.03.2018, Sayi 30364 (Mukerrer), Ankara.",
 "TFD, 2017. Life Safety Information from the Tokyo Fire Department IV - Quake! Don't Let Your Furniture Kill You, Tokyo, Erişim adresi: https://www.tfd.metro.tokyo.lg.jp/eng/merumaga/info_en_2017nov.html",
 "Uzer L., Uc B., 2026. Deprem guvenligi baglaminda konut ic mekanlarinda guvenli tefris: geleneksel Turk evi uzerinden mekansal tasarim onerileri, [[i:International Journal of Social and Humanities Sciences]] 10(2), 33-68.",
 "Yim C.S., Chopra A.K., Penzien J., 1980. Rocking response of rigid blocks to earthquakes, [[i:Earthq. Eng. Struct. Dyn.]] 8(6), 565-587.",
 "Yolcu F.Z., 2026. Deprem sonrasi gecici barinma mekanlarinda adaptif mobilya tasarim kriterleri, [[i:Mimarlik ve Yasam Dergisi]] 11(1), 123-146.",
 "Zhang J., Makris N., 2001. Rocking response of free-standing blocks under cycloidal pulses, [[i:J. Eng. Mech.]] 127(5), 473-483.",
]
for k, r_ in enumerate(REFS):
    add(P(r_, jc='left'))
    add(blank())
add(blank())

# ---------------------------------------------------------------- beyanlar
def head_bi(tr, en):
    return f'<w:p>{ppr("both", b=True)}{run(tr + " ", b=True)}{run(en, i=True)}</w:p>'

add(head_bi('ARAŞTIRMA VERİSİ', '(Research Data)')); add(blank())
add(P("Çalışmada saha ölçümü veya kurumlardan temin edilen ham veri kullanılmamıştır; tüm veriler çalışma kapsamında hesaplamalı olarak üretilmiştir. Deprem tehlike düzeyleri AFAD Deprem Dairesi Başkanlığı'nın Türkiye Deprem Tehlike Haritası (TDTH) ve TBDY 2018 deprem tasarım sınıfları esas alınarak tanımlanmıştır. Analiz kodu, üretilen veriler ve web hesaplayıcı CC BY 4.0 lisansıyla [[h:GitHub/Zenodo bağlantısı ve DOI]] adresinde paylaşılmaktadır."))
add(blank())
add(head_bi('ÇIKAR ÇATIŞMASI / İLİŞKİSİ', '(Conflict of Interest / Relationship)')); add(blank())
add(P("Yazarlar, bu çalışma kapsamında herhangi bir kişi, kurum veya ticari kuruluşla çıkar çatışması ya da ilişkisi bulunmadığını beyan eder. Çalışmada yer alan mobilya tipleri temsilî olup herhangi bir marka veya üreticiyle ilişkilendirilmemiştir."))
add(blank())
add(head_bi('YAZARLARIN KATKI ORANI BEYANI', '(Author Contributions)')); add(blank())
CONTR = [("Çalışmanın tasarlanması ", "(Designing of the study)"),
         ("Literatür araştırması ", "(Literature research)"),
         ("Saha çalışması, veri temini/derleme ", "(Fieldwork, collection/compilation of data)"),
         ("Verilerin işlenmesi/analiz edilmesi ", "(Processing/analysis of data)"),
         ("Şekil/Tablo/Yazılım hazırlanması ", "(Preparation of figures/tables/software)"),
         ("Bulguların yorumlanması ", "(Interpretation of findings)"),
         ("Makale yazımı, düzenleme, kontrol ", "(Writing, editing and checking of manuscript)")]
LIST_PPR = ('<w:pPr><w:pStyle w:val="ListeParagraf"/><w:numPr><w:ilvl w:val="0"/><w:numId w:val="4"/></w:numPr>'
            '<w:autoSpaceDE w:val="0"/><w:autoSpaceDN w:val="0"/><w:adjustRightInd w:val="0"/>'
            '<w:spacing w:after="0" w:line="240" w:lineRule="auto"/><w:ind w:left="284" w:hanging="284"/><w:jc w:val="both"/>'
            + rpr() + '</w:pPr>')
for tr_, en_ in CONTR:
    add(f'<w:p>{LIST_PPR}{run(tr_)}{run(en_, i=True)}{run(": ")}{run("[A.I.P., H.B., F.K.]", hl=True)}</w:p>')
add(blank())

BODY = ''.join(body)

# ---------------------------------------------------------------- assemble package
if OUT_DIR.exists():
    shutil.rmtree(OUT_DIR)
shutil.copytree(SRC, OUT_DIR)
doc = (OUT_DIR / 'word/document.xml').read_text(encoding='utf-8')
head = doc[:doc.index('<w:body>') + len('<w:body>')]
sect = doc[doc.index('<w:sectPr'):]
(OUT_DIR / 'word/document.xml').write_text(head + BODY + sect, encoding='utf-8')

# görseller ve ilişkiler
(OUT_DIR / 'word/media/image1.png').unlink(missing_ok=True)
rels_p = OUT_DIR / 'word/_rels/document.xml.rels'
rels = rels_p.read_text(encoding='utf-8')
rels = re.sub(r'<Relationship Id="rId8"[^>]*/>', '', rels)
rels = re.sub(r'<Relationship Id="rId9"[^>]*/>', '', rels)   # şablondaki WoS bağlantısı artık kullanılmıyor
add_rels = ''.join(f'<Relationship Id="{rid}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="{t}"/>'
                   for rid, t, _ in IMG_RELS)
rels = rels.replace('</Relationships>', add_rels + '</Relationships>')
rels_p.write_text(rels, encoding='utf-8')
for rid, t, src in IMG_RELS:
    shutil.copy(src, OUT_DIR / 'word' / t)

# belge özellikleri: başlık
core_p = OUT_DIR / 'docProps/core.xml'
core = core_p.read_text(encoding='utf-8')
core = re.sub(r'<dc:title>.*?</dc:title>', '<dc:title>Serbest Duran Mobilyalarin Deprem Kaynakli Devrilme Riski</dc:title>', core)
core_p.write_text(core, encoding='utf-8')

if OUT_DOCX.exists():
    OUT_DOCX.unlink()
with zipfile.ZipFile(OUT_DOCX, 'w', zipfile.ZIP_DEFLATED) as z:
    ct = OUT_DIR / '[Content_Types].xml'
    z.write(ct, '[Content_Types].xml')
    for p in sorted(OUT_DIR.rglob('*')):
        if p.is_file() and p.name != '[Content_Types].xml':
            z.write(p, p.relative_to(OUT_DIR).as_posix())
print('Yazıldı:', OUT_DOCX, '| kaynak sayısı:', len(REFS))
