"""
Sevkiyat Motoru - R4U Allocator
Sanal Planner için sevkiyat hesaplama modülü

Bu modül R4U'nun sevkiyat algoritmasını içerir:
1. Segmentasyon (ürün/mağaza cover grupları)
2. İhtiyaç hesaplama (RPT, Initial, Min)
3. Depo stok dağıtımı
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict, List, Tuple


class SevkiyatMotoru:
    """
    R4U Sevkiyat Hesaplama Motoru
    
    Kullanım:
        motor = SevkiyatMotoru(kup_veri)
        sonuc = motor.hesapla(kategori_kod=11, forward_cover=7.0)
    """
    
    def __init__(self, kup_veri):
        """
        Args:
            kup_veri: KupVeri instance (anlik_stok_satis, urun_master, magaza_master, depo_stok, kpi)
        """
        self.kup = kup_veri
        
        # Default segmentasyon aralıkları
        self.segment_ranges = [(0, 4), (5, 8), (9, 12), (12, 15), (15, 20), (20, float('inf'))]
        self.segment_labels = ['0-4', '5-8', '9-12', '12-15', '15-20', '20-inf']
        
        # Default matris değerleri
        self.default_sisme = 0.5
        self.default_genlestirme = 1.0
        self.default_min_oran = 1.0
        
    def hesapla(
        self,
        kategori_kod: Optional[int] = None,
        marka_kod: Optional[str] = None,
        forward_cover: float = 7.0,
        sisme_orani: float = None,
        genlestirme_orani: float = None,
        min_stok_orani: float = None
    ) -> Dict:
        """
        Sevkiyat ihtiyacını hesaplar ve depo stoğunu dağıtır.
        
        Args:
            kategori_kod: Kategori filtresi (11=Renkli Kozmetik, 14=Saç, vb.)
            marka_kod: Marka filtresi
            forward_cover: Hedef cover değeri (default 7 gün)
            sisme_orani: Şişme oranı override (default matrise göre)
            genlestirme_orani: Genleştirme oranı override
            min_stok_orani: Minimum stok oranı override
            
        Returns:
            Dict: {
                'sonuc': DataFrame (sevkiyat detayları),
                'ozet': Dict (özet metrikler),
                'hata': str veya None
            }
        """
        try:
            # 1. VERİ KONTROLÜ
            if not self._veri_kontrol():
                return {
                    'sonuc': None,
                    'ozet': None,
                    'hata': 'Gerekli veriler eksik (anlik_stok_satis, depo_stok)'
                }
            
            # 2. VERİ HAZIRLA
            df = self._veri_hazirla(kategori_kod, marka_kod)
            
            if len(df) == 0:
                return {
                    'sonuc': pd.DataFrame(),
                    'ozet': {'toplam_sevkiyat': 0, 'urun_sayisi': 0, 'magaza_sayisi': 0},
                    'hata': 'Filtrelere uygun veri bulunamadı'
                }
            
            # 3. SEGMENTASYON
            df = self._segmentasyon_uygula(df)
            
            # 4. MATRİS DEĞERLERİ
            df = self._matris_degerleri_ekle(df, sisme_orani, genlestirme_orani, min_stok_orani)
            
            # 5. İHTİYAÇ HESAPLA
            df = self._ihtiyac_hesapla(df, forward_cover)
            
            # 6. DEPO STOK DAĞIT
            sonuc = self._depo_stok_dagit(df)
            
            # 7. ÖZET OLUŞTUR
            ozet = self._ozet_olustur(sonuc)
            
            return {
                'sonuc': sonuc,
                'ozet': ozet,
                'hata': None
            }
            
        except Exception as e:
            return {
                'sonuc': None,
                'ozet': None,
                'hata': f'Hesaplama hatası: {str(e)}'
            }
    
    def _veri_kontrol(self) -> bool:
        """Gerekli verilerin varlığını kontrol et"""
        if self.kup.anlik_stok_satis is None or len(self.kup.anlik_stok_satis) == 0:
            return False
        if self.kup.depo_stok is None or len(self.kup.depo_stok) == 0:
            return False
        return True
    
    def _veri_hazirla(self, kategori_kod: Optional[int], marka_kod: Optional[str]) -> pd.DataFrame:
        """Ana veriyi hazırla ve filtrele"""
        df = self.kup.anlik_stok_satis.copy()
        df['urun_kod'] = df['urun_kod'].astype(str)
        df['magaza_kod'] = df['magaza_kod'].astype(str)
        
        # Ürün master varsa birleştir
        if self.kup.urun_master is not None:
            urun_m = self.kup.urun_master.copy()
            urun_m['urun_kod'] = urun_m['urun_kod'].astype(str)
            
            # İlgili kolonları seç
            urun_cols = ['urun_kod']
            if 'kategori_kod' in urun_m.columns:
                urun_cols.append('kategori_kod')
            if 'marka_kod' in urun_m.columns:
                urun_cols.append('marka_kod')
            if 'mg' in urun_m.columns:
                urun_cols.append('mg')
            
            df = df.merge(urun_m[urun_cols], on='urun_kod', how='left')
            
            # Kategori filtresi
            if kategori_kod is not None and 'kategori_kod' in df.columns:
                df = df[df['kategori_kod'] == kategori_kod]
            
            # Marka filtresi
            if marka_kod is not None and 'marka_kod' in df.columns:
                df = df[df['marka_kod'] == marka_kod]
        
        # Mağaza master varsa depo kodunu ekle
        if self.kup.magaza_master is not None:
            mag_m = self.kup.magaza_master.copy()
            mag_m['magaza_kod'] = mag_m['magaza_kod'].astype(str)
            
            if 'depo_kod' in mag_m.columns:
                df = df.merge(mag_m[['magaza_kod', 'depo_kod']], on='magaza_kod', how='left')
                df['depo_kod'] = df['depo_kod'].fillna(1).astype(int)
            else:
                df['depo_kod'] = 1
        else:
            df['depo_kod'] = 1
        
        return df
    
    def _segmentasyon_uygula(self, df: pd.DataFrame) -> pd.DataFrame:
        """Ürün ve mağaza segmentasyonu uygula"""
        
        # Ürün bazında toplam stok/satış
        urun_agg = df.groupby('urun_kod').agg({
            'stok': 'sum',
            'satis': 'sum'
        }).reset_index()
        urun_agg['urun_oran'] = urun_agg['stok'] / urun_agg['satis'].replace(0, 1)
        
        # Mağaza bazında toplam stok/satış
        magaza_agg = df.groupby('magaza_kod').agg({
            'stok': 'sum',
            'satis': 'sum'
        }).reset_index()
        magaza_agg['magaza_oran'] = magaza_agg['stok'] / magaza_agg['satis'].replace(0, 1)
        
        # Segment ataması
        bins = [r[0] for r in self.segment_ranges] + [self.segment_ranges[-1][1]]
        
        urun_agg['urun_segment'] = pd.cut(
            urun_agg['urun_oran'],
            bins=bins,
            labels=self.segment_labels,
            include_lowest=True
        ).astype(str)
        
        magaza_agg['magaza_segment'] = pd.cut(
            magaza_agg['magaza_oran'],
            bins=bins,
            labels=self.segment_labels,
            include_lowest=True
        ).astype(str)
        
        # Ana dataframe'e ekle
        df = df.merge(urun_agg[['urun_kod', 'urun_segment']], on='urun_kod', how='left')
        df = df.merge(magaza_agg[['magaza_kod', 'magaza_segment']], on='magaza_kod', how='left')
        
        df['urun_segment'] = df['urun_segment'].fillna('0-4')
        df['magaza_segment'] = df['magaza_segment'].fillna('0-4')
        
        return df
    
    def _matris_degerleri_ekle(
        self, 
        df: pd.DataFrame,
        sisme_orani: Optional[float],
        genlestirme_orani: Optional[float],
        min_stok_orani: Optional[float]
    ) -> pd.DataFrame:
        """Matris değerlerini ekle (şişme, genleştirme, min oran)"""
        
        # Override varsa kullan, yoksa default
        df['sisme'] = sisme_orani if sisme_orani is not None else self.default_sisme
        df['genlestirme'] = genlestirme_orani if genlestirme_orani is not None else self.default_genlestirme
        df['min_oran'] = min_stok_orani if min_stok_orani is not None else self.default_min_oran
        
        # KPI'dan min değer
        if self.kup.kpi is not None and 'mg' in df.columns:
            kpi = self.kup.kpi.copy()
            if 'mg_id' in kpi.columns and 'min_deger' in kpi.columns:
                kpi['mg_id'] = kpi['mg_id'].astype(str)
                df['mg'] = df['mg'].astype(str)
                
                df = df.merge(
                    kpi[['mg_id', 'min_deger']],
                    left_on='mg',
                    right_on='mg_id',
                    how='left'
                )
                df['min_deger'] = df['min_deger'].fillna(0)
                df.drop('mg_id', axis=1, inplace=True, errors='ignore')
            else:
                df['min_deger'] = 0
        else:
            df['min_deger'] = 0
        
        return df
    
    def _ihtiyac_hesapla(self, df: pd.DataFrame, forward_cover: float) -> pd.DataFrame:
        """İhtiyaç hesapla (MAX yaklaşımı: RPT, Initial, Min)"""
        
        # Yol kolonu yoksa 0
        if 'yol' not in df.columns:
            df['yol'] = 0
        
        # RPT İhtiyacı
        df['rpt_ihtiyac'] = (
            forward_cover * df['satis'] * df['genlestirme']
        ) - (df['stok'] + df['yol'])
        
        # Min İhtiyacı
        df['min_ihtiyac'] = (
            df['min_oran'] * df['min_deger']
        ) - (df['stok'] + df['yol'])
        
        # Negatif değerleri sıfırla
        df['rpt_ihtiyac'] = df['rpt_ihtiyac'].clip(lower=0)
        df['min_ihtiyac'] = df['min_ihtiyac'].clip(lower=0)
        
        # MAX'ı al
        df['ihtiyac'] = df[['rpt_ihtiyac', 'min_ihtiyac']].max(axis=1)
        
        # Hangi türden geldiğini belirle
        df['ihtiyac_turu'] = np.where(
            df['ihtiyac'] == 0, 'Yok',
            np.where(df['ihtiyac'] == df['rpt_ihtiyac'], 'RPT', 'Min')
        )
        
        return df
    
    def _depo_stok_dagit(self, df: pd.DataFrame) -> pd.DataFrame:
        """Depo stoğunu ihtiyaçlara göre dağıt"""
        
        # Sadece pozitif ihtiyaçları al
        result = df[df['ihtiyac'] > 0].copy()
        
        if len(result) == 0:
            return pd.DataFrame()
        
        # Öncelik sıralaması (ihtiyaca göre büyükten küçüğe)
        result = result.sort_values('ihtiyac', ascending=False).reset_index(drop=True)
        
        # Depo stok dictionary
        depo_df = self.kup.depo_stok.copy()
        depo_df['urun_kod'] = depo_df['urun_kod'].astype(str)
        depo_df['depo_kod'] = depo_df['depo_kod'].astype(int)
        
        depo_stok_dict = {}
        for _, row in depo_df.iterrows():
            key = (int(row['depo_kod']), str(row['urun_kod']))
            depo_stok_dict[key] = float(row['stok'])
        
        # Sevkiyat hesapla
        sevkiyat_list = []
        
        for idx, row in result.iterrows():
            key = (int(row['depo_kod']), str(row['urun_kod']))
            ihtiyac = float(row['ihtiyac'])
            
            if key in depo_stok_dict and depo_stok_dict[key] > 0:
                sevk = min(ihtiyac, depo_stok_dict[key])
                depo_stok_dict[key] -= sevk
            else:
                sevk = 0
            
            sevkiyat_list.append(sevk)
        
        result['sevkiyat_miktari'] = sevkiyat_list
        result['karsilanamayan'] = result['ihtiyac'] - result['sevkiyat_miktari']
        
        # Sonuç kolonlarını düzenle
        output_cols = [
            'magaza_kod', 'urun_kod', 'depo_kod',
            'stok', 'yol', 'satis', 'ihtiyac', 'ihtiyac_turu',
            'sevkiyat_miktari', 'karsilanamayan',
            'urun_segment', 'magaza_segment'
        ]
        
        # Kategori/marka varsa ekle
        if 'kategori_kod' in result.columns:
            output_cols.insert(3, 'kategori_kod')
        if 'marka_kod' in result.columns:
            output_cols.insert(4, 'marka_kod')
        
        # Mevcut kolonları filtrele
        output_cols = [c for c in output_cols if c in result.columns]
        
        return result[output_cols]
    
    def _ozet_olustur(self, sonuc: pd.DataFrame) -> Dict:
        """Özet metrikleri oluştur"""
        
        if sonuc is None or len(sonuc) == 0:
            return {
                'toplam_sevkiyat': 0,
                'toplam_ihtiyac': 0,
                'karsilama_orani': 0,
                'urun_sayisi': 0,
                'magaza_sayisi': 0,
                'depo_sayisi': 0
            }
        
        toplam_sevkiyat = sonuc['sevkiyat_miktari'].sum()
        toplam_ihtiyac = sonuc['ihtiyac'].sum()
        karsilama = (toplam_sevkiyat / toplam_ihtiyac * 100) if toplam_ihtiyac > 0 else 0
        
        return {
            'toplam_sevkiyat': int(toplam_sevkiyat),
            'toplam_ihtiyac': int(toplam_ihtiyac),
            'karsilama_orani': round(karsilama, 1),
            'urun_sayisi': sonuc['urun_kod'].nunique(),
            'magaza_sayisi': sonuc['magaza_kod'].nunique(),
            'depo_sayisi': sonuc['depo_kod'].nunique(),
            'karsilanamayan_toplam': int(sonuc['karsilanamayan'].sum())
        }
    
    def hizli_ozet(self, kategori_kod: Optional[int] = None) -> str:
        """
        Hızlı özet raporu (Agent için)
        
        Returns:
            str: Markdown formatında özet
        """
        result = self.hesapla(kategori_kod=kategori_kod)
        
        if result['hata']:
            return f"❌ Hata: {result['hata']}"
        
        ozet = result['ozet']
        sonuc = result['sonuc']
        
        if ozet['toplam_sevkiyat'] == 0:
            return "ℹ️ Sevkiyat ihtiyacı bulunamadı."
        
        # En çok sevkiyat alan ürünler
        top_urunler = sonuc.groupby('urun_kod')['sevkiyat_miktari'].sum().nlargest(5)
        
        # En çok sevkiyat alan mağazalar
        top_magazalar = sonuc.groupby('magaza_kod')['sevkiyat_miktari'].sum().nlargest(5)
        
        rapor = f"""
## 📦 Sevkiyat Hesaplama Sonucu

### Özet Metrikler
| Metrik | Değer |
|--------|-------|
| Toplam Sevkiyat | {ozet['toplam_sevkiyat']:,} adet |
| Toplam İhtiyaç | {ozet['toplam_ihtiyac']:,} adet |
| Karşılama Oranı | %{ozet['karsilama_orani']} |
| Karşılanamayan | {ozet['karsilanamayan_toplam']:,} adet |
| Ürün Sayısı | {ozet['urun_sayisi']} |
| Mağaza Sayısı | {ozet['magaza_sayisi']} |

### 🏆 En Çok Sevkiyat Alan Ürünler
"""
        for urun, miktar in top_urunler.items():
            rapor += f"- {urun}: {int(miktar):,} adet\n"
        
        rapor += "\n### 🏪 En Çok Sevkiyat Alan Mağazalar\n"
        for magaza, miktar in top_magazalar.items():
            rapor += f"- {magaza}: {int(miktar):,} adet\n"
        
        return rapor


# ============================================
# KULLANIM ÖRNEĞİ
# ============================================
if __name__ == "__main__":
    print("Sevkiyat Motoru - Test")
    print("=" * 50)
    print("""
    Kullanım:
    
    from sevkiyat_motoru import SevkiyatMotoru
    
    # KupVeri yükle
    kup = KupVeri('./data')
    
    # Motor oluştur
    motor = SevkiyatMotoru(kup)
    
    # Sevkiyat hesapla
    sonuc = motor.hesapla(kategori_kod=11, forward_cover=7.0)
    
    # Hızlı özet
    print(motor.hizli_ozet(kategori_kod=11))
    """)
