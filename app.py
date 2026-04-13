import streamlit as st
import pandas as pd
import plotly.express as px
from streamlit_autorefresh import st_autorefresh
import gspread
import io
import pytz
import os
from datetime import datetime
import google.generativeai as genai
from google.auth import default
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.cloud import storage

# --- CONFIGURAÇÕES DO SENTINELA ---
st.set_page_config(page_title="Sentinela", layout="wide", page_icon="🛡️")
st_autorefresh(interval=60 * 1000, key="datarefresh")

PLANILHA_ID = "1DYQ6Hsbp5xua9RFGmNGeKqITGZygvo6gIdtF4WkMG1Q"
BUCKET_NAME = "bucket-sentinela"
MATRIZ_FILE_NAME = "matriz_sentinela.csv"
MODEL_NAME = 'models/gemini-3.1-flash-lite-preview'

fuso_br = pytz.timezone('America/Sao_Paulo')

# --- FUNÇÕES DE DADOS E AUTENTICAÇÃO OAUTH2 ---
def carregar_contexto_google():
    # Usando a mesma lógica que funcionou no seu backend
    SCOPES = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive',
        'https://www.googleapis.com/auth/generative-language'
    ]
    creds, _ = default(scopes=SCOPES)
    
    # Configura o Gemini para usar OAuth2 em vez de API_KEY
    genai.configure(credentials=creds)
    
    client_gs = gspread.authorize(creds)
    sh = client_gs.open_by_key(PLANILHA_ID)
    return sh.sheet1, creds

def obter_matriz_do_storage():
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(MATRIZ_FILE_NAME)
        conteudo = blob.download_as_text()
        return pd.read_csv(io.StringIO(conteudo))
    except:
        return pd.DataFrame()

# --- SISTEMA DE LOGIN CENTRALIZADO ---
if 'logado' not in st.session_state:
    st.session_state.logado = False

if not st.session_state.logado:
    col_l1, col_l2, col_l3 = st.columns([1, 1, 1])
    with col_l2:
        st.write("#")
        st.title("🛡️ Sentinela")
        senha_input = st.text_input("Senha de Acesso", type="password")
        if st.button("Entrar"):
            if senha_input == "farol2026":
                st.session_state.logado = True
                st.rerun()
            else:
                st.error("Senha incorreta.")
    st.stop()

# --- CARREGAMENTO DE DADOS ---
try:
    ws, creds = carregar_contexto_google()
    df = pd.DataFrame(ws.get_all_records())
except Exception as e:
    st.error(f"Erro de conexão com ecossistema Google: {e}")
    st.stop()

# --- MENU LATERAL ---
st.sidebar.title("🛡️ Sentinela")
menu = st.sidebar.radio("Navegação", ["Dashboard", "Controle"])
st.sidebar.divider()
if st.sidebar.button("Sair"):
    st.session_state.logado = False
    st.rerun()

# --- ABA: DASHBOARD ---
if menu == "Dashboard":
    st.header("Dashboard")
    c1, c2, c3, c4 = st.columns(4)
    total = len(df)
    proc = len(df[df['Status'].astype(str).str.contains('2', na=False)])
    pend = len(df[df['Status'].astype(str).str.contains('1', na=False)])

    c1.metric("Arquivos", total)
    c2.metric("Processados", proc)
    c3.metric("Pendentes", pend)
    c4.metric("Eficiência", f"{(proc/total*100 if total > 0 else 0):.1f}%")

    if 'Data' in df.columns:
        df['Data_dt'] = pd.to_datetime(df['Data'], dayfirst=True, errors='coerce')
        df_dia = df.groupby(df['Data_dt'].dt.date)['Status'].value_counts().unstack().fillna(0)
        st.plotly_chart(px.line(df_dia, title="Volume Diário", markers=True), use_container_width=True)

# --- ABA: CONTROLE ---
elif menu == "Controle":
    st.header("Controle")
    
    # Colunas solicitadas atualizadas
    colunas_exibicao = [
        "Número do Processo", 
        "Nome do Documento", 
        "Tipo de Documento", 
        "Data", 
        "Data Ultimo Processamento", 
        "Status"
    ]
    colunas_presentes = [c for c in colunas_exibicao if c in df.columns]
    
    selecao = st.dataframe(
        df[colunas_presentes], 
        use_container_width=True, 
        on_select="rerun", 
        selection_mode="single-row", 
        hide_index=True
    )

    if len(selecao['selection']['rows']) > 0:
        idx = selecao['selection']['rows'][0]
        row = df.iloc[idx]
        
        st.divider()
        st.subheader(f"🔍 Análise: {row.get('Número do Processo')}")
        
        t1, t2 = st.tabs(["📄 Resultado da IA", "🚀 Ações"])
        
        with t1:
            st.write(row.get('Retorno', 'Sem dados.'))
                
        with t2:
            btn_col1, btn_col2 = st.columns(2)
            with btn_col1:
                if st.button("📝 Disparar Re-análise"):
                    with st.spinner("O Sentinela está re-analisando via OAuth2..."):
                        try:
                            model = genai.GenerativeModel(MODEL_NAME)
                            service_drive = build('drive', 'v3', credentials=creds)
                            file_id = row.get('ID do Arquivo')
                            
                            # Verificação de MimeType para suportar Google Docs (export)
                            meta = service_drive.files().get(fileId=file_id, fields='mimeType').execute()
                            mime = meta.get('mimeType')
                            
                            fh = io.BytesIO()
                            if "google-apps.document" in mime:
                                req = service_drive.files().export_media(fileId=file_id, mimeType='application/pdf')
                            else:
                                req = service_drive.files().get_media(fileId=file_id)
                            
                            downloader = MediaIoBaseDownload(fh, req)
                            done = False
                            while not done: _, done = downloader.next_chunk()
                            
                            # Lógica da Matriz (Usando to_string para evitar erro de tabulate)
                            df_matriz = obter_matriz_do_storage()
                            regras = df_matriz.to_string(index=False) if not df_matriz.empty else "Padrões gerais."
                            
                            prompt = f"Você é o Agente Sentinela. Analise conforme a MATRIZ: {regras}. Responda em JSON."
                            
                            response = model.generate_content([
                                prompt, 
                                {'mime_type': 'application/pdf', 'data': fh.getvalue()}
                            ])
                            
                            # Atualização na Planilha
                            cabecalho_planilha = ws.row_values(1)
                            if 'Retorno' in cabecalho_planilha:
                                ws.update_cell(idx + 2, cabecalho_planilha.index('Retorno') + 1, response.text)
                            
                            if 'Data Ultimo Processamento' in cabecalho_planilha:
                                agora = datetime.now(fuso_br).strftime("%d/%m/%Y %H:%M:%S")
                                ws.update_cell(idx + 2, cabecalho_planilha.index('Data Ultimo Processamento') + 1, agora)

                            st.success("Análise atualizada com sucesso!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro no processamento: {e}")

            with btn_col2:
                # Alterado para abrir a PASTA do processo via ID da Pasta
                id_pasta = row.get('ID da Pasta')
                if id_pasta:
                    st.link_button("📂 Abrir Pasta do Processo", f"https://drive.google.com/drive/folders/{id_pasta}")
                else:
                    st.warning("Coluna 'ID da Pasta' não encontrada ou vazia.")
