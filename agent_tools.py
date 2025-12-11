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

# =============================================================================
# VERİ YÜKLEYİCİ
# =============================================================================

class KupVeri:
    """CSV tabanlı küp verisi yönetimi"""
    
    def __init__(self, veri_klasoru: str):
        """
        veri_klasoru: CSV dosyalarının bulunduğu klasör
        """
        self.veri_klasoru = veri_klasoru
        self._yukle()
        self._hazirla()
    
    def _yukle(self):
        """Tüm CSV'leri yükle"""
        
        # Anlık stok satış (parçalı dosyaları birleştir)
        stok_satis_files = glob.glob(os.path.join(self.veri_klasoru, "anlik_stok_satis*.csv"))
        if stok_satis_files:
            dfs = []
            for f in stok_satis_files:
                try:
                    df = pd.read_csv(f, encoding='utf-8')
                except:
                    df = pd.read_csv(f, encoding='latin-1')
                dfs.append(df)
            self.stok_satis = pd.concat(dfs, ignore_index=True)
        else:
            self.stok_satis = pd.DataFrame()
        
        # Master tablolar
        urun_path = os.path.join(self.veri_klasoru, "urun_master.csv")
        if os.path.exists(urun_path):
            try:
                self.urun_master = pd.read_csv(urun_path, encoding='utf-8')
            except:
                self.urun_master = pd.read_csv(urun_path, encoding='latin-1')
        else:
            self.urun_master = pd.DataFrame()
        
        magaza_path = os.path.join(self.veri_klasoru, "magaza_master.csv")
        if os.path.exists(magaza_path):
            try:
                self.magaza_master = pd.read_csv(magaza_path, encoding='utf-8')
            except:
                self.magaza_master = pd.read_csv(magaza_path, encoding='latin-1')
        else:
            self.magaza_master = pd.DataFrame()
        
        depo_path = os.path.join(self.veri_klasoru, "depo_stok.csv")
        if os.path.exists(depo_path):
            try:
                self.depo_stok = pd.read_csv(depo_path, encoding='utf-8')
            except:
                self.depo_stok = pd.read_csv(depo_path, encoding='latin-1')
        else:
            self.depo_stok = pd.DataFrame()
        
        kpi_path = os.path.join(self.veri_klasoru, "kpi.csv")
        if os.path.exists(kpi_path):
            try:
                self.kpi = pd.read_csv(kpi_path, encoding='utf-8')
            except:
                self.kpi = pd.read_csv(kpi_path, encoding='latin-1')
        else:
            self.kpi = pd.DataFrame()
        
        print(f"✅ Veri yüklendi:")
        print(f"   - Stok/Satış: {len(self.stok_satis):,} satır")
        print(f"   - Ürün Master: {len(self.urun_master):,} ürün | Kolonlar: {list(self.urun_master.columns)}")
        print(f"   - Mağaza Master: {len(self.magaza_master):,} mağaza | Kolonlar: {list(self.magaza_master.columns)}")
        print(f"   - Depo Stok: {len(self.depo_stok):,} satır")
        print(f"   - KPI: {len(self.kpi):,} satır | Kolonlar: {list(self.kpi.columns)}")
    
    def _hazirla(self):
        """Veriyi zenginleştir ve hesaplamalar yap"""
        
        if len(self.stok_satis) == 0:
            return
        
        # Ürün master ile join (sadece mevcut kolonları al)
        if len(self.urun_master) > 0:
            urun_kolonlar = ['urun_kod']
            for kol in ['kategori_kod', 'umg', 'mg', 'marka_kod', 'nitelik', 'durum']:
                if kol in self.urun_master.columns:
                    urun_kolonlar.append(kol)
            
            if len(urun_kolonlar) > 1:
                self.stok_satis = self.stok_satis.merge(
                    self.urun_master[urun_kolonlar],
                    on='urun_kod',
                    how='left'
                )
        
        # Mağaza master ile join (sadece mevcut kolonları al)
        if len(self.magaza_master) > 0:
            mag_kolonlar = ['magaza_kod']
            for kol in ['il', 'bolge', 'tip', 'depo_kod']:
                if kol in self.magaza_master.columns:
                    mag_kolonlar.append(kol)
            
            if len(mag_kolonlar) > 1:
                self.stok_satis = self.stok_satis.merge(
                    self.magaza_master[mag_kolonlar],
                    on='magaza_kod',
                    how='left'
                )
        
        # KPI ile join (mg bazlı)
        if len(self.kpi) > 0 and 'mg' in self.stok_satis.columns:
            kpi_df = self.kpi.copy()
            if 'mg_id' in kpi_df.columns:
                kpi_df = kpi_df.rename(columns={'mg_id': 'mg'})
            
            if 'mg' in kpi_df.columns:
                self.stok_satis = self.stok_satis.merge(
                    kpi_df,
                    on='mg',
                    how='left'
                )
        
        # Kar hesapla
        self.stok_satis['kar'] = self.stok_satis['ciro'] - self.stok_satis['smm']
        
        # Kar marjı
        self.stok_satis['kar_marji'] = np.where(
            self.stok_satis['ciro'] > 0,
            self.stok_satis['kar'] / self.stok_satis['ciro'],
            0
        )
        
        # Haftalık satış (şimdilik satis kolonunu kullan)
        self.stok_satis['haftalik_satis'] = self.stok_satis['satis']
        
        # Cover hesapla
        self.stok_satis['cover'] = np.where(
            self.stok_satis['haftalik_satis'] > 0,
            self.stok_satis['stok'] / self.stok_satis['haftalik_satis'],
            np.where(self.stok_satis['stok'] > 0, 999, 0)
        )
        
        # Stok durumu değerlendirme
        self.stok_satis['stok_durum'] = 'NORMAL'
        
        # Min altı = SEVKİYAT GEREKLİ
        mask_min = self.stok_satis['stok'] < self.stok_satis['min_deger'].fillna(3)
        self.stok_satis.loc[mask_min, 'stok_durum'] = 'SEVK_GEREKLI'
        
        # Max üstü = FAZLA STOK
        mask_max = self.stok_satis['stok'] > self.stok_satis['max_deger'].fillna(20)
        self.stok_satis.loc[mask_max, 'stok_durum'] = 'FAZLA_STOK'
        
        # Cover hedefin üstünde = YAVAS
        mask_cover = self.stok_satis['cover'] > self.stok_satis['forward_cover'].fillna(4) * 3
        self.stok_satis.loc[mask_cover & (self.stok_satis['stok_durum'] == 'NORMAL'), 'stok_durum'] = 'YAVAS'


# =============================================================================
# ARAÇ FONKSİYONLARI
# =============================================================================

def genel_ozet(kup: KupVeri) -> str:
    """Genel özet - kategoriler ve bölgeler bazında durum"""
    
    if len(kup.stok_satis) == 0:
        return "Veri yüklenmemiş."
    
    sonuc = []
    sonuc.append("=== GENEL ÖZET ===\n")
    
    # Toplam metrikler
    toplam_stok = kup.stok_satis['stok'].sum()
    toplam_satis = kup.stok_satis['satis'].sum()
    toplam_ciro = kup.stok_satis['ciro'].sum()
    toplam_kar = kup.stok_satis['kar'].sum()
    
    sonuc.append(f"📦 Toplam Mağaza Stok: {toplam_stok:,.0f} adet")
    sonuc.append(f"🛒 Toplam Satış: {toplam_satis:,.0f} adet")
    sonuc.append(f"💰 Toplam Ciro: {toplam_ciro:,.0f} TL")
    sonuc.append(f"📈 Toplam Kar: {toplam_kar:,.0f} TL")
    
    # Depo stok
    if len(kup.depo_stok) > 0:
        depo_toplam = kup.depo_stok['stok'].sum()
        sonuc.append(f"🏭 Toplam Depo Stok: {depo_toplam:,.0f} adet")
    
    # Stok durumu dağılımı
    sonuc.append("\n--- Stok Durumu Dağılımı ---")
    durum_ozet = kup.stok_satis.groupby('stok_durum').agg({
        'urun_kod': 'count',
        'stok': 'sum'
    }).reset_index()
    durum_ozet.columns = ['Durum', 'Satir_Sayisi', 'Stok']
    
    for _, row in durum_ozet.iterrows():
        emoji = {'SEVK_GEREKLI': '🔴', 'FAZLA_STOK': '🟡', 'YAVAS': '🟠', 'NORMAL': '✅'}.get(row['Durum'], '⚪')
        sonuc.append(f"{emoji} {row['Durum']}: {row['Satir_Sayisi']:,} satır, {row['Stok']:,.0f} adet stok")
    
    # Kategori bazlı özet
    if 'kategori_kod' in kup.stok_satis.columns:
        sonuc.append("\n--- Kategori Bazlı Özet ---")
        kat_ozet = kup.stok_satis.groupby('kategori_kod').agg({
            'stok': 'sum',
            'satis': 'sum',
            'ciro': 'sum',
            'kar': 'sum'
        }).reset_index()
        kat_ozet['kar_marji'] = kat_ozet['kar'] / (kat_ozet['ciro'] + 0.01) * 100
        kat_ozet = kat_ozet.nlargest(10, 'ciro')
        
        for _, row in kat_ozet.iterrows():
            durum = "✅" if row['kar_marji'] > 0 else "🔴"
            sonuc.append(f"{durum} Kat {row['kategori_kod']}: Stok {row['stok']:,.0f} | Satış {row['satis']:,.0f} | Kar %{row['kar_marji']:.1f}")
    
    # Bölge bazlı özet
    if 'bolge' in kup.stok_satis.columns:
        sonuc.append("\n--- Bölge Bazlı Özet ---")
        bolge_ozet = kup.stok_satis.groupby('bolge').agg({
            'stok': 'sum',
            'satis': 'sum',
            'ciro': 'sum'
        }).reset_index()
        bolge_ozet = bolge_ozet.nlargest(10, 'ciro')
        
        for _, row in bolge_ozet.iterrows():
            if pd.notna(row['bolge']):
                sonuc.append(f"  {row['bolge']}: Stok {row['stok']:,.0f} | Satış {row['satis']:,.0f} | Ciro {row['ciro']:,.0f}")
    
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
    
    # Sevk gereken satırlar
    sevk_gerekli = kup.stok_satis[kup.stok_satis['stok_durum'] == 'SEVK_GEREKLI'].copy()
    
    if len(sevk_gerekli) == 0:
        return "✅ Sevk gereken ürün bulunmuyor."
    
    sonuc.append(f"Toplam sevk gereken: {len(sevk_gerekli):,} mağaza×ürün kombinasyonu\n")
    
    # Ürün bazlı önceliklendirme (satışa göre)
    urun_oncelik = sevk_gerekli.groupby('urun_kod').agg({
        'magaza_kod': 'count',
        'satis': 'sum',
        'stok': 'sum',
        'min_deger': 'first'
    }).reset_index()
    urun_oncelik.columns = ['urun_kod', 'magaza_sayisi', 'toplam_satis', 'toplam_stok', 'min_deger']
    urun_oncelik['eksik'] = urun_oncelik['magaza_sayisi'] * urun_oncelik['min_deger'].fillna(3) - urun_oncelik['toplam_stok']
    urun_oncelik = urun_oncelik.sort_values('toplam_satis', ascending=False).head(limit)
    
    # Depo stok kontrolü
    if len(kup.depo_stok) > 0:
        urun_oncelik = urun_oncelik.merge(
            kup.depo_stok.groupby('urun_kod')['stok'].sum().reset_index().rename(columns={'stok': 'depo_stok'}),
            on='urun_kod',
            how='left'
        )
        urun_oncelik['depo_stok'] = urun_oncelik['depo_stok'].fillna(0)
    else:
        urun_oncelik['depo_stok'] = 0
    
    sonuc.append(f"{'Ürün Kodu':<12} | {'Mağaza#':>8} | {'Satış':>8} | {'Eksik':>8} | {'Depo':>8} | Durum")
    sonuc.append("-" * 75)
    
    for _, row in urun_oncelik.iterrows():
        if row['depo_stok'] >= row['eksik']:
            durum = "✅ Sevk edilebilir"
        elif row['depo_stok'] > 0:
            durum = "🟡 Kısmi sevk"
        else:
            durum = "🔴 Depoda yok"
        
        sonuc.append(f"{row['urun_kod']:<12} | {row['magaza_sayisi']:>8,} | {row['toplam_satis']:>8,.0f} | {row['eksik']:>8,.0f} | {row['depo_stok']:>8,.0f} | {durum}")
    
    # Özet
    sevk_edilebilir = len(urun_oncelik[urun_oncelik['depo_stok'] >= urun_oncelik['eksik']])
    sonuc.append(f"\n--- Özet ---")
    sonuc.append(f"✅ Tam sevk edilebilir: {sevk_edilebilir} ürün")
    sonuc.append(f"🟡 Kısmi sevk: {len(urun_oncelik[(urun_oncelik['depo_stok'] > 0) & (urun_oncelik['depo_stok'] < urun_oncelik['eksik'])])} ürün")
    sonuc.append(f"🔴 Depoda yok: {len(urun_oncelik[urun_oncelik['depo_stok'] == 0])} ürün")
    
    return "\n".join(sonuc)


def fazla_stok_analiz(kup: KupVeri, limit: int = 50) -> str:
    """Fazla stok analizi - indirim adayları"""
    
    sonuc = []
    sonuc.append("=== FAZLA STOK ANALİZİ (İNDİRİM ADAYLARI) ===\n")
    
    # Fazla stok ve yavaş dönen
    fazla = kup.stok_satis[kup.stok_satis['stok_durum'].isin(['FAZLA_STOK', 'YAVAS'])].copy()
    
    if len(fazla) == 0:
        return "✅ Fazla stok bulunmuyor."
    
    sonuc.append(f"Toplam fazla/yavaş stok: {len(fazla):,} mağaza×ürün kombinasyonu\n")
    
    # Ürün bazlı özet
    urun_ozet = fazla.groupby('urun_kod').agg({
        'magaza_kod': 'count',
        'stok': 'sum',
        'satis': 'sum',
        'ciro': 'sum'
    }).reset_index()
    urun_ozet.columns = ['urun_kod', 'magaza_sayisi', 'toplam_stok', 'toplam_satis', 'toplam_ciro']
    urun_ozet['cover'] = urun_ozet['toplam_stok'] / (urun_ozet['toplam_satis'] + 0.1)
    urun_ozet = urun_ozet.sort_values('toplam_stok', ascending=False).head(limit)
    
    sonuc.append(f"{'Ürün Kodu':<12} | {'Mağaza#':>8} | {'Stok':>10} | {'Satış':>8} | {'Cover':>8} | Öneri")
    sonuc.append("-" * 75)
    
    for _, row in urun_ozet.iterrows():
        if row['cover'] > 52:
            oneri = "🔴 Agresif indirim"
        elif row['cover'] > 26:
            oneri = "🟡 Kampanya"
        else:
            oneri = "🟢 İzle"
        
        sonuc.append(f"{row['urun_kod']:<12} | {row['magaza_sayisi']:>8,} | {row['toplam_stok']:>10,.0f} | {row['toplam_satis']:>8,.0f} | {row['cover']:>7.1f}hf | {oneri}")
    
    return "\n".join(sonuc)


def bolge_karsilastir(kup: KupVeri) -> str:
    """Bölgeler arası karşılaştırma"""
    
    if 'bolge' not in kup.stok_satis.columns:
        return "Bölge bilgisi mevcut değil."
    
    sonuc = []
    sonuc.append("=== BÖLGE KARŞILAŞTIRMASI ===\n")
    
    bolge_ozet = kup.stok_satis.groupby('bolge').agg({
        'magaza_kod': 'nunique',
        'urun_kod': 'nunique',
        'stok': 'sum',
        'satis': 'sum',
        'ciro': 'sum',
        'kar': 'sum'
    }).reset_index()
    bolge_ozet.columns = ['Bolge', 'Magaza', 'Urun', 'Stok', 'Satis', 'Ciro', 'Kar']
    bolge_ozet['Kar_Marji'] = bolge_ozet['Kar'] / (bolge_ozet['Ciro'] + 0.01) * 100
    bolge_ozet['Cover'] = bolge_ozet['Stok'] / (bolge_ozet['Satis'] + 0.1)
    bolge_ozet = bolge_ozet.sort_values('Ciro', ascending=False)
    
    sonuc.append(f"{'Bölge':<15} | {'Mağaza':>7} | {'Ciro':>12} | {'Kar %':>7} | {'Cover':>7}")
    sonuc.append("-" * 60)
    
    for _, row in bolge_ozet.iterrows():
        if pd.notna(row['Bolge']):
            durum = "✅" if row['Kar_Marji'] > 0 else "🔴"
            sonuc.append(f"{durum} {str(row['Bolge']):<13} | {row['Magaza']:>7,} | {row['Ciro']:>12,.0f} | {row['Kar_Marji']:>6.1f}% | {row['Cover']:>6.1f}hf")
    
    return "\n".join(sonuc)


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
    }
]

SYSTEM_PROMPT = """Sen EVE Kozmetik için çalışan deneyimli bir Retail Planner'sın. Adın "Sanal Planner".

Görevin mağaza ve ürün verilerini analiz edip şu kararları vermek:
1. Sevkiyat stratejisi - KPI hedeflerine göre hangi ürünler hangi mağazalara gönderilmeli
2. İndirim/kampanya kararları - fazla stoklu ve yavaş dönen ürünler için öneriler
3. Bölge ve kategori bazlı performans analizi
4. Mağaza ve ürün bazlı detaylı inceleme

Kullandığın KPI kriterleri:
- min_deger: Mağazada minimum olması gereken stok
- max_deger: Mağazada maksimum olması gereken stok  
- forward_cover: Hedef stok/satış oranı (hafta)

Stok durumu tanımları:
- SEVK_GEREKLI (🔴): Stok < min_deger → Acil sevkiyat gerekli
- FAZLA_STOK (🟡): Stok > max_deger → İndirim/kampanya düşünülmeli
- YAVAS (🟠): Cover > hedefin 3 katı → Yavaş dönen ürün
- NORMAL (✅): Hedef aralığında

Çalışma şeklin:
1. Önce genel_ozet ile büyük resme bak
2. Sorunlu alanları tespit et (kategori, bölge, mağaza)
3. Detay araçlarıyla derine in
4. sevkiyat_plani veya fazla_stok_analiz ile aksiyon listesi çıkar

Türkçe yanıt ver. Bulgularını net ve aksiyona dönük şekilde sun."""


def agent_calistir(api_key: str, kup: KupVeri, kullanici_mesaji: str) -> str:
    """Agent'ı çalıştır ve sonuç al"""
    
    client = anthropic.Anthropic(api_key=api_key)
    
    messages = [{"role": "user", "content": kullanici_mesaji}]
    
    tum_cevaplar = []
    max_iterasyon = 10
    iterasyon = 0
    
    while iterasyon < max_iterasyon:
        iterasyon += 1
        
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages
        )
        
        # Tool kullanımı var mı kontrol et
        tool_kullanimi = False
        
        for block in response.content:
            if block.type == "text":
                tum_cevaplar.append(block.text)
            
            elif block.type == "tool_use":
                tool_kullanimi = True
                tool_name = block.name
                tool_input = block.input
                tool_use_id = block.id
                
                # Tool'u çağır
                if tool_name == "genel_ozet":
                    tool_result = genel_ozet(kup)
                elif tool_name == "kategori_analiz":
                    tool_result = kategori_analiz(kup, tool_input.get("kategori_kod", ""))
                elif tool_name == "magaza_analiz":
                    tool_result = magaza_analiz(kup, tool_input.get("magaza_kod", ""))
                elif tool_name == "urun_analiz":
                    tool_result = urun_analiz(kup, tool_input.get("urun_kod", ""))
                elif tool_name == "sevkiyat_plani":
                    tool_result = sevkiyat_plani(kup, tool_input.get("limit", 50))
                elif tool_name == "fazla_stok_analiz":
                    tool_result = fazla_stok_analiz(kup, tool_input.get("limit", 50))
                elif tool_name == "bolge_karsilastir":
                    tool_result = bolge_karsilastir(kup)
                else:
                    tool_result = f"Bilinmeyen araç: {tool_name}"
                
                # Mesajlara ekle
                messages.append({"role": "assistant", "content": response.content})
                messages.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": tool_result
                    }]
                })
        
        # Tool kullanımı yoksa döngüden çık
        if not tool_kullanimi or response.stop_reason == "end_turn":
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
