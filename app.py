import streamlit as st
import pandas as pd
import gspread
import io
import google.generativeai as genai
from google.auth import default
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# --- CONFIGURAÇÕES DO TESTE ---
PLANILHA_ID = "1DYQ6Hsbp5xua9RFGmNGeKqITGZygvo6gIdtF4WkMG1Q"
MODEL_NAME = 'models/gemini-3.1-flash-lite-preview'

st.title("🛡️ Sentinela - Debug OAuth2")

if st.button("🚀 Iniciar Teste de Conexão"):
    try:
        # 1. OBTER CREDENCIAIS DO AMBIENTE (OAuth2)
        # O segredo é incluir o escopo 'generative-language'
        SCOPES = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive',
            'https://www.googleapis.com/auth/generative-language'
        ]
        
        st.info("Obtendo credenciais do sistema...")
        creds, _ = default(scopes=SCOPES)
        
        # 2. CONFIGURAR GEMINI COM OAUTH2
        # Note que não passamos api_key aqui, apenas as credentials
        genai.configure(credentials=creds)
        model = genai.GenerativeModel(MODEL_NAME)
        
        # 3. TESTAR ACESSO AO DRIVE
        st.info("Acessando Planilha e Drive...")
        client_gs = gspread.authorize(creds)
        sh = client_gs.open_by_key(PLANILHA_ID)
        ws = sh.sheet1
        df = pd.DataFrame(ws.get_all_records())
        
        if df.empty:
            st.error("Planilha vazia!")
            st.stop()
            
        row = df.iloc[0]
        file_id = row.get('ID do Arquivo')
        
        # 4. DOWNLOAD DE TESTE
        service_drive = build('drive', 'v3', credentials=creds)
        req = service_drive.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, req)
        done = False
        while not done: _, done = downloader.next_chunk()
        
        # 5. TESTAR CHAMADA DA IA
        st.warning(f"Chamando {MODEL_NAME} via OAuth2...")
        prompt = "Resuma este documento em uma frase."
        doc = {'mime_type': 'application/pdf', 'data': fh.getvalue()}
        
        response = model.generate_content([prompt, doc])
        
        st.success("✅ SUCESSO ABSOLUTO!")
        st.write("**Resposta da IA:**")
        st.write(response.text)
        
    except Exception as e:
        st.error("❌ O teste falhou!")
        st.exception(e)
