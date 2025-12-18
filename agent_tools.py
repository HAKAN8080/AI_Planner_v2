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
        # 5. COVER DİAGRAM (Excel) - Mağaza×AltGrup cover analizi
        # =====================================================================
        cover_files = glob.glob(os.path.join(self.veri_klasoru, "*Cover*diyagram*")) + \
                      glob.glob(os.path.join(self.veri_klasoru, "*Cover*Diagram*")) + \
                      glob.glob(os.path.join(self.veri_klasoru, "*cover*diagram*")) + \
                      glob.glob(os.path.join(self.veri_klasoru, "*Cover diyagram*"))
        
        self.cover_diagram = pd.DataFrame()
        if cover_files:
            try:
                self.cover_diagram = pd.read_excel(cover_files[0], sheet_name=0)
                print(f"   ✅ Cover Diagram yüklendi: {len(self.cover_diagram)} satır")
            except Exception as e:
                print(f"   ⚠️ Cover Diagram okunamadı: {e}")
        
        # =====================================================================
        # 6. KAPASİTE-PERFORMANS (Excel) - Mağaza doluluk analizi
        # =====================================================================
        kapasite_files = glob.glob(os.path.join(self.veri_klasoru, "*Kapasite*Periyod*")) + \
                         glob.glob(os.path.join(self.veri_klasoru, "*kapasite*")) + \
                         glob.glob(os.path.join(self.veri_klasoru, "*Özet Kapasite*")) + \
                         glob.glob(os.path.join(self.veri_klasoru, "*Kapasite-Zaman*")) + \
                         glob.glob(os.path.join(self.veri_klasoru, "*Kapasite*"))
        
        self.kapasite = pd.DataFrame()
        if kapasite_files:
            try:
                self.kapasite = pd.read_excel(kapasite_files[0], sheet_name=0)
                print(f"   ✅ Kapasite yüklendi: {len(self.kapasite)} satır")
            except Exception as e:
                print(f"   ⚠️ Kapasite okunamadı: {e}")
        
        # =====================================================================
        # 7. SİPARİŞ TAKİP (Excel) - Satınalma ve sipariş durumu
        # =====================================================================
        siparis_files = glob.glob(os.path.join(self.veri_klasoru, "*Sipariş*Takip*")) + \
                        glob.glob(os.path.join(self.veri_klasoru, "*siparis*takip*")) + \
                        glob.glob(os.path.join(self.veri_klasoru, "*Satınalma*"))
        
        self.siparis_takip = pd.DataFrame()
        if siparis_files:
            try:
                self.siparis_takip = pd.read_excel(siparis_files[0], sheet_name=0)
                print(f"   ✅ Sipariş Takip yüklendi: {len(self.siparis_takip)} satır")
            except Exception as e:
                print(f"   ⚠️ Sipariş Takip okunamadı: {e}")
        
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
        print(f"   - Cover Diagram: {len(self.cover_diagram):,} satır")
        print(f"   - Kapasite: {len(self.kapasite):,} satır")
        print(f"   - Sipariş Takip: {len(self.siparis_takip):,} satır")
    
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

def trading_analiz(kup: KupVeri, ana_grup: str = None, ara_grup: str = None) -> str:
    """
    Trading raporu analizi - 3 Seviyeli Hiyerarşi
    
    Hiyerarşi Kolonları:
    - Mevcut Ana Grup: RENKLİ KOZMETİK, CİLT BAKIM, SAÇ BAKIM, PARFÜM...
    - Mevcut Ara Grup: GÖZ ÜRÜNLERİ, YÜZ ÜRÜNLERİ, ŞAMPUAN...
    - Alt Grup: MASKARA, FAR, FONDOTEN... (en detay seviye)
    
    Kullanım:
    - trading_analiz() → Şirket özeti + Ana Gruplar
    - trading_analiz(ana_grup="RENKLİ KOZMETİK") → Ara Grup detayı
    - trading_analiz(ana_grup="RENKLİ KOZMETİK", ara_grup="GÖZ ÜRÜNLERİ") → Alt Grup detayı
    """
    
    if len(kup.trading) == 0:
        return "❌ Trading raporu yüklenmemiş."
    
    sonuc = []
    df = kup.trading.copy()
    
    # Kolon isimlerini normalize et
    df.columns = [str(c).strip() for c in df.columns]
    kolonlar = list(df.columns)
    print(f"Trading kolonları: {kolonlar[:10]}")
    
    # Hiyerarşi kolonlarını bul
    col_ana_grup = None
    col_ara_grup = None
    col_alt_grup = None
    
    for kol in df.columns:
        kol_lower = str(kol).lower()
        if 'ana grup' in kol_lower or 'ana_grup' in kol_lower:
            col_ana_grup = kol
        elif 'ara grup' in kol_lower or 'ara_grup' in kol_lower:
            col_ara_grup = kol
        elif 'alt grup' in kol_lower or 'alt_grup' in kol_lower:
            col_alt_grup = kol
    
    print(f"Hiyerarşi kolonları: ana={col_ana_grup}, ara={col_ara_grup}, alt={col_alt_grup}")
    
    # Kolon mapping fonksiyonu
    def find_col(keywords, exclude=[]):
        for kol in df.columns:
            kol_lower = str(kol).lower()
            if all(k in kol_lower for k in keywords) and not any(e in kol_lower for e in exclude):
                return kol
        return None
    
    # Kritik kolonları bul
    col_ciro_achieved = find_col(['achieved', 'sales', 'budget', 'value', 'try'], ['profit', 'unit'])
    col_ty_cover = find_col(['ty', 'store', 'cover'], ['lfl', 'ly'])
    col_ly_cover = find_col(['ly', 'store', 'cover'], ['lfl'])
    col_ty_marj = find_col(['ty', 'gross', 'margin', 'try'], ['lfl', 'ly', 'budget'])
    col_ly_marj = find_col(['ly', 'lfl', 'gross', 'margin'], ['ty', 'budget'])
    col_lfl_ciro = find_col(['lfl', 'sales', 'value', 'tyvsly'], ['unit', 'profit'])
    col_lfl_adet = find_col(['lfl', 'sales', 'unit', 'tyvsly'], ['value', 'cost'])
    col_lfl_stok = find_col(['lfl', 'stock', 'unit', 'tyvsly'], [])
    col_fiyat_artis = find_col(['lfl', 'unit', 'sales', 'price', 'tyvsly'], [])
    col_lfl_kar = find_col(['lfl', 'profit', 'tyvsly'], ['unit'])
    
    # PAY KOLONLARI
    col_adet_pay = find_col(['ty', 'lfl', 'sales', 'unit'], ['tyvsly', 'price', 'cost', 'budget'])
    col_stok_pay = find_col(['ty', 'avg', 'store', 'stock', 'cost', 'lc'], ['tyvsly'])
    col_ciro_pay = find_col(['ty', 'lfl', 'sales', 'value', 'lc'], ['tyvsly'])
    col_kar_pay = find_col(['ty', 'lfl', 'gross', 'profit', 'lc'], ['tyvsly'])
    
    # Parse fonksiyonu
    def parse_val(val):
        if pd.isna(val):
            return 0
        if isinstance(val, str):
            val = val.replace('%', '').replace(',', '.').replace(' ', '').strip()
            try:
                return float(val)
            except:
                return 0
        try:
            return float(val)
        except:
            return 0
    
    def parse_pct(val):
        """Yüzde değeri parse et - ondalık ise 100 ile çarp"""
        v = parse_val(val)
        if -2 < v < 2 and v != 0:
            return v * 100
        return v
    
    # Satır verilerini çıkar
    def extract_row(row):
        return {
            'ana_grup': str(row.get(col_ana_grup, '')).strip() if col_ana_grup else '',
            'ara_grup': str(row.get(col_ara_grup, '')).strip() if col_ara_grup else '',
            'alt_grup': str(row.get(col_alt_grup, '')).strip() if col_alt_grup else '',
            'ciro_achieved': parse_pct(row.get(col_ciro_achieved, 0)),
            'ty_cover': parse_val(row.get(col_ty_cover, 0)),
            'ly_cover': parse_val(row.get(col_ly_cover, 0)),
            'ty_marj': parse_pct(row.get(col_ty_marj, 0)),
            'ly_marj': parse_pct(row.get(col_ly_marj, 0)),
            'lfl_ciro': parse_pct(row.get(col_lfl_ciro, 0)),
            'lfl_adet': parse_pct(row.get(col_lfl_adet, 0)),
            'lfl_stok': parse_pct(row.get(col_lfl_stok, 0)),
            'lfl_kar': parse_pct(row.get(col_lfl_kar, 0)),
            'fiyat_artis': parse_pct(row.get(col_fiyat_artis, 0)),
            'adet_pay': parse_pct(row.get(col_adet_pay, 0)),
            'stok_pay': parse_pct(row.get(col_stok_pay, 0)),
            'ciro_pay': parse_pct(row.get(col_ciro_pay, 0)),
            'kar_pay': parse_pct(row.get(col_kar_pay, 0))
        }
    
    # Toplam satırlarını filtrele
    def is_toplam(row_data):
        """Toplam satırı mı kontrol et"""
        ana = row_data['ana_grup'].lower()
        ara = row_data['ara_grup'].lower()
        if 'toplam' in ana or 'genel toplam' in ana:
            return True
        if 'toplam' in ara:
            return True
        return False
    
    def is_ana_grup_toplam(row_data):
        """Ana grup toplam satırı mı (Toplam RENKLİ KOZMETİK gibi)"""
        ana = row_data['ana_grup']
        ara = row_data['ara_grup']
        alt = row_data['alt_grup']
        return ana.startswith('Toplam ') and ara == '' and alt == ''
    
    def is_ara_grup_toplam(row_data):
        """Ara grup toplam satırı mı (Toplam GÖZ ÜRÜNLERİ gibi)"""
        ara = row_data['ara_grup']
        alt = row_data['alt_grup']
        return ara.startswith('Toplam ') and alt == ''
    
    # ====================================================================
    # VERİYİ SEVİYEYE GÖRE FİLTRELE
    # ====================================================================
    
    all_rows = [extract_row(row) for _, row in df.iterrows()]
    
    # Genel Toplam satırını bul
    genel_toplam = None
    for r in all_rows:
        if r['ana_grup'] == 'Genel Toplam' or 'genel toplam' in r['ana_grup'].lower():
            genel_toplam = r
            break
    
    if ana_grup is None:
        # ŞİRKET ÖZETİ + ANA GRUPLAR
        # Ana grup toplamlarını bul (Toplam RENKLİ KOZMETİK, Toplam CİLT BAKIM...)
        ana_gruplar = [r for r in all_rows if is_ana_grup_toplam(r)]
        
        # Toplam kelimesini kaldır ve sırala
        for ag in ana_gruplar:
            ag['ad'] = ag['ana_grup'].replace('Toplam ', '')
        ana_gruplar.sort(key=lambda x: x['ciro_pay'], reverse=True)
        
        # Şirket özeti
        sonuc.append("=" * 60)
        sonuc.append("📊 ŞİRKET TOPLAMI - HAFTALIK PERFORMANS")
        sonuc.append("=" * 60 + "\n")
        
        if genel_toplam:
            gt = genel_toplam
            # Bütçe
            butce_emoji = "✅" if gt['ciro_achieved'] >= 0 else ("🔴" if gt['ciro_achieved'] < -15 else "⚠️")
            sonuc.append(f"💰 BÜTÇE: {butce_emoji} %{100 + gt['ciro_achieved']:.0f} gerçekleşme")
            
            # Cover
            cover_emoji = "🔴" if gt['ty_cover'] > 12 else ("⚠️" if gt['ty_cover'] > 10 else "✅")
            sonuc.append(f"📦 COVER: {cover_emoji} {gt['ty_cover']:.1f} hf (GY: {gt['ly_cover']:.1f})")
            
            # Marj
            marj_deg = gt['ty_marj'] - gt['ly_marj']
            marj_emoji = "🔴" if marj_deg < -3 else ("⚠️" if marj_deg < 0 else "✅")
            sonuc.append(f"💵 MARJ: {marj_emoji} %{gt['ty_marj']:.1f} (GY: %{gt['ly_marj']:.1f}, {marj_deg:+.1f})")
            
            # LFL
            lfl_emoji = "🔴" if gt['lfl_ciro'] < -10 else ("⚠️" if gt['lfl_ciro'] < 0 else "✅")
            sonuc.append(f"📈 LFL CİRO: {lfl_emoji} %{gt['lfl_ciro']:+.1f}")
            sonuc.append(f"   LFL ADET: %{gt['lfl_adet']:+.1f} | FİYAT ARTIŞI: %{gt['fiyat_artis']:+.1f}")
        
        # Ana Gruplar Tablosu
        sonuc.append("\n" + "=" * 60)
        sonuc.append("🏆 ANA GRUP PERFORMANSI")
        sonuc.append("=" * 60 + "\n")
        
        sonuc.append(f"{'Ana Grup':<28} {'Ciro%':>6} {'Adet%':>6} {'Stok%':>6} {'Kar%':>6} {'Cover':>6} {'Bütçe':>7}")
        sonuc.append("-" * 75)
        
        for ag in ana_gruplar[:12]:
            ad = ag['ad'][:27]
            cover_str = f"{ag['ty_cover']:.1f}"
            butce_str = f"{ag['ciro_achieved']:+.0f}%"
            sonuc.append(f"{ad:<28} {ag['ciro_pay']:>5.1f}% {ag['adet_pay']:>5.1f}% {ag['stok_pay']:>5.1f}% {ag['kar_pay']:>5.1f}% {cover_str:>6} {butce_str:>7}")
        
        # Kritik durumlar
        sonuc.append("\n" + "-" * 60)
        kritik = [ag for ag in ana_gruplar if ag['ciro_achieved'] < -15 or ag['ty_cover'] > 12]
        if kritik:
            sonuc.append("⚠️ KRİTİK ANA GRUPLAR:")
            for k in kritik[:5]:
                issues = []
                if k['ciro_achieved'] < -15:
                    issues.append(f"Bütçe {k['ciro_achieved']:+.0f}%")
                if k['ty_cover'] > 12:
                    issues.append(f"Cover {k['ty_cover']:.0f}hf")
                sonuc.append(f"   • {k['ad']}: {', '.join(issues)}")
        
        sonuc.append(f"\n💡 Detay için: trading_analiz(ana_grup='RENKLİ KOZMETİK')")
        
    elif ara_grup is None:
        # ANA GRUP DETAYI - ARA GRUPLARI GÖSTER
        ana_grup_upper = ana_grup.upper()
        
        # Bu ana grubun ara grup toplamlarını bul
        ara_gruplar = []
        for r in all_rows:
            if r['ana_grup'].upper() == ana_grup_upper and is_ara_grup_toplam(r):
                r['ad'] = r['ara_grup'].replace('Toplam ', '')
                ara_gruplar.append(r)
        
        if not ara_gruplar:
            return f"❌ '{ana_grup}' ana grubunda ara grup bulunamadı."
        
        ara_gruplar.sort(key=lambda x: x['ciro_pay'], reverse=True)
        
        sonuc.append("=" * 60)
        sonuc.append(f"📊 {ana_grup_upper} - ARA GRUP DETAYI")
        sonuc.append("=" * 60 + "\n")
        
        sonuc.append(f"{'Ara Grup':<28} {'Ciro%':>6} {'Adet%':>6} {'Stok%':>6} {'Kar%':>6} {'Cover':>6} {'LFL':>7}")
        sonuc.append("-" * 75)
        
        for ag in ara_gruplar:
            ad = ag['ad'][:27]
            cover_str = f"{ag['ty_cover']:.1f}"
            lfl_str = f"{ag['lfl_ciro']:+.0f}%"
            sonuc.append(f"{ad:<28} {ag['ciro_pay']:>5.1f}% {ag['adet_pay']:>5.1f}% {ag['stok_pay']:>5.1f}% {ag['kar_pay']:>5.1f}% {cover_str:>6} {lfl_str:>7}")
        
        # Stok/Ciro dengesizliği
        sonuc.append("\n" + "-" * 60)
        for ag in ara_gruplar:
            if ag['ciro_pay'] > 0:
                oran = ag['stok_pay'] / ag['ciro_pay']
                if oran > 1.3:
                    sonuc.append(f"⚠️ {ag['ad']}: Stok fazla (stok/ciro: {oran:.1f}x) → ERİTME")
                elif oran < 0.7:
                    sonuc.append(f"⚠️ {ag['ad']}: Stok az (stok/ciro: {oran:.1f}x) → SEVKİYAT")
        
        sonuc.append(f"\n💡 Detay için: trading_analiz(ana_grup='{ana_grup}', ara_grup='GÖZ ÜRÜNLERİ')")
        
    else:
        # ARA GRUP DETAYI - ALT GRUPLARI GÖSTER
        ana_grup_upper = ana_grup.upper()
        ara_grup_upper = ara_grup.upper()
        
        # Bu ara grubun alt gruplarını bul (toplam olmayanlar)
        alt_gruplar = []
        for r in all_rows:
            ana_match = r['ana_grup'].upper() == ana_grup_upper
            ara_match = r['ara_grup'].upper() == ara_grup_upper
            has_alt = r['alt_grup'] != '' and not r['alt_grup'].startswith('Toplam')
            
            if ana_match and ara_match and has_alt:
                r['ad'] = r['alt_grup']
                alt_gruplar.append(r)
        
        if not alt_gruplar:
            return f"❌ '{ana_grup} > {ara_grup}' altında ürün grubu bulunamadı."
        
        alt_gruplar.sort(key=lambda x: x['ciro_pay'], reverse=True)
        
        sonuc.append("=" * 60)
        sonuc.append(f"📊 {ana_grup_upper} > {ara_grup_upper} - MAL GRUBU DETAYI")
        sonuc.append("=" * 60 + "\n")
        
        sonuc.append(f"{'Mal Grubu':<24} {'Ciro%':>6} {'Adet%':>6} {'Stok%':>6} {'Cover':>6} {'LFL':>7} {'Bütçe':>7}")
        sonuc.append("-" * 75)
        
        for ag in alt_gruplar:
            ad = ag['ad'][:23]
            cover_str = f"{ag['ty_cover']:.1f}"
            lfl_str = f"{ag['lfl_ciro']:+.0f}%"
            butce_str = f"{ag['ciro_achieved']:+.0f}%"
            sonuc.append(f"{ad:<24} {ag['ciro_pay']:>5.1f}% {ag['adet_pay']:>5.1f}% {ag['stok_pay']:>5.1f}% {cover_str:>6} {lfl_str:>7} {butce_str:>7}")
        
        # En iyi ve en kötü performans
        sonuc.append("\n" + "-" * 60)
        en_iyi = max(alt_gruplar, key=lambda x: x['lfl_ciro'])
        en_kotu = min(alt_gruplar, key=lambda x: x['lfl_ciro'])
        sonuc.append(f"✅ En iyi: {en_iyi['ad']} (LFL: %{en_iyi['lfl_ciro']:+.0f})")
        sonuc.append(f"🔴 En kötü: {en_kotu['ad']} (LFL: %{en_kotu['lfl_ciro']:+.0f})")
    
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


def cover_diagram_analiz(kup: KupVeri, alt_grup: str = None, magaza: str = None) -> str:
    """
    Cover Diagram analizi - Mağaza×AltGrup cover analizi
    
    Kolonlar: Alt Grup, StoreName, Mağaza Sayısı, TY Back Cover, 
              TY Avg Store Stock Unit, TY Sales Unit, TY Sales Value TRY,
              Toplam Sipariş, LFL Stok Değişim, LFL Satış Değişim
    """
    
    if len(kup.cover_diagram) == 0:
        return "❌ Cover Diagram yüklenmemiş."
    
    df = kup.cover_diagram.copy()
    kolonlar = list(df.columns)
    
    sonuc = []
    sonuc.append("=" * 60)
    sonuc.append("📊 COVER DİAGRAM ANALİZİ")
    sonuc.append("=" * 60 + "\n")
    
    # Kolon mapping
    def find_col(keywords):
        for kol in kolonlar:
            kol_lower = str(kol).lower()
            if all(k in kol_lower for k in keywords):
                return kol
        return None
    
    col_alt_grup = find_col(['alt', 'grup']) or find_col(['grup'])
    col_magaza = find_col(['store']) or find_col(['mağaza'])
    col_cover = find_col(['cover']) or find_col(['back', 'cover'])
    col_stok = find_col(['stock', 'unit']) or find_col(['stok'])
    col_satis_adet = find_col(['sales', 'unit']) or find_col(['satış', 'adet'])
    col_satis_tutar = find_col(['sales', 'value']) or find_col(['satış', 'tutar'])
    col_siparis = find_col(['sipariş']) or find_col(['toplam', 'sip'])
    col_lfl_stok = find_col(['lfl', 'stok']) or find_col(['stok', 'değişim'])
    col_lfl_satis = find_col(['lfl', 'satış']) or find_col(['satış', 'değişim'])
    
    print(f"Cover Diagram kolonları: {kolonlar[:10]}")
    
    # Filtrele
    if alt_grup:
        df = df[df[col_alt_grup].astype(str).str.upper().str.contains(alt_grup.upper())]
        sonuc.append(f"📁 Alt Grup Filtresi: {alt_grup}\n")
    
    if magaza:
        df = df[df[col_magaza].astype(str).str.upper().str.contains(magaza.upper())]
        sonuc.append(f"🏪 Mağaza Filtresi: {magaza}\n")
    
    if len(df) == 0:
        return "❌ Filtreye uygun veri bulunamadı."
    
    # Parse fonksiyonu
    def parse_val(val):
        if pd.isna(val):
            return 0
        try:
            return float(str(val).replace('%', '').replace(',', '.').strip())
        except:
            return 0
    
    # ÖZET ANALİZ
    sonuc.append(f"📊 GENEL ÖZET ({len(df)} satır)")
    sonuc.append("-" * 50)
    
    if col_cover:
        df['_cover'] = df[col_cover].apply(parse_val)
        avg_cover = df['_cover'].mean()
        cover_yuksek = len(df[df['_cover'] > 12])
        cover_dusuk = len(df[df['_cover'] < 4])
        sonuc.append(f"   Cover Ortalama: {avg_cover:.1f} hafta")
        sonuc.append(f"   🔴 Cover > 12 hafta: {cover_yuksek} satır")
        sonuc.append(f"   ⚠️ Cover < 4 hafta: {cover_dusuk} satır")
    
    if col_lfl_satis:
        df['_lfl_satis'] = df[col_lfl_satis].apply(parse_val)
        avg_lfl = df['_lfl_satis'].mean()
        lfl_neg = len(df[df['_lfl_satis'] < -20])
        sonuc.append(f"   LFL Satış Ort: %{avg_lfl:+.1f}")
        sonuc.append(f"   🔴 LFL < -%20: {lfl_neg} satır")
    
    # ALT GRUP BAZINDA ÖZET
    if col_alt_grup and not alt_grup:
        sonuc.append(f"\n📁 ALT GRUP BAZINDA COVER")
        sonuc.append("-" * 50)
        
        grup_ozet = df.groupby(col_alt_grup).agg({
            '_cover': 'mean' if '_cover' in df.columns else 'count'
        }).sort_values('_cover', ascending=False).head(15)
        
        sonuc.append(f"{'Alt Grup':<30} {'Ort Cover':>10}")
        sonuc.append("-" * 45)
        for idx, row in grup_ozet.iterrows():
            cover_emoji = "🔴" if row['_cover'] > 12 else ("⚠️" if row['_cover'] > 10 else "")
            sonuc.append(f"{str(idx)[:29]:<30} {row['_cover']:>8.1f}hf {cover_emoji}")
    
    # MAĞAZA BAZINDA ÖZET
    if col_magaza and not magaza:
        sonuc.append(f"\n🏪 MAĞAZA BAZINDA COVER (En Yüksek 10)")
        sonuc.append("-" * 50)
        
        mag_ozet = df.groupby(col_magaza).agg({
            '_cover': 'mean'
        }).sort_values('_cover', ascending=False).head(10)
        
        for idx, row in mag_ozet.iterrows():
            cover_emoji = "🔴" if row['_cover'] > 12 else ""
            sonuc.append(f"   {str(idx)[:30]}: {row['_cover']:.1f}hf {cover_emoji}")
    
    return "\n".join(sonuc)


def kapasite_analiz(kup: KupVeri, magaza: str = None) -> str:
    """
    Kapasite-Performans analizi - Mağaza doluluk ve performans
    
    Kolonlar: StoreName, Karlı-Hızlı Metrik, Store Capacity dm3, Fiili Doluluk,
              Nihai Doluluk, #Store Cover, LFL değişimler, Kar Marjı
    """
    
    if len(kup.kapasite) == 0:
        return "❌ Kapasite raporu yüklenmemiş."
    
    df = kup.kapasite.copy()
    kolonlar = list(df.columns)
    
    sonuc = []
    sonuc.append("=" * 60)
    sonuc.append("📦 KAPASİTE VE PERFORMANS ANALİZİ")
    sonuc.append("=" * 60 + "\n")
    
    # Kolon mapping
    def find_col(keywords):
        for kol in kolonlar:
            kol_lower = str(kol).lower().replace('_', ' ')
            if all(k in kol_lower for k in keywords):
                return kol
        return None
    
    col_magaza = find_col(['store']) or find_col(['mağaza']) or kolonlar[0]
    col_karli_hizli = find_col(['karlı', 'hızlı']) or find_col(['metrik'])
    col_kapasite = find_col(['capacity']) or find_col(['kapasite'])
    col_fiili_doluluk = find_col(['fiili', 'doluluk'])
    col_nihai_doluluk = find_col(['nihai', 'doluluk'])
    col_cover = find_col(['cover'])
    col_lfl_stok = find_col(['lfl', 'stok'])
    col_lfl_satis_adet = find_col(['lfl', 'satış', 'adet'])
    col_lfl_satis_tutar = find_col(['lfl', 'satış', 'tutar'])
    col_kar_marj = find_col(['kar', 'marj']) or find_col(['marj'])
    
    print(f"Kapasite kolonları: {kolonlar[:10]}")
    
    # Filtrele
    if magaza:
        df = df[df[col_magaza].astype(str).str.upper().str.contains(magaza.upper())]
        sonuc.append(f"🏪 Mağaza Filtresi: {magaza}\n")
    
    if len(df) == 0:
        return "❌ Filtreye uygun mağaza bulunamadı."
    
    # Parse fonksiyonu
    def parse_val(val):
        if pd.isna(val):
            return 0
        try:
            return float(str(val).replace('%', '').replace(',', '.').strip())
        except:
            return 0
    
    def parse_pct(val):
        v = parse_val(val)
        if -2 < v < 2 and v != 0:
            return v * 100
        return v
    
    # GENEL ÖZET
    sonuc.append(f"📊 GENEL ÖZET ({len(df)} mağaza)")
    sonuc.append("-" * 50)
    
    # Doluluk analizi
    if col_fiili_doluluk:
        df['_fiili'] = df[col_fiili_doluluk].apply(parse_pct)
        avg_doluluk = df['_fiili'].mean()
        dolu_fazla = len(df[df['_fiili'] > 90])
        dolu_az = len(df[df['_fiili'] < 50])
        sonuc.append(f"   Ortalama Doluluk: %{avg_doluluk:.0f}")
        sonuc.append(f"   🔴 Doluluk > %90: {dolu_fazla} mağaza (TAŞIYOR)")
        sonuc.append(f"   ⚠️ Doluluk < %50: {dolu_az} mağaza (BOŞ)")
    
    # Cover analizi
    if col_cover:
        df['_cover'] = df[col_cover].apply(parse_val)
        avg_cover = df['_cover'].mean()
        sonuc.append(f"   Ortalama Cover: {avg_cover:.1f} hafta")
    
    # LFL analizi
    if col_lfl_satis_tutar:
        df['_lfl_satis'] = df[col_lfl_satis_tutar].apply(parse_pct)
        avg_lfl = df['_lfl_satis'].mean()
        sonuc.append(f"   LFL Satış Ort: %{avg_lfl:+.1f}")
    
    # Kar marjı
    if col_kar_marj:
        df['_marj'] = df[col_kar_marj].apply(parse_pct)
        avg_marj = df['_marj'].mean()
        sonuc.append(f"   Ortalama Marj: %{avg_marj:.1f}")
    
    # KARLI-HIZLI DAĞILIM
    if col_karli_hizli:
        sonuc.append(f"\n📊 KARLI-HIZLI METRİK DAĞILIMI")
        sonuc.append("-" * 50)
        
        metrik_dag = df[col_karli_hizli].value_counts()
        for metrik, sayi in metrik_dag.items():
            oran = sayi / len(df) * 100
            emoji = "✅" if 'karlı' in str(metrik).lower() and 'hızlı' in str(metrik).lower() else ""
            sonuc.append(f"   {metrik}: {sayi} mağaza (%{oran:.0f}) {emoji}")
    
    # EN DOLU MAĞAZALAR
    if col_fiili_doluluk:
        sonuc.append(f"\n🔴 EN DOLU MAĞAZALAR (Kapasite Sorunu)")
        sonuc.append("-" * 50)
        
        en_dolu = df.nlargest(10, '_fiili')
        sonuc.append(f"{'Mağaza':<35} {'Doluluk':>10} {'Cover':>8}")
        sonuc.append("-" * 55)
        for _, row in en_dolu.iterrows():
            mag = str(row[col_magaza])[:34]
            doluluk = row['_fiili']
            cover = row.get('_cover', 0)
            sonuc.append(f"{mag:<35} %{doluluk:>8.0f} {cover:>7.1f}hf")
    
    # EN PERFORMANSLI MAĞAZALAR
    if col_lfl_satis_tutar and '_lfl_satis' in df.columns:
        sonuc.append(f"\n✅ EN İYİ PERFORMANS (LFL Satış)")
        sonuc.append("-" * 50)
        
        en_iyi = df.nlargest(10, '_lfl_satis')
        for _, row in en_iyi.iterrows():
            mag = str(row[col_magaza])[:30]
            lfl = row['_lfl_satis']
            sonuc.append(f"   {mag}: %{lfl:+.0f}")
    
    return "\n".join(sonuc)


def siparis_takip_analiz(kup: KupVeri, ana_grup: str = None) -> str:
    """
    Sipariş Yerleştirme ve Satınalma Takip analizi
    
    Kolonlar: Ana Grup, Ara Grup, Alt Grup, Onaylı Alım Bütçe, Total Sipariş,
              Depoya Giren, Bekleyen Sipariş, Depo Giriş oranları
    """
    
    if len(kup.siparis_takip) == 0:
        return "❌ Sipariş Takip raporu yüklenmemiş."
    
    df = kup.siparis_takip.copy()
    kolonlar = list(df.columns)
    
    sonuc = []
    sonuc.append("=" * 60)
    sonuc.append("📦 SİPARİŞ VE SATINALMA TAKİP")
    sonuc.append("=" * 60 + "\n")
    
    # Kolon mapping
    def find_col(keywords, exclude=[]):
        for kol in kolonlar:
            kol_lower = str(kol).lower()
            if all(k in kol_lower for k in keywords) and not any(e in kol_lower for e in exclude):
                return kol
        return None
    
    col_ana_grup = find_col(['ana', 'grup']) or find_col(['yeni', 'ana'])
    col_ara_grup = find_col(['ara', 'grup'])
    col_alt_grup = find_col(['alt', 'grup']) or find_col(['yeni', 'alt'])
    col_alim_butce = find_col(['onaylı', 'alım', 'bütçe', 'tutar'], ['adet'])
    col_siparis = find_col(['total', 'sipariş', 'tutar'], ['adet', 'hariç'])
    col_depo_giren = find_col(['depoya', 'giren', 'tutar'], ['adet', 'hariç'])
    col_bekleyen = find_col(['bekleyen', 'sipariş', 'tutar'], ['adet', 'hariç'])
    col_gerceklesme = find_col(['depo', 'giriş', 'alım', 'bütçe', 'oran'])
    
    print(f"Sipariş Takip kolonları: {kolonlar[:10]}")
    
    # Filtrele
    if ana_grup:
        df = df[df[col_ana_grup].astype(str).str.upper().str.contains(ana_grup.upper())]
        sonuc.append(f"📁 Ana Grup Filtresi: {ana_grup}\n")
    
    if len(df) == 0:
        return "❌ Filtreye uygun veri bulunamadı."
    
    # Parse fonksiyonu
    def parse_val(val):
        if pd.isna(val):
            return 0
        try:
            return float(str(val).replace('%', '').replace(',', '.').replace(' ', '').strip())
        except:
            return 0
    
    def parse_pct(val):
        v = parse_val(val)
        if -2 < v < 2 and v != 0:
            return v * 100
        return v
    
    # GENEL ÖZET
    sonuc.append(f"📊 GENEL ÖZET ({len(df)} satır)")
    sonuc.append("-" * 50)
    
    if col_alim_butce:
        toplam_butce = df[col_alim_butce].apply(parse_val).sum()
        sonuc.append(f"   Onaylı Alım Bütçe: {toplam_butce/1e6:,.1f}M TL")
    
    if col_siparis:
        toplam_siparis = df[col_siparis].apply(parse_val).sum()
        sonuc.append(f"   Total Sipariş: {toplam_siparis/1e6:,.1f}M TL")
    
    if col_depo_giren:
        toplam_giren = df[col_depo_giren].apply(parse_val).sum()
        sonuc.append(f"   Depoya Giren: {toplam_giren/1e6:,.1f}M TL")
    
    if col_bekleyen:
        toplam_bekleyen = df[col_bekleyen].apply(parse_val).sum()
        sonuc.append(f"   Bekleyen Sipariş: {toplam_bekleyen/1e6:,.1f}M TL")
    
    # Gerçekleşme oranı
    if col_alim_butce and col_depo_giren:
        butce = df[col_alim_butce].apply(parse_val).sum()
        giren = df[col_depo_giren].apply(parse_val).sum()
        if butce > 0:
            oran = giren / butce * 100
            emoji = "✅" if oran >= 80 else ("⚠️" if oran >= 60 else "🔴")
            sonuc.append(f"   {emoji} Gerçekleşme Oranı: %{oran:.0f}")
    
    # ANA GRUP BAZINDA
    if col_ana_grup and not ana_grup:
        sonuc.append(f"\n📁 ANA GRUP BAZINDA SİPARİŞ DURUMU")
        sonuc.append("-" * 60)
        
        # Grupla
        df['_butce'] = df[col_alim_butce].apply(parse_val) if col_alim_butce else 0
        df['_siparis'] = df[col_siparis].apply(parse_val) if col_siparis else 0
        df['_giren'] = df[col_depo_giren].apply(parse_val) if col_depo_giren else 0
        df['_bekleyen'] = df[col_bekleyen].apply(parse_val) if col_bekleyen else 0
        
        grup_ozet = df.groupby(col_ana_grup).agg({
            '_butce': 'sum',
            '_siparis': 'sum',
            '_giren': 'sum',
            '_bekleyen': 'sum'
        }).sort_values('_butce', ascending=False)
        
        sonuc.append(f"{'Ana Grup':<25} {'Bütçe':>12} {'Sipariş':>12} {'Giren':>12} {'Bekleyen':>12} {'%Gerç':>8}")
        sonuc.append("-" * 85)
        
        for idx, row in grup_ozet.head(12).iterrows():
            grup = str(idx)[:24]
            butce = row['_butce'] / 1e6
            siparis = row['_siparis'] / 1e6
            giren = row['_giren'] / 1e6
            bekleyen = row['_bekleyen'] / 1e6
            oran = (giren / butce * 100) if butce > 0 else 0
            emoji = "✅" if oran >= 80 else ("⚠️" if oran >= 60 else "🔴")
            sonuc.append(f"{grup:<25} {butce:>10.1f}M {siparis:>10.1f}M {giren:>10.1f}M {bekleyen:>10.1f}M {oran:>6.0f}% {emoji}")
    
    # BEKLEYEN SİPARİŞ UYARISI
    if col_bekleyen:
        df['_bekleyen'] = df[col_bekleyen].apply(parse_val)
        bekleyen_yuksek = df[df['_bekleyen'] > df['_bekleyen'].quantile(0.9)]
        
        if len(bekleyen_yuksek) > 0:
            sonuc.append(f"\n⚠️ YÜKSEK BEKLEYEN SİPARİŞ (Top 10)")
            sonuc.append("-" * 50)
            
            for _, row in bekleyen_yuksek.nlargest(10, '_bekleyen').iterrows():
                grup = str(row.get(col_alt_grup, row.get(col_ana_grup, 'N/A')))[:30]
                bekleyen = row['_bekleyen'] / 1e6
                sonuc.append(f"   {grup}: {bekleyen:.1f}M TL bekliyor")
    
    return "\n".join(sonuc)


def web_arama(sorgu: str) -> str:
    """
    Web'den güncel bilgi arar - Enflasyon, sektör verileri, ekonomik göstergeler
    DuckDuckGo ücretsiz API kullanır
    """
    import urllib.request
    import urllib.parse
    import json
    
    sonuc = []
    sonuc.append(f"🔍 WEB ARAMA: {sorgu}")
    sonuc.append("-" * 50)
    
    try:
        # DuckDuckGo Instant Answer API
        encoded_query = urllib.parse.quote(sorgu)
        url = f"https://api.duckduckgo.com/?q={encoded_query}&format=json&no_html=1"
        
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
        
        # Abstract (özet bilgi)
        if data.get('Abstract'):
            sonuc.append(f"\n📋 ÖZET:")
            sonuc.append(data['Abstract'])
        
        # Related Topics
        if data.get('RelatedTopics'):
            sonuc.append(f"\n📌 İLGİLİ BİLGİLER:")
            for topic in data['RelatedTopics'][:5]:
                if isinstance(topic, dict) and topic.get('Text'):
                    sonuc.append(f"   • {topic['Text'][:200]}")
        
        # Eğer sonuç yoksa, basit bir mesaj
        if not data.get('Abstract') and not data.get('RelatedTopics'):
            sonuc.append(f"\n⚠️ Direkt sonuç bulunamadı.")
            sonuc.append(f"Sorgu: {sorgu}")
            sonuc.append(f"\n💡 Manuel referans değerleri (Aralık 2024):")
            sonuc.append(f"   • Türkiye TÜFE (yıllık): ~%47")
            sonuc.append(f"   • Kozmetik sektör büyümesi: ~%35-40")
            sonuc.append(f"   • USD/TRY: ~34-35 TL")
            sonuc.append(f"   • Perakende büyümesi: ~%25-30")
        
        sonuc.append(f"\n📅 Sorgu zamanı: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}")
        
    except Exception as e:
        sonuc.append(f"\n❌ Web arama hatası: {str(e)}")
        sonuc.append(f"\n💡 Manuel referans değerleri (Aralık 2024):")
        sonuc.append(f"   • Türkiye TÜFE (yıllık): ~%47")
        sonuc.append(f"   • Kozmetik sektör büyümesi: ~%35-40")
        sonuc.append(f"   • USD/TRY: ~34-35 TL")
        sonuc.append(f"   • Perakende büyümesi: ~%25-30")
    
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


def sevkiyat_hesapla(kup: KupVeri, kategori_kod = None, urun_kod: str = None, marka_kod: str = None, forward_cover: float = 7.0, export_excel: bool = False) -> str:
    """
    Sevkiyat hesaplaması - INLINE versiyon
    
    Mantık:
    1. hedef_stok = haftalik_satis × forward_cover
    2. rpt_ihtiyac = hedef_stok - stok - yol
    3. min_ihtiyac = min - stok - yol (eğer stok+yol < min ise)
    4. final_ihtiyac = MAX(rpt_ihtiyac, min_ihtiyac)
    
    export_excel=True ise Excel dosyası oluşturur ve yolunu döner
    """
    print("\n" + "="*50)
    print("🚀 SEVKIYAT_HESAPLA ÇAĞRILDI (INLINE)")
    print(f"   Parametreler: kategori={kategori_kod}, urun={urun_kod}, fc={forward_cover}, excel={export_excel}")
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
        
        # EXCEL EXPORT
        if export_excel:
            try:
                import os
                from datetime import datetime
                
                # Export için DataFrame hazırla
                export_df = sonuc_df[['magaza_kod', 'urun_kod', 'depo_kod', 'stok', 'yol', 'min',
                                      'haftalik_satis', 'cover', 'hedef_stok', 'rpt_ihtiyac', 
                                      'ihtiyac', 'ihtiyac_turu', 'sevkiyat', 'karsilanamayan']].copy()
                
                # Kolon isimlerini Türkçeleştir
                export_df.columns = ['Mağaza', 'Ürün Kodu', 'Depo', 'Stok', 'Yol', 'Min',
                                    'Haftalık Satış', 'Cover', 'Hedef Stok', 'RPT İhtiyaç',
                                    'Toplam İhtiyaç', 'İhtiyaç Türü', 'Sevk Adet', 'Karşılanamayan']
                
                # Dosya adı oluştur
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                if urun_kod:
                    filename = f"sevkiyat_{urun_kod}_{timestamp}.xlsx"
                elif kategori_kod:
                    filename = f"sevkiyat_kat{kategori_kod}_{timestamp}.xlsx"
                else:
                    filename = f"sevkiyat_tum_{timestamp}.xlsx"
                
                # Dosya yolu
                export_path = os.path.join("/tmp", filename)
                
                # Excel'e yaz
                export_df.to_excel(export_path, index=False, sheet_name='Sevkiyat')
                
                rapor.append(f"\n📁 EXCEL DOSYASI OLUŞTURULDU:")
                rapor.append(f"   📥 {export_path}")
                
                print(f"✅ Excel export: {export_path}")
                
            except Exception as ex:
                rapor.append(f"\n⚠️ Excel export hatası: {str(ex)}")
        
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
        "name": "web_arama",
        "description": "Web'den güncel ekonomik veri arar. Enflasyon, TÜFE, döviz kuru, sektör büyümesi gibi makro verileri getirir. Fiyat artışı yorumlarken MUTLAKA enflasyonla karşılaştır!",
        "input_schema": {
            "type": "object",
            "properties": {
                "sorgu": {
                    "type": "string",
                    "description": "Aranacak sorgu. Örn: 'Türkiye enflasyon 2024', 'kozmetik sektör büyümesi', 'USD TRY kuru'"
                }
            },
            "required": ["sorgu"]
        }
    },
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
        "description": "Trading raporunu 3 seviyeli hiyerarşi ile analiz eder. Parametre verilmezse şirket özeti + ana gruplar gösterir. ana_grup verilirse o grubun ara gruplarını, ana_grup+ara_grup verilirse mal gruplarını gösterir. Drill-down analiz için kullan.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ana_grup": {
                    "type": "string",
                    "description": "Ana grup adı (RENKLİ KOZMETİK, CİLT BAKIM, SAÇ BAKIM, PARFÜM vb). Boş bırakılırsa şirket özeti gösterir."
                },
                "ara_grup": {
                    "type": "string",
                    "description": "Ara grup adı (GÖZ ÜRÜNLERİ, YÜZ ÜRÜNLERİ, ŞAMPUAN vb). ana_grup ile birlikte kullanılır, mal grubu detayı gösterir."
                }
            },
            "required": []
        }
    },
    {
        "name": "cover_analiz",
        "description": "SC Tablosundan cover grup analizini yapar. (Eski format). Yeni format için cover_diagram_analiz kullan.",
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
        "name": "cover_diagram_analiz",
        "description": "Cover Diagram raporunu analiz eder. Mağaza×AltGrup bazında cover analizi. Yüksek/düşük cover durumları, LFL değişimler. Alt grup veya mağaza filtresi ile detaya inebilir.",
        "input_schema": {
            "type": "object",
            "properties": {
                "alt_grup": {
                    "type": "string",
                    "description": "Alt grup filtresi (opsiyonel). Örn: 'MASKARA', 'ŞAMPUAN'"
                },
                "magaza": {
                    "type": "string",
                    "description": "Mağaza filtresi (opsiyonel). Örn: 'ANKARA', 'İSTANBUL'"
                }
            },
            "required": []
        }
    },
    {
        "name": "kapasite_analiz",
        "description": "Kapasite-Performans raporunu analiz eder. Mağaza doluluk oranları, kapasite sorunları, Karlı-Hızlı metrik dağılımı, LFL performans. Taşan veya boş mağazaları tespit eder.",
        "input_schema": {
            "type": "object",
            "properties": {
                "magaza": {
                    "type": "string",
                    "description": "Mağaza filtresi (opsiyonel). Örn: 'ANKARA', 'KORUPARK'"
                }
            },
            "required": []
        }
    },
    {
        "name": "siparis_takip_analiz",
        "description": "Sipariş Yerleştirme ve Satınalma Takip raporunu analiz eder. Onaylı bütçe, total sipariş, depoya giren, bekleyen sipariş. Satınalma gerçekleşme oranlarını gösterir.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ana_grup": {
                    "type": "string",
                    "description": "Ana grup filtresi (opsiyonel). Örn: 'RENKLİ KOZMETİK', 'SAÇ BAKIM'"
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
        "description": "R4U Allocator motorunu çalıştırarak otomatik sevkiyat hesaplaması yapar. Segmentasyon, ihtiyaç hesaplama ve depo stok dağıtımını içerir. Kategori veya ürün filtresi ile çalıştırılabilir. export_excel=true ile Excel dosyası oluşturur.",
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
                    "description": "Hedef cover değeri (hafta). Varsayılan: 7",
                    "default": 7.0
                },
                "export_excel": {
                    "type": "boolean",
                    "description": "Excel dosyası oluşturmak için true yap. Mağaza, stok, yol, sevk adet gibi kolonları içeren detaylı Excel çıktısı alırsın.",
                    "default": False
                }
            },
            "required": []
        }
    }
]

SYSTEM_PROMPT = """Sen deneyimli bir Retail Planner'sın. Adın "Sanal Planner". 

## 🎯 KİMLİĞİN
- Kullanıcıya "Hakan Bey" diye hitap et
- Profesyonel ama samimi bir ton kullan
- Rakamları yorumla, sadece listeleme yapma!
- Derinlemesine analiz yap, kısa kesme

## 🗣️ KONUŞMA TARZI
- Doğal, akıcı cümlelerle anlat
- Rakamları yazıyla: "15.234" → "yaklaşık 15 bin"
- Yüzdeleri doğal: "%107.5" → "yüzde 107 ile bütçenin üstünde"
- Önce SONUÇ ve YORUM, sonra detay

## 📊 HAFTALIK ANALİZ STANDARDI (ÇOK ÖNEMLİ!)

"Bu hafta nasıl gitti?", "Genel analiz", "Durum nedir?" gibi sorularda MUTLAKA bu yapıyı takip et:

### A. TOPLAM SEVİYE ANALİZİ (Şirket Geneli)

#### A.1) BÜTÇE GERÇEKLEŞMESİ (Trading'den)
- trading_analiz() çağır
- `Achieved TY Sales Budget Value TRY` kolonu ile şirket toplamı bütçe gerçekleşme
- Mevcut Ana Grup bazında bütçe durumu
- Örnek: "Toplamda %107 ile mükemmel bir bütçe gerçekleşmemiz var."

#### A.2) MAĞAZA DOLULUK (Kapasite'den)
- kapasite_analiz() çağır  
- `#Fiili Doluluk_` kolonu ile toplam doluluk
- Örnek: "Mağazalarımız ortalama %78 dolu durumda."

#### A.3) EN ÇOK CİRO YAPAN 3 ANA GRUP
- Trading'den `TY Sales Value TRY` en yüksek 3 Mevcut Ana Grup
- Bu 3 grubun bütçe gerçekleşme durumu
- Örnek: "İlk 3 grup (RENKLİ KOZMETİK, CİLT BAKIM, SAÇ BAKIM) cironun %65'ini oluşturuyor ve üçü de bütçenin üzerinde."

#### A.4) HIZ (COVER) ANALİZİ (Trading'den)
- `LY Store Back Cover TRY` vs `TY Store Back Cover TRY` karşılaştır
- Şirket ve Mevcut Ana Grup bazında cover değişimi
- Hız iyileşmesi nereden geldi? → LFL Stok değişimi mi, satış artışı mı?
  - Eğer stok azaldıysa (`LFL Store Stock Unit TYvsLY` negatif) ve cover düştüyse → "Hız iyileşmesi STOK ERİTME'den geliyor"
  - Eğer satış arttıysa (`LFL Sales Unit TYvsLY` pozitif) ve cover düştüyse → "Hız iyileşmesi SATIŞ ARTIŞI'ndan geliyor"
- Örnek: "Cover 8.5 haftadan 7.2 haftaya düştü. Bu iyileşme satış artışından geliyor çünkü LFL adet %12 büyümüş."

#### A.5) MARJ DEĞİŞİMİ (Trading'den)
- `LY LFL Gross Margin LC%` vs `TY Budget Gross Margin TRY` karşılaştır
- Marj değişiminin LFL Ciro artışına etkisi
- Örnek: "Marj %40'tan %42'ye çıkmış. Bu 2 puanlık artış LFL ciro büyümesine olumlu katkı sağlamış."

#### A.6) FİYAT ARTIŞI vs ENFLASYON (ZORUNLU!)
- Trading'den fiyat artışını bul (`LFL Unit Sales Price TYvsLY`)
- web_arama("Türkiye enflasyon TÜFE 2024") çağır
- Fiyat artışını enflasyonla karşılaştır
- Örnek yorumlar:
  - Eğer fiyat artışı < enflasyon: "Fiyat artışımız %26, enflasyon %47. Reel fiyatta %21 gerileme var - bu sürdürülebilir, hatta marj baskısı yaratabilir."
  - Eğer fiyat artışı > enflasyon: "Fiyat artışımız %50, enflasyon %47. Reel fiyatta %3 artış var - müşteri direnci olabilir, dikkat!"
  - Eğer fiyat artışı ≈ enflasyon: "Fiyat artışımız enflasyonla paralel, reel fiyat korunmuş."

### B. ALT GRUP ANALİZİ

#### B.1) SORUNLU ALT GRUPLAR (Trading'den)
- `TY Sales Value TRY` > 500.000 TL olan Alt Grupları filtrele (büyük gruplar)
- Bu gruplar için:
  - Bütçe gerçekleşme (`Achieved TY Sales Budget Value TRY`)
  - Kar marjı (`TY Gross Margin TRY`)
  - Cover (`TY Store Back Cover TRY`)
- Sorunlu olanları belirle (Cover > 12 veya Bütçe < %85 veya Marj düşüşü)

#### B.2) SORUNLU 3 ALT GRUP İÇİN MAĞAZA ANALİZİ (Cover Diagram'dan)
- cover_diagram_analiz(alt_grup="SORUNLU_GRUP") çağır
- "Çok Yavaş" grubundaki mağaza sayısı ve yüzdesi
- Örnek: "MASKARA grubunda 45 mağaza (%32) 'Çok Yavaş' kategorisinde. Bu mağazalarda eritme kampanyası başlatılmalı."

#### B.3) AKSİYON ÖNERİLERİ
- Her sorunlu grup için spesifik aksiyon öner
- Örnek: "FONDOTEN için 15 mağazada %20 indirim kampanyası başlat, hedef 3 hafta içinde cover'ı 12'den 8'e düşürmek."

### C. SİPARİŞ TAKİP ANALİZİ

#### C.1) TOPLAM SİPARİŞ DURUMU (Sipariş Takip'ten)
- siparis_takip_analiz() çağır
- Toplam onaylı bütçe vs toplam sipariş vs depoya giren
- Gerçekleşme oranı
- Bekleyen sipariş tutarı

#### C.2) ANA GRUP BAZINDA SİPARİŞ
- Yeni Ana Grup bazında sipariş ve kalan durumu
- Hangi gruplarda tedarik sıkıntısı var?
- Örnek: "RENKLİ KOZMETİK'te bütçenin %75'i sipariş verilmiş, %60'ı depoya girmiş. 2M TL bekleyen sipariş var."

## 🔧 ÇOKLU TOOL KULLANIMI (ZORUNLU!)

"Genel analiz" sorulduğunda TEK TOOL YETERLİ DEĞİL! MUTLAKA şu sırayla çağır:
1. trading_analiz() → Şirket + Ana Grup performans
2. kapasite_analiz() → Mağaza doluluk
3. cover_diagram_analiz() → Alt grup + mağaza cover detayı
4. siparis_takip_analiz() → Tedarik durumu

4 TOOL'UN HEPSİNİ KULLAN! Eksik bırakma!

## ⚠️ KRİTİK EŞİK DEĞERLERİ

| Metrik | Kritik Eşik | Yorum |
|--------|-------------|-------|
| Cover | > 12 hafta | 🔴 "Stok fazlası, eritme/indirim planla" |
| Cover | < 4 hafta | 🔴 "Stok az, sevkiyat gerekli" |
| Bütçe | < %85 | 🔴 "Bütçe altında, satış aksiyonu şart" |
| Bütçe | > %115 | ✅ "Mükemmel, bütçe aşımı" |
| LFL Ciro | < -%10 | ⚠️ "Küçülme var, dikkat" |
| Marj | < %35 | ⚠️ "Marj baskısı var" |
| Doluluk | > %90 | 🔴 "Mağaza taşıyor, kapasite sorunu" |
| Doluluk | < %50 | ⚠️ "Mağaza boş, ürün eksik" |

## ❌ YAPMA!
- Tek tool ile yetinme - 4 tool kullan
- "Veri yok" deyip bırakma - tool'ları çağır
- Sadece rakam listele - YORUM yap
- Kısa cevap verme - en az 500 kelime
- **KULLANICIYA SORU SORMA!** "Hangi kategoriye odaklanmamızı istersiniz?" gibi sorular YASAK!
- **TEMBELLİK YAPMA!** Verilen prompt'u takip et, adım adım analiz yap
- **EVE KOZMETİK değil, yüklenen VERİYE bak!** Kullanıcı hangi firmayı yüklediyse onu analiz et

## ✅ YAP!
- 4 tool'un hepsini kullan
- A, B, C bölümlerini sırayla takip et
- Rakamları yorumla ve bağlam ver
- Hız değişiminin NEDEN'ini açıkla (stok mu satış mı)
- Aksiyon öner (ne yapılmalı, hangi kategoride, kaç mağazada)
- Sorunlu 3 alt grup için mağaza detayı ver
- **CREATİVE OL!** Standart cevaplar verme, insight üret
- **DOĞRUDAN ANALİZE GİR!** Soru sormadan verileri analiz et
- **HER TOOL'DAN GELEN VERİYİ YORUMLA!** Boş geçme

## 📋 KOLON İSİMLERİ REHBERİ

### Trading.xlsx
- Bütçe Gerçekleşme: `Achieved TY Sales Budget Value TRY`
- Bu Yıl Ciro: `TY Sales Value TRY`
- Bu Yıl Cover: `TY Store Back Cover TRY`
- Geçen Yıl Cover: `LY Store Back Cover TRY`
- Bu Yıl Marj: `TY Gross Margin TRY`
- Geçen Yıl Marj: `LY LFL Gross Margin LC%`
- LFL Ciro: `LFL Sales Value TYvsLY`
- LFL Adet: `LFL Sales Unit TYvsLY`
- LFL Stok: `LFL Store Stock Unit TYvsLY`
- Fiyat Artışı: `LFL Unit Sales Price TYvsLY`

### Kapasite.xlsx
- Fiili Doluluk: `#Fiili Doluluk_`
- Nihai Doluluk: `#Nihai Doluluk_`
- Cover: `#Store Cover_`

### Cover Diagram.xlsx
- Alt Grup: `Alt Grup` veya `Yeni Metrik`
- Mağaza: `StoreName`
- Cover: `TY Back Cover`

### Sipariş Takip.xlsx
- Ana Grup: `Yeni Ana Grup`
- Onaylı Bütçe: `Onaylı Alım Bütçe Tutar`
- Total Sipariş: `Total Sipariş Tutar`
- Depoya Giren: `Depoya Giren Tutar`
- Bekleyen: `Bekleyen Sipariş Tutar`

Her zaman Türkçe, detaylı ve stratejik ol!"""


def agent_calistir(api_key: str, kup: KupVeri, kullanici_mesaji: str, analiz_kurallari: dict = None) -> str:
    """Agent'ı çalıştır ve sonuç al
    
    analiz_kurallari: Kullanıcının tanımladığı eşikler ve yorumlar
    """
    
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
    
    # Dinamik SYSTEM_PROMPT oluştur
    system_prompt = SYSTEM_PROMPT
    
    if analiz_kurallari:
        kural_eki = "\n\n## 📋 KULLANICI TANIMI ANALİZ KURALLARI\n"
        
        # Analiz sırası
        if analiz_kurallari.get('analiz_sirasi'):
            kural_eki += f"\n### Analiz Sırası:\n"
            for i, analiz in enumerate(analiz_kurallari['analiz_sirasi'], 1):
                kural_eki += f"{i}. {analiz}\n"
        
        # Eşikler
        esikler = analiz_kurallari.get('esikler', {})
        if esikler:
            kural_eki += f"\n### Kritik Eşikler (Bu değerleri kullan!):\n"
            kural_eki += f"- Cover > {esikler.get('cover_yuksek', 12)} hafta → 🔴 YÜKSEK COVER, stok eritme gerekli\n"
            kural_eki += f"- Cover < {esikler.get('cover_dusuk', 4)} hafta → 🔴 DÜŞÜK COVER, sevkiyat gerekli\n"
            kural_eki += f"- Bütçe sapması > %{esikler.get('butce_sapma', 15)} → 🔴 KRİTİK bütçe altında\n"
            kural_eki += f"- LFL düşüş > %{esikler.get('lfl_dusus', 20)} → 🔴 CİDDİ küçülme\n"
            kural_eki += f"- Marj düşüşü > {esikler.get('marj_dusus', 3)} puan → 🔴 MARJ baskısı\n"
            kural_eki += f"- Stok/Ciro oranı > {esikler.get('stok_fazla', 1.3)} → ⚠️ Stok fazlası, ERİTME gerekli\n"
            kural_eki += f"- Stok/Ciro oranı < {esikler.get('stok_az', 0.7)} → ⚠️ Stok az, SEVKİYAT gerekli\n"
        
        # Yorumlar
        yorumlar = analiz_kurallari.get('yorumlar', {})
        if yorumlar:
            kural_eki += f"\n### Yorum Kuralları (Bu önerileri yap!):\n"
            if yorumlar.get('cover_yuksek'):
                kural_eki += f"- Cover yüksekse: {yorumlar['cover_yuksek']}\n"
            if yorumlar.get('butce_dusuk'):
                kural_eki += f"- Bütçe düşükse: {yorumlar['butce_dusuk']}\n"
            if yorumlar.get('marj_dusuk'):
                kural_eki += f"- Marj düşüşü varsa: {yorumlar['marj_dusuk']}\n"
            if yorumlar.get('lfl_negatif'):
                kural_eki += f"- LFL negatifse: {yorumlar['lfl_negatif']}\n"
        
        # Öncelik sırası
        if analiz_kurallari.get('oncelik_sirasi'):
            kural_eki += f"\n### Raporlama Önceliği:\n"
            kural_eki += f"Şu sırayla raporla: {', '.join(analiz_kurallari['oncelik_sirasi'])}\n"
        
        # Ek talimatlar
        if analiz_kurallari.get('ek_talimatlar'):
            kural_eki += f"\n### Ek Talimatlar:\n{analiz_kurallari['ek_talimatlar']}\n"
        
        system_prompt = SYSTEM_PROMPT + kural_eki
        print(f"   📋 Analiz kuralları eklendi ({len(kural_eki)} karakter)")
    
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
                max_tokens=4096,  # Daha uzun yanıtlar için artırıldı
                system=system_prompt,
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
                if tool_name == "web_arama":
                    tool_result = web_arama(tool_input.get("sorgu", "Türkiye enflasyon"))
                elif tool_name == "genel_ozet":
                    tool_result = genel_ozet(kup)
                elif tool_name == "trading_analiz":
                    tool_result = trading_analiz(
                        kup,
                        ana_grup=tool_input.get("ana_grup", None),
                        ara_grup=tool_input.get("ara_grup", None)
                    )
                elif tool_name == "cover_analiz":
                    tool_result = cover_analiz(kup, tool_input.get("sayfa", None))
                elif tool_name == "cover_diagram_analiz":
                    tool_result = cover_diagram_analiz(
                        kup,
                        alt_grup=tool_input.get("alt_grup", None),
                        magaza=tool_input.get("magaza", None)
                    )
                elif tool_name == "kapasite_analiz":
                    tool_result = kapasite_analiz(
                        kup,
                        magaza=tool_input.get("magaza", None)
                    )
                elif tool_name == "siparis_takip_analiz":
                    tool_result = siparis_takip_analiz(
                        kup,
                        ana_grup=tool_input.get("ana_grup", None)
                    )
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
                        forward_cover=tool_input.get("forward_cover", 7.0),
                        export_excel=tool_input.get("export_excel", False)
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
