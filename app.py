import streamlit as st
import pandas as pd
import plotly.express as px
from streamlit_autorefresh import st_autorefresh
import gspread
import io
import pytz
import time
from datetime import datetime
import google.generativeai as genai
from google.auth import default
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.cloud import storage

# --- CONFIGURAÇÕES DO SENTINELA ---
st.set_page_config(page_title="Sentinela Web - v0.2", layout="wide", page_icon="🛡️")
st_autorefresh(interval=60 * 1000, key="datarefresh")

API_KEY = "AQ.Ab8RN6JE7BnDyhh_t8iY8lHnJ8Ul4Ea0_DARUh8I2ifcHAqb6w"
PLANILHA_ID = "1DYQ6Hsbp5xua9RFGmNGeKqITGZygvo6gIdtF4WkMG1Q"
BUCKET_NAME = "bucket-sentinela"
MATRIZ_FILE_NAME = "matriz_sentinela.csv"
FOLDER_ID_DESTINO = "1Ei8yXaANNHoj-Hvsy6Yyvm-AQVTzHX2N"

genai.configure(api_key=API_KEY, transport='rest')
fuso_br = pytz.timezone('America/Sao_Paulo')

# --- FUNÇÕES NATIVAS DO MONITOR ---
def obter_matriz_do_storage():
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(MATRIZ_FILE_NAME)
        conteudo = blob.download_as_text()
        return pd.read_csv(io.StringIO(conteudo))
    except:
        return pd.DataFrame()

def carregar_dados_planilha():
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    creds, _ = default(scopes=SCOPES)
    client_gs = gspread.authorize(creds)
    sh = client_gs.open_by_key(PLANILHA_ID)
    worksheet = sh.sheet1
    df = pd.DataFrame(worksheet.get_all_records())
    return df, worksheet, creds

# --- INTERFACE ---
st.title("🛡️ Sentinela - Inteligência Fiscal Autônoma")

if 'logado' not in st.session_state:
    st.session_state.logado = False

if not st.session_state.logado:
    with st.sidebar:
        senha = st.text_input("Acesso Sentinela", type="password")
        if senha == "farol2026":
            st.session_state.logado = True
            st.rerun()
    st.warning("Aguardando autenticação...")
    st.stop()

# Carregamento Real-time
try:
    df, ws, creds = carregar_dados_planilha()
except Exception as e:
    st.error(f"Erro de conexão com o ecossistema Google: {e}")
    st.stop()

# Dashboard de métricas reais
col1, col2, col3, col4 = st.columns(4)
total = len(df)
proc = len(df[df['Status'].str.contains('2', na=False)])
pend = len(df[df['Status'].str.contains('1', na=False)])

col1.metric("Arquivos no Fluxo", total)
col2.metric("Processados ✅", proc)
col3.metric("Aguardando ⏳", pend, delta=f"{pend} pendentes", delta_color="inverse")
col4.metric("Eficiência", f"{(proc/total*100 if total > 0 else 0):.1f}%")

# Área de Auditoria
st.divider()
colunas_tabela = ["Número do Processo", "Tipo de Documento", "Data", "Status"]
selecao = st.dataframe(df[colunas_tabela], use_container_width=True, on_select="rerun", selection_mode="single-row")

if len(selecao['selection']['rows']) > 0:
    idx = selecao['selection']['rows'][0]
    row = df.iloc[idx]
    
    st.subheader(f"🔍 Análise: {row['Número do Processo']}")
    
    tab1, tab2 = st.tabs(["📄 Resultado da IA", "🚀 Ações do Auditor"])
    
    with tab1:
        st.write(row.get('Retorno', 'Sem dados de retorno.'))
        if 'Métricas de Execução' in row:
            st.caption(f"⚙️ {row['Métricas de Execução']}")
            
    with tab2:
        if st.button("📝 Disparar Re-análise (Gemini 3.1 Flash Lite)"):
            with st.spinner("O Sentinela está re-analisando o documento..."):
                # REPRODUZINDO A LÓGICA DO SEU MONITOR
                model = genai.GenerativeModel(model_name='models/gemini-3.1-flash-lite-preview')
                service_drive = build('drive', 'v3', credentials=creds)
                file_id = row.get('ID do Arquivo')
                
                # Download
                req = service_drive.files().get_media(fileId=file_id)
                fh = io.BytesIO()
                downloader = MediaIoBaseDownload(fh, req)
                done = False
                while not done: _, done = downloader.next_chunk()
                
                # IA
                df_matriz = obter_matriz_do_storage()
                regras = df_matriz.to_markdown(index=False) if not df_matriz.empty else "Analise conforme padrões gerais."
                
                prompt = f"Você é o Agente Sentinela. Analise conforme a MATRIZ: {regras}. Responda em JSON."
                pdf_part = {"mime_type": "application/pdf", "data": fh.getvalue()}
                
                response = model.generate_content([prompt, pdf_part], generation_config={"response_mime_type": "application/json"})
                
                # Atualização (Linha idx + 2 pois pandas é 0 e planilha tem cabeçalho)
                cabecalho = ws.row_values(1)
                col_ret = cabecalho.index('Retorno') + 1
                ws.update_cell(idx + 2, col_ret, response.text)
                st.success("Análise atualizada na planilha!")
                st.rerun()

        st.link_button("📂 Abrir Arquivo no Drive", f"https://docs.google.com/document/d/{row['ID do Arquivo']}")

# Gráfico Evolutivo
df['Data_dt'] = pd.to_datetime(df['Data'], dayfirst=True, errors='coerce')
df_dia = df.groupby(df['Data_dt'].dt.date)['Status'].value_counts().unstack().fillna(0)
st.plotly_chart(px.line(df_dia, title="Monitoramento Sentinela 24h", markers=True), use_container_width=True)
