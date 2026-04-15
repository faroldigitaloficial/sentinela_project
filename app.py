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
    # Função auxiliar para o farol de risco
    if valor == "Alto": return "🔴"
    if valor == "Médio": return "🟡"
    return "🟢"

# --- LOGIN ---
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
    df_raw = pd.DataFrame(ws.get_all_records())
    
    # Criando dados fakes de Processos (Pai) enquanto não existe a aba na planilha
    if not df_raw.empty:
        # Extrai processos únicos
        df_processos = df_raw[['Número do Processo', 'ID da Pasta']].drop_duplicates().reset_index(drop=True)
        # Adiciona colunas fakes solicitadas
        df_processos['Fase'] = "Instrução"
        df_processos['Risco'] = df_processos.index.map(lambda x: "Médio" if x % 2 == 0 else "Baixo")
        df_processos['Farol'] = df_processos['Risco'].apply(mapear_cor_risco)
        
        # Adiciona risco fake nos documentos (Filho)
        df_raw['Risco'] = "Baixo"
        df_raw['Farol'] = "🟢"
except Exception as e:
    st.error(f"Erro de conexão: {e}")
    st.stop()

# --- MENU LATERAL ---
st.sidebar.title("🛡️ Sentinela")
menu = st.sidebar.radio("Navegação", ["Dashboard", "Controle"])
if st.sidebar.button("Sair"):
    st.session_state.logado = False
    st.rerun()

# --- ABA: DASHBOARD ---
if menu == "Dashboard":
    st.header("Dashboard")
    c1, c2, c3 = st.columns(3)
    c1.metric("Total de Processos", len(df_processos))
    c2.metric("Documentos Analisados", len(df_raw[df_raw['Status'].astype(str).str.contains('2')]))
    c3.metric("Alertas de Risco", len(df_processos[df_processos['Risco'] == "Alto"]))

# --- ABA: CONTROLE (PAI e FILHO) ---
elif menu == "Controle":
    st.subheader("📁 Processos")
    
    # Tabela de Processos (PAI)
    # Incluindo a coluna de Abrir Pasta aqui como solicitado
    cols_p = ["Farol", "Número do Processo", "Fase", "Risco"]
    
    sel_processo = st.dataframe(
        df_processos[cols_p],
        use_container_width=True,
        on_select="rerun",
        selection_mode="single-row",
        hide_index=True
    )

    if len(sel_processo['selection']['rows']) > 0:
        p_idx = sel_processo['selection']['rows'][0]
        proc_selecionado = df_processos.iloc[p_idx]
        num_proc = proc_selecionado['Número do Processo']
        id_pasta = proc_selecionado['ID da Pasta']

        st.divider()
        col_header_1, col_header_2 = st.columns([0.8, 0.2])
        with col_header_1:
            st.subheader(f"📄 Documentos do Processo: {num_proc}")
        with col_header_2:
            if id_pasta:
                st.link_button("📂 Abrir Pasta no Drive", f"https://drive.google.com/drive/folders/{id_pasta}")

        # Filtrar documentos (FILHO)
        df_docs = df_raw[df_raw['Número do Processo'] == num_proc].reset_index()
        cols_d = ["Farol", "Nome do Documento", "Tipo de Documento", "Status", "Data Ultimo Processamento"]
        
        sel_doc = st.dataframe(
            df_docs[cols_d],
            use_container_width=True,
            on_select="rerun",
            selection_mode="single-row",
            hide_index=True
        )

        if len(sel_doc['selection']['rows']) > 0:
            d_idx = sel_doc['selection']['rows'][0]
            doc_row = df_docs.iloc[d_idx]
            original_idx = doc_row['index'] # Index real na planilha para o update_cell
            
            st.info(f"🔍 **Documento:** {doc_row['Nome do Documento']}")
            
            t_resumo, t_analise, t_acoes = st.tabs(["📝 Resumo", "📊 Análise", "🚀 Ações"])
            
            with t_resumo:
                st.markdown(doc_row.get('Resumo', '*Nenhum resumo gerado.*'))
            
            with t_analise:
                st.markdown(doc_row.get('Retorno', '*Nenhuma análise disponível.*'))
            
            with t_acoes:
                c_btn1, c_btn2 = st.columns(2)
                
                with c_btn1:
                    if st.button("🔄 Disparar Re-análise"):
                        with st.spinner("IA processando documento..."):
                            try:
                                # Lógica de Re-análise mantida
                                model = genai.GenerativeModel(MODEL_NAME)
                                service_drive = build('drive', 'v3', credentials=creds)
                                file_id = doc_row.get('ID do Arquivo')
                                
                                meta = service_drive.files().get(fileId=file_id, fields='mimeType').execute()
                                fh = io.BytesIO()
                                if "google-apps.document" in meta.get('mimeType'):
                                    req = service_drive.files().export_media(fileId=file_id, mimeType='application/pdf')
                                else:
                                    req = service_drive.files().get_media(fileId=file_id)
                                
                                downloader = MediaIoBaseDownload(fh, req)
                                done = False
                                while not done: _, done = downloader.next_chunk()
                                
                                df_matriz = obter_matriz_do_storage()
                                regras = df_matriz.to_string(index=False) if not df_matriz.empty else "Análise geral."
                                
                                prompt = f"Analise conforme a MATRIZ: {regras}. Responda em texto estruturado."
                                response = model.generate_content([prompt, {'mime_type': 'application/pdf', 'data': fh.getvalue()}])
                                
                                # Atualiza na Planilha (usando o índice original)
                                cabecalho = ws.row_values(1)
                                if 'Retorno' in cabecalho:
                                    ws.update_cell(original_idx + 2, cabecalho.index('Retorno') + 1, response.text)
                                
                                st.success("Documento re-analisado!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro: {e}")

                with c_btn2:
                    # NOVA LÓGICA: Em vez de criar arquivo, mostra o texto para cópia
                    if st.button("📄 Gerar Relatório para Cópia"):
                        st.session_state.show_copy_area = True

                if st.session_state.get('show_copy_area'):
                    st.divider()
                    st.subheader("📋 Relatório da Análise")
                    st.caption("Copie o texto abaixo para seu documento oficial:")
                    relatorio_full = f"ANÁLISE SENTINELA\nDocumento: {doc_row['Nome do Documento']}\nData: {doc_row['Data Ultimo Processamento']}\n\n{doc_row['Retorno']}"
                    st.text_area("Conteúdo", value=relatorio_full, height=300)
                    if st.button("Fechar Relatório"):
                        st.session_state.show_copy_area = False
                        st.rerun()
