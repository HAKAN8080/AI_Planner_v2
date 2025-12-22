"""
SANAL PLANNER - Agentic Streamlit Arayüzü
Claude API Tool Calling ile akıllı retail planner
🔊 Sesli Yanıt Özellikli (Edge TTS - Kaliteli Türkçe)
📑 PDF Rapor Desteği (Türkçe karakter tam uyumlu)
"""

import streamlit as st
import pandas as pd
from datetime import datetime
import os
import base64
from io import BytesIO
import asyncio

# ============================================
# 📑 PDF RAPOR MODÜLÜ - TÜRKÇE DESTEKLI
# ============================================

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor, black, gray
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import re

# Emoji → Metin dönüşüm tablosu
EMOJI_MAP = {
    '📊': '[GRAFIK]', '📋': '[LISTE]', '📦': '[KUTU]', '🔴': '[!]',
    '🟡': '[~]', '🟢': '[OK]', '✅': '[OK]', '❌': '[X]', '⚠️': '[!]',
    '🚨': '[!!]', '💰': '[TL]', '💵': '[TL]', '📈': '[+]', '📉': '[-]',
    '🏆': '[TOP]', '🏪': '[MAG]', '🏭': '[DEPO]', '🎯': '[*]', '⭐': '[*]',
    '🤖': '', '🧑': '', '💬': '', '📁': '[DOSYA]', '📌': '[*]',
    '💡': '[i]', '🔍': '[?]', '📅': '[TARIH]', '🔧': '[AYAR]',
    '📥': '[INDIR]', '📑': '[PDF]',
}

def setup_turkish_fonts():
    """Türkçe karakter destekleyen fontları yükle"""
    font_paths = [
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
    ]
    for path in font_paths:
        if 'Bold' not in path and os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont('DejaVuSans', path))
            except:
                pass
        elif 'Bold' in path and os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', path))
            except:
                pass

def temizle_emoji(text: str) -> str:
    """Emojileri metin karşılıklarıyla değiştir"""
    for emoji, replacement in EMOJI_MAP.items():
        text = text.replace(emoji, replacement)
    # Kalan emojileri kaldır
    text = re.sub(r'[\U0001F600-\U0001F64F]', '', text)
    text = re.sub(r'[\U0001F300-\U0001F5FF]', '', text)
    text = re.sub(r'[\U0001F680-\U0001F6FF]', '', text)
    text = re.sub(r'[\U0001F900-\U0001F9FF]', '', text)
    return text

def get_turkish_styles():
    """Türkçe karakter destekli stiller"""
    styles = getSampleStyleSheet()
    
    # Tüm stillere Türkçe font ata
    for style_name in ['Normal', 'BodyText', 'Title', 'Heading1', 'Heading2', 'Heading3']:
        if style_name in styles:
            styles[style_name].fontName = 'DejaVuSans'
    
    styles['Normal'].fontSize = 10
    styles['Normal'].leading = 14
    
    styles['Heading1'].fontName = 'DejaVuSans-Bold'
    styles['Heading1'].fontSize = 14
    styles['Heading1'].textColor = HexColor('#1E3A8A')
    
    styles['Heading2'].fontName = 'DejaVuSans-Bold'
    styles['Heading2'].fontSize = 12
    styles['Heading2'].textColor = HexColor('#374151')
    
    styles['Heading3'].fontName = 'DejaVuSans-Bold'
    styles['Heading3'].fontSize = 10
    styles['Heading3'].textColor = HexColor('#4B5563')
    
    # Özel stiller
    styles.add(ParagraphStyle(
        name='TurkishTitle',
        fontName='DejaVuSans-Bold',
        fontSize=18,
        leading=22,
        alignment=TA_CENTER,
        spaceAfter=20,
        textColor=HexColor('#1E3A8A')
    ))
    
    styles.add(ParagraphStyle(
        name='ListItem',
        fontName='DejaVuSans',
        fontSize=10,
        leading=14,
        leftIndent=20,
    ))
    
    styles.add(ParagraphStyle(
        name='Footer',
        fontName='DejaVuSans',
        fontSize=8,
        textColor=gray,
        alignment=TA_CENTER
    ))
    
    return styles

def parse_markdown_to_elements(text: str, styles) -> list:
    """Markdown'ı PDF elementlerine çevir"""
    elements = []
    lines = text.split('\n')
    
    table_buffer = []
    in_table = False
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        if not line:
            if in_table and table_buffer:
                elements.append(create_table_element(table_buffer))
                table_buffer = []
                in_table = False
            elements.append(Spacer(1, 6))
            i += 1
            continue
        
        line = temizle_emoji(line)
        
        # Ayraç
        if re.match(r'^[=\-]{3,}$', line):
            if in_table and table_buffer:
                elements.append(create_table_element(table_buffer))
                table_buffer = []
                in_table = False
            elements.append(HRFlowable(width="100%", thickness=1, color=gray))
            i += 1
            continue
        
        # Tablo satırı
        if '|' in line and not line.startswith('#'):
            if re.match(r'^[\|\-\s:]+$', line):
                i += 1
                continue
            in_table = True
            cells = [c.strip() for c in line.split('|') if c.strip()]
            if cells:
                table_buffer.append(cells)
            i += 1
            continue
        
        if in_table and table_buffer:
            elements.append(create_table_element(table_buffer))
            table_buffer = []
            in_table = False
        
        # Başlıklar
        if line.startswith('# '):
            title = line[2:].strip()
            title = re.sub(r'\*\*(.+?)\*\*', r'\1', title)
            elements.append(Paragraph(title, styles['Heading1']))
            elements.append(Spacer(1, 10))
            i += 1
            continue
        
        if line.startswith('## '):
            title = line[3:].strip()
            title = re.sub(r'\*\*(.+?)\*\*', r'\1', title)
            elements.append(Paragraph(title, styles['Heading2']))
            elements.append(Spacer(1, 8))
            i += 1
            continue
        
        if line.startswith('### '):
            title = line[4:].strip()
            title = re.sub(r'\*\*(.+?)\*\*', r'\1', title)
            elements.append(Paragraph(title, styles['Heading3']))
            elements.append(Spacer(1, 6))
            i += 1
            continue
        
        # Liste
        if re.match(r'^[\-\*]\s+', line):
            item = re.sub(r'^[\-\*]\s+', '', line)
            item = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', item)
            elements.append(Paragraph(f"• {item}", styles['ListItem']))
            i += 1
            continue
        
        # Numaralı liste
        if re.match(r'^\d+\.\s+', line):
            num = re.match(r'^(\d+)\.', line).group(1)
            item = re.sub(r'^\d+\.\s+', '', line)
            item = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', item)
            elements.append(Paragraph(f"{num}. {item}", styles['ListItem']))
            i += 1
            continue
        
        # Normal paragraf
        para = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', line)
        elements.append(Paragraph(para, styles['Normal']))
        i += 1
    
    if table_buffer:
        elements.append(create_table_element(table_buffer))
    
    return elements

def create_table_element(rows: list) -> Table:
    """Tablo oluştur"""
    if not rows:
        return Spacer(1, 1)
    
    max_cols = max(len(row) for row in rows)
    normalized = [row + [''] * (max_cols - len(row)) for row in rows]
    
    table = Table(normalized)
    table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, 0), 'DejaVuSans-Bold'),
        ('FONTNAME', (0, 1), (-1, -1), 'DejaVuSans'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#E8E8E8')),
        ('GRID', (0, 0), (-1, -1), 0.5, gray),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    return table

def create_pdf_report(soru: str, cevap: str, title: str = "Sanal Planner - Analiz Raporu") -> bytes:
    """PDF raporu oluştur"""
    setup_turkish_fonts()
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                           leftMargin=2*cm, rightMargin=2*cm,
                           topMargin=2*cm, bottomMargin=2*cm)
    
    styles = get_turkish_styles()
    story = []
    
    # Başlık
    story.append(Paragraph(title, styles['TurkishTitle']))
    tarih = datetime.now().strftime('%d.%m.%Y %H:%M')
    story.append(Paragraph(f"Tarih: {tarih}", styles['Footer']))
    story.append(HRFlowable(width="100%", thickness=2, color=HexColor('#1E3A8A')))
    story.append(Spacer(1, 20))
    
    # Soru
    if soru:
        story.append(Paragraph("SORU", styles['Heading2']))
        story.append(Paragraph(temizle_emoji(soru), styles['Normal']))
        story.append(Spacer(1, 15))
    
    # Cevap
    story.append(Paragraph("ANALİZ SONUCU", styles['Heading2']))
    story.append(Spacer(1, 10))
    
    cevap_elements = parse_markdown_to_elements(cevap, styles)
    story.extend(cevap_elements)
    
    # Footer
    story.append(Spacer(1, 30))
    story.append(HRFlowable(width="100%", thickness=1, color=gray))
    story.append(Paragraph("Sanal Planner | Thorius AR4U", styles['Footer']))
    
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

def create_chat_pdf(messages: list) -> bytes:
    """Tüm sohbetten PDF oluştur"""
    setup_turkish_fonts()
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                           leftMargin=2*cm, rightMargin=2*cm,
                           topMargin=2*cm, bottomMargin=2*cm)
    
    styles = get_turkish_styles()
    story = []
    
    story.append(Paragraph("Sanal Planner - Sohbet Geçmişi", styles['TurkishTitle']))
    tarih = datetime.now().strftime('%d.%m.%Y %H:%M')
    story.append(Paragraph(f"Tarih: {tarih}", styles['Footer']))
    story.append(HRFlowable(width="100%", thickness=2, color=HexColor('#1E3A8A')))
    story.append(Spacer(1, 20))
    
    for i, msg in enumerate(messages):
        role = msg.get('role', 'user')
        content = msg.get('content', '')
        
        if role == 'user':
            story.append(Paragraph("KULLANICI", styles['Heading3']))
            story.append(Paragraph(temizle_emoji(content), styles['Normal']))
        else:
            story.append(Paragraph("SANAL PLANNER", styles['Heading3']))
            elements = parse_markdown_to_elements(content, styles)
            story.extend(elements)
        
        story.append(Spacer(1, 15))
        if role == 'agent' and i < len(messages) - 1:
            story.append(HRFlowable(width="80%", thickness=0.5, color=gray))
            story.append(Spacer(1, 15))
    
    story.append(Spacer(1, 30))
    story.append(HRFlowable(width="100%", thickness=1, color=gray))
    story.append(Paragraph("Sanal Planner | Thorius AR4U", styles['Footer']))
    
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


# ============================================
# 🔊 TTS (Text-to-Speech) FONKSİYONU - EDGE TTS
# ============================================
def sesli_oku(metin: str, ses: str = "tr-TR-AhmetNeural") -> str:
    """Metni Türkçe sese çevirir ve HTML audio player döner."""
    try:
        import edge_tts
        
        temiz_metin = metin[:3000] if len(metin) > 3000 else metin
        for char in ['===', '---', '📊', '🚨', '✅', '❌', '⚠️', '🔴', '🏆', '🏪', '🏭', '📦', '💰', '📈', '🤖', '🧑', '💬', '*', '#']:
            temiz_metin = temiz_metin.replace(char, '')
        
        async def generate_audio():
            communicate = edge_tts.Communicate(temiz_metin, ses)
            audio_buffer = BytesIO()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_buffer.write(chunk["data"])
            return audio_buffer.getvalue()
        
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        audio_data = loop.run_until_complete(generate_audio())
        audio_base64 = base64.b64encode(audio_data).decode()
        
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


# ============================================
# STREAMLIT ARAYÜZÜ
# ============================================

st.set_page_config(
    page_title="Sanal Planner | EVE Kozmetik",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .main-header { font-size: 2.5rem; font-weight: bold; color: #1E3A8A; margin-bottom: 0; }
    .sub-header { font-size: 1.1rem; color: #6B7280; margin-top: 0; }
    .chat-message { padding: 1rem; border-radius: 10px; margin: 0.5rem 0; }
    .user-message { background-color: #E0E7FF; margin-left: 20%; }
    .agent-message { background-color: #F3F4F6; margin-right: 20%; }
</style>
""", unsafe_allow_html=True)

col1, col2 = st.columns([3, 1])
with col1:
    st.markdown('<p class="main-header">🤖 Sanal Planner</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">EVE Kozmetik | Agentic Retail Planning Assistant</p>', unsafe_allow_html=True)
with col2:
    st.markdown(f"**📅 {datetime.now().strftime('%d.%m.%Y')}**")

st.markdown("---")

# Sidebar
with st.sidebar:
    st.header("⚙️ Ayarlar")
    
    # API Key
    st.subheader("🔑 Claude API")
    try:
        api_key_secret = st.secrets.get("ANTHROPIC_API_KEY", "")
    except:
        api_key_secret = ""
    
    if api_key_secret:
        api_key = api_key_secret
        st.success("✅ API Key (secrets'tan)")
    else:
        api_key = st.text_input("API Key", type="password")
        if api_key:
            st.success("✅ API Key girildi")
        else:
            st.warning("⚠️ API Key gerekli")
    
    st.markdown("---")
    
    # Veri Yükleme
    st.subheader("📊 Veri Yükle")
    uploaded_files = st.file_uploader(
        "Dosyaları seçin",
        type=['csv', 'xlsx', 'xls'],
        accept_multiple_files=True
    )
    
    if uploaded_files:
        if st.button("📂 Veriyi Yükle", use_container_width=True):
            try:
                import tempfile
                from agent_tools import KupVeri
                
                with tempfile.TemporaryDirectory() as temp_dir:
                    for uploaded_file in uploaded_files:
                        file_path = os.path.join(temp_dir, uploaded_file.name)
                        with open(file_path, 'wb') as f:
                            f.write(uploaded_file.getbuffer())
                        st.caption(f"✅ {uploaded_file.name}")
                    
                    with st.spinner("Veri işleniyor..."):
                        st.session_state['kup'] = KupVeri(temp_dir)
                        st.session_state['kup_yuklendi'] = True
                
                st.success("✅ Veri yüklendi!")
                st.rerun()
                
            except Exception as e:
                import traceback
                st.error(f"❌ Hata: {str(e)}")
                st.code(traceback.format_exc())
    
    if st.session_state.get('kup_yuklendi') and 'kup' in st.session_state:
        st.success("✅ Veri hazır")
        kup = st.session_state['kup']
        if len(kup.trading) > 0:
            st.caption(f"📈 Trading: {len(kup.trading):,} satır")
        if hasattr(kup, 'cover_diagram') and len(kup.cover_diagram) > 0:
            st.caption(f"🎯 Cover Diagram: {len(kup.cover_diagram):,} satır")
        if hasattr(kup, 'kapasite') and len(kup.kapasite) > 0:
            st.caption(f"🏪 Kapasite: {len(kup.kapasite):,} satır")
        if hasattr(kup, 'siparis_takip') and len(kup.siparis_takip) > 0:
            st.caption(f"📋 Sipariş Takip: {len(kup.siparis_takip):,} satır")
    else:
        st.info("👆 Dosyaları yükleyin")
    
    st.markdown("---")
    
    # Sesli Yanıt
    st.subheader("🔊 Sesli Yanıt")
    sesli_aktif = st.toggle("Cevapları sesli oku", value=False)
    st.session_state['sesli_aktif'] = sesli_aktif
    
    if sesli_aktif:
        ses_secimi = st.radio("Ses seçin:", ["👨 Erol (Erkek)", "👩 Eftelya (Kadın)"], horizontal=True)
        st.session_state['ses_turu'] = "tr-TR-AhmetNeural" if "Erol" in ses_secimi else "tr-TR-EmelNeural"
    
    st.markdown("---")
    
    # Analiz Kuralları
    st.subheader("📋 Analiz Kuralları")
    with st.expander("⚙️ AI Eğitim Ayarları", expanded=False):
        analiz_sirasi = st.multiselect(
            "Analiz sırası",
            ["Trading Analiz", "Cover Analiz", "Sevkiyat Kontrolü", "Stok/Ciro Dengesi"],
            default=["Trading Analiz", "Cover Analiz"]
        )
        
        col1, col2 = st.columns(2)
        with col1:
            esik_cover_yuksek = st.number_input("Cover Yüksek (hf)", 6, 20, 12)
            esik_cover_dusuk = st.number_input("Cover Düşük (hf)", 1, 8, 4)
        with col2:
            esik_butce_sapma = st.number_input("Bütçe Sapma (%)", 5, 30, 15)
            esik_lfl_dusus = st.number_input("LFL Düşüş (%)", 5, 40, 20)
        
        st.session_state['analiz_kurallari'] = {
            'analiz_sirasi': analiz_sirasi,
            'esikler': {
                'cover_yuksek': esik_cover_yuksek,
                'cover_dusuk': esik_cover_dusuk,
                'butce_sapma': esik_butce_sapma,
                'lfl_dusus': esik_lfl_dusus,
            }
        }
    
    st.markdown("---")
    
    # Hızlı Komutlar
    st.subheader("⚡ Hızlı Komutlar")
    if st.button("📊 Genel Durum", use_container_width=True):
        st.session_state['hizli_komut'] = "Bu haftanın genel analizini yap. Şirket toplamı bütçe gerçekleşme, en yüksek cirolu 3 ana grup, cover durumu, marj değişimi ve fiyat artışı vs enflasyon karşılaştırması yap."
    if st.button("🏪 Kapasite Analizi", use_container_width=True):
        st.session_state['hizli_komut'] = "Mağaza kapasite analizini yap. Doluluk oranları, en dolu ve en boş mağazalar, cover durumları ve kapasite sorunlarını detaylı analiz et."
    if st.button("📋 Sipariş Durumu", use_container_width=True):
        st.session_state['hizli_komut'] = "Sipariş ve tedarik durumunu analiz et. Toplam bütçe vs sipariş vs depoya giren, ana grup bazında sipariş durumu ve tedarik sıkıntıları neler?"
    
    # Grup Detay Analizi
    st.markdown("---")
    st.subheader("🔍 Grup Detay Analizi")
    
    # Ana grupları trading'den çek
    ana_grup_listesi = []
    if st.session_state.get('kup_yuklendi') and 'kup' in st.session_state:
        kup = st.session_state['kup']
        if len(kup.trading) > 0:
            # Mevcut Ana Grup kolonunu bul
            ana_grup_kolon = None
            for col in kup.trading.columns:
                if 'ana grup' in str(col).lower() or 'ana_grup' in str(col).lower():
                    ana_grup_kolon = col
                    break
            
            if ana_grup_kolon:
                # Unique ana grupları al, Toplam ve Genel Toplam hariç
                tum_gruplar = kup.trading[ana_grup_kolon].dropna().unique().tolist()
                ana_grup_listesi = [g for g in tum_gruplar if g and 'Toplam' not in str(g) and 'Genel' not in str(g) and str(g).strip() != '' and str(g).lower() != 'nan']
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
                if st.button("📈 Trading", use_container_width=True, key="btn_trading"):
                    st.session_state['hizli_komut'] = f"{secili_ana_grup} ana grubunun detaylı trading analizini yap. Bütçe gerçekleşme, ciro, cover, marj ve LFL performansını göster."
            with col2:
                if st.button("🎯 Cover", use_container_width=True, key="btn_cover"):
                    st.session_state['hizli_komut'] = f"{secili_ana_grup} ana grubunun cover diagram analizini yap. Hangi alt gruplarda ve mağazalarda yavaş stok var?"
            
            if st.button(f"🔎 {secili_ana_grup} Tam Detay", use_container_width=True, key="btn_detay"):
                st.session_state['hizli_komut'] = f"{secili_ana_grup} grubunu detaylı analiz et. Ara grupları, alt grupları, sorunlu ürünleri ve aksiyon önerilerini sun."
    else:
        st.caption("📁 Veri yüklenince ana gruplar burada listelenecek")


# Ana içerik - Chat
st.header("💬 Planner ile Konuş")

if 'messages' not in st.session_state:
    st.session_state['messages'] = []

for msg in st.session_state['messages']:
    if msg['role'] == 'user':
        st.markdown(f'<div class="chat-message user-message">🧑 {msg["content"]}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="chat-message agent-message">🤖 {msg["content"]}</div>', unsafe_allow_html=True)

# Hızlı komut
if 'hizli_komut' in st.session_state and st.session_state['hizli_komut']:
    kullanici_mesaji = st.session_state['hizli_komut']
    st.session_state['hizli_komut'] = None
else:
    kullanici_mesaji = None

user_input = st.chat_input("Soru sor...")
mesaj = kullanici_mesaji or user_input

if mesaj:
    if not api_key:
        st.error("❌ API key girin.")
    elif 'kup' not in st.session_state:
        st.error("❌ Veri yükleyin.")
    else:
        st.markdown(f'<div class="chat-message user-message">🧑 {mesaj}</div>', unsafe_allow_html=True)
        
        with st.spinner("🤖 Sanal Planner düşünüyor..."):
            try:
                from agent_tools import agent_calistir
                
                analiz_kurallari = st.session_state.get('analiz_kurallari', None)
                sonuc = agent_calistir(api_key, st.session_state['kup'], mesaj, analiz_kurallari=analiz_kurallari)
                
                if sonuc and len(sonuc.strip()) > 0:
                    st.session_state['messages'].append({'role': 'user', 'content': mesaj})
                    st.session_state['messages'].append({'role': 'agent', 'content': sonuc})
                    st.markdown(f'<div class="chat-message agent-message">🤖 {sonuc}</div>', unsafe_allow_html=True)
                    
                    if st.session_state.get('sesli_aktif', False):
                        sesli_metin = sonuc.split("📊")[0] if "📊" in sonuc else sonuc[:1500]
                        ses_turu = st.session_state.get('ses_turu', 'tr-TR-AhmetNeural')
                        audio_html = sesli_oku(sesli_metin.strip(), ses=ses_turu)
                        st.markdown(audio_html, unsafe_allow_html=True)
                else:
                    st.warning("⚠️ Agent yanıt vermedi.")
                    
            except Exception as e:
                import traceback
                st.error(f"❌ Hata: {str(e)}")
                st.code(traceback.format_exc())


# Alt butonlar
col1, col2, col3, col4 = st.columns(4)

with col1:
    if st.button("🗑️ Sohbeti Temizle", use_container_width=True):
        st.session_state['messages'] = []
        st.rerun()

with col2:
    if st.session_state.get('messages'):
        sohbet_metni = ""
        for msg in st.session_state['messages']:
            prefix = "🧑 KULLANICI" if msg['role'] == 'user' else "🤖 SANAL PLANNER"
            sohbet_metni += f"{prefix}:\n{msg['content']}\n\n{'='*60}\n\n"
        
        st.download_button(
            label="📋 TXT İndir",
            data=sohbet_metni,
            file_name="sanal_planner_sohbet.txt",
            mime="text/plain",
            use_container_width=True
        )

with col3:
    # Son cevabı PDF olarak indir
    if st.session_state.get('messages'):
        son_soru = ""
        son_cevap = ""
        for msg in reversed(st.session_state['messages']):
            if msg['role'] == 'agent' and not son_cevap:
                son_cevap = msg['content']
            elif msg['role'] == 'user' and son_cevap and not son_soru:
                son_soru = msg['content']
                break
        
        if son_cevap:
            try:
                pdf_bytes = create_pdf_report(soru=son_soru, cevap=son_cevap)
                st.download_button(
                    label="📄 Son Rapor PDF",
                    data=pdf_bytes,
                    file_name=f"sanal_planner_rapor_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
            except Exception as e:
                st.error(f"PDF hatası: {e}")

with col4:
    # Tüm sohbeti PDF olarak indir
    if st.session_state.get('messages') and len(st.session_state['messages']) >= 2:
        try:
            pdf_bytes = create_chat_pdf(st.session_state['messages'])
            st.download_button(
                label="📑 Tüm Sohbet PDF",
                data=pdf_bytes,
                file_name=f"sanal_planner_sohbet_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                mime="application/pdf",
                use_container_width=True
            )
        except Exception as e:
            st.error(f"PDF hatası: {e}")


# Footer
st.markdown("---")
st.markdown(
    """<div style='text-align: center; color: #6B7280; font-size: 0.9rem;'>
    🤖 Sanal Planner v2.1 | Thorius AR4U | EVE Kozmetik
    </div>""",
    unsafe_allow_html=True
)
