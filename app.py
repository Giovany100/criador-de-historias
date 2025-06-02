import streamlit as st
import os
from pyngrok import ngrok

# Importar a função refatorada do main.py
# Certifique-se de que main.py esteja na mesma pasta ou no PYTHONPATH
try:
    from main import iniciar_processamento_em_lote
    # Tentar importar a constante PASTA_SAIDA_PRINCIPAL aqui também, se existir globalmente em main
    # Se não, usaremos um valor padrão definido abaixo.
    from main import PASTA_SAIDA_PRINCIPAL as MAIN_PASTA_SAIDA_PRINCIPAL 
except ImportError:
    # Se a importação de iniciar_processamento_em_lote falhar, o app para.
    # Se apenas PASTA_SAIDA_PRINCIPAL falhar, usamos o default.
    MAIN_PASTA_SAIDA_PRINCIPAL = "resultados_processamento"
    # Se iniciar_processamento_em_lote não puder ser importado, o app deve parar.
    # Isso será tratado no primeiro bloco try-except.
    if 'iniciar_processamento_em_lote' not in globals():
        st.error("Erro crítico ao importar 'iniciar_processamento_em_lote' de main.py. O app não pode continuar.")
        st.stop()

# Definir a constante localmente em app.py para garantir disponibilidade
# Usar o valor importado se bem-sucedido, senão o default.
APP_PASTA_SAIDA_PRINCIPAL = MAIN_PASTA_SAIDA_PRINCIPAL if 'MAIN_PASTA_SAIDA_PRINCIPAL' in locals() else "resultados_processamento"

st.set_page_config(
    page_title="Criador de Histórias IA", 
    page_icon="🤖", 
    layout="wide", # Usar layout wide para mais espaço
    initial_sidebar_state="expanded" # Manter sidebar aberta por padrão
)

# --- Barra Lateral (Sidebar) para Entradas ---
st.sidebar.header("⚙️ Configurações de Entrada")
pasta_resumos = st.sidebar.text_input(
    "Pasta com os arquivos de resumo (.txt):", 
    key="pasta_resumos_input",
    help="Forneça o caminho completo para a pasta. Ex: C:/Users/SeuUsuario/Resumos"
)

st.sidebar.subheader("🗣️ Idiomas para Tradução")
# Mapeamento de códigos de idioma para nomes amigáveis
mapa_nomes_idiomas_interface = {
    "italiano": "Italiano", "ingles": "Inglês", "espanhol": "Espanhol",
    "polones": "Polonês", "romeno": "Romeno", "alemao": "Alemão",
    "frances": "Francês", "hungaro": "Húngaro", "grego": "Grego",
    "croata": "Croata", "espanhol_mx": "Espanhol (México)", "suica": "Suíço (Alemão)",
}

idiomas_disponiveis = list(mapa_nomes_idiomas_interface.keys())
idiomas_selecionados_map = {}

# Criar colunas para os checkboxes para melhor organização se houver muitos idiomas
num_colunas = 2 # Ajuste conforme necessário
colunas_idiomas = st.sidebar.columns(num_colunas)

for i, cod_idioma in enumerate(idiomas_disponiveis):
    col = colunas_idiomas[i % num_colunas]
    idiomas_selecionados_map[cod_idioma] = col.checkbox(mapa_nomes_idiomas_interface[cod_idioma], key=f"chk_{cod_idioma}")

# Coletar os idiomas selecionados para passar para a função de processamento
idiomas_para_processar_lista = [cod for cod, selecionado in idiomas_selecionados_map.items() if selecionado]
idiomas_str_para_funcao = ",".join(idiomas_para_processar_lista)

btn_iniciar_processamento = st.sidebar.button(
    "🚀 Iniciar Processamento", 
    type="primary", 
    use_container_width=True, 
    key="btn_iniciar"
)
st.sidebar.markdown("---_---")
st.sidebar.caption(f"Version 1.2 | Pasta de Saída: {APP_PASTA_SAIDA_PRINCIPAL}")

# --- Página Principal ---
st.title("🌟 Criador de Histórias e Imagens com IA 🎬")
st.markdown("Bem-vindo ao seu assistente para transformar resumos em roteiros completos, traduzidos e com sugestões de imagens!")
st.markdown("Configure as entradas na barra lateral à esquerda e clique em **Iniciar Processamento**.")

st.info("ℹ️ **Nota:** Os logs detalhados do processo aparecerão no console (terminal) onde o Streamlit foi iniciado.", icon="📢")
st.divider()

# Lógica de processamento (quando o botão é clicado)
if btn_iniciar_processamento:
    if not pasta_resumos:
        st.warning("Por favor, forneça o caminho para a pasta de resumos na barra lateral.", icon="⚠️")
    elif not os.path.isdir(pasta_resumos):
        st.error(f"O caminho da pasta de resumos fornecido não é válido ou não existe: {pasta_resumos}", icon="❌")
    else:
        # Placeholder para o log na interface (será aprimorado depois)
        log_area = st.empty()
        log_area.info("Iniciando o processamento... Por favor, aguarde.", icon="⏳")
        
        with st.spinner('🤖 Processando resumos, gerando histórias, traduzindo e criando imagens... Isso pode levar um bom tempo!'):
            try:
                # Chamar a função principal do main.py
                # Idealmente, a função iniciar_processamento_em_lote seria modificada para aceitar um callback 
                # para atualizar a interface Streamlit com os logs.
                # Por enquanto, os logs principais ainda irão para o console.
                
                sucesso = iniciar_processamento_em_lote(pasta_resumos, idiomas_str_para_funcao)
                
                log_area.empty() # Limpar a mensagem de "Iniciando..."
                if sucesso:
                    st.success(f"Processamento concluído com sucesso! 🎉 Verifique a pasta de resultados (normalmente em '{APP_PASTA_SAIDA_PRINCIPAL}') e o console para logs detalhados.", icon="✅")
                    st.balloons()
                else:
                    st.error("O processamento encontrou um problema ou foi interrompido. Verifique os logs no console.", icon="🚨")
            except ImportError:
                 st.error("Falha ao executar o processamento. O módulo 'main' não pôde ser importado corretamente no início.")                 
            except Exception as e:
                log_area.empty()
                st.error(f"Ocorreu um erro inesperado durante o processamento: {e}", icon="🔥")
                st.exception(e) # Mostra o traceback completo na interface para depuração
else:
    st.markdown("### Como usar:")
    st.markdown("1. Preencha os campos na **barra lateral à esquerda**.")
    st.markdown("2. Clique em `Iniciar Processamento`.")
    st.markdown("3. Acompanhe o progresso no console e aguarde a mensagem de finalização aqui.")

# Configuração do ngrok (adicione no início do arquivo)
def iniciar_tunnel():
    try:
        public_url = ngrok.connect(8501)
        st.sidebar.success(f'Acesse este app em: {public_url}')
    except Exception as e:
        st.sidebar.error('Erro ao criar túnel ngrok. Verifique sua conexão com a internet.')

if __name__ == "__main__":
    import streamlit.web.cli as stcli
    import sys
    
    # Iniciar o túnel ngrok
    iniciar_tunnel()
    
    sys.argv = ["streamlit", "run", "app.py", "--server.address", "0.0.0.0", "--server.port", "8501"]
    sys.exit(stcli.main()) 