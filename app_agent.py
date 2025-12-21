"""
SANAL PLANNER - Agentic Streamlit Arayüzü
Claude API Tool Calling ile akıllı retail planner
🔊 Sesli Yanıt Özellikli (Edge TTS - Kaliteli Türkçe)
"""

import streamlit as st
import pandas as pd
from datetime import datetime
import os
import base64
from io import BytesIO
import asyncio

# ============================================
# 🔊 TTS (Text-to-Speech) FONKSİYONU - EDGE TTS
# ============================================
def sesli_oku(metin: str, ses: str = "tr-TR-AhmetNeural") -> str:
    """
    Metni Türkçe sese çevirir ve HTML audio player döner.
    Edge TTS kullanır - ÜCRETSİZ ve kaliteli!
    
    Ses seçenekleri:
    - tr-TR-AhmetNeural (Erkek - varsayılan)
    - tr-TR-EmelNeural (Kadın)
    """
    try:
        import edge_tts
        
        # Metni temizle (çok uzunsa kısalt)
        temiz_metin = metin[:3000] if len(metin) > 3000 else metin
        
        # Özel karakterleri temizle
        temiz_metin = temiz_metin.replace("===", "").replace("---", "")
        temiz_metin = temiz_metin.replace("📊", "").replace("🚨", "").replace("✅", "")
        temiz_metin = temiz_metin.replace("❌", "").replace("⚠️", "").replace("🔴", "")
        temiz_metin = temiz_metin.replace("🏆", "").replace("🏪", "").replace("🏭", "")
        temiz_metin = temiz_metin.replace("📦", "").replace("💰", "").replace("📈", "")
        temiz_metin = temiz_metin.replace("🤖", "").replace("🧑", "").replace("💬", "")
        temiz_metin = temiz_metin.replace("*", "").replace("#", "")
        
        # Async fonksiyonu çalıştır
        async def generate_audio():
            communicate = edge_tts.Communicate(temiz_metin, ses)
            audio_buffer = BytesIO()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_buffer.write(chunk["data"])
            return audio_buffer.getvalue()
        
        # Event loop
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        audio_data = loop.run_until_complete(generate_audio())
        
        # Base64'e çevir
        audio_base64 = base64.b64encode(audio_data).decode()
        
        # HTML audio player (autoplay)
        audio_html = f'''
        <audio autoplay controls style="width: 100%; margin-top: 10px; border-radius: 10px;">
            <source src="data:audio/mp3;base64,{audio_base64}" type="audio/mp3">
        </audio>
        '''
        return audio_html
        
    except ImportError:
        return "<p style='color: orange;'>⚠️ Sesli okuma için: pip install edge-tts</p>"
    except Exception as e:
        return f"<p style='color: red;'>❌ Ses hatası: {str(e)}</p>"

# Sayfa ayarları
st.set_page_config(
    page_title="Sanal Planner | EVE Kozmetik",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1E3A8A;
        margin-bottom: 0;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #6B7280;
        margin-top: 0;
    }
    .chat-message {
        padding: 1rem;
        border-radius: 10px;
        margin: 0.5rem 0;
    }
    .user-message {
        background-color: #E0E7FF;
        margin-left: 20%;
    }
    .agent-message {
        background-color: #F3F4F6;
        margin-right: 20%;
    }
    .tool-call {
        background-color: #FEF3C7;
        font-size: 0.8rem;
        padding: 0.5rem;
        border-radius: 5px;
        margin: 0.3rem 0;
    }
</style>
""", unsafe_allow_html=True)

# Header
col1, col2 = st.columns([3, 1])
with col1:
    st.markdown('<p class="main-header">🤖 Sanal Planner</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">EVE Kozmetik | Agentic Retail Planning Assistant</p>', unsafe_allow_html=True)
with col2:
    st.markdown(f"**📅 {datetime.now().strftime('%d.%m.%Y')}**")

st.markdown("---")

# Sidebar - API Key ve Veri Yükleme
with st.sidebar:
    st.header("⚙️ Ayarlar")
    
    # API Key - önce secrets'tan dene, yoksa input al
    st.subheader("🔑 Claude API")
    
    # Secrets'tan oku
    try:
        api_key_secret = st.secrets.get("ANTHROPIC_API_KEY", "")
    except:
        api_key_secret = ""
    
    if api_key_secret:
        api_key = api_key_secret
        st.success("✅ API Key (secrets'tan)")
    else:
        api_key = st.text_input(
            "API Key",
            type="password",
            help="console.anthropic.com'dan aldığın API key"
        )
        if api_key:
            st.success("✅ API Key girildi")
        else:
            st.warning("⚠️ API Key gerekli (secrets veya manuel)")
    
    st.markdown("---")
    
    # Veri Yükleme - FILE UPLOAD
    st.subheader("📊 Veri Yükle")
    
    st.caption("CSV ve Excel dosyalarını yükleyin")
    
    # Dosya upload alanları
    uploaded_files = st.file_uploader(
        "Dosyaları seçin",
        type=['csv', 'xlsx', 'xls'],
        accept_multiple_files=True,
        help="anlik_stok_satis.csv, urun_master.csv, magaza_master.csv, depo_stok.csv, kpi.csv, trading.xlsx, SC Tablosu.xlsx"
    )
    
    if uploaded_files:
        if st.button("📂 Veriyi Yükle", use_container_width=True):
            try:
                import tempfile
                import os
                from agent_tools import KupVeri
                
                # Geçici klasör oluştur
                with tempfile.TemporaryDirectory() as temp_dir:
                    # Dosyaları geçici klasöre kaydet
                    for uploaded_file in uploaded_files:
                        file_path = os.path.join(temp_dir, uploaded_file.name)
                        with open(file_path, 'wb') as f:
                            f.write(uploaded_file.getbuffer())
                        st.caption(f"✅ {uploaded_file.name}")
                    
                    # KupVeri ile yükle
                    with st.spinner("Veri işleniyor..."):
                        st.session_state['kup'] = KupVeri(temp_dir)
                        st.session_state['kup_yuklendi'] = True
                
                st.success("✅ Veri yüklendi!")
                st.rerun()
                
            except Exception as e:
                import traceback
                st.error(f"❌ Hata: {str(e)}")
                st.code(traceback.format_exc())
    
    # Veri durumu göster
    if st.session_state.get('kup_yuklendi') and 'kup' in st.session_state:
        st.success("✅ Veri hazır")
        kup = st.session_state['kup']
        
        # Sadece yüklenen raporları göster
        if len(kup.trading) > 0:
            st.caption(f"📈 Trading: {len(kup.trading):,} satır")
        if len(kup.cover_diagram) > 0:
            st.caption(f"🎯 Cover Diagram: {len(kup.cover_diagram):,} satır")
        if len(kup.kapasite) > 0:
            st.caption(f"🏪 Kapasite: {len(kup.kapasite):,} satır")
        if len(kup.siparis_takip) > 0:
            st.caption(f"📋 Sipariş Takip: {len(kup.siparis_takip):,} satır")
        
        # Opsiyonel: Eski raporlar (varsa göster)
        if len(kup.stok_satis) > 0:
            st.caption(f"📦 Stok/Satış: {len(kup.stok_satis):,} satır")
        if len(kup.depo_stok) > 0:
            st.caption(f"🏭 Depo: {len(kup.depo_stok):,} satır")
    else:
        st.info("👆 Dosyaları yükleyin ve 'Veriyi Yükle' butonuna basın")
    
    st.markdown("---")
    
    # 🔊 Sesli Yanıt Ayarı
    st.subheader("🔊 Sesli Yanıt")
    sesli_aktif = st.toggle("Cevapları sesli oku", value=False, help="Sanal Planner cevaplarını Türkçe sesli okur")
    st.session_state['sesli_aktif'] = sesli_aktif
    
    if sesli_aktif:
        ses_secimi = st.radio(
            "Ses seçin:",
            options=["👨 Erol (Erkek)", "👩 Eftelya (Kadın)"],
            horizontal=True
        )
        if "Erol" in ses_secimi:
            st.session_state['ses_turu'] = "tr-TR-AhmetNeural"
        else:
            st.session_state['ses_turu'] = "tr-TR-EmelNeural"
        st.caption("🎧 Sanal Planner Sesi - Doğal Türkçe")
    
    st.markdown("---")
    
    # ================================================================
    # 📋 ANALİZ KURALLARI - AI EĞİTİM PANELİ
    # ================================================================
    st.subheader("📋 Analiz Kuralları")
    
    with st.expander("⚙️ AI Eğitim Ayarları", expanded=False):
        
        # --- ANALİZ SIRASI ---
        st.markdown("**📊 Analiz Sırası**")
        analiz_sirasi = st.multiselect(
            "Sırayla hangi analizler yapılsın?",
            options=["Trading Analiz", "Cover Analiz", "Sevkiyat Kontrolü", "Stok/Ciro Dengesi"],
            default=["Trading Analiz", "Cover Analiz"],
            help="AI bu sırayla analiz yapacak"
        )
        
        st.markdown("---")
        
        # --- UYARI EŞİKLERİ ---
        st.markdown("**⚠️ Uyarı Eşikleri**")
        
        col1, col2 = st.columns(2)
        with col1:
            esik_cover_yuksek = st.number_input("Cover Yüksek (hafta)", min_value=6, max_value=20, value=12, help="Bu değerin üstü 🔴 uyarı")
            esik_cover_dusuk = st.number_input("Cover Düşük (hafta)", min_value=1, max_value=8, value=4, help="Bu değerin altı 🔴 sevkiyat gerek")
        with col2:
            esik_butce_sapma = st.number_input("Bütçe Sapma (%)", min_value=5, max_value=30, value=15, help="Bu yüzdenin altı 🔴 kritik")
            esik_lfl_dusus = st.number_input("LFL Düşüş (%)", min_value=5, max_value=40, value=20, help="Bu yüzdenin altı 🔴 ciddi küçülme")
        
        esik_marj_dusus = st.number_input("Marj Düşüşü (puan)", min_value=1, max_value=10, value=3, help="Geçen yıla göre bu kadar puan düşüş 🔴")
        
        st.markdown("---")
        
        # --- STOK/CİRO DENGESİ ---
        st.markdown("**📦 Stok/Ciro Dengesi**")
        col1, col2 = st.columns(2)
        with col1:
            esik_stok_fazla = st.slider("Stok Fazlası Oranı", 1.0, 2.0, 1.3, 0.1, help="Stok payı / Ciro payı > bu değer ise 'ERİTME gerekli'")
        with col2:
            esik_stok_az = st.slider("Stok Azlığı Oranı", 0.3, 1.0, 0.7, 0.1, help="Stok payı / Ciro payı < bu değer ise 'SEVKİYAT gerekli'")
        
        st.markdown("---")
        
        # --- YORUM KURALLARI ---
        st.markdown("**💬 Yorum Kuralları**")
        
        yorum_cover_yuksek = st.text_input(
            "Cover yüksekse:",
            value="Stok eritme kampanyası başlat, indirim planla",
            help="AI bu yorumu yapacak"
        )
        yorum_butce_dusuk = st.text_input(
            "Bütçe düşükse:",
            value="Satış hızlandırıcı aksiyonlar gerekli, kampanya planla",
            help="AI bu yorumu yapacak"
        )
        yorum_marj_dusuk = st.text_input(
            "Marj düşüşü varsa:",
            value="Fiyat/maliyet analizi yap, tedarikçi görüşmesi öner",
            help="AI bu yorumu yapacak"
        )
        yorum_lfl_negatif = st.text_input(
            "LFL negatifse:",
            value="Kategori performans analizi yap, rakip araştırması öner",
            help="AI bu yorumu yapacak"
        )
        
        st.markdown("---")
        
        # --- ÖNCELİK SIRASI ---
        st.markdown("**🎯 Raporlama Önceliği**")
        oncelik_sirasi = st.multiselect(
            "Raporda önce hangi metrikler gösterilsin?",
            options=["Bütçe Gerçekleşme", "Cover", "LFL Ciro", "LFL Adet", "Marj", "Fiyat Artışı"],
            default=["Bütçe Gerçekleşme", "Cover", "LFL Ciro"],
            help="AI bu sırayla raporlayacak"
        )
        
        # --- EK TALİMATLAR ---
        st.markdown("**📝 Ek Talimatlar**")
        ek_talimatlar = st.text_area(
            "AI'ya özel talimatlar:",
            value="Her zaman önce şirket toplamına bak, sonra kategorilere in. Kritik durumları vurgula.",
            height=80,
            help="Serbest metin - AI bu talimatlara uyacak"
        )
        
        # Session state'e kaydet
        st.session_state['analiz_kurallari'] = {
            'analiz_sirasi': analiz_sirasi,
            'esikler': {
                'cover_yuksek': esik_cover_yuksek,
                'cover_dusuk': esik_cover_dusuk,
                'butce_sapma': esik_butce_sapma,
                'lfl_dusus': esik_lfl_dusus,
                'marj_dusus': esik_marj_dusus,
                'stok_fazla': esik_stok_fazla,
                'stok_az': esik_stok_az
            },
            'yorumlar': {
                'cover_yuksek': yorum_cover_yuksek,
                'butce_dusuk': yorum_butce_dusuk,
                'marj_dusuk': yorum_marj_dusuk,
                'lfl_negatif': yorum_lfl_negatif
            },
            'oncelik_sirasi': oncelik_sirasi,
            'ek_talimatlar': ek_talimatlar
        }
        
        st.success("✅ Kurallar kaydedildi")
    
    st.markdown("---")
    
    # Hızlı Komutlar
    st.subheader("⚡ Hızlı Komutlar")
    
    # 1. Genel Durum
    if st.button("📊 Genel Durum", use_container_width=True):
        st.session_state['hizli_komut'] = "Bu haftanın genel analizini yap. Şirket toplamı bütçe gerçekleşme, en yüksek cirolu 3 ana grup, cover durumu, marj değişimi ve fiyat artışı vs enflasyon karşılaştırması yap."
    
    # 2. Kapasite Analizi
    if st.button("🏪 Kapasite Analizi", use_container_width=True):
        st.session_state['hizli_komut'] = "Mağaza kapasite analizini yap. Doluluk oranları, en dolu ve en boş mağazalar, cover durumları ve kapasite sorunlarını detaylı analiz et."
    
    # 3. Sipariş Durum Analizi
    if st.button("📋 Sipariş Durumu", use_container_width=True):
        st.session_state['hizli_komut'] = "Sipariş ve tedarik durumunu analiz et. Toplam bütçe vs sipariş vs depoya giren, ana grup bazında sipariş durumu ve tedarik sıkıntıları neler?"
    
    # 4. Grup Detay Analizi (Seçimli)
    st.markdown("---")
    st.markdown("**🔍 Grup Detay Analizi**")
    
    # Ana grupları trading'den çek
    ana_grup_listesi = []
    if st.session_state.get('kup_yuklendi') and 'kup' in st.session_state:
        kup = st.session_state['kup']
        if len(kup.trading) > 0:
            # Mevcut Ana Grup kolonunu bul
            ana_grup_kolon = None
            for col in kup.trading.columns:
                if 'ana grup' in col.lower() or 'ana_grup' in col.lower():
                    ana_grup_kolon = col
                    break
            
            if ana_grup_kolon:
                # Unique ana grupları al, Toplam ve Genel Toplam hariç
                tum_gruplar = kup.trading[ana_grup_kolon].dropna().unique().tolist()
                ana_grup_listesi = [g for g in tum_gruplar if g and 'Toplam' not in str(g) and 'Genel' not in str(g)]
                ana_grup_listesi = sorted(set(ana_grup_listesi))
    
    if ana_grup_listesi:
        secili_ana_grup = st.selectbox(
            "Ana Grup Seçin:",
            options=["-- Seçiniz --"] + ana_grup_listesi,
            key="ana_grup_secim"
        )
        
        if secili_ana_grup and secili_ana_grup != "-- Seçiniz --":
            col1, col2 = st.columns(2)
            with col1:
                if st.button("📈 Trading Analiz", use_container_width=True, key="btn_trading"):
                    st.session_state['hizli_komut'] = f"{secili_ana_grup} ana grubunun detaylı trading analizini yap. Bütçe gerçekleşme, ciro, cover, marj ve LFL performansını göster."
            with col2:
                if st.button("🎯 Cover Analiz", use_container_width=True, key="btn_cover"):
                    st.session_state['hizli_komut'] = f"{secili_ana_grup} ana grubunun cover diagram analizini yap. Hangi alt gruplarda ve mağazalarda yavaş stok var?"
            
            if st.button(f"🔎 {secili_ana_grup} Tam Detay", use_container_width=True, key="btn_detay"):
                st.session_state['hizli_komut'] = f"{secili_ana_grup} grubunu detaylı analiz et. Ara grupları, alt grupları, sorunlu ürünleri ve aksiyon önerilerini sun."
    else:
        st.caption("📁 Veri yüklenince ana gruplar burada listelenecek")

# Ana içerik - Chat arayüzü
st.header("💬 Planner ile Konuş")

# Chat geçmişi
if 'messages' not in st.session_state:
    st.session_state['messages'] = []

# Mesajları göster
for msg in st.session_state['messages']:
    if msg['role'] == 'user':
        st.markdown(f'<div class="chat-message user-message">🧑 {msg["content"]}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="chat-message agent-message">🤖 {msg["content"]}</div>', unsafe_allow_html=True)

# Hızlı komut varsa kullan
if 'hizli_komut' in st.session_state and st.session_state['hizli_komut']:
    kullanici_mesaji = st.session_state['hizli_komut']
    st.session_state['hizli_komut'] = None
else:
    kullanici_mesaji = None

# Chat input
user_input = st.chat_input("Soru sor... (örn: 'Bu hafta nasıl gitti?', 'Stok durumu nedir?', 'Hangi kategoriler sorunlu?')")

# Input varsa işle
mesaj = kullanici_mesaji or user_input

if mesaj:
    # Kontroller
    if not api_key:
        st.error("❌ Lütfen sol panelden API key girin.")
    elif 'kup' not in st.session_state:
        st.error("❌ Lütfen sol panelden veri dosyalarını yükleyin.")
    else:
        # Kullanıcı mesajını hemen göster
        st.markdown(f'<div class="chat-message user-message">🧑 {mesaj}</div>', unsafe_allow_html=True)
        
        # Spinner ile cevap bekle
        with st.spinner("🤖 Sanal Planner düşünüyor... (Bu 10-30 saniye sürebilir)"):
            try:
                from agent_tools import agent_calistir
                import traceback
                
                # Analiz kurallarını al
                analiz_kurallari = st.session_state.get('analiz_kurallari', None)
                
                sonuc = agent_calistir(
                    api_key,
                    st.session_state['kup'],
                    mesaj,
                    analiz_kurallari=analiz_kurallari
                )
                
                if sonuc and len(sonuc.strip()) > 0:
                    # Session'a kaydet
                    st.session_state['messages'].append({'role': 'user', 'content': mesaj})
                    st.session_state['messages'].append({'role': 'agent', 'content': sonuc})
                    # Cevabı göster
                    st.markdown(f'<div class="chat-message agent-message">🤖 {sonuc}</div>', unsafe_allow_html=True)
                    
                    # 🔊 Sesli okuma aktifse oku (sadece tablo öncesi kısmı)
                    if st.session_state.get('sesli_aktif', False):
                        # Tablodan önceki kısmı al (📊 veya | işaretine kadar)
                        sesli_metin = sonuc
                        if "📊" in sesli_metin:
                            sesli_metin = sesli_metin.split("📊")[0]
                        elif "|" in sesli_metin and "---" in sesli_metin:
                            # Markdown tablo var, öncesini al
                            lines = sesli_metin.split("\n")
                            sesli_lines = []
                            for line in lines:
                                if "|" in line or "---" in line:
                                    break
                                sesli_lines.append(line)
                            sesli_metin = "\n".join(sesli_lines)
                        
                        ses_turu = st.session_state.get('ses_turu', 'tr-TR-AhmetNeural')
                        audio_html = sesli_oku(sesli_metin.strip(), ses=ses_turu)
                        st.markdown(audio_html, unsafe_allow_html=True)
                else:
                    st.session_state['messages'].append({'role': 'user', 'content': mesaj})
                    st.session_state['messages'].append({'role': 'agent', 'content': "⚠️ Agent yanıt vermedi. Lütfen tekrar deneyin."})
                    st.warning("⚠️ Agent yanıt vermedi. Lütfen tekrar deneyin.")
                
            except Exception as e:
                error_msg = f"❌ Hata: {str(e)}\n\nDetay:\n{traceback.format_exc()}"
                st.error(error_msg)
                st.session_state['messages'].append({'role': 'user', 'content': mesaj})
                st.session_state['messages'].append({'role': 'agent', 'content': error_msg})

# Temizle ve Dışa Aktar butonları
col1, col2, col3, col4 = st.columns([1, 1, 1, 1])

with col1:
    if st.button("🗑️ Sohbeti Temizle", use_container_width=True):
        st.session_state['messages'] = []
        st.rerun()

with col2:
    # Sohbeti kopyala butonu
    if st.session_state.get('messages'):
        sohbet_metni = ""
        for msg in st.session_state['messages']:
            if msg['role'] == 'user':
                sohbet_metni += f"🧑 KULLANICI:\n{msg['content']}\n\n"
            else:
                sohbet_metni += f"🤖 SANAL PLANNER:\n{msg['content']}\n\n{'='*60}\n\n"
        
        st.download_button(
            label="📋 Sohbeti İndir",
            data=sohbet_metni,
            file_name="sanal_planner_sohbet.txt",
            mime="text/plain",
            use_container_width=True
        )

with col3:
    # Son cevabı kopyala
    if st.session_state.get('messages'):
        son_cevap = ""
        for msg in reversed(st.session_state['messages']):
            if msg['role'] == 'agent':
                son_cevap = msg['content']
                break
        
        if son_cevap:
            st.download_button(
                label="📄 Son Cevabı İndir",
                data=son_cevap,
                file_name="sanal_planner_analiz.md",
                mime="text/markdown",
                use_container_width=True
            )

with col4:
    # PDF oluştur - önce reportlab var mı kontrol et
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        import io
        
        REPORTLAB_AVAILABLE = True
    except ImportError:
        REPORTLAB_AVAILABLE = False
    
    if st.session_state.get('messages') and REPORTLAB_AVAILABLE:
        # PDF'i önceden oluştur
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, 
                               leftMargin=2*cm, rightMargin=2*cm,
                               topMargin=2*cm, bottomMargin=2*cm)
        
        styles = getSampleStyleSheet()
        story = []
        
        # Başlık
        title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=18, spaceAfter=20)
        story.append(Paragraph("Sanal Planner - Analiz Raporu", title_style))
        story.append(Spacer(1, 12))
        
        # Mesajları ekle
        for msg in st.session_state['messages']:
            if msg['role'] == 'user':
                # Türkçe karakterleri ve özel karakterleri temizle
                clean_q = msg['content'].encode('ascii', 'ignore').decode('ascii')
                story.append(Paragraph(f"<b>Soru:</b> {clean_q}", styles['Normal']))
            else:
                # Markdown ve emojileri temizle
                clean_text = msg['content']
                for char in ['**', '##', '#', '🤖', '🧑', '📊', '📋', '🔴', '✅', '⚠️', '🎯', '💰', '📦', '📈', '💵', '🏆', '⭐', '🚨']:
                    clean_text = clean_text.replace(char, '')
                clean_text = clean_text.encode('ascii', 'ignore').decode('ascii')
                story.append(Paragraph(f"<b>Cevap:</b><br/>{clean_text[:2500]}", styles['Normal']))
            story.append(Spacer(1, 12))
        
        try:
            doc.build(story)
            buffer.seek(0)
            
            st.download_button(
                label="📑 PDF İndir",
                data=buffer.getvalue(),
                file_name="sanal_planner_rapor.pdf",
                mime="application/pdf",
                use_container_width=True
            )
        except Exception as e:
            st.error(f"PDF hatası: {e}")
    
    elif st.session_state.get('messages') and not REPORTLAB_AVAILABLE:
        if st.button("📑 PDF (kurulum gerekli)", use_container_width=True, disabled=True):
            pass
        st.caption("pip install reportlab")

# Footer
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: #6B7280; font-size: 0.9rem;'>
        🤖 Sanal Planner v2.0 (Agentic) | Thorius AR4U Ekosistemi | EVE Kozmetik
    </div>
    """, 
    unsafe_allow_html=True
)
