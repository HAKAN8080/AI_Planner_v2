"""
SANAL PLANNER - Agentic Tool Calling v2
CSV tabanlı küp verisi ile çalışan akıllı agent
"""

import pandas as pd
import numpy as np
import json
from typing import Optional, List, Dict
import anthropic
import os
import glob
import sys

# Sevkiyat motoru artık INLINE - ayrı modül yok
SEVKIYAT_MOTORU_AVAILABLE = True  # Her zaman True çünkü inline
print("✅ Sevkiyat hesaplama INLINE modda çalışıyor")

# =============================================================================
# VERİ YÜKLEYİCİ
# =============================================================================

class KupVeri:
    """CSV ve Excel tabanlı küp verisi yönetimi"""
    
    def __init__(self, veri_klasoru: str):
        """
        veri_klasoru: CSV ve Excel dosyalarının bulunduğu klasör
        """
        self.veri_klasoru = veri_klasoru
        self._yukle()
        self._hazirla()
    
    def _yukle(self):
        """Tüm veri dosyalarını yükle"""
        
        # =====================================================================
        # 1. ANLIK STOK SATIŞ (CSV - parçalı dosyalar)
        # =====================================================================
        stok_satis_files = glob.glob(os.path.join(self.veri_klasoru, "anlik_stok_satis*.csv"))
        if stok_satis_files:
            dfs = []
            for f in stok_satis_files:
                try:
                    df = pd.read_csv(f, encoding='utf-8', sep=None, engine='python')
                except:
                    try:
                        df = pd.read_csv(f, encoding='latin-1', sep=None, engine='python')
                    except:
                        df = pd.read_csv(f, encoding='utf-8', sep=';')
                dfs.append(df)
            self.stok_satis = pd.concat(dfs, ignore_index=True)
        else:
            self.stok_satis = pd.DataFrame()
        
        
        # =====================================================================
        # 2. MASTER TABLOLAR (CSV)
        # =====================================================================
        urun_path = os.path.join(self.veri_klasoru, "urun_master.csv")
        if os.path.exists(urun_path):
            try:
                self.urun_master = pd.read_csv(urun_path, encoding='utf-8', sep=None, engine='python')
            except:
                self.urun_master = pd.read_csv(urun_path, encoding='latin-1', sep=None, engine='python')
        else:
            self.urun_master = pd.DataFrame()
        
        magaza_path = os.path.join(self.veri_klasoru, "magaza_master.csv")
        if os.path.exists(magaza_path):
            try:
                self.magaza_master = pd.read_csv(magaza_path, encoding='utf-8', sep=None, engine='python')
            except:
                self.magaza_master = pd.read_csv(magaza_path, encoding='latin-1', sep=None, engine='python')
        else:
            self.magaza_master = pd.DataFrame()
        
        depo_path = os.path.join(self.veri_klasoru, "depo_stok.csv")
        if os.path.exists(depo_path):
            try:
                self.depo_stok = pd.read_csv(depo_path, encoding='utf-8', sep=None, engine='python')
            except:
                self.depo_stok = pd.read_csv(depo_path, encoding='latin-1', sep=None, engine='python')
        else:
            self.depo_stok = pd.DataFrame()
        
        kpi_path = os.path.join(self.veri_klasoru, "kpi.csv")
        if os.path.exists(kpi_path):
            try:
                self.kpi = pd.read_csv(kpi_path, encoding='utf-8', sep=None, engine='python')
            except:
                self.kpi = pd.read_csv(kpi_path, encoding='latin-1', sep=None, engine='python')
        else:
            self.kpi = pd.DataFrame()
        
        # =====================================================================
        # 3. TRADING RAPORU (Excel)
        # =====================================================================
        trading_path = os.path.join(self.veri_klasoru, "trading.xlsx")
        if os.path.exists(trading_path):
            try:
                self.trading = pd.read_excel(trading_path, sheet_name='mtd')
            except:
                try:
                    self.trading = pd.read_excel(trading_path, sheet_name=0)
                except:
                    self.trading = pd.DataFrame()
        else:
            self.trading = pd.DataFrame()
        
        # =====================================================================
        # 4. SC TABLOSU (Excel - birden fazla sayfa)
        # =====================================================================
        sc_files = glob.glob(os.path.join(self.veri_klasoru, "*SC*.xlsx")) + \
                   glob.glob(os.path.join(self.veri_klasoru, "*sc*.xlsx")) + \
                   glob.glob(os.path.join(self.veri_klasoru, "*Tablosu*.xlsx"))
        
        self.sc_sayfalari = {}
        if sc_files:
            sc_path = sc_files[0]  # İlk bulunan SC dosyası
            try:
                xl = pd.ExcelFile(sc_path)
                for sheet_name in xl.sheet_names:
                    try:
                        self.sc_sayfalari[sheet_name] = pd.read_excel(xl, sheet_name=sheet_name)
                    except:
                        pass
            except Exception as e:
                print(f"SC dosyası okunamadı: {e}")
        
        # =====================================================================
        # LOG
        # =====================================================================
        print(f"✅ Veri yüklendi:")
        print(f"   - Stok/Satış: {len(self.stok_satis):,} satır")
        print(f"   - Ürün Master: {len(self.urun_master):,} ürün")
        print(f"   - Mağaza Master: {len(self.magaza_master):,} mağaza")
        print(f"   - Depo Stok: {len(self.depo_stok):,} satır")
        print(f"   - KPI: {len(self.kpi):,} satır")
        print(f"   - Trading: {len(self.trading):,} satır")
        print(f"   - SC Sayfaları: {list(self.sc_sayfalari.keys())}")
    
    def _hazirla(self):
        """Veriyi zenginleştir ve hesaplamalar yap"""
        
        if len(self.stok_satis) == 0:
            return
        
        # BOM karakterini temizle ve kolon isimlerini normalize et
        def temizle_kolonlar(df):
            df.columns = df.columns.str.replace('\ufeff', '').str.lower().str.strip()
            return df
        
        self.stok_satis = temizle_kolonlar(self.stok_satis)
        if len(self.urun_master) > 0:
            self.urun_master = temizle_kolonlar(self.urun_master)
        if len(self.magaza_master) > 0:
            self.magaza_master = temizle_kolonlar(self.magaza_master)
        if len(self.depo_stok) > 0:
            self.depo_stok = temizle_kolonlar(self.depo_stok)
        if len(self.kpi) > 0:
            self.kpi = temizle_kolonlar(self.kpi)
        
        print(f"\n🔍 JOIN ÖNCESİ KONTROL:")
        print(f"   Stok/Satış kolonları: {list(self.stok_satis.columns)}")
        print(f"   Ürün Master kolonları: {list(self.urun_master.columns) if len(self.urun_master) > 0 else 'BOŞ'}")
        print(f"   Mağaza Master kolonları: {list(self.magaza_master.columns) if len(self.magaza_master) > 0 else 'BOŞ'}")
        
        # Ürün master ile join
        if len(self.urun_master) > 0 and 'urun_kod' in self.stok_satis.columns and 'urun_kod' in self.urun_master.columns:
            # Veri tiplerini eşitle (integer olarak tut, sonra string yap)
            self.stok_satis['urun_kod'] = pd.to_numeric(self.stok_satis['urun_kod'], errors='coerce').fillna(0).astype(int).astype(str)
            self.urun_master['urun_kod'] = pd.to_numeric(self.urun_master['urun_kod'], errors='coerce').fillna(0).astype(int).astype(str)
            
            urun_kolonlar = ['urun_kod']
            for kol in ['kategori_kod', 'umg', 'mg', 'marka_kod', 'nitelik', 'durum']:
                if kol in self.urun_master.columns:
                    urun_kolonlar.append(kol)
            
            print(f"   Ürün join kolonları: {urun_kolonlar}")
            print(f"   Stok urun_kod örnek: {self.stok_satis['urun_kod'].head(3).tolist()}")
            print(f"   Master urun_kod örnek: {self.urun_master['urun_kod'].head(3).tolist()}")
            
            if len(urun_kolonlar) > 1:
                before_len = len(self.stok_satis)
                self.stok_satis = self.stok_satis.merge(
                    self.urun_master[urun_kolonlar],
                    on='urun_kod',
                    how='left'
                )
                print(f"   ✅ Ürün join: {before_len} → {len(self.stok_satis)} satır")
                
                # Join sonrası kontrol
                if 'kategori_kod' in self.stok_satis.columns:
                    non_null = self.stok_satis['kategori_kod'].notna().sum()
                    print(f"   kategori_kod dolu: {non_null:,} / {len(self.stok_satis):,}")
        
        # Mağaza master ile join
        if len(self.magaza_master) > 0 and 'magaza_kod' in self.stok_satis.columns and 'magaza_kod' in self.magaza_master.columns:
            # Veri tiplerini eşitle
            self.stok_satis['magaza_kod'] = pd.to_numeric(self.stok_satis['magaza_kod'], errors='coerce').fillna(0).astype(int).astype(str)
            self.magaza_master['magaza_kod'] = pd.to_numeric(self.magaza_master['magaza_kod'], errors='coerce').fillna(0).astype(int).astype(str)
            
            mag_kolonlar = ['magaza_kod']
            for kol in ['il', 'bolge', 'tip', 'depo_kod']:
                if kol in self.magaza_master.columns:
                    mag_kolonlar.append(kol)
            
            print(f"   Mağaza join kolonları: {mag_kolonlar}")
            print(f"   Stok magaza_kod örnek: {self.stok_satis['magaza_kod'].head(3).tolist()}")
            print(f"   Master magaza_kod örnek: {self.magaza_master['magaza_kod'].head(3).tolist()}")
            
            if len(mag_kolonlar) > 1:
                before_len = len(self.stok_satis)
                self.stok_satis = self.stok_satis.merge(
                    self.magaza_master[mag_kolonlar],
                    on='magaza_kod',
                    how='left'
                )
                print(f"   ✅ Mağaza join: {before_len} → {len(self.stok_satis)} satır")
                
                # Join sonrası kontrol
                if 'bolge' in self.stok_satis.columns:
                    non_null = self.stok_satis['bolge'].notna().sum()
                    print(f"   bolge dolu: {non_null:,} / {len(self.stok_satis):,}")
        
        # KPI ile join (mg bazlı)
        if len(self.kpi) > 0 and 'mg' in self.stok_satis.columns:
            kpi_df = self.kpi.copy()
            if 'mg_id' in kpi_df.columns:
                kpi_df = kpi_df.rename(columns={'mg_id': 'mg'})
            
            if 'mg' in kpi_df.columns:
                # Veri tiplerini eşitle
                self.stok_satis['mg'] = pd.to_numeric(self.stok_satis['mg'], errors='coerce').fillna(0).astype(int).astype(str)
                kpi_df['mg'] = pd.to_numeric(kpi_df['mg'], errors='coerce').fillna(0).astype(int).astype(str)
                
                self.stok_satis = self.stok_satis.merge(
                    kpi_df,
                    on='mg',
                    how='left'
                )
                print(f"   ✅ KPI join tamamlandı")
        
        # Kar hesapla (kolonlar varsa)
        if 'ciro' in self.stok_satis.columns and 'smm' in self.stok_satis.columns:
            self.stok_satis['kar'] = self.stok_satis['ciro'] - self.stok_satis['smm']
        else:
            self.stok_satis['kar'] = 0
            self.stok_satis['ciro'] = self.stok_satis.get('ciro', 0)
        
        # Kar marjı
        if 'ciro' in self.stok_satis.columns:
            self.stok_satis['kar_marji'] = np.where(
                self.stok_satis['ciro'] > 0,
                self.stok_satis['kar'] / self.stok_satis['ciro'],
                0
            )
        else:
            self.stok_satis['kar_marji'] = 0
        
        # Haftalık satış (satis kolonunu kullan)
        if 'satis' in self.stok_satis.columns:
            self.stok_satis['haftalik_satis'] = self.stok_satis['satis']
        else:
            self.stok_satis['haftalik_satis'] = 0
        
        # Cover hesapla
        if 'stok' in self.stok_satis.columns:
            self.stok_satis['cover'] = np.where(
                self.stok_satis['haftalik_satis'] > 0,
                self.stok_satis['stok'] / self.stok_satis['haftalik_satis'],
                np.where(self.stok_satis['stok'] > 0, 999, 0)
            )
        else:
            self.stok_satis['cover'] = 0
            self.stok_satis['stok'] = 0
        
        # Stok durumu değerlendirme
        self.stok_satis['stok_durum'] = 'NORMAL'
        
        # min_deger ve max_deger kolonları yoksa varsayılan değer kullan
        if 'min_deger' not in self.stok_satis.columns:
            self.stok_satis['min_deger'] = 3
        if 'max_deger' not in self.stok_satis.columns:
            self.stok_satis['max_deger'] = 20
        if 'forward_cover' not in self.stok_satis.columns:
            self.stok_satis['forward_cover'] = 4
        
        # Min altı = SEVKİYAT GEREKLİ
        mask_min = self.stok_satis['stok'] < self.stok_satis['min_deger'].fillna(3)
        self.stok_satis.loc[mask_min, 'stok_durum'] = 'SEVK_GEREKLI'
        
        # Max üstü = FAZLA STOK
        mask_max = self.stok_satis['stok'] > self.stok_satis['max_deger'].fillna(20)
        self.stok_satis.loc[mask_max, 'stok_durum'] = 'FAZLA_STOK'
        
        # Cover hedefin üstünde = YAVAS
        mask_cover = self.stok_satis['cover'] > self.stok_satis['forward_cover'].fillna(4) * 3
        self.stok_satis.loc[mask_cover & (self.stok_satis['stok_durum'] == 'NORMAL'), 'stok_durum'] = 'YAVAS'
        
        # Detaylı debug bilgisi
        print(f"\n📊 VERİ DURUMU:")
        print(f"   - Toplam kayıt: {len(self.stok_satis):,}")
        print(f"   - Kolonlar: {list(self.stok_satis.columns)}")
        
        # Kritik kolonları kontrol et
        for kol in ['magaza_kod', 'urun_kod', 'kategori_kod', 'mg', 'bolge']:
            if kol in self.stok_satis.columns:
                non_null = self.stok_satis[kol].notna().sum()
                unique_vals = self.stok_satis[kol].dropna().unique()[:5]
                print(f"   ✅ {kol}: {non_null:,} dolu, örnek değerler: {list(unique_vals)}")
            else:
                print(f"   ❌ {kol}: KOLON YOK")


# =============================================================================
# ARAÇ FONKSİYONLARI
# =============================================================================

def trading_analiz(kup: KupVeri) -> str:
    """
    Trading raporu analizi - Basit versiyon
    
    NOT: Trading.xlsx'te sadece 1. seviye (ana kategori) verisi olmalı.
    Alt kategoriler ve mal grupları ayrı dosyada tutulacak.
    
    Analiz Sırası:
    1. Şirket Toplamı
    2. Kategori Bazlı Performans
    3. Top 10 Ürün + Depo Stok
    4. Kritik Durumlar
    """
    
    if len(kup.trading) == 0:
        return "❌ Trading raporu yüklenmemiş."
    
    sonuc = []
    df = kup.trading.copy()
    
    # Kolon isimlerini bul
    kolonlar = list(df.columns)
    print(f"Trading kolonları: {kolonlar[:15]}")
    
    # Kategori kolonu bul (ilk kolon genellikle)
    kategori_kol = df.columns[0]
    for kol in df.columns:
        kol_lower = str(kol).lower()
        if 'satır' in kol_lower or 'etiket' in kol_lower or 'kategori' in kol_lower:
            kategori_kol = kol
            break
    
    # Kolon mapping
    def find_col(keywords, exclude=[]):
        for kol in df.columns:
            kol_lower = str(kol).lower()
            if all(k in kol_lower for k in keywords) and not any(e in kol_lower for e in exclude):
                return kol
        return None
    
    # Kritik kolonları bul
    col_ciro_achieved = find_col(['achieved', 'sales', 'budget', 'value', 'try'], ['profit', 'unit'])
    col_adet_achieved = find_col(['achieved', 'sales', 'budget', 'unit'], ['value', 'profit'])
    col_ty_cover = find_col(['ty', 'store', 'cover'], ['lfl', 'ly'])
    col_ly_cover = find_col(['ly', 'store', 'cover'], ['lfl'])
    col_ty_marj = find_col(['ty', 'gross', 'margin', 'try'], ['lfl', 'ly', 'budget'])
    col_ly_marj = find_col(['ly', 'lfl', 'gross', 'margin'], ['ty', 'budget'])
    col_lfl_ciro = find_col(['lfl', 'sales', 'value', 'tyvsly'], ['unit', 'profit'])
    col_lfl_adet = find_col(['lfl', 'sales', 'unit', 'tyvsly'], ['value', 'cost'])
    col_lfl_stok = find_col(['lfl', 'stock', 'unit', 'tyvsly'], [])
    col_fiyat_artis = find_col(['lfl', 'unit', 'sales', 'price', 'tyvsly'], [])
    col_lfl_kar = find_col(['lfl', 'profit', 'tyvsly'], ['unit'])
    col_ciro = find_col(['ty', 'sales', 'value', 'try'], ['budget', 'achieved', 'lfl', 'gap'])
    col_indirim = find_col(['tw', 'indirim'], []) or find_col(['ty', 'discount'], [])
    
    print(f"Bulunan kolonlar: ciro_achieved={col_ciro_achieved}, ty_marj={col_ty_marj}, ly_marj={col_ly_marj}")
    
    if col_ciro_achieved is None:
        return f"❌ 'Achieved TY Sales Budget Value TRY' kolonu bulunamadı.\nMevcut kolonlar: {kolonlar[:15]}"
    
    # Parse fonksiyonu
    def parse_val(val):
        if pd.isna(val):
            return None
        if isinstance(val, str):
            val = val.replace('%', '').replace(',', '.').replace(' ', '').strip()
            try:
                return float(val)
            except:
                return None
        try:
            return float(val)
        except:
            return None
    
    # Tüm kategorileri topla
    kategoriler = []
    toplam_ciro = 0
    
    for _, row in df.iterrows():
        kategori = str(row.get(kategori_kol, 'N/A'))[:40]
        
        # Total/Grand satırlarını atla
        if pd.isna(kategori) or kategori == 'nan' or kategori == 'N/A':
            continue
        if any(x in kategori.lower() for x in ['total', 'grand', 'genel', 'toplam']):
            continue
        
        ciro_achieved = parse_val(row.get(col_ciro_achieved, None))
        if ciro_achieved is None:
            continue
        
        # Ondalık ise yüzdeye çevir
        if -2 < ciro_achieved < 2 and ciro_achieved != 0:
            ciro_achieved = ciro_achieved * 100
        
        # Diğer değerleri al
        ty_cover = parse_val(row.get(col_ty_cover, 0)) or 0
        ly_cover = parse_val(row.get(col_ly_cover, 0)) or 0
        
        ty_marj = parse_val(row.get(col_ty_marj, 0)) or 0
        if -2 < ty_marj < 2 and ty_marj != 0:
            ty_marj = ty_marj * 100
            
        ly_marj = parse_val(row.get(col_ly_marj, 0)) or 0
        if -2 < ly_marj < 2 and ly_marj != 0:
            ly_marj = ly_marj * 100
            
        lfl_ciro = parse_val(row.get(col_lfl_ciro, 0)) or 0
        if -2 < lfl_ciro < 2 and lfl_ciro != 0:
            lfl_ciro = lfl_ciro * 100
            
        lfl_adet = parse_val(row.get(col_lfl_adet, 0)) or 0
        if -2 < lfl_adet < 2 and lfl_adet != 0:
            lfl_adet = lfl_adet * 100
            
        lfl_stok = parse_val(row.get(col_lfl_stok, 0)) or 0
        if -2 < lfl_stok < 2 and lfl_stok != 0:
            lfl_stok = lfl_stok * 100
            
        fiyat_artis = parse_val(row.get(col_fiyat_artis, 0)) or 0
        if -2 < fiyat_artis < 2 and fiyat_artis != 0:
            fiyat_artis = fiyat_artis * 100
        
        lfl_kar = parse_val(row.get(col_lfl_kar, 0)) or 0
        if -2 < lfl_kar < 2 and lfl_kar != 0:
            lfl_kar = lfl_kar * 100
        
        ciro = parse_val(row.get(col_ciro, 0)) or 0
        toplam_ciro += ciro
        
        kategoriler.append({
            'ad': kategori,
            'ciro': ciro,
            'ciro_achieved': ciro_achieved,
            'ty_cover': ty_cover,
            'ly_cover': ly_cover,
            'ty_marj': ty_marj,
            'ly_marj': ly_marj,
            'lfl_ciro': lfl_ciro,
            'lfl_adet': lfl_adet,
            'lfl_stok': lfl_stok,
            'lfl_kar': lfl_kar,
            'fiyat_artis': fiyat_artis
        })
    
    if not kategoriler:
        return "❌ Analiz edilecek kategori bulunamadı."
    
    # Ciro payı hesapla
    for kat in kategoriler:
        kat['ciro_pay'] = (kat['ciro'] / toplam_ciro * 100) if toplam_ciro > 0 else 0
    
    # Ciroya göre sırala
    kategoriler.sort(key=lambda x: x['ciro'], reverse=True)
    
    print(f"Hiyerarşi özeti: {len(kategoriler)} ana kategori, {len(alt_kategoriler)} alt kategori, {len(mal_gruplari)} mal grubu")
    
    # ========================================
    # 1. ŞİRKET TOPLAMI
    # ========================================
    sonuc.append("=" * 55)
    sonuc.append("📊 ŞİRKET TOPLAMI - HAFTALIK PERFORMANS")
    sonuc.append("=" * 55 + "\n")
    
    # Ağırlıklı ortalama hesapla (ana kategorilerden)
    if toplam_ciro > 0:
        avg_achieved = sum(k['ciro_achieved'] * k['ciro'] for k in kategoriler) / toplam_ciro
        avg_ty_cover = sum(k['ty_cover'] * k['ciro'] for k in kategoriler) / toplam_ciro
        avg_ly_cover = sum(k['ly_cover'] * k['ciro'] for k in kategoriler) / toplam_ciro
        avg_ty_marj = sum(k['ty_marj'] * k['ciro'] for k in kategoriler) / toplam_ciro
        avg_ly_marj = sum(k['ly_marj'] * k['ciro'] for k in kategoriler) / toplam_ciro
        avg_lfl_ciro = sum(k['lfl_ciro'] * k['ciro'] for k in kategoriler) / toplam_ciro
        avg_lfl_adet = sum(k['lfl_adet'] * k['ciro'] for k in kategoriler) / toplam_ciro
        avg_lfl_stok = sum(k['lfl_stok'] * k['ciro'] for k in kategoriler) / toplam_ciro
        avg_lfl_kar = sum(k['lfl_kar'] * k['ciro'] for k in kategoriler) / toplam_ciro
        avg_fiyat = sum(k['fiyat_artis'] * k['ciro'] for k in kategoriler) / toplam_ciro
    else:
        avg_achieved = avg_ty_cover = avg_ly_cover = avg_ty_marj = avg_ly_marj = 0
        avg_lfl_ciro = avg_lfl_adet = avg_lfl_stok = avg_lfl_kar = avg_fiyat = 0
    
    # --- BÜTÇE DURUMU ---
    sonuc.append("💰 BÜTÇE PERFORMANSI")
    if avg_achieved >= 0:
        sonuc.append(f"   ✅ Ciro Bütçe Gerçekleşme: %{100 + avg_achieved:.1f}")
        sonuc.append(f"      Hedefin %{avg_achieved:.1f} ÜSTÜNDEYİZ")
    else:
        emoji = "🔴" if avg_achieved < -15 else "⚠️"
        sonuc.append(f"   {emoji} Ciro Bütçe Gerçekleşme: %{100 + avg_achieved:.1f}")
        sonuc.append(f"      Hedefin %{abs(avg_achieved):.1f} altındayız")
    
    # --- COVER DURUMU ---
    sonuc.append("\n📦 STOK DÖNÜŞ HIZI (Cover)")
    cover_degisim = avg_ty_cover - avg_ly_cover
    cover_emoji = "🔴" if avg_ty_cover > 12 else ("⚠️" if avg_ty_cover > 10 else "✅")
    sonuc.append(f"   {cover_emoji} Bu Yıl: {avg_ty_cover:.1f} hafta | Geçen Yıl: {avg_ly_cover:.1f} hafta")
    if cover_degisim > 1:
        sonuc.append(f"      ⚠️ Cover {cover_degisim:.1f} hafta ARTTI (stok birikiyor)")
    elif cover_degisim < -1:
        sonuc.append(f"      ✅ Cover {abs(cover_degisim):.1f} hafta AZALDI (stok hızlandı)")
    else:
        sonuc.append(f"      → Cover stabil")
    
    # --- BRÜT KAR MARJI ---
    sonuc.append("\n📈 BRÜT KAR MARJI")
    marj_degisim = avg_ty_marj - avg_ly_marj
    marj_emoji = "🔴" if avg_ty_marj < 30 else ("⚠️" if marj_degisim < -2 else "✅")
    sonuc.append(f"   {marj_emoji} Bu Yıl: %{avg_ty_marj:.1f} | Geçen Yıl: %{avg_ly_marj:.1f}")
    if marj_degisim > 0:
        sonuc.append(f"      ✅ Marj {marj_degisim:.1f} puan İYİLEŞTİ")
    elif marj_degisim < -2:
        sonuc.append(f"      🔴 Marj {abs(marj_degisim):.1f} puan GERİLEDİ - fiyat/maliyet baskısı var")
    else:
        sonuc.append(f"      → Marj stabil")
    
    # --- LFL BÜYÜME ---
    sonuc.append("\n📊 LFL BÜYÜME (Geçen Yıla Göre)")
    
    # LFL Ciro
    lfl_ciro_emoji = "🔴" if avg_lfl_ciro < -20 else ("⚠️" if avg_lfl_ciro < 0 else "✅")
    sonuc.append(f"   {lfl_ciro_emoji} Ciro: %{avg_lfl_ciro:+.1f}")
    
    # LFL Adet
    lfl_adet_emoji = "🔴" if avg_lfl_adet < -20 else ("⚠️" if avg_lfl_adet < 0 else "✅")
    sonuc.append(f"   {lfl_adet_emoji} Adet: %{avg_lfl_adet:+.1f}")
    
    # Ciro vs Adet yorumu
    if avg_lfl_ciro > 0 and avg_lfl_adet < 0:
        sonuc.append(f"      → Ciro artıyor ama adet düşüyor: FİYAT ARTIŞI etkisi")
    elif avg_lfl_ciro < avg_lfl_adet:
        sonuc.append(f"      → Adet ciroya göre iyi: KAMPANYA/İNDİRİM etkisi olabilir")
    
    # LFL Stok
    lfl_stok_emoji = "🔴" if avg_lfl_stok < -30 else ("⚠️" if avg_lfl_stok > 20 else "✅")
    sonuc.append(f"   {lfl_stok_emoji} Stok: %{avg_lfl_stok:+.1f}")
    
    # LFL Brüt Kar
    if avg_lfl_kar != 0:
        lfl_kar_emoji = "🔴" if avg_lfl_kar < -20 else ("⚠️" if avg_lfl_kar < 0 else "✅")
        sonuc.append(f"   {lfl_kar_emoji} Brüt Kar: %{avg_lfl_kar:+.1f}")
    
    # Fiyat artışı
    sonuc.append(f"   💰 Fiyat Artışı: %{avg_fiyat:+.1f}")
    
    # ========================================
    # 2. KATEGORİ KONSANTRASYONU
    # ========================================
    sonuc.append("\n" + "=" * 55)
    sonuc.append("🏆 KATEGORİ KONSANTRASYONU")
    sonuc.append("=" * 55 + "\n")
    
    # İlk 3 kategorinin payı
    top3_ciro = sum(k['ciro'] for k in kategoriler[:3])
    top3_pay = (top3_ciro / toplam_ciro * 100) if toplam_ciro > 0 else 0
    
    sonuc.append(f"İlk 3 kategori toplam cironun %{top3_pay:.0f}'ini oluşturuyor:\n")
    
    for i, kat in enumerate(kategoriler[:3], 1):
        cover_durum = "🔴 yüksek" if kat['ty_cover'] > 12 else ("⚠️" if kat['ty_cover'] > 10 else "")
        marj_trend = f"(GY: %{kat['ly_marj']:.0f})" if kat['ly_marj'] > 0 else ""
        
        sonuc.append(f"{i}. {kat['ad']}")
        sonuc.append(f"   📊 Ciro Payı: %{kat['ciro_pay']:.1f}")
        sonuc.append(f"   📦 Cover: {kat['ty_cover']:.1f} hf (GY: {kat['ly_cover']:.1f}) {cover_durum}")
        sonuc.append(f"   💰 Brüt Marj: %{kat['ty_marj']:.1f} {marj_trend}")
        sonuc.append(f"   📈 Bütçe: %{kat['ciro_achieved']:+.0f} | LFL Ciro: %{kat['lfl_ciro']:+.1f}")
        sonuc.append("")
    
    # ========================================
    # 3. TOP 10 ÜRÜN ANALİZİ
    # ========================================
    sonuc.append("=" * 55)
    sonuc.append("🔝 EN ÇOK SATAN 10 ÜRÜN + DEPO STOK DURUMU")
    sonuc.append("=" * 55 + "\n")
    
    # Anlık stok satış verisinden top 10 ürün
    stok_satis = getattr(kup, 'stok_satis', None)
    depo_stok = getattr(kup, 'depo_stok', None)
    urun_master = getattr(kup, 'urun_master', None)
    
    if stok_satis is not None and len(stok_satis) > 0:
        # Ürün bazında ciro topla
        urun_ciro = stok_satis.groupby('urun_kod').agg({
            'ciro': 'sum',
            'satis': 'sum',
            'stok': 'sum'
        }).reset_index()
        urun_ciro = urun_ciro.sort_values('ciro', ascending=False).head(10)
        
        # Depo stok dictionary
        depo_dict = {}
        if depo_stok is not None and len(depo_stok) > 0:
            depo_grp = depo_stok.groupby('urun_kod')['stok'].sum()
            depo_dict = depo_grp.to_dict()
        
        # Ürün adı dictionary
        urun_adi_dict = {}
        if urun_master is not None and 'urun_kod' in urun_master.columns:
            if 'mg' in urun_master.columns:
                urun_adi_dict = dict(zip(urun_master['urun_kod'].astype(str), urun_master['mg'].astype(str)))
        
        sonuc.append(f"{'Sıra':<4} {'Ürün Kodu':<12} {'Haftalık Ciro':>14} {'Satış':>8} {'Mğz Stok':>10} {'Depo Stok':>10} {'Durum':<12}")
        sonuc.append("-" * 75)
        
        for i, row in enumerate(urun_ciro.itertuples(), 1):
            urun_kod = str(row.urun_kod)
            ciro = row.ciro
            satis = row.satis
            mgz_stok = row.stok
            depo = depo_dict.get(urun_kod, depo_dict.get(int(row.urun_kod) if str(row.urun_kod).isdigit() else 0, 0))
            
            # Cover hesapla
            haftalik_satis = satis if satis > 0 else 1
            cover = (mgz_stok + depo) / haftalik_satis
            
            # Durum belirle
            if depo == 0 and mgz_stok < haftalik_satis * 2:
                durum = "🔴 KRİTİK"
            elif depo == 0:
                durum = "⚠️ Depo Yok"
            elif cover < 4:
                durum = "⚠️ Düşük"
            elif cover > 12:
                durum = "📦 Fazla"
            else:
                durum = "✅ OK"
            
            sonuc.append(f"{i:<4} {urun_kod:<12} {ciro:>14,.0f} {satis:>8,.0f} {mgz_stok:>10,.0f} {depo:>10,.0f} {durum:<12}")
        
        # Top 10 özeti
        top10_depo_yok = sum(1 for _, row in urun_ciro.iterrows() 
                            if depo_dict.get(str(row['urun_kod']), 0) == 0)
        if top10_depo_yok > 0:
            sonuc.append(f"\n⚠️ DİKKAT: En çok satan 10 üründen {top10_depo_yok} tanesinde DEPO STOK YOK!")
    else:
        sonuc.append("(Anlık stok/satış verisi yüklenmemiş)")
    
    # ========================================
    # 4. KRİTİK DURUMLAR (Sadece büyük kategoriler)
    # ========================================
    sonuc.append("\n" + "=" * 55)
    sonuc.append("⚠️ KRİTİK DURUMLAR (Ana Kategoriler)")
    sonuc.append("=" * 55 + "\n")
    
    # Ana kategorilerdeki kritik durumlar
    kritik_butce = [k for k in kategoriler if k['ciro_achieved'] < -15]
    kritik_cover = [k for k in kategoriler if k['ty_cover'] > 12]
    kritik_lfl = [k for k in kategoriler if k['lfl_ciro'] < -20]
    kritik_marj = [k for k in kategoriler if k['ty_marj'] < k['ly_marj'] - 3]
    
    if kritik_butce:
        sonuc.append(f"🔴 BÜTÇE ALTINDA ({len(kritik_butce)} kategori - sapma >%15):")
        for kat in sorted(kritik_butce, key=lambda x: x['ciro_achieved'])[:5]:
            sonuc.append(f"   • {kat['ad']}: Bütçe %{kat['ciro_achieved']:+.0f} (ciro payı %{kat['ciro_pay']:.1f})")
        sonuc.append("")
    
    if kritik_cover:
        sonuc.append(f"🔴 YÜKSEK COVER ({len(kritik_cover)} kategori - >12 hafta):")
        for kat in sorted(kritik_cover, key=lambda x: x['ty_cover'], reverse=True)[:5]:
            sonuc.append(f"   • {kat['ad']}: {kat['ty_cover']:.1f} hf → Stok eritme gerekli")
        sonuc.append("")
    
    if kritik_lfl:
        sonuc.append(f"🔴 CİDDİ KÜÇÜLME ({len(kritik_lfl)} kategori - LFL <-%20):")
        for kat in sorted(kritik_lfl, key=lambda x: x['lfl_ciro'])[:5]:
            sonuc.append(f"   • {kat['ad']}: LFL Ciro %{kat['lfl_ciro']:+.0f}")
        sonuc.append("")
    
    if kritik_marj:
        sonuc.append(f"🔴 MARJ BASKISI ({len(kritik_marj)} kategori - >3 puan düşüş):")
        for kat in sorted(kritik_marj, key=lambda x: x['ty_marj'] - x['ly_marj'])[:5]:
            degisim = kat['ty_marj'] - kat['ly_marj']
            sonuc.append(f"   • {kat['ad']}: %{kat['ty_marj']:.0f} (GY: %{kat['ly_marj']:.0f}) → {degisim:+.1f} puan")
        sonuc.append("")
    
    if not kritik_butce and not kritik_cover and not kritik_lfl and not kritik_marj:
        sonuc.append("✅ Ana kategorilerde kritik durum yok.\n")
    
    # ========================================
    # 5. İYİ GİDEN KATEGORİLER
    # ========================================
    iyi_gidenler = [k for k in kategoriler if k['ciro_achieved'] >= 0 and k['lfl_ciro'] >= 0]
    if iyi_gidenler:
        sonuc.append("✅ İYİ PERFORMANS GÖSTEREN KATEGORİLER:")
        for kat in sorted(iyi_gidenler, key=lambda x: x['ciro_achieved'], reverse=True)[:3]:
            sonuc.append(f"   • {kat['ad']}: Bütçe %{kat['ciro_achieved']:+.0f}, LFL %{kat['lfl_ciro']:+.0f}, Marj %{kat['ty_marj']:.0f}")
    
    # ========================================
    # 6. ÖZET VE ÖNERİLER
    # ========================================
    sonuc.append("\n" + "-" * 55)
    sonuc.append("💡 HAFTALIK DEĞERLENDİRME VE ÖNERİLER")
    sonuc.append("-" * 55)
    
    # Genel durum
    if avg_achieved >= 0:
        sonuc.append("\n✅ Bütçe hedeflerine ulaşılmış durumda.")
    elif avg_achieved >= -15:
        sonuc.append(f"\n⚠️ Bütçenin %{abs(avg_achieved):.0f} altındayız - performans artırıcı aksiyonlar gerekli.")
    else:
        sonuc.append(f"\n🔴 Bütçenin %{abs(avg_achieved):.0f} altındayız - ACİL AKSİYON şart!")
    
    # Cover yorumu
    if avg_ty_cover > 12:
        sonuc.append(f"🔴 Ortalama cover {avg_ty_cover:.1f} hafta - stok eritme kampanyası başlatılmalı.")
    elif avg_ty_cover > avg_ly_cover + 2:
        sonuc.append(f"⚠️ Cover geçen yıla göre artmış ({avg_ly_cover:.1f} → {avg_ty_cover:.1f}) - satış hızlandırılmalı.")
    
    # Marj yorumu
    if marj_degisim < -2:
        sonuc.append(f"⚠️ Brüt marj {abs(marj_degisim):.1f} puan geriledi - fiyat/maliyet optimizasyonu gerekli.")
    
    # Spesifik öneriler
    if kritik_butce:
        en_kotu = min(kritik_butce, key=lambda x: x['ciro_achieved'])
        sonuc.append(f"\n📌 ÖNCELİK 1: {en_kotu['ad']} - bütçenin %{abs(en_kotu['ciro_achieved']):.0f} altında")
    
    if kritik_cover:
        en_yuksek = max(kritik_cover, key=lambda x: x['ty_cover'])
        sonuc.append(f"📌 ÖNCELİK 2: {en_yuksek['kategori']} - {en_yuksek['ty_cover']:.0f} haftalık stok, eritme şart")
    
    return "\n".join(sonuc)


def cover_analiz(kup: KupVeri, sayfa: str = None) -> str:
    """SC Tablosu cover grup analizi"""
    
    if len(kup.sc_sayfalari) == 0:
        return "❌ SC Tablosu yüklenmemiş."
    
    sonuc = []
    sonuc.append("=== COVER GRUP ANALİZİ ===\n")
    
    # Mevcut sayfaları göster
    sonuc.append(f"Mevcut sayfalar: {list(kup.sc_sayfalari.keys())}\n")
    
    # Sayfa seç
    if sayfa and sayfa in kup.sc_sayfalari:
        df = kup.sc_sayfalari[sayfa]
        sonuc.append(f"Seçili sayfa: {sayfa}\n")
    else:
        # İlk uygun sayfayı bul
        for s in ['LW-TW Kategori Klasman Analiz', 'LW-TW Cover Analiz', 'Cover']:
            if s in kup.sc_sayfalari:
                df = kup.sc_sayfalari[s]
                sonuc.append(f"Seçili sayfa: {s}\n")
                break
        else:
            # İlk sayfayı al
            first_key = list(kup.sc_sayfalari.keys())[0]
            df = kup.sc_sayfalari[first_key]
            sonuc.append(f"Seçili sayfa: {first_key}\n")
    
    sonuc.append(f"Kolonlar: {list(df.columns)[:15]}...")
    sonuc.append(f"Satır sayısı: {len(df)}\n")
    
    # İlk 20 satırı göster
    sonuc.append("--- İlk 20 Satır ---")
    for i, row in df.head(20).iterrows():
        row_str = " | ".join([f"{str(v)[:15]}" for v in row.values[:8]])
        sonuc.append(row_str)
    
    # Cover grup analizi yap (eğer cover kolonu varsa)
    cover_kol = None
    for kol in df.columns:
        if 'cover' in str(kol).lower():
            cover_kol = kol
            break
    
    if cover_kol:
        sonuc.append(f"\n--- Cover Dağılımı ({cover_kol}) ---")
        try:
            cover_dist = df[cover_kol].value_counts().head(10)
            for val, count in cover_dist.items():
                sonuc.append(f"  {val}: {count} satır")
        except:
            pass
    
    return "\n".join(sonuc)


def ihtiyac_hesapla(kup: KupVeri, limit: int = 50) -> str:
    """Mağaza ihtiyacı vs Depo stok karşılaştırması"""
    
    sonuc = []
    sonuc.append("=== İHTİYAÇ ANALİZİ ===\n")
    sonuc.append("Mağaza ihtiyacı vs Depo stok karşılaştırması\n")
    
    if len(kup.stok_satis) == 0:
        return "❌ Stok/Satış verisi yüklenmemiş."
    
    if len(kup.depo_stok) == 0:
        return "❌ Depo stok verisi yüklenmemiş."
    
    df = kup.stok_satis.copy()
    
    # Mağaza bazında ihtiyaç hesapla
    if 'stok_durum' not in df.columns:
        return "❌ Stok durumu hesaplanamamış."
    
    # Sevk gereken satırları al
    sevk_gerekli = df[df['stok_durum'] == 'SEVK_GEREKLI'].copy()
    
    if len(sevk_gerekli) == 0:
        return "✅ Sevk gereken ürün bulunmuyor."
    
    # Ürün bazında ihtiyaç topla
    if 'urun_kod' not in sevk_gerekli.columns:
        return "❌ urun_kod kolonu bulunamadı."
    
    ihtiyac = sevk_gerekli.groupby('urun_kod').agg({
        'stok': 'sum',
        'min_deger': 'first'
    }).reset_index()
    ihtiyac.columns = ['urun_kod', 'mevcut_stok', 'min_deger']
    
    # Mağaza sayısını hesapla
    magaza_sayisi = sevk_gerekli.groupby('urun_kod').size().reset_index(name='magaza_sayisi')
    ihtiyac = ihtiyac.merge(magaza_sayisi, on='urun_kod')
    
    # İhtiyaç hesapla
    ihtiyac['ihtiyac'] = ihtiyac['magaza_sayisi'] * ihtiyac['min_deger'].fillna(3) - ihtiyac['mevcut_stok']
    ihtiyac['ihtiyac'] = ihtiyac['ihtiyac'].clip(lower=0)
    
    # Depo stok ile birleştir
    depo = kup.depo_stok.copy()
    depo.columns = depo.columns.str.lower().str.strip()
    
    if 'urun_kod' in depo.columns:
        depo['urun_kod'] = depo['urun_kod'].astype(str)
        ihtiyac['urun_kod'] = ihtiyac['urun_kod'].astype(str)
        
        depo_grouped = depo.groupby('urun_kod')['stok'].sum().reset_index()
        depo_grouped.columns = ['urun_kod', 'depo_stok']
        
        ihtiyac = ihtiyac.merge(depo_grouped, on='urun_kod', how='left')
        ihtiyac['depo_stok'] = ihtiyac['depo_stok'].fillna(0)
    else:
        ihtiyac['depo_stok'] = 0
    
    # Karşılama durumu
    ihtiyac['karsilama'] = np.where(
        ihtiyac['depo_stok'] >= ihtiyac['ihtiyac'],
        'TAM',
        np.where(ihtiyac['depo_stok'] > 0, 'KISMİ', 'YOK')
    )
    
    # Önceliklendir
    ihtiyac = ihtiyac.sort_values('ihtiyac', ascending=False).head(limit)
    
    sonuc.append(f"{'Ürün Kodu':<12} | {'Mağaza#':>8} | {'İhtiyaç':>10} | {'Depo':>10} | Durum")
    sonuc.append("-" * 65)
    
    for _, row in ihtiyac.iterrows():
        if row['karsilama'] == 'TAM':
            durum = "✅ Tam karşılanır"
        elif row['karsilama'] == 'KISMİ':
            durum = "🟡 Kısmi"
        else:
            durum = "🔴 Depoda yok"
        
        sonuc.append(f"{row['urun_kod']:<12} | {row['magaza_sayisi']:>8} | {row['ihtiyac']:>10,.0f} | {row['depo_stok']:>10,.0f} | {durum}")
    
    # Özet
    sonuc.append("\n--- ÖZET ---")
    tam = len(ihtiyac[ihtiyac['karsilama'] == 'TAM'])
    kismi = len(ihtiyac[ihtiyac['karsilama'] == 'KISMİ'])
    yok = len(ihtiyac[ihtiyac['karsilama'] == 'YOK'])
    
    sonuc.append(f"✅ Tam karşılanabilir: {tam} ürün")
    sonuc.append(f"🟡 Kısmi karşılanabilir: {kismi} ürün")
    sonuc.append(f"🔴 Depoda yok: {yok} ürün")
    
    toplam_ihtiyac = ihtiyac['ihtiyac'].sum()
    toplam_depo = ihtiyac['depo_stok'].sum()
    karsilama_orani = (toplam_depo / toplam_ihtiyac * 100) if toplam_ihtiyac > 0 else 0
    
    sonuc.append(f"\nToplam ihtiyaç: {toplam_ihtiyac:,.0f} adet")
    sonuc.append(f"Toplam depo stok: {toplam_depo:,.0f} adet")
    sonuc.append(f"Karşılama oranı: %{karsilama_orani:.1f}")
    
    return "\n".join(sonuc)


def genel_ozet(kup: KupVeri) -> str:
    """Genel özet - kategoriler ve bölgeler bazında durum"""
    
    if len(kup.stok_satis) == 0:
        return "Veri yüklenmemiş."
    
    sonuc = []
    
    # Toplam metrikler
    toplam_stok = kup.stok_satis['stok'].sum() if 'stok' in kup.stok_satis.columns else 0
    toplam_satis = kup.stok_satis['satis'].sum() if 'satis' in kup.stok_satis.columns else 0
    toplam_ciro = kup.stok_satis['ciro'].sum() if 'ciro' in kup.stok_satis.columns else 0
    toplam_kar = kup.stok_satis['kar'].sum() if 'kar' in kup.stok_satis.columns else 0
    
    # Depo stok
    depo_toplam = kup.depo_stok['stok'].sum() if len(kup.depo_stok) > 0 else 0
    
    # Stok durumu sayıları
    sevk_gerekli = len(kup.stok_satis[kup.stok_satis['stok_durum'] == 'SEVK_GEREKLI'])
    fazla_stok = len(kup.stok_satis[kup.stok_satis['stok_durum'] == 'FAZLA_STOK'])
    yavas = len(kup.stok_satis[kup.stok_satis['stok_durum'] == 'YAVAS'])
    normal = len(kup.stok_satis[kup.stok_satis['stok_durum'] == 'NORMAL'])
    toplam_kayit = len(kup.stok_satis)
    
    # Cover hesapla
    if toplam_satis > 0:
        genel_cover = (toplam_stok + depo_toplam) / toplam_satis
    else:
        genel_cover = 999
    
    # ANLATIMLI RAPOR
    sonuc.append("=== EVE KOZMETİK GENEL DURUM ANALİZİ ===\n")
    
    # Genel değerlendirme
    sevk_oran = sevk_gerekli / toplam_kayit * 100 if toplam_kayit > 0 else 0
    fazla_oran = (fazla_stok + yavas) / toplam_kayit * 100 if toplam_kayit > 0 else 0
    
    if sevk_oran > 50:
        sonuc.append("🚨 DURUM KRİTİK: Mağazaların yarısından fazlasında stok eksikliği var!")
        sonuc.append(f"   {sevk_gerekli:,} mağaza×ürün kombinasyonunda acil sevkiyat gerekiyor.\n")
    elif sevk_oran > 30:
        sonuc.append("⚠️ DURUM ENDİŞE VERİCİ: Önemli sayıda mağazada stok sıkıntısı var.")
        sonuc.append(f"   {sevk_gerekli:,} noktada sevkiyat bekliyor.\n")
    else:
        sonuc.append("✅ GENEL DURUM: Stok seviyeleri kontrol altında.\n")
    
    # Temel metrikler - anlatımlı
    sonuc.append("📊 TEMEL GÖSTERGELER")
    sonuc.append(f"  • Mağazalarda toplam {toplam_stok:,.0f} adet ürün bulunuyor")
    sonuc.append(f"  • Depoda {depo_toplam:,.0f} adet sevke hazır stok var")
    sonuc.append(f"  • Haftalık satış hızı: {toplam_satis:,.0f} adet")
    sonuc.append(f"  • Genel cover: {genel_cover:.1f} hafta (depo dahil)")
    
    if toplam_ciro > 0:
        kar_marji = toplam_kar / toplam_ciro * 100
        sonuc.append(f"  • Kar marjı: %{kar_marji:.1f}")
    
    # Stok durumu - anlatımlı
    sonuc.append("\n📦 STOK DURUMU ANALİZİ")
    
    if sevk_gerekli > 0:
        sonuc.append(f"  🔴 SEVKİYAT GEREKLİ: {sevk_gerekli:,} nokta (%{sevk_oran:.1f})")
        sonuc.append(f"     Bu mağazalarda stok minimum seviyenin altına düşmüş.")
    
    if fazla_stok > 0:
        sonuc.append(f"  🟡 FAZLA STOK: {fazla_stok:,} nokta")
        sonuc.append(f"     Bu ürünlerde stok eritme kampanyası düşünülebilir.")
    
    if yavas > 0:
        sonuc.append(f"  🟠 YAVAŞ DÖNEN: {yavas:,} nokta")
        sonuc.append(f"     Satış hızı düşük, indirim veya promosyon gerekebilir.")
    
    if normal > 0:
        sonuc.append(f"  ✅ NORMAL: {normal:,} nokta")
    
    # Öncelikli aksiyonlar
    sonuc.append("\n🎯 ÖNCELİKLİ AKSİYONLAR")
    
    aksiyon_no = 1
    if sevk_oran > 30:
        sonuc.append(f"  {aksiyon_no}. Acil sevkiyat planı oluştur (sevkiyat_plani aracını kullan)")
        aksiyon_no += 1
    
    if fazla_oran > 20:
        sonuc.append(f"  {aksiyon_no}. Fazla stoklar için kampanya planla (fazla_stok_analiz aracını kullan)")
        aksiyon_no += 1
    
    sonuc.append(f"  {aksiyon_no}. Detaylı kategori analizi için kategori_analiz aracını kullan")
    
    return "\n".join(sonuc)


def kategori_analiz(kup: KupVeri, kategori_kod: str) -> str:
    """Belirli kategorinin detaylı analizi"""
    
    # Kategori filtrele
    if 'kategori_kod' in kup.stok_satis.columns:
        kat_veri = kup.stok_satis[kup.stok_satis['kategori_kod'].astype(str) == str(kategori_kod)]
    else:
        return "Kategori bilgisi mevcut değil."
    
    if len(kat_veri) == 0:
        return f"Kategori '{kategori_kod}' bulunamadı."
    
    sonuc = []
    sonuc.append(f"=== KATEGORİ ANALİZİ: {kategori_kod} ===\n")
    
    # Özet metrikler
    sonuc.append(f"Toplam Satır: {len(kat_veri):,}")
    sonuc.append(f"Benzersiz Ürün: {kat_veri['urun_kod'].nunique():,}")
    sonuc.append(f"Benzersiz Mağaza: {kat_veri['magaza_kod'].nunique():,}")
    sonuc.append(f"Toplam Stok: {kat_veri['stok'].sum():,.0f}")
    sonuc.append(f"Toplam Satış: {kat_veri['satis'].sum():,.0f}")
    sonuc.append(f"Toplam Ciro: {kat_veri['ciro'].sum():,.0f} TL")
    sonuc.append(f"Toplam Kar: {kat_veri['kar'].sum():,.0f} TL")
    
    # Stok durumu
    sonuc.append("\n--- Stok Durumu ---")
    for durum in ['SEVK_GEREKLI', 'FAZLA_STOK', 'YAVAS', 'NORMAL']:
        count = len(kat_veri[kat_veri['stok_durum'] == durum])
        if count > 0:
            emoji = {'SEVK_GEREKLI': '🔴', 'FAZLA_STOK': '🟡', 'YAVAS': '🟠', 'NORMAL': '✅'}[durum]
            sonuc.append(f"{emoji} {durum}: {count:,} satır")
    
    # Mal grubu kırılımı
    if 'mg' in kat_veri.columns:
        sonuc.append("\n--- Mal Grubu Kırılımı ---")
        mg_ozet = kat_veri.groupby('mg').agg({
            'urun_kod': 'nunique',
            'stok': 'sum',
            'satis': 'sum'
        }).reset_index()
        mg_ozet.columns = ['MG', 'Urun_Sayisi', 'Stok', 'Satis']
        mg_ozet['Cover'] = mg_ozet['Stok'] / (mg_ozet['Satis'] + 0.1)
        mg_ozet = mg_ozet.nlargest(10, 'Stok')
        
        for _, row in mg_ozet.iterrows():
            durum = "🔴" if row['Cover'] > 12 else "✅"
            sonuc.append(f"{durum} MG {row['MG']}: {row['Urun_Sayisi']} ürün, Stok {row['Stok']:,.0f}, Cover {row['Cover']:.1f} hf")
    
    # En çok satan ürünler
    sonuc.append("\n--- En Çok Satan Ürünler ---")
    top_satis = kat_veri.groupby('urun_kod').agg({
        'satis': 'sum',
        'stok': 'sum',
        'ciro': 'sum'
    }).reset_index().nlargest(10, 'satis')
    
    for _, row in top_satis.iterrows():
        sonuc.append(f"  {row['urun_kod']}: Satış {row['satis']:,.0f} | Stok {row['stok']:,.0f}")
    
    # Sevk gereken ürünler
    sevk_gerekli = kat_veri[kat_veri['stok_durum'] == 'SEVK_GEREKLI']
    if len(sevk_gerekli) > 0:
        sonuc.append(f"\n--- Sevk Gereken ({len(sevk_gerekli)} satır) ---")
        top_sevk = sevk_gerekli.groupby('urun_kod').size().reset_index(name='magaza_sayisi')
        top_sevk = top_sevk.nlargest(10, 'magaza_sayisi')
        for _, row in top_sevk.iterrows():
            sonuc.append(f"  🔴 {row['urun_kod']}: {row['magaza_sayisi']} mağazada stok düşük")
    
    return "\n".join(sonuc)


def magaza_analiz(kup: KupVeri, magaza_kod: str) -> str:
    """Belirli mağazanın detaylı analizi"""
    
    mag_veri = kup.stok_satis[kup.stok_satis['magaza_kod'].astype(str) == str(magaza_kod)]
    
    if len(mag_veri) == 0:
        return f"Mağaza '{magaza_kod}' bulunamadı."
    
    sonuc = []
    sonuc.append(f"=== MAĞAZA ANALİZİ: {magaza_kod} ===\n")
    
    # Mağaza bilgileri
    if len(kup.magaza_master) > 0:
        mag_info = kup.magaza_master[kup.magaza_master['magaza_kod'].astype(str) == str(magaza_kod)]
        if len(mag_info) > 0:
            info = mag_info.iloc[0]
            sonuc.append(f"İl: {info.get('il', 'N/A')}")
            sonuc.append(f"Bölge: {info.get('bolge', 'N/A')}")
            sonuc.append(f"Tip: {info.get('tip', 'N/A')}")
            sonuc.append(f"SM: {info.get('sm', 'N/A')}")
            sonuc.append(f"Depo: {info.get('depo_kod', 'N/A')}")
    
    # Metrikler
    sonuc.append(f"\n--- Performans ---")
    sonuc.append(f"Toplam SKU: {mag_veri['urun_kod'].nunique():,}")
    sonuc.append(f"Toplam Stok: {mag_veri['stok'].sum():,.0f} adet")
    sonuc.append(f"Toplam Satış: {mag_veri['satis'].sum():,.0f} adet")
    sonuc.append(f"Toplam Ciro: {mag_veri['ciro'].sum():,.0f} TL")
    sonuc.append(f"Toplam Kar: {mag_veri['kar'].sum():,.0f} TL")
    
    # Stok durumu
    sonuc.append("\n--- Stok Durumu ---")
    for durum in ['SEVK_GEREKLI', 'FAZLA_STOK', 'YAVAS', 'NORMAL']:
        count = len(mag_veri[mag_veri['stok_durum'] == durum])
        if count > 0:
            emoji = {'SEVK_GEREKLI': '🔴', 'FAZLA_STOK': '🟡', 'YAVAS': '🟠', 'NORMAL': '✅'}[durum]
            sonuc.append(f"{emoji} {durum}: {count:,} ürün")
    
    # Sevk gereken ürünler
    sevk = mag_veri[mag_veri['stok_durum'] == 'SEVK_GEREKLI'].head(10)
    if len(sevk) > 0:
        sonuc.append(f"\n--- Sevk Gereken Ürünler ---")
        for _, row in sevk.iterrows():
            sonuc.append(f"  🔴 {row['urun_kod']}: Stok {row['stok']:.0f}, Min {row.get('min_deger', 3):.0f}")
    
    return "\n".join(sonuc)


def urun_analiz(kup: KupVeri, urun_kod: str) -> str:
    """Belirli ürünün detaylı analizi"""
    
    urun_veri = kup.stok_satis[kup.stok_satis['urun_kod'].astype(str) == str(urun_kod)]
    
    if len(urun_veri) == 0:
        return f"Ürün '{urun_kod}' bulunamadı."
    
    sonuc = []
    sonuc.append(f"=== ÜRÜN ANALİZİ: {urun_kod} ===\n")
    
    # Ürün bilgileri
    if len(kup.urun_master) > 0:
        urun_info = kup.urun_master[kup.urun_master['urun_kod'].astype(str) == str(urun_kod)]
        if len(urun_info) > 0:
            info = urun_info.iloc[0]
            sonuc.append(f"Kategori: {info.get('kategori_kod', 'N/A')}")
            sonuc.append(f"ÜMG: {info.get('umg', 'N/A')}")
            sonuc.append(f"MG: {info.get('mg', 'N/A')}")
            sonuc.append(f"Marka: {info.get('marka_kod', 'N/A')}")
            sonuc.append(f"Nitelik: {info.get('nitelik', 'N/A')}")
            sonuc.append(f"Durum: {info.get('durum', 'N/A')}")
    
    # Mağaza bazlı özet
    sonuc.append(f"\n--- Dağılım ---")
    sonuc.append(f"Mağaza Sayısı: {urun_veri['magaza_kod'].nunique():,}")
    sonuc.append(f"Toplam Mağaza Stok: {urun_veri['stok'].sum():,.0f} adet")
    sonuc.append(f"Toplam Satış: {urun_veri['satis'].sum():,.0f} adet")
    sonuc.append(f"Toplam Ciro: {urun_veri['ciro'].sum():,.0f} TL")
    
    # Depo stok
    if len(kup.depo_stok) > 0:
        depo_urun = kup.depo_stok[kup.depo_stok['urun_kod'].astype(str) == str(urun_kod)]
        if len(depo_urun) > 0:
            sonuc.append(f"\n--- Depo Stok ---")
            for _, row in depo_urun.iterrows():
                sonuc.append(f"  Depo {row['depo_kod']}: {row['stok']:,.0f} adet")
            sonuc.append(f"  Toplam Depo: {depo_urun['stok'].sum():,.0f} adet")
    
    # Stok durumu dağılımı
    sonuc.append("\n--- Mağaza Stok Durumu ---")
    for durum in ['SEVK_GEREKLI', 'FAZLA_STOK', 'YAVAS', 'NORMAL']:
        count = len(urun_veri[urun_veri['stok_durum'] == durum])
        if count > 0:
            emoji = {'SEVK_GEREKLI': '🔴', 'FAZLA_STOK': '🟡', 'YAVAS': '🟠', 'NORMAL': '✅'}[durum]
            sonuc.append(f"{emoji} {durum}: {count:,} mağaza")
    
    # Sevk gereken mağazalar
    sevk = urun_veri[urun_veri['stok_durum'] == 'SEVK_GEREKLI'].head(10)
    if len(sevk) > 0:
        sonuc.append(f"\n--- Sevk Gereken Mağazalar ---")
        for _, row in sevk.iterrows():
            sonuc.append(f"  🔴 Mağaza {row['magaza_kod']}: Stok {row['stok']:.0f}, Satış {row['satis']:.0f}")
    
    return "\n".join(sonuc)


def sevkiyat_plani(kup: KupVeri, limit: int = 50) -> str:
    """Sevkiyat planı oluştur - KPI bazlı"""
    
    sonuc = []
    sonuc.append("=== SEVKİYAT PLANI ===\n")
    
    # Mevcut kolonları kontrol et
    kolonlar = list(kup.stok_satis.columns)
    sonuc.append(f"Debug - Mevcut kolonlar: {kolonlar[:10]}...\n")
    
    # Sevk gereken satırlar
    if 'stok_durum' not in kup.stok_satis.columns:
        return "❌ Stok durumu hesaplanamamış."
    
    sevk_gerekli = kup.stok_satis[kup.stok_satis['stok_durum'] == 'SEVK_GEREKLI'].copy()
    
    if len(sevk_gerekli) == 0:
        return "✅ Sevk gereken ürün bulunmuyor."
    
    sonuc.append(f"Toplam sevk gereken: {len(sevk_gerekli):,} mağaza×ürün kombinasyonu\n")
    
    # Ürün bazlı önceliklendirme - dinamik kolon kullanımı
    agg_dict = {}
    if 'magaza_kod' in sevk_gerekli.columns:
        agg_dict['magaza_kod'] = 'count'
    if 'satis' in sevk_gerekli.columns:
        agg_dict['satis'] = 'sum'
    if 'stok' in sevk_gerekli.columns:
        agg_dict['stok'] = 'sum'
    if 'min_deger' in sevk_gerekli.columns:
        agg_dict['min_deger'] = 'first'
    
    if len(agg_dict) == 0 or 'urun_kod' not in sevk_gerekli.columns:
        return "❌ Gerekli kolonlar bulunamadı."
    
    urun_oncelik = sevk_gerekli.groupby('urun_kod').agg(agg_dict).reset_index()
    
    # Kolon isimlerini düzelt
    rename_map = {'magaza_kod': 'magaza_sayisi', 'satis': 'toplam_satis', 'stok': 'toplam_stok'}
    urun_oncelik = urun_oncelik.rename(columns=rename_map)
    
    # Eksik hesapla
    if 'magaza_sayisi' in urun_oncelik.columns and 'min_deger' in urun_oncelik.columns:
        urun_oncelik['eksik'] = urun_oncelik['magaza_sayisi'] * urun_oncelik['min_deger'].fillna(3) - urun_oncelik.get('toplam_stok', 0)
    else:
        urun_oncelik['eksik'] = 0
    
    # Sıralama
    if 'toplam_satis' in urun_oncelik.columns:
        urun_oncelik = urun_oncelik.sort_values('toplam_satis', ascending=False).head(limit)
    else:
        urun_oncelik = urun_oncelik.head(limit)
    
    # Depo stok kontrolü
    if len(kup.depo_stok) > 0 and 'urun_kod' in kup.depo_stok.columns:
        depo_grouped = kup.depo_stok.groupby('urun_kod')['stok'].sum().reset_index()
        depo_grouped.columns = ['urun_kod', 'depo_stok']
        urun_oncelik = urun_oncelik.merge(depo_grouped, on='urun_kod', how='left')
        urun_oncelik['depo_stok'] = urun_oncelik['depo_stok'].fillna(0)
    else:
        urun_oncelik['depo_stok'] = 0
    
    sonuc.append(f"{'Ürün Kodu':<12} | {'Mağaza#':>8} | {'Satış':>8} | {'Eksik':>8} | {'Depo':>8} | Durum")
    sonuc.append("-" * 75)
    
    for _, row in urun_oncelik.iterrows():
        magaza_s = row.get('magaza_sayisi', 0)
        toplam_s = row.get('toplam_satis', 0)
        eksik = row.get('eksik', 0)
        depo = row.get('depo_stok', 0)
        
        if depo >= eksik:
            durum = "✅ Sevk edilebilir"
        elif depo > 0:
            durum = "🟡 Kısmi sevk"
        else:
            durum = "🔴 Depoda yok"
        
        sonuc.append(f"{row['urun_kod']:<12} | {magaza_s:>8,} | {toplam_s:>8,.0f} | {eksik:>8,.0f} | {depo:>8,.0f} | {durum}")
    
    # Özet
    if 'eksik' in urun_oncelik.columns:
        sevk_edilebilir = len(urun_oncelik[urun_oncelik['depo_stok'] >= urun_oncelik['eksik']])
        kismi = len(urun_oncelik[(urun_oncelik['depo_stok'] > 0) & (urun_oncelik['depo_stok'] < urun_oncelik['eksik'])])
        depoda_yok = len(urun_oncelik[urun_oncelik['depo_stok'] == 0])
        
        sonuc.append(f"\n--- Özet ---")
        sonuc.append(f"✅ Tam sevk edilebilir: {sevk_edilebilir} ürün")
        sonuc.append(f"🟡 Kısmi sevk: {kismi} ürün")
        sonuc.append(f"🔴 Depoda yok: {depoda_yok} ürün")
    
    return "\n".join(sonuc)


def fazla_stok_analiz(kup: KupVeri, limit: int = 50) -> str:
    """Fazla stok analizi - indirim adayları"""
    
    sonuc = []
    sonuc.append("=== FAZLA STOK ANALİZİ (İNDİRİM ADAYLARI) ===\n")
    
    if 'stok_durum' not in kup.stok_satis.columns:
        return "❌ Stok durumu hesaplanamamış."
    
    # Fazla stok ve yavaş dönen
    fazla = kup.stok_satis[kup.stok_satis['stok_durum'].isin(['FAZLA_STOK', 'YAVAS'])].copy()
    
    if len(fazla) == 0:
        return "✅ Fazla stok bulunmuyor."
    
    sonuc.append(f"Toplam fazla/yavaş stok: {len(fazla):,} mağaza×ürün kombinasyonu\n")
    
    # Ürün bazlı özet - dinamik kolon kullanımı
    if 'urun_kod' not in fazla.columns:
        return "❌ urun_kod kolonu bulunamadı."
    
    agg_dict = {}
    if 'magaza_kod' in fazla.columns:
        agg_dict['magaza_kod'] = 'count'
    if 'stok' in fazla.columns:
        agg_dict['stok'] = 'sum'
    if 'satis' in fazla.columns:
        agg_dict['satis'] = 'sum'
    if 'ciro' in fazla.columns:
        agg_dict['ciro'] = 'sum'
    
    if len(agg_dict) == 0:
        return "❌ Gerekli kolonlar bulunamadı."
    
    urun_ozet = fazla.groupby('urun_kod').agg(agg_dict).reset_index()
    
    # Kolon isimlerini düzelt
    rename_map = {'magaza_kod': 'magaza_sayisi', 'stok': 'toplam_stok', 'satis': 'toplam_satis', 'ciro': 'toplam_ciro'}
    urun_ozet = urun_ozet.rename(columns=rename_map)
    
    # Cover hesapla
    if 'toplam_stok' in urun_ozet.columns and 'toplam_satis' in urun_ozet.columns:
        urun_ozet['cover'] = urun_ozet['toplam_stok'] / (urun_ozet['toplam_satis'] + 0.1)
    else:
        urun_ozet['cover'] = 0
    
    if 'toplam_stok' in urun_ozet.columns:
        urun_ozet = urun_ozet.sort_values('toplam_stok', ascending=False).head(limit)
    else:
        urun_ozet = urun_ozet.head(limit)
    
    sonuc.append(f"{'Ürün Kodu':<12} | {'Mağaza#':>8} | {'Stok':>10} | {'Satış':>8} | {'Cover':>8} | Öneri")
    sonuc.append("-" * 75)
    
    for _, row in urun_ozet.iterrows():
        cover = row.get('cover', 0)
        if cover > 52:
            oneri = "🔴 Agresif indirim"
        elif cover > 26:
            oneri = "🟡 Kampanya"
        else:
            oneri = "🟢 İzle"
        
        magaza_s = row.get('magaza_sayisi', 0)
        toplam_stok = row.get('toplam_stok', 0)
        toplam_satis = row.get('toplam_satis', 0)
        
        sonuc.append(f"{row['urun_kod']:<12} | {magaza_s:>8,} | {toplam_stok:>10,.0f} | {toplam_satis:>8,.0f} | {cover:>7.1f}hf | {oneri}")
    
    return "\n".join(sonuc)


def bolge_karsilastir(kup: KupVeri) -> str:
    """Bölgeler arası karşılaştırma"""
    
    if 'bolge' not in kup.stok_satis.columns:
        return "Bölge bilgisi mevcut değil."
    
    sonuc = []
    sonuc.append("=== BÖLGE KARŞILAŞTIRMASI ===\n")
    
    # Dinamik agg dict
    agg_dict = {}
    if 'magaza_kod' in kup.stok_satis.columns:
        agg_dict['magaza_kod'] = 'nunique'
    if 'urun_kod' in kup.stok_satis.columns:
        agg_dict['urun_kod'] = 'nunique'
    if 'stok' in kup.stok_satis.columns:
        agg_dict['stok'] = 'sum'
    if 'satis' in kup.stok_satis.columns:
        agg_dict['satis'] = 'sum'
    if 'ciro' in kup.stok_satis.columns:
        agg_dict['ciro'] = 'sum'
    if 'kar' in kup.stok_satis.columns:
        agg_dict['kar'] = 'sum'
    
    if len(agg_dict) == 0:
        return "❌ Gerekli kolonlar bulunamadı."
    
    bolge_ozet = kup.stok_satis.groupby('bolge').agg(agg_dict).reset_index()
    
    # Kolon isimlerini düzelt
    rename_map = {'magaza_kod': 'Magaza', 'urun_kod': 'Urun', 'stok': 'Stok', 'satis': 'Satis', 'ciro': 'Ciro', 'kar': 'Kar'}
    bolge_ozet = bolge_ozet.rename(columns=rename_map)
    bolge_ozet = bolge_ozet.rename(columns={'bolge': 'Bolge'})
    
    if 'Kar' in bolge_ozet.columns and 'Ciro' in bolge_ozet.columns:
        bolge_ozet['Kar_Marji'] = bolge_ozet['Kar'] / (bolge_ozet['Ciro'] + 0.01) * 100
    else:
        bolge_ozet['Kar_Marji'] = 0
    
    if 'Stok' in bolge_ozet.columns and 'Satis' in bolge_ozet.columns:
        bolge_ozet['Cover'] = bolge_ozet['Stok'] / (bolge_ozet['Satis'] + 0.1)
    else:
        bolge_ozet['Cover'] = 0
    
    if 'Ciro' in bolge_ozet.columns:
        bolge_ozet = bolge_ozet.sort_values('Ciro', ascending=False)
    
    sonuc.append(f"{'Bölge':<15} | {'Mağaza':>7} | {'Ciro':>12} | {'Kar %':>7} | {'Cover':>7}")
    sonuc.append("-" * 60)
    
    for _, row in bolge_ozet.iterrows():
        if pd.notna(row.get('Bolge')):
            durum = "✅" if row.get('Kar_Marji', 0) > 0 else "🔴"
            magaza = row.get('Magaza', 0)
            ciro = row.get('Ciro', 0)
            kar_marji = row.get('Kar_Marji', 0)
            cover = row.get('Cover', 0)
            sonuc.append(f"{durum} {str(row['Bolge']):<13} | {magaza:>7,} | {ciro:>12,.0f} | {kar_marji:>6.1f}% | {cover:>6.1f}hf")
    
    return "\n".join(sonuc)


def sevkiyat_hesapla(kup: KupVeri, kategori_kod = None, urun_kod: str = None, marka_kod: str = None, forward_cover: float = 7.0) -> str:
    """
    Sevkiyat hesaplaması - INLINE versiyon
    
    Mantık:
    1. hedef_stok = haftalik_satis × forward_cover
    2. rpt_ihtiyac = hedef_stok - stok - yol
    3. min_ihtiyac = min - stok - yol (eğer stok+yol < min ise)
    4. final_ihtiyac = MAX(rpt_ihtiyac, min_ihtiyac)
    """
    print("\n" + "="*50)
    print("🚀 SEVKIYAT_HESAPLA ÇAĞRILDI (INLINE)")
    print(f"   Parametreler: kategori={kategori_kod}, urun={urun_kod}, fc={forward_cover}")
    print("="*50)
    
    try:
        # 1. VERİ KONTROLÜ
        stok_satis = getattr(kup, 'stok_satis', None)
        depo_stok = getattr(kup, 'depo_stok', None)
        
        if stok_satis is None or len(stok_satis) == 0:
            return "❌ Anlık stok/satış verisi yüklenmemiş."
        
        if depo_stok is None or len(depo_stok) == 0:
            return "❌ Depo stok verisi yüklenmemiş."
        
        print(f"✅ Veri OK: stok_satis={len(stok_satis)}, depo_stok={len(depo_stok)}")
        
        # 2. ANA VERİYİ HAZIRLA
        df = stok_satis.copy()
        df['urun_kod'] = df['urun_kod'].astype(str)
        df['magaza_kod'] = df['magaza_kod'].astype(str)
        print(f"   Başlangıç: {len(df)} satır")
        
        # Ürün filtresi
        if urun_kod is not None:
            urun_kod = str(urun_kod).strip()
            df = df[df['urun_kod'] == urun_kod]
            print(f"   Ürün filtresi ({urun_kod}): {len(df)} satır")
            if len(df) == 0:
                return f"❌ {urun_kod} kodlu ürün bulunamadı."
        
        # Kategori filtresi
        if kategori_kod is not None:
            kategori_kod = int(kategori_kod)
            if 'kategori_kod' in df.columns:
                df['kategori_kod'] = pd.to_numeric(df['kategori_kod'], errors='coerce').fillna(0).astype(int)
                df = df[df['kategori_kod'] == kategori_kod]
                print(f"   Kategori filtresi ({kategori_kod}): {len(df)} satır")
        
        if len(df) == 0:
            return "❌ Filtrelere uygun veri bulunamadı."
        
        # 3. DEPO KODU EKLE
        if 'depo_kod' not in df.columns:
            mag_m = getattr(kup, 'magaza_master', None)
            if mag_m is not None and 'depo_kod' in mag_m.columns:
                mag_m = mag_m.copy()
                mag_m['magaza_kod'] = mag_m['magaza_kod'].astype(str)
                df = df.merge(mag_m[['magaza_kod', 'depo_kod']], on='magaza_kod', how='left')
                df['depo_kod'] = pd.to_numeric(df['depo_kod'], errors='coerce').fillna(9001).astype(int)
            else:
                df['depo_kod'] = 9001
        else:
            df['depo_kod'] = pd.to_numeric(df['depo_kod'], errors='coerce').fillna(9001).astype(int)
        
        print(f"   Depo kodları: {df['depo_kod'].unique().tolist()}")
        
        # 4. SAYISAL KOLONLARI HAZIRLA
        df['haftalik_satis'] = pd.to_numeric(df['satis'], errors='coerce').fillna(0)
        df['stok'] = pd.to_numeric(df['stok'], errors='coerce').fillna(0)
        df['yol'] = pd.to_numeric(df.get('yol', 0), errors='coerce').fillna(0)
        
        # Min değeri - KPI'dan geliyorsa kullan, yoksa default
        if 'min_deger' in df.columns:
            df['min'] = pd.to_numeric(df['min_deger'], errors='coerce').fillna(0)
        else:
            # Default min = 1 haftalık satış
            df['min'] = df['haftalik_satis'] * 1
        
        # 5. COVER HESAPLA
        df['mevcut'] = df['stok'] + df['yol']
        df['cover'] = df['mevcut'] / df['haftalik_satis'].replace(0, 0.001)
        
        # 6. İHTİYAÇ HESAPLA
        forward_cover = float(forward_cover) if forward_cover else 7.0
        
        # Hedef stok = haftalık satış × forward cover
        df['hedef_stok'] = df['haftalik_satis'] * forward_cover
        
        # RPT ihtiyaç = hedef - stok - yol
        df['rpt_ihtiyac'] = (df['hedef_stok'] - df['stok'] - df['yol']).clip(lower=0)
        
        # Min ihtiyaç = eğer stok+yol < min ise, min - stok - yol
        df['min_ihtiyac'] = np.where(
            df['mevcut'] < df['min'],
            (df['min'] - df['stok'] - df['yol']).clip(lower=0),
            0
        )
        
        # Final ihtiyaç = MAX(RPT, Min)
        df['ihtiyac'] = df[['rpt_ihtiyac', 'min_ihtiyac']].max(axis=1)
        
        # İhtiyaç türünü belirle
        df['ihtiyac_turu'] = np.where(
            df['ihtiyac'] == 0, 'Yok',
            np.where(df['ihtiyac'] == df['min_ihtiyac'], 'MIN', 'RPT')
        )
        
        print(f"   İhtiyaç hesaplandı:")
        print(f"      - RPT ihtiyaç olan: {(df['rpt_ihtiyac'] > 0).sum()}")
        print(f"      - MIN ihtiyaç olan: {(df['min_ihtiyac'] > 0).sum()}")
        print(f"      - Toplam ihtiyaç olan: {(df['ihtiyac'] > 0).sum()}")
        
        # 7. DEPO STOK SÖZLÜĞÜ OLUŞTUR
        depo_df = depo_stok.copy()
        depo_df.columns = [c.lower().strip() for c in depo_df.columns]
        depo_df['urun_kod'] = depo_df['urun_kod'].astype(str)
        depo_df['depo_kod'] = pd.to_numeric(depo_df['depo_kod'], errors='coerce').fillna(9001).astype(int)
        depo_df['stok'] = pd.to_numeric(depo_df['stok'], errors='coerce').fillna(0)
        
        depo_stok_dict = {}
        for _, row in depo_df.iterrows():
            key = (int(row['depo_kod']), str(row['urun_kod']))
            depo_stok_dict[key] = depo_stok_dict.get(key, 0) + float(row['stok'])
        
        print(f"   Depo stok: {len(depo_stok_dict)} ürün×depo kombinasyonu")
        
        # 8. SEVKİYAT DAĞIT
        ihtiyac_df = df[df['ihtiyac'] > 0].copy()
        ihtiyac_df = ihtiyac_df.sort_values('ihtiyac', ascending=False)
        
        sevkiyat_list = []
        for _, row in ihtiyac_df.iterrows():
            key = (int(row['depo_kod']), str(row['urun_kod']))
            ihtiyac = float(row['ihtiyac'])
            
            mevcut_depo = depo_stok_dict.get(key, 0)
            if mevcut_depo > 0:
                sevk = min(ihtiyac, mevcut_depo)
                depo_stok_dict[key] -= sevk
            else:
                sevk = 0
            
            sevkiyat_list.append({
                'magaza_kod': row['magaza_kod'],
                'urun_kod': row['urun_kod'],
                'depo_kod': row['depo_kod'],
                'stok': int(row['stok']),
                'yol': int(row['yol']),
                'min': int(row['min']),
                'haftalik_satis': round(row['haftalik_satis'], 1),
                'cover': round(row['cover'], 1),
                'hedef_stok': int(row['hedef_stok']),
                'ihtiyac': int(ihtiyac),
                'ihtiyac_turu': row['ihtiyac_turu'],
                'sevkiyat': int(sevk),
                'karsilanamayan': int(ihtiyac - sevk)
            })
        
        if not sevkiyat_list:
            return "ℹ️ Sevkiyat ihtiyacı bulunamadı. Tüm mağazaların stoku yeterli."
        
        sonuc_df = pd.DataFrame(sevkiyat_list)
        
        # 9. ÖZET OLUŞTUR
        toplam_ihtiyac = sonuc_df['ihtiyac'].sum()
        toplam_sevkiyat = sonuc_df['sevkiyat'].sum()
        karsilanamayan = sonuc_df['karsilanamayan'].sum()
        karsilama_orani = (toplam_sevkiyat / toplam_ihtiyac * 100) if toplam_ihtiyac > 0 else 0
        
        rpt_count = (sonuc_df['ihtiyac_turu'] == 'RPT').sum()
        min_count = (sonuc_df['ihtiyac_turu'] == 'MIN').sum()
        
        print(f"✅ Hesaplama tamamlandı: {len(sonuc_df)} satır, {toplam_sevkiyat:,.0f} adet sevkiyat")
        
        # 10. RAPOR OLUŞTUR
        rapor = []
        
        # Filtre bilgisi
        filtre_text = ""
        if urun_kod:
            filtre_text = f" (Ürün: {urun_kod})"
        elif kategori_kod:
            kat_adi = {11: "Renkli Kozmetik", 14: "Saç Bakım", 16: "Cilt Bakım", 19: "Parfüm", 20: "Kişisel Bakım"}.get(kategori_kod, str(kategori_kod))
            filtre_text = f" ({kat_adi})"
        
        rapor.append(f"=== SEVKİYAT HESAPLAMA SONUCU{filtre_text} ===")
        rapor.append(f"Forward Cover: {forward_cover} hafta\n")
        
        rapor.append("📊 ÖZET:")
        rapor.append(f"   Toplam İhtiyaç: {toplam_ihtiyac:,.0f} adet")
        rapor.append(f"   Toplam Sevkiyat: {toplam_sevkiyat:,.0f} adet")
        rapor.append(f"   Karşılama Oranı: %{karsilama_orani:.1f}")
        rapor.append(f"   Karşılanamayan: {karsilanamayan:,.0f} adet")
        rapor.append(f"   Mağaza Sayısı: {sonuc_df['magaza_kod'].nunique()}")
        if not urun_kod:
            rapor.append(f"   Ürün Sayısı: {sonuc_df['urun_kod'].nunique()}")
        rapor.append("")
        
        rapor.append("📋 İHTİYAÇ TÜRLERİ:")
        rapor.append(f"   RPT (Replenishment): {rpt_count} mağaza×ürün")
        rapor.append(f"   MIN (Minimum Altı): {min_count} mağaza×ürün")
        rapor.append("")
        
        # Durum değerlendirmesi
        if karsilama_orani >= 90:
            rapor.append("✅ DURUM: İyi - Depo stoku ihtiyaçların çoğunu karşılıyor.")
        elif karsilama_orani >= 70:
            rapor.append("⚠️ DURUM: Orta - Bazı mağazalarda stok yetersizliği var.")
        else:
            rapor.append("🚨 DURUM: Kritik - Depo stok yetersiz, satınalma gerekli.")
        rapor.append("")
        
        # En çok sevkiyat gereken mağazalar
        rapor.append("🏪 EN ÇOK SEVKİYAT GEREKEN MAĞAZALAR (Top 10):")
        top_mag = sonuc_df.groupby('magaza_kod')['sevkiyat'].sum().nlargest(10)
        for i, (mag, miktar) in enumerate(top_mag.items(), 1):
            rapor.append(f"   {i}. Mağaza {mag}: {int(miktar):,} adet")
        rapor.append("")
        
        # Tek ürün değilse, en çok sevkiyat gereken ürünler
        if not urun_kod:
            rapor.append("🏆 EN ÇOK SEVKİYAT GEREKEN ÜRÜNLER (Top 10):")
            top_urun = sonuc_df.groupby('urun_kod')['sevkiyat'].sum().nlargest(10)
            for i, (urun, miktar) in enumerate(top_urun.items(), 1):
                rapor.append(f"   {i}. {urun}: {int(miktar):,} adet")
            rapor.append("")
        
        # Depo bazında dağılım
        rapor.append("🏭 DEPO BAZINDA DAĞILIM:")
        depo_ozet = sonuc_df.groupby('depo_kod')['sevkiyat'].sum().sort_values(ascending=False)
        for depo, miktar in depo_ozet.items():
            rapor.append(f"   Depo {depo}: {int(miktar):,} adet")
        rapor.append("")
        
        # Karşılanamayan varsa
        if karsilanamayan > 0:
            rapor.append("⚠️ KARŞILANAMAYAN - SATINALMA GEREKLİ:")
            kars_df = sonuc_df[sonuc_df['karsilanamayan'] > 0]
            if urun_kod:
                # Tek ürün - mağaza bazında göster
                for _, row in kars_df.nlargest(10, 'karsilanamayan').iterrows():
                    rapor.append(f"   Mağaza {row['magaza_kod']}: {int(row['karsilanamayan']):,} adet eksik")
            else:
                # Çoklu ürün - ürün bazında göster
                kars_urun = kars_df.groupby('urun_kod')['karsilanamayan'].sum().nlargest(10)
                for urun, miktar in kars_urun.items():
                    rapor.append(f"   {urun}: {int(miktar):,} adet eksik")
        
        rapor.append(f"\n📋 Toplam {len(sonuc_df):,} mağaza×ürün için hesaplama yapıldı.")
        
        return "\n".join(rapor)
        
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"❌ HATA: {e}")
        print(error_detail[:500])
        return f"❌ Sevkiyat hesaplama hatası: {str(e)}\n\nDetay:\n{error_detail[:300]}"


# =============================================================================
# CLAUDE AGENT - TOOL CALLING
# =============================================================================

TOOLS = [
    {
        "name": "genel_ozet",
        "description": "Tüm verinin genel özetini gösterir. Toplam stok, satış, ciro, kar ve stok durumu dağılımını içerir. Analize başlarken ilk çağrılması gereken araç.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "kategori_analiz",
        "description": "Belirli bir kategorinin detaylı analizini yapar. Mal grubu kırılımı, en çok satanlar, sevk gereken ürünleri gösterir.",
        "input_schema": {
            "type": "object",
            "properties": {
                "kategori_kod": {
                    "type": "string",
                    "description": "Analiz edilecek kategori kodu. Örn: '14', '16'"
                }
            },
            "required": ["kategori_kod"]
        }
    },
    {
        "name": "magaza_analiz",
        "description": "Belirli bir mağazanın detaylı analizini yapar. Mağaza bilgileri, performans, stok durumu ve sevk gereken ürünleri gösterir.",
        "input_schema": {
            "type": "object",
            "properties": {
                "magaza_kod": {
                    "type": "string",
                    "description": "Analiz edilecek mağaza kodu. Örn: '1002', '1178'"
                }
            },
            "required": ["magaza_kod"]
        }
    },
    {
        "name": "urun_analiz",
        "description": "Belirli bir ürünün tüm mağazalardaki durumunu analiz eder. Ürün bilgileri, dağılım, depo stok ve sevk gereken mağazaları gösterir.",
        "input_schema": {
            "type": "object",
            "properties": {
                "urun_kod": {
                    "type": "string",
                    "description": "Analiz edilecek ürün kodu. Örn: '1000048', '1032064'"
                }
            },
            "required": ["urun_kod"]
        }
    },
    {
        "name": "sevkiyat_plani",
        "description": "KPI hedeflerine göre sevkiyat planı oluşturur. Stoku minimum değerin altına düşen mağaza×ürün kombinasyonlarını önceliklendirir ve depo stok kontrolü yapar.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Listelenecek maksimum ürün sayısı. Varsayılan: 50",
                    "default": 50
                }
            },
            "required": []
        }
    },
    {
        "name": "fazla_stok_analiz",
        "description": "Fazla stok ve yavaş dönen ürünleri analiz eder. İndirim ve kampanya adaylarını belirler.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Listelenecek maksimum ürün sayısı. Varsayılan: 50",
                    "default": 50
                }
            },
            "required": []
        }
    },
    {
        "name": "bolge_karsilastir",
        "description": "Bölgeler arası performans karşılaştırması yapar. Mağaza sayısı, ciro, kar marjı ve cover bilgilerini gösterir.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "trading_analiz",
        "description": "Trading raporunu analiz eder. Bütçe gerçekleştirme oranları, LFL (Like-for-Like) büyüme, kategori bazlı performans. Ana karar aracı - önce bunu çağır.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "cover_analiz",
        "description": "SC Tablosundan cover grup analizini yapar. Kategori × Cover Grup matrisi, stok dağılımı, marj analizi. Hangi cover grubunda sorun var gösterir.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sayfa": {
                    "type": "string",
                    "description": "Analiz edilecek SC sayfa adı. Boş bırakılırsa otomatik seçilir."
                }
            },
            "required": []
        }
    },
    {
        "name": "ihtiyac_hesapla",
        "description": "Mağaza ihtiyacı vs Depo stok karşılaştırması yapar. Hangi ürünlerin sevk edilebilir, hangilerinin depoda yok olduğunu gösterir.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Listelenecek maksimum ürün sayısı. Varsayılan: 50",
                    "default": 50
                }
            },
            "required": []
        }
    },
    {
        "name": "sevkiyat_hesapla",
        "description": "R4U Allocator motorunu çalıştırarak otomatik sevkiyat hesaplaması yapar. Segmentasyon, ihtiyaç hesaplama ve depo stok dağıtımını içerir. Kategori veya marka filtresi ile çalıştırılabilir. Sevkiyat planı oluşturmak için kullan.",
        "input_schema": {
            "type": "object",
            "properties": {
                "kategori_kod": {
                    "type": "integer",
                    "description": "Kategori filtresi. 11=Renkli Kozmetik, 14=Saç, 16=Cilt, 19=Parfüm, 20=Kişisel Bakım"
                },
                "urun_kod": {
                    "type": "string",
                    "description": "Tek bir ürün için sevkiyat hesaplamak istiyorsan ürün kodunu gir. Örn: '1017239'"
                },
                "marka_kod": {
                    "type": "string",
                    "description": "Marka filtresi (opsiyonel)"
                },
                "forward_cover": {
                    "type": "number",
                    "description": "Hedef cover değeri (gün). Varsayılan: 7",
                    "default": 7.0
                }
            },
            "required": []
        }
    }
]

SYSTEM_PROMPT = """Sen EVE Kozmetik için çalışan deneyimli bir Retail Planner'sın. Adın "Sanal Planner". 
Günlük 20M TL ciro yapan büyük bir perakende şirketi için stratejik analizler yapıyorsun.

## 🎯 KİMLİĞİN
- Deneyimli, güvenilir bir retail uzmanısın
- Kullanıcıya "Hakan Bey" diye hitap et
- Profesyonel ama samimi bir ton kullan
- Rakamları yorumla, sadece sıralama!

## 🗣️ KONUŞMA TARZI
Cevabını İKİ BÖLÜM halinde ver:

### BÖLÜM 1: SÖZLÜ AÇIKLAMA (Üstte)
- Doğal, akıcı cümlelerle anlat
- Rakamları yazıyla: "15.234" → "yaklaşık 15 bin"
- Yüzdeleri doğal: "%78.5" → "yüzde 78 civarı"
- Önce SONUÇ ve YORUM
- Ne yapılması gerektiğini öner

### BÖLÜM 2: DETAY TABLOLARI (Altta)
- "📊 Detayları aşağıda paylaşıyorum:"
- Tablolar sesli okunmayacak

## 📊 HAFTALIK ANALİZ STANDARDI (ÇOK ÖNEMLİ!)

"Bu hafta nasıl gitti?", "Genel durum", "Haftalık analiz" gibi sorularda bu sırayla analiz yap:

### 1️⃣ ŞİRKET TOPLAMI (Trading'den)
Önce genel resmi çiz:
- Bütçe Gerçekleşme: "Achieved TY Sales Budget Value TRY" (hedef %100)
- Cover: "TY Store Back Cover" (hafta)
- Brüt Kar Marjı: "TY Gross Margin TRY" (%)
- LFL Ciro Büyüme: "LFL Sales Value TYvsLY LC%"
- LFL Adet Büyüme: "LFL Sales Unit TYvsLY%"
- LFL Stok Büyüme: "LFL Store Stock Unit TYvsLY%"
- Fiyat Artışı: "LFL Unit Sales Price TYvsLY LC%"

Örnek yorum: "Hakan Bey, bu hafta şirket toplamında bütçenin yüzde 94'ünü tutturduk. 
8 haftalık cover ile dönüyoruz. LFL bazda ciroda yüzde 5 büyürken, adette yüzde 2 küçüldük - 
bu fiyat artışından geliyor. Brüt marjımız yüzde 38 seviyesinde."

### 2️⃣ KATEGORİ KONSANTRASYONU
- İlk 3 kategori toplam cironun %kaçını yapıyor?
- Bu 3 kategori stoğun %kaçına sahip?
- Her birinin cover ve brüt kar durumu

Örnek: "İlk 3 kategori (Renkli Kozmetik, Parfüm, Cilt Bakım) cironun yüzde 65'ini 
yaparken stoğun yüzde 58'ine sahip. Bu dengeli bir dağılım."

### 3️⃣ KRİTİK DURUMLAR (Sadece önemli olanlar)
Toplam cironun %2'sinden AZ yapan kategorileri ATLAMA (küçük gruplar).
Sadece büyük kategorilerdeki sorunlara odaklan.

## ⚠️ KRİTİK EŞİK DEĞERLERİ

| Metrik | Kritik Eşik | Aksiyon |
|--------|-------------|---------|
| Cover | > 12 hafta | 🔴 "Stok fazlası var, indirim/eritme gerekli" |
| Cover | < 4 hafta | 🔴 "Stok az, acil sevkiyat gerekli" |
| Bütçe Sapması | > ±%15 | ⚠️ "Bütçeden sapma var, dikkat" |
| LFL Ciro | < -%20 | 🔴 "Ciddi küçülme, aksiyon şart" |
| LFL Stok | < -%30 | 🔴 "Stok erimesi var, tedarik kontrolü" |
| Brüt Marj | < %30 | ⚠️ "Marj baskısı var" |

## 📋 VERİ KAYNAKLARI VE KOLONLAR

### Trading Raporu (Şirket/Kategori Toplamları)
- `Achieved TY Sales Budget Value TRY` → Bütçe tutturma %
- `TY Store Back Cover` → Bu yıl cover (hafta)
- `TY Gross Margin TRY` → Brüt kar %
- `LFL Sales Value TYvsLY LC%` → LFL ciro büyüme
- `LFL Sales Unit TYvsLY%` → LFL adet büyüme
- `LFL Store Stock Unit TYvsLY%` → LFL stok büyüme
- `LFL Unit Sales Price TYvsLY LC%` → Fiyat artışı %
- `TY Sales Value TRY` → Bu hafta ciro

### SC Tablosu (Detay Analiz)
- `TW Cover` → Bu hafta cover
- `TW Gerç Marj` → Bu hafta brüt kar %
- `TW İndirim` → Bu hafta indirim %
- `TW/LW Ciro Değ%` → Haftalık ciro değişim
- `TW/LW Adet Değ%` → Haftalık adet değişim
- `TW Ciro` → Bu hafta ciro
- `Mğz Stok TL` → Mağaza stok değeri

## 🎯 ANALİZ PRENSİPLERİ

1. **Büyükten Küçüğe**: Önce şirket toplamı → sonra büyük kategoriler → sonra detay
2. **Pareto**: İlk 3 kategorinin payını mutlaka belirt
3. **Karşılaştırma**: TW vs LW, TY vs LY, Bütçe vs Gerçekleşen
4. **Filtre**: Ciro payı <%2 olan kategorileri detayda atlama
5. **Yorum**: Rakam değil, anlam ver - "neden" ve "ne yapmalı"

## ❌ YAPMA!
- Küçük kategorileri tek tek saymak (MAKAS, BABET ÇORAP gibi)
- Sadece rakam sıralamak
- Yorum yapmadan tablo vermek
- Her kategoriyi aynı detayda anlatmak

## ✅ YAP!
- Önce büyük resmi çiz
- Sadece önemli sapmaları vurgula
- Aksiyon öner
- Büyük kategorilere odaklan

## SEVKİYAT HESAPLAMA
"Sevkiyat yap", "sevk planı" denildiğinde → sevkiyat_hesapla tool'unu kullan.
Hesaplama mantığı:
- hedef_stok = haftalik_satis × forward_cover
- rpt_ihtiyac = hedef_stok - stok - yol  
- min_ihtiyac = min - stok - yol (eğer stok+yol < min ise)
- final_ihtiyac = MAX(rpt_ihtiyac, min_ihtiyac)

## KATEGORİ KODLARI
- 11: RENKLİ KOZMETİK | 14: SAÇ BAKIM | 16: CİLT BAKIM
- 19: PARFÜM | 20: KİŞİSEL BAKIM | 21: AKSESUAR
- 22: ERKEK BAKIM | 23: EV BAKIM

Her zaman Türkçe, profesyonel ve stratejik ol!"""


def agent_calistir(api_key: str, kup: KupVeri, kullanici_mesaji: str) -> str:
    """Agent'ı çalıştır ve sonuç al"""
    
    import time
    start_time = time.time()
    
    print(f"\n🤖 AGENT BAŞLADI: {kullanici_mesaji[:50]}...")
    print(f"   API Key: {api_key[:20]}...")
    
    try:
        client = anthropic.Anthropic(api_key=api_key, timeout=60.0)  # 60 saniye timeout
        print("   ✅ Anthropic client oluşturuldu")
    except Exception as e:
        print(f"   ❌ Client hatası: {e}")
        return f"❌ API Client hatası: {str(e)}"
    
    messages = [{"role": "user", "content": kullanici_mesaji}]
    
    tum_cevaplar = []
    max_iterasyon = 12  # 8'den 12'ye çıkardım
    iterasyon = 0
    
    while iterasyon < max_iterasyon:
        iterasyon += 1
        print(f"\n   📡 İterasyon {iterasyon}/{max_iterasyon} - API çağrısı yapılıyor...")
        
        # Süre kontrolü - 120 saniyeyi geçerse dur
        elapsed = time.time() - start_time
        if elapsed > 120:
            print(f"   ⏱️ Zaman aşımı! ({elapsed:.1f}s)")
            tum_cevaplar.append("\n⏱️ Zaman limiti aşıldı. Mevcut bulgular yukarıda.")
            break
        
        try:
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2048,  # 1024'ten 2048'e çıkardım
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=messages
            )
            print(f"   ✅ API yanıt aldı: stop_reason={response.stop_reason}")
        except Exception as api_error:
            tum_cevaplar.append(f"\n❌ API Hatası: {str(api_error)}")
            break
        
        # Text içeriklerini topla
        for block in response.content:
            if block.type == "text":
                tum_cevaplar.append(block.text)
        
        # Tool kullanımlarını topla
        tool_uses = [block for block in response.content if block.type == "tool_use"]
        
        # Tool kullanımı yoksa bitir
        if not tool_uses:
            break
        
        # Assistant mesajını ekle
        messages.append({"role": "assistant", "content": response.content})
        
        # Tüm tool'lar için sonuçları topla
        tool_results = []
        for tool_use in tool_uses:
            tool_name = tool_use.name
            tool_input = tool_use.input
            tool_use_id = tool_use.id
            
            # Tool'u çağır
            try:
                if tool_name == "genel_ozet":
                    tool_result = genel_ozet(kup)
                elif tool_name == "trading_analiz":
                    tool_result = trading_analiz(kup)
                elif tool_name == "cover_analiz":
                    tool_result = cover_analiz(kup, tool_input.get("sayfa", None))
                elif tool_name == "ihtiyac_hesapla":
                    tool_result = ihtiyac_hesapla(kup, tool_input.get("limit", 30))
                elif tool_name == "kategori_analiz":
                    tool_result = kategori_analiz(kup, tool_input.get("kategori_kod", ""))
                elif tool_name == "magaza_analiz":
                    tool_result = magaza_analiz(kup, tool_input.get("magaza_kod", ""))
                elif tool_name == "urun_analiz":
                    tool_result = urun_analiz(kup, tool_input.get("urun_kod", ""))
                elif tool_name == "sevkiyat_plani":
                    tool_result = sevkiyat_plani(kup, tool_input.get("limit", 30))
                elif tool_name == "fazla_stok_analiz":
                    tool_result = fazla_stok_analiz(kup, tool_input.get("limit", 30))
                elif tool_name == "bolge_karsilastir":
                    tool_result = bolge_karsilastir(kup)
                elif tool_name == "sevkiyat_hesapla":
                    tool_result = sevkiyat_hesapla(
                        kup,
                        kategori_kod=tool_input.get("kategori_kod", None),
                        urun_kod=tool_input.get("urun_kod", None),
                        marka_kod=tool_input.get("marka_kod", None),
                        forward_cover=tool_input.get("forward_cover", 7.0)
                    )
                else:
                    tool_result = f"Bilinmeyen araç: {tool_name}"
                
                # Sonucu logla
                print(f"      🔧 {tool_name}: {len(tool_result)} karakter")
                
                # Sonuç çok uzunsa kısalt (API limiti için)
                if len(tool_result) > 8000:
                    tool_result = tool_result[:8000] + "\n\n... (kısaltıldı)"
                    print(f"      ⚠️ Sonuç kısaltıldı: 8000 karakter")
                    
            except Exception as e:
                tool_result = f"Hata: {str(e)}"
                print(f"      ❌ Tool hatası: {e}")
            
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_use_id,
                "content": tool_result
            })
        
        # Tüm tool sonuçlarını tek bir user mesajında gönder
        messages.append({
            "role": "user",
            "content": tool_results
        })
        
        # Stop reason end_turn ise bitir
        if response.stop_reason == "end_turn":
            break
    
    return "\n".join(tum_cevaplar)


# =============================================================================
# TEST
# =============================================================================

if __name__ == "__main__":
    # Test için
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    
    if not api_key:
        print("ANTHROPIC_API_KEY environment variable gerekli!")
    else:
        # Veriyi yükle (CSV'lerin olduğu klasör)
        kup = KupVeri("./data")
        
        # Agent'ı çalıştır
        sonuc = agent_calistir(
            api_key, 
            kup, 
            "Genel duruma bak, sorunları tespit et ve sevkiyat planı oluştur."
        )
        
        print(sonuc)
