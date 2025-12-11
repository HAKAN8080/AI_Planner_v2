"""
SANAL PLANNER - Agentic Streamlit Arayüzü
Claude API Tool Calling ile akıllı retail planner
"""

import streamlit as st
import pandas as pd
from datetime import datetime
import os

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
    
    # Veri Yükleme
    st.subheader("📊 Veri Yükle (CSV)")
    
    st.caption("CSV dosyalarının olduğu klasör yolunu gir")
    
    veri_klasoru = st.text_input(
        "Veri Klasörü",
        value="./data",
        help="anlik_stok_satis*.csv, urun_master.csv, magaza_master.csv, depo_stok.csv, kpi.csv dosyalarının bulunduğu klasör"
    )
    
    if st.button("📂 Veriyi Yükle", use_container_width=True):
        try:
            from agent_tools import KupVeri
            with st.spinner("Veri yükleniyor..."):
                st.session_state['kup'] = KupVeri(veri_klasoru)
                st.session_state['kup_yuklendi'] = True
            st.success("✅ Veri yüklendi!")
        except Exception as e:
            st.error(f"❌ Hata: {str(e)}")
    
    if 'kup_yuklendi' in st.session_state and st.session_state['kup_yuklendi']:
        st.success("✅ Veri hazır")
    
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
