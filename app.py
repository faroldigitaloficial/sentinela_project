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

# Configuração do Gemini (Fixando o modelo que você definiu)
genai.configure(api_key=API_KEY)
MODEL_NAME = 'models/gemini-3.1-flash-lite-preview'

def carregar_contexto_google():
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    creds, _ = default(scopes=SCOPES)
    client_gs = gspread.authorize(creds)
    sh = client_gs.open_by_key(PLANILHA_ID)
    return sh.sheet1, creds

st.title("🛡️ Debug Sentinela - Teste de IA")

if st.button("🚀 TESTAR CHAMADA GEMINI 3.1"):
    try:
        ws, creds = carregar_contexto_google()
        df = pd.DataFrame(ws.get_all_records())
        
        if df.empty:
            st.error("Planilha vazia!")
            st.stop()

        # Pega o primeiro arquivo para teste
        row = df.iloc[0]
        file_id = row.get('ID do Arquivo')
        
        st.info(f"Testando com Arquivo ID: {file_id}")

        # 1. Download do Drive (Usa credenciais OAuth2)
        service_drive = build('drive', 'v3', credentials=creds)
        req = service_drive.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, req)
        done = False
        while not done: _, done = downloader.next_chunk()
        
        # 2. Chamada Gemini (Usa API_KEY)
        # O segredo aqui é não passar as credenciais do Cloud para o modelo
        model = genai.GenerativeModel(model_name=MODEL_NAME)
        
        prompt = "Você é o Agente Sentinela. Analise este documento e retorne um resumo simples em JSON."
        
        # Enviando como bytes (data)
        documento = {
            "mime_type": "application/pdf",
            "data": fh.getvalue()
        }

        st.warning("Chamando Gemini 3.1 Flash Lite...")
        response = model.generate_content([prompt, documento])
        
        st.success("✅ SUCESSO! A IA respondeu:")
        st.json(response.text)

    except Exception as e:
        st.error(f"❌ ERRO IDENTIFICADO: {str(e)}")
        st.code(e)

st.divider()
st.write("Se este teste funcionar sem o erro 401, o problema era o conflito de transporte entre a API Key e o OAuth2.")
