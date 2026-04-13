import streamlit as st
import time
import pandas as pd
from datetime import datetime

# Configuração Visual
st.set_page_config(page_title="Sentinela Web", page_icon="🛡️", layout="wide")

# --- SIMULAÇÃO DE LOGIN ---
if 'logado' not in st.session_state:
    st.session_state.logado = False

if not st.session_state.logado:
    st.title("🛡️ Sentinela - Farol Digital")
    st.subheader("Login do Auditor")
    user = st.text_input("Usuário")
    pw = st.text_input("Senha", type="password")
    if st.button("Entrar"):
        st.session_state.logado = True
        st.rerun()
    st.stop()

# --- DASHBOARD PRINCIPAL ---
st.sidebar.title("Família Sentinela")
aba = st.sidebar.radio("Navegação", ["Dashboard", "Painel de Auditoria", "Configurações"])

if aba == "Dashboard":
    st.title("📊 Indicadores Gerenciais")
    c1, c2, c3 = st.columns(3)
    c1.metric("Processos em Análise", "14", "+2 hoje")
    c2.metric("Conformidade Média", "88%", "Estável")
    c3.metric("Tempo Economizado", "42h", "Este mês")

elif aba == "Painel de Auditoria":
    st.title("🛡️ Painel do Auditor")
    st.write("Selecione os documentos para gerar a manifestação técnica:")

    # Simulando dados da nossa planilha
    dados = [
        {"Selecionar": False, "Arquivo": "ETP_Digitalizacao_01.pdf", "Tipo": "ETP", "Status": "Analisado"},
        {"Selecionar": False, "Arquivo": "TR_Servicos_Nuvem.docx", "Tipo": "TR", "Status": "Analisado"},
        {"Selecionar": False, "Arquivo": "Parecer_Juridico_Ref.html", "Tipo": "Parecer", "Status": "Pendente"},
    ]
    df = pd.DataFrame(dados)
    
    # Criando a tabela com seleção
    edited_df = st.data_editor(df, hide_index=True, use_container_width=True)

    st.divider()

    # --- O MOMENTO UAU: GERAÇÃO COM GHOST WRITING ---
    if st.button("⚡ Gerar Manifestação Técnica"):
        selecionados = edited_df[edited_df['Selecionar'] == True]['Arquivo'].tolist()
        
        if len(selecionados) < 2:
            st.warning("Selecione pelo menos 2 documentos (ex: ETP e TR) para cruzar os dados.")
        else:
            st.write("### 🧠 Inteligência Sentinela em Ação")
            
            with st.status("Processando documentos...", expanded=True) as status:
                st.write("🔍 Acessando cofre de templates no Farol Storage...")
                time.sleep(1.5)
                st.write(f"📄 Cruzando informações de: {', '.join(selecionados)}...")
                time.sleep(2)
                st.write("✍️ Redigindo parecer técnico moderno...")
                status.update(label="Manifestação Concluída!", state="complete", expanded=False)

            # EFEITO GHOST WRITING
            st.subheader("📝 Prévia da Manifestação")
            placeholder = st.empty()
            texto_final = f"""
            **ANÁLISE TÉCNICA SENTINELA nº {datetime.now().year}/001**
            
            Direto ao ponto: a análise cruzada entre o {selecionados[0]} e o {selecionados[1]} 
            revela total convergência técnica. Os requisitos de sustentabilidade e os 
            critérios de aceitabilidade estão alinhados com a legislação vigente.
            
            **Conclusão:** O processo está apto para prosseguimento, sem óbices identificados.
            
            ---
            *Documento pronto para assinatura digital.*
            """
            
            frase_atual = ""
            for char in texto_final:
                frase_atual += char
                placeholder.markdown(frase_atual + " ▌")
                time.sleep(0.01) # Velocidade da digitação
            
            placeholder.markdown(texto_final)
            
            st.success("✅ Documento salvo com sucesso no Drive do Processo!")
            st.button("📄 Abrir no Google Docs")