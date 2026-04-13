import streamlit as st
import pandas as pd
import gspread
import io
import google.generativeai as genai
from google.auth import default
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# --- CONFIGURAÇÕES ---
API_KEY = "AQ.Ab8RN6JE7BnDyhh_t8iY8lHnJ8Ul4Ea0_DARUh8I2ifcHAqb6w"
PLANILHA_ID = "1DYQ6Hsbp5xua9RFGmNGeKqITGZygvo6gIdtF4WkMG1Q"
MODEL_NAME = 'models/gemini-3.1-flash-lite-preview'

def carregar_contexto_google():
    # Escopos apenas para Planilha e Drive
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    creds, _ = default(scopes=SCOPES)
    client_gs = gspread.authorize(creds)
    sh = client_gs.open_by_key(PLANILHA_ID)
    return sh.sheet1, creds

st.title("🛡️ Debug Sentinela - Fix Auth 401")

if st.button("🚀 EXECUTAR TESTE DE IA"):
    try:
        # 1. Carregar dados da Planilha e Drive
        ws, creds = carregar_contexto_google()
        df = pd.DataFrame(ws.get_all_records())
        
        if df.empty:
            st.error("Planilha sem dados!")
            st.stop()

        row = df.iloc[0]
        file_id = row.get('ID do Arquivo')
        st.info(f"Baixando arquivo: {file_id}")

        # 2. Download do binário (Drive)
        service_drive = build('drive', 'v3', credentials=creds)
        req = service_drive.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, req)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        
        pdf_bytes = fh.getvalue()
        st.success("✅ Download concluído!")

        # 3. CHAMADA GEMINI (ISOLADA)
        # Forçamos a configuração da API_KEY novamente antes da chamada
        genai.configure(api_key=API_KEY)
        
        # Criamos o modelo
        model = genai.GenerativeModel(model_name=MODEL_NAME)
        
        prompt = "Você é o Agente Sentinela. Analise este documento e retorne um JSON."
        
        # Preparação do conteúdo
        content = [
            prompt,
            {"mime_type": "application/pdf", "data": pdf_bytes}
        ]

        st.warning(f"Solicitando análise ao {MODEL_NAME}...")
        
        # AQUI É ONDE O ERRO OCORRIA: 
        # Adicionamos uma tentativa de limpar qualquer transporte residual
        response = model.generate_content(content)
        
        st.success("✅ IA RESPONDEU COM SUCESSO:")
        st.write(response.text)

    except Exception as e:
        st.error("❌ ERRO DETECTADO")
        # Mostra o erro detalhado para diagnóstico
        st.exception(e)

st.divider()
st.caption("Nota: Se o erro 401 persistir, pode haver uma variável de ambiente 'GOOGLE_APPLICATION_CREDENTIALS' conflitando com a API Key.")
