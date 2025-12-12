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
def sesli_oku(metin: str, ses: str = "tr-TR-MertNeural") -> str:
    """
    Metni Türkçe sese çevirir ve HTML audio player döner.
    Edge TTS kullanır - ÜCRETSİZ ve kaliteli!
    
    Ses seçenekleri:
    - tr-TR-MertNeural (Erkek - varsayılan)
    - tr-TR-MeralNeural (Kadın)
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
        st.caption(f"📦 Stok/Satış: {len(kup.stok_satis):,} satır")
        st.caption(f"🏭 Depo: {len(kup.depo_stok):,} satır")
        if len(kup.trading) > 0:
            st.caption(f"📈 Trading: {len(kup.trading):,} satır")
        if len(kup.sc_sayfalari) > 0:
            st.caption(f"📊 SC Tablosu: {len(kup.sc_sayfalari)} sayfa")
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
            options=["👨 Mert (Erkek)", "👩 Meral (Kadın)"],
            horizontal=True
        )
        if "Mert" in ses_secimi:
            st.session_state['ses_turu'] = "tr-TR-MertNeural"
        else:
            st.session_state['ses_turu'] = "tr-TR-MeralNeural"
        st.caption("🎧 Microsoft Edge TTS - Doğal Türkçe ses")
    
    st.markdown("---")
    
    # Hızlı Komutlar
    st.subheader("⚡ Hızlı Komutlar")
    
    if st.button("📊 Genel Analiz Yap", use_container_width=True):
        st.session_state['hizli_komut'] = "Bu haftanın genel analizini yap. Kategorilere bak, sorunları tespit et, aksiyon önerileri sun."
    
    if st.button("🔴 Sorunları Bul", use_container_width=True):
        st.session_state['hizli_komut'] = "Tüm sorunlu SKU'ları tara. Yüksek cover, sevk gerekli ve düşük satışlı ürünleri bul."
    
    if st.button("🚚 Sevkiyat Planı", use_container_width=True):
        st.session_state['hizli_komut'] = "Sevk edilmesi gereken ürünleri bul ve önceliklendir."
    
    if st.button("🏷️ İndirim Önerileri", use_container_width=True):
        st.session_state['hizli_komut'] = "İndirime alınması gereken ürünleri bul. Cover'ı yüksek, satışı düşük olanları listele."

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
user_input = st.chat_input("Agent'a bir şey sor... (örn: 'SAÇ BAKIM kategorisini analiz et')")

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
                
                sonuc = agent_calistir(
                    api_key,
                    st.session_state['kup'],
                    mesaj
                )
                
                if sonuc and len(sonuc.strip()) > 0:
                    # Session'a kaydet
                    st.session_state['messages'].append({'role': 'user', 'content': mesaj})
                    st.session_state['messages'].append({'role': 'agent', 'content': sonuc})
                    # Cevabı göster
                    st.markdown(f'<div class="chat-message agent-message">🤖 {sonuc}</div>', unsafe_allow_html=True)
                    
                    # 🔊 Sesli okuma aktifse oku
                    if st.session_state.get('sesli_aktif', False):
                        ses_turu = st.session_state.get('ses_turu', 'tr-TR-MertNeural')
                        audio_html = sesli_oku(sonuc, ses=ses_turu)
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

# Temizle butonu
col1, col2, col3 = st.columns([1, 1, 1])
with col2:
    if st.button("🗑️ Sohbeti Temizle", use_container_width=True):
        st.session_state['messages'] = []
        st.rerun()

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
