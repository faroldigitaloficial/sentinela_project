import streamlit as st
import pandas as pd
import plotly.express as px
from streamlit_autorefresh import st_autorefresh
import gspread
import io
import pytz
import os
import re 
from datetime import datetime
import google.generativeai as genai
from google.auth import default
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.cloud import storage

# --- CONFIGURAÇÕES DO SENTINELA ---
st.set_page_config(page_title="Sentinela 0.5", layout="wide", page_icon="🛡️")
st_autorefresh(interval=60 * 1000, key="datarefresh")

PLANILHA_ID = "1DYQ6Hsbp5xua9RFGmNGeKqITGZygvo6gIdtF4WkMG1Q"
BUCKET_NAME = "bucket-sentinela"
MATRIZ_FILE_NAME = "matriz_sentinela.csv"
MODEL_NAME = 'models/gemini-3.1-flash-lite-preview'

fuso_br = pytz.timezone('America/Sao_Paulo')

# --- FUNÇÕES DE APOIO ---
def carregar_contexto_google():
    SCOPES = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive',
        'https://www.googleapis.com/auth/generative-language'
    ]
    creds, _ = default(scopes=SCOPES)
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

def mapear_cor_risco(valor):
    if valor == "Alto": return "🔴"
    if valor == "Médio": return "🟡"
    return "🟢"

# --- LOGIN ---
if 'logado' not in st.session_state:
    st.session_state.logado = False

if not st.session_state.logado:
    col_l2 = st.columns([1, 1, 1])[1]
    with col_l2:
        st.write("#")
        st.title("🛡️ Sentinela 0.5")
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
    df_raw = pd.DataFrame(ws.get_all_records())
    
    if not df_raw.empty:
        # Preparação de Processos (Distinct)
        df_processos = df_raw[['Número do Processo', 'ID da Pasta']].drop_duplicates().sort_values('Número do Processo').reset_index(drop=True)
        df_processos['Fase'] = "Instrução"
        df_processos['Risco'] = "Baixo" # Default
        df_processos['Farol'] = df_processos['Risco'].apply(mapear_cor_risco)
        
        # Lógica de Farol por Score para os documentos
        df_raw['Farol'] = df_raw['Score'].apply(lambda x: "🔴" if str(x).replace('%','') != '' and int(str(x).replace('%','')) < 50 else "🟢")
except Exception as e:
    st.error(f"Erro de conexão: {e}")
    st.stop()

# --- MENU LATERAL ---
st.sidebar.title("🛡️ Sentinela 0.5")
menu = st.sidebar.radio("Navegação", ["Dashboard", "Controle"])
if st.sidebar.button("Sair"):
    st.session_state.logado = False
    st.rerun()

# --- ABA: DASHBOARD ---
if menu == "Dashboard":
    st.header("Dashboard Sentinela 0.5")
    
    # Cálculos dos Cards
    total_processos = df_raw['Número do Processo'].nunique()
    total_docs = len(df_raw)
    docs_processados = len(df_raw[df_raw['Status'].astype(str).str.contains('2')])
    docs_pendentes = len(df_raw[df_raw['Status'].astype(str).str.contains('1')])
    percentual_concluido = (docs_processados / total_docs * 100) if total_docs > 0 else 0

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Qte Processos", total_processos)
    c2.metric("Qte Documentos", total_docs)
    c3.metric("Processados", docs_processados)
    c4.metric("Pendentes", docs_pendentes)
    c5.metric("% Concluído", f"{percentual_concluido:.1f}%")

    # Gráfico Temporal
    st.subheader("Produtividade: Documentos Processados por Dia")
    if 'Data Ultimo Processamento' in df_raw.columns:
        df_vix = df_raw[df_raw['Status'].astype(str).str.contains('2')].copy()
        # Converte para data simples (YYYY-MM-DD)
        df_vix['Data'] = pd.to_datetime(df_vix['Data Ultimo Processamento'], dayfirst=True, errors='coerce').dt.date
        df_timeline = df_vix.groupby('Data').size().reset_index(name='Quantidade')
        
        if not df_timeline.empty:
            fig = px.line(df_timeline, x='Data', y='Quantidade', markers=True, template="plotly_white", color_discrete_sequence=['#00CC96'])
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Aguardando processamento de documentos para gerar gráfico.")

# --- ABA: CONTROLE ---
elif menu == "Controle":
    st.subheader("📁 Processos (Sentinela 0.5)")
    cols_p = ["Farol", "Número do Processo", "Fase", "Risco"]
    sel_processo = st.dataframe(df_processos[cols_p], use_container_width=True, on_select="rerun", selection_mode="single-row", hide_index=True)

    if len(sel_processo['selection']['rows']) > 0:
        proc_selecionado = df_processos.iloc[sel_processo['selection']['rows'][0]]
        num_proc = proc_selecionado['Número do Processo']
        id_pasta = proc_selecionado['ID da Pasta']

        st.divider()
        c_h1, c_h2 = st.columns([0.8, 0.2])
        c_h1.subheader(f"📄 Documentos do Processo: {num_proc}")
        if id_pasta: c_h2.link_button("📂 Abrir Pasta", f"https://drive.google.com/drive/folders/{id_pasta}")

        # Ordenar documentos por nome e filtrar pelo processo
        df_docs = df_raw[df_raw['Número do Processo'] == num_proc].sort_values('Nome do Documento').reset_index()
        
        # Nova Ordem de Colunas Solicitada
        cols_d = ["Farol", "Score", "Tipo de Documento", "Nome do Documento", "Status"]
        sel_doc = st.dataframe(df_docs[cols_d], use_container_width=True, on_select="rerun", selection_mode="single-row", hide_index=True)

        if len(sel_doc['selection']['rows']) > 0:
            doc_row = df_docs.iloc[sel_doc['selection']['rows'][0]]
            original_idx = doc_row['index']
            st.info(f"🔍 **Análise:** {doc_row['Nome do Documento']}")
            
            t_resumo, t_analise, t_acoes = st.tabs(["📝 Resumo", "📊 Análise de Auditoria", "🚀 Ações"])
            with t_resumo: st.markdown(doc_row.get('Resumo', '*Nenhum resumo.*'))
            with t_analise: st.markdown(doc_row.get('Retorno', '*Nenhuma análise.*'))
            
            with t_acoes:
                if st.button("🔄 Disparar Re-análise (Gemini 3.1)"):
                    with st.spinner("Analisando integridade do documento..."):
                        try:
                            model = genai.GenerativeModel(MODEL_NAME)
                            service_drive = build('drive', 'v3', credentials=creds)
                            file_id = doc_row.get('ID do Arquivo')
                            
                            meta = service_drive.files().get(fileId=file_id, fields='mimeType').execute()
                            mime_type = meta.get('mimeType')
                            fh = io.BytesIO()
                            
                            # Download e Preparação de Conteúdo (Suporte HTML e PDF)
                            if "google-apps.document" in mime_type:
                                req = service_drive.files().export_media(fileId=file_id, mimeType='application/pdf')
                            else:
                                req = service_drive.files().get_media(fileId=file_id)
                            
                            downloader = MediaIoBaseDownload(fh, req)
                            done = False
                            while not done: _, done = downloader.next_chunk()
                            
                            if "text/html" in mime_type or "html" in doc_row['Nome do Documento'].lower():
                                input_data = [f"CONTEÚDO HTML:\n{fh.getvalue().decode('iso-8859-1', errors='ignore')}"]
                            else:
                                input_data = [{'mime_type': 'application/pdf' if "google-apps.document" in mime_type else mime_type, 'data': fh.getvalue()}]
                            
                            df_matriz = obter_matriz_do_storage()
                            matriz_texto = df_matriz.to_string(index=False) if not df_matriz.empty else "Matriz Padrão Lei 14.133."

                            prompt_final = f"Analise este documento baseado na Matriz: {matriz_texto}\nAo final escreva SCORE_FINAL: X%"
                            response = model.generate_content([prompt_final] + input_data)
                            texto_retorno = response.text
                            
                            score_match = re.search(r"SCORE_FINAL:\s*(\d+%)", texto_retorno)
                            score_valor = score_match.group(1) if score_match else "0%"

                            cabecalho = ws.row_values(1)
                            agora = datetime.now(fuso_br).strftime("%d/%m/%Y %H:%M:%S")
                            if 'Retorno' in cabecalho: ws.update_cell(original_idx + 2, cabecalho.index('Retorno') + 1, texto_retorno)
                            if 'Score' in cabecalho: ws.update_cell(original_idx + 2, cabecalho.index('Score') + 1, score_valor)
                            if 'Status' in cabecalho: ws.update_cell(original_idx + 2, cabecalho.index('Status') + 1, "2 - Processado")
                            if 'Data Ultimo Processamento' in cabecalho: ws.update_cell(original_idx + 2, cabecalho.index('Data Ultimo Processamento') + 1, agora)
                            
                            st.success(f"Sucesso! Score: {score_valor}")
                            st.rerun()
                        except Exception as e: st.error(f"Erro: {e}")
