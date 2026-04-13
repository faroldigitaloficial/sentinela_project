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
st.set_page_config(page_title="Sentinela - v0.3", layout="wide", page_icon="🛡️")
st_autorefresh(interval=60 * 1000, key="datarefresh")

PLANILHA_ID = "1DYQ6Hsbp5xua9RFGmNGeKqITGZygvo6gIdtF4WkMG1Q"
BUCKET_NAME = "bucket-sentinela"
MATRIZ_FILE_NAME = "matriz_sentinela.csv"

# Definição de Escopos para autenticação de sistema
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/generative-language',
    'https://www.googleapis.com/auth/cloud-platform'
]

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
    # Obtém as credenciais padrão do ambiente (OAuth2)
    creds, _ = default(scopes=SCOPES)
    client_gs = gspread.authorize(creds)
    sh = client_gs.open_by_key(PLANILHA_ID)
    worksheet = sh.sheet1
    df = pd.DataFrame(worksheet.get_all_records())
    return df, worksheet, creds

# --- TELA DE LOGIN ANTIGA (CENTRALIZADA) ---
if 'logado' not in st.session_state:
    st.session_state.logado = False

if not st.session_state.logado:
    col_l1, col_l2, col_l3 = st.columns([1, 1, 1])
    with col_l2:
        st.write("#")
        st.write("#")
        st.title("🛡️ Sentinela")
        senha = st.text_input("Senha de Acesso", type="password")
        if st.button("Entrar"):
            if senha == "farol2026":
                st.session_state.logado = True
                st.rerun()
            else:
                st.error("Senha incorreta.")
    st.stop()

# --- CARREGAMENTO DE DADOS ---
try:
    df, ws, creds = carregar_dados_planilha()
    # Configura o Gemini usando as credenciais de sistema em vez de API_KEY
    genai.configure(credentials=creds)
except Exception as e:
    st.error(f"Erro de conexão: {e}")
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
    st.header("Dashboard de Performance")
    
    col1, col2, col3, col4 = st.columns(4)
    total = len(df)
    proc = len(df[df['Status'].astype(str).str.contains('2', na=False)])
    pend = len(df[df['Status'].astype(str).str.contains('1', na=False)])

    col1.metric("Arquivos no Fluxo", total)
    col2.metric("Processados ✅", proc)
    col3.metric("Aguardando ⏳", pend, delta=f"{pend} pendentes", delta_color="inverse")
    col4.metric("Eficiência", f"{(proc/total*100 if total > 0 else 0):.1f}%")

    st.divider()
    
    # Gráfico Evolutivo
    df['Data_dt'] = pd.to_datetime(df['Data'], dayfirst=True, errors='coerce')
    df_dia = df.groupby(df['Data_dt'].dt.date)['Status'].value_counts().unstack().fillna(0)
    st.plotly_chart(px.line(df_dia, title="Volume de Processamento por Dia", markers=True), use_container_width=True)

# --- ABA: CONTROLE ---
elif menu == "Controle":
    st.header("Controle de Processamento")
    
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
        st.subheader(f"🔍 Detalhes: {row.get('Número do Processo', 'N/A')}")
        
        tab1, tab2 = st.tabs(["📄 Resultado da IA", "🚀 Ações"])
        
        with tab1:
            st.write(row.get('Retorno', 'Sem dados de retorno.'))
            if 'Métricas de Execução' in row:
                st.caption(f"⚙️ {row['Métricas de Execução']}")
                
        with tab2:
            col_btn1, col_btn2 = st.columns(2)
            
            with col_btn1:
                if st.button("📝 Disparar Re-análise"):
                    with st.spinner("O Sentinela está re-analisando..."):
                        try:
                            # Chama o modelo configurado via credenciais de sistema
                            model = genai.GenerativeModel(model_name='models/gemini-3.1-flash-lite-preview')
                            service_drive = build('drive', 'v3', credentials=creds)
                            file_id = row.get('ID do Arquivo')
                            
                            # Download
                            meta = service_drive.files().get(fileId=file_id, fields='mimeType').execute()
                            mime_real = meta.get('mimeType')

                            if "google-apps.document" in mime_real:
                                req = service_drive.files().export_media(fileId=file_id, mimeType='application/pdf')
                                mime_ia = 'application/pdf'
                            else:
                                req = service_drive.files().get_media(fileId=file_id)
                                mime_ia = mime_real
                            
                            fh = io.BytesIO()
                            downloader = MediaIoBaseDownload(fh, req)
                            done = False
                            while not done: _, done = downloader.next_chunk()
                            
                            # IA
                            df_matriz = obter_matriz_do_storage()
                            regras = df_matriz.to_string(index=False) if not df_matriz.empty else "Analise conforme padrões gerais."
                            
                            prompt = f"Você é o Agente Sentinela. Analise conforme a MATRIZ: {regras}. Responda em JSON."
                            
                            response = model.generate_content(
                                [prompt, {"mime_type": "application/pdf" if "document" in mime_real else mime_ia, "data": fh.getvalue()}], 
                                generation_config={"response_mime_type": "application/json"}
                            )
                            
                            # Atualização na Planilha
                            cabecalho = ws.row_values(1)
                            col_ret = cabecalho.index('Retorno') + 1
                            ws.update_cell(idx + 2, col_ret, response.text)
                            
                            if 'Data Ultimo Processamento' in cabecalho:
                                col_data_proc = cabecalho.index('Data Ultimo Processamento') + 1
                                agora = datetime.now(fuso_br).strftime("%d/%m/%Y %H:%M:%S")
                                ws.update_cell(idx + 2, col_data_proc, agora)

                            st.success("Análise atualizada!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro no processamento: {e}")

            with col_btn2:
                id_pasta = row.get('ID da Pasta')
                if id_pasta:
                    st.link_button("📂 Abrir Pasta do Processo", f"https://drive.google.com/drive/folders/{id_pasta}")
                else:
                    st.warning("ID da Pasta não localizado.")

# Rodapé simples
st.sidebar.caption(f"Sentinela Web v0.3 | {datetime.now().year}")
