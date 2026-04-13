import streamlit as st
import pandas as pd
import plotly.express as px
from streamlit_autorefresh import st_autorefresh
import gspread
import io
import pytz
from datetime import datetime
import google.generativeai as genai
from google.auth import default
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.cloud import storage

# --- CONFIGURAÇÕES DO SENTINELA ---
st.set_page_config(page_title="Sentinela 0.4", layout="wide", page_icon="🛡️")
st_autorefresh(interval=60 * 1000, key="datarefresh")

API_KEY = "AQ.Ab8RN6JE7BnDyhh_t8iY8lHnJ8Ul4Ea0_DARUh8I2ifcHAqb6w"
PLANILHA_ID = "1DYQ6Hsbp5xua9RFGmNGeKqITGZygvo6gIdtF4WkMG1Q"
BUCKET_NAME = "bucket-sentinela"
MATRIZ_FILE_NAME = "matriz_sentinela.csv"

genai.configure(api_key=API_KEY, transport='rest')
fuso_br = pytz.timezone('America/Sao_Paulo')

# --- FUNÇÕES DE DADOS ---
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

# --- SISTEMA DE LOGIN ---
if 'logado' not in st.session_state:
    st.session_state.logado = False

if not st.session_state.logado:
    col_l1, col_l2, col_l3 = st.columns([1, 1, 1])
    with col_l2:
        st.write("#")
        st.write("#")
        st.title("🛡️ Sentinela")
        senha_input = st.text_input("Senha de Acesso", type="password")
        if st.button("Entrar"):
            if senha_input == "farol2026":
                st.session_state.logado = True
                st.rerun()  # Força a atualização para entrar no sistema
            else:
                st.error("Senha incorreta.")
    st.stop()

# --- CARREGAMENTO DE DADOS (PÓS-LOGIN) ---
try:
    df, ws, creds = carregar_dados_planilha()
except Exception as e:
    st.error(f"Erro de conexão com Google: {e}")
    st.stop()

# --- MENU LATERAL ---
st.sidebar.title("🛡️ Sentinela 0.4")
menu = st.sidebar.radio("Navegação", ["Dashboard", "Controle"])
st.sidebar.divider()
if st.sidebar.button("Sair"):
    st.session_state.logado = False
    st.rerun()

# --- ABA: DASHBOARD ---
if menu == "Dashboard":
    st.header("Dashboard")
    
    col1, col2, col3, col4 = st.columns(4)
    total = len(df)
    proc = len(df[df['Status'].astype(str).str.contains('2', na=False)])
    pend = len(df[df['Status'].astype(str).str.contains('1', na=False)])

    col1.metric("Arquivos", total)
    col2.metric("Processados", proc)
    col3.metric("Pendentes", pend)
    col4.metric("Eficiência", f"{(proc/total*100 if total > 0 else 0):.1f}%")

    st.divider()
    
    # Gráfico
    if 'Data' in df.columns:
        df['Data_dt'] = pd.to_datetime(df['Data'], dayfirst=True, errors='coerce')
        df_dia = df.groupby(df['Data_dt'].dt.date)['Status'].value_counts().unstack().fillna(0)
        st.plotly_chart(px.line(df_dia, title="Volume Diário", markers=True), use_container_width=True)

# --- ABA: CONTROLE ---
elif menu == "Controle":
    st.header("Controle")
    
    # Colunas solicitadas (incluindo as novas: Nome do Documento, Tipo e Data Ultimo Proc.)
    colunas_exibicao = [
        "Número do Processo", 
        "Nome do Documento", 
        "Tipo de Documento", 
        "Data", 
        "Data Ultimo Processamento", 
        "Status"
    ]
    
    # Filtra apenas o que existe na planilha para evitar erro
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
        
        t1, t2 = st.tabs(["📄 Resultado", "🚀 Ações"])
        
        with t1:
            st.write(row.get('Retorno', 'Sem dados.'))
                
        with t2:
            c1, c2 = st.columns(2)
            with c1:
                if st.button("📝 Re-analisar"):
                    with st.spinner("Processando..."):
                        try:
                            model = genai.GenerativeModel(model_name='models/gemini-3.1-flash-lite-preview')
                            service_drive = build('drive', 'v3', credentials=creds)
                            
                            # Download
                            req = service_drive.files().get_media(fileId=row.get('ID do Arquivo'))
                            fh = io.BytesIO()
                            downloader = MediaIoBaseDownload(fh, req)
                            done = False
                            while not done: _, done = downloader.next_chunk()
                            
                            # IA - Usando to_string para evitar dependência de tabulate
                            df_matriz = obter_matriz_do_storage()
                            regras = df_matriz.to_string(index=False) if not df_matriz.empty else "Padrões gerais."
                            
                            prompt = f"Agente Sentinela. Analise conforme: {regras}. Responda em JSON."
                            
                            response = model.generate_content(
                                [prompt, {"mime_type": "application/pdf", "data": fh.getvalue()}], 
                                generation_config={"response_mime_type": "application/json"}
                            )
                            
                            # Updates
                            cabecalho = ws.row_values(1)
                            if 'Retorno' in cabecalho:
                                ws.update_cell(idx + 2, cabecalho.index('Retorno') + 1, response.text)
                            
                            if 'Data Ultimo Processamento' in cabecalho:
                                agora = datetime.now(fuso_br).strftime("%d/%m/%Y %H:%M:%S")
                                ws.update_cell(idx + 2, cabecalho.index('Data Ultimo Processamento') + 1, agora)

                            st.success("Concluído!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro: {e}")

            with c2:
                id_pasta = row.get('ID da Pasta')
                if id_pasta:
                    st.link_button("📂 Abrir Pasta do Processo", f"https://drive.google.com/drive/folders/{id_pasta}")
