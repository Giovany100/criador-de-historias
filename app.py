import streamlit as st
import os
import tempfile # Adicionado para lidar com arquivos temporários
import zipfile # Adicionado para funcionalidade de ZIP
import io # Adicionado para manipulação de bytes em memória

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

# Criar a pasta de saída principal se ela não existir no ambiente do Streamlit Cloud
# Isso é importante porque o main.py também tenta criá-la, mas é bom garantir.
if not os.path.exists(APP_PASTA_SAIDA_PRINCIPAL):
    try:
        os.makedirs(APP_PASTA_SAIDA_PRINCIPAL)
    except OSError as e:
        st.error(f"Não foi possível criar a pasta de saída principal '{APP_PASTA_SAIDA_PRINCIPAL}' no ambiente do Streamlit: {e}")
        # Não necessariamente parar, pois main.py pode tentar novamente, mas é um aviso.

st.set_page_config(
    page_title="Criador de Histórias IA", 
    page_icon="🤖", 
    layout="wide", # Usar layout wide para mais espaço
    initial_sidebar_state="expanded" # Manter sidebar aberta por padrão
)

# --- Barra Lateral (Sidebar) para Entradas ---
st.sidebar.header("⚙️ Configurações de Entrada")

# Alterado de text_input para file_uploader
arquivos_resumo_carregados = st.sidebar.file_uploader(
    "Carregue os arquivos de resumo (.txt):",
    type=["txt"],
    accept_multiple_files=True,  # Permitir múltiplos arquivos
    key="resumos_uploader",
    help="Selecione um ou mais arquivos de texto (.txt) contendo os resumos."
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
st.sidebar.caption(f"Version 1.2 | Pasta de Saída Relativa: {APP_PASTA_SAIDA_PRINCIPAL}")

# --- Página Principal ---
st.title("🌟 Criador de Histórias e Imagens com IA 🎬")
st.markdown("Bem-vindo ao seu assistente para transformar resumos em roteiros completos, traduzidos e com sugestões de imagens!")
st.markdown("Configure as entradas na barra lateral à esquerda e clique em **Iniciar Processamento**.")

st.divider()

# Lógica de processamento (quando o botão é clicado)
if btn_iniciar_processamento:
    if not arquivos_resumo_carregados: 
        st.warning("Por favor, carregue pelo menos um arquivo de resumo (.txt) na barra lateral.", icon="⚠️")
    else:
        log_area = st.empty()
        log_area.info("Iniciando o processamento... Por favor, aguarde.", icon="⏳")
        
        with tempfile.TemporaryDirectory(prefix="resumos_streamlit_") as temp_dir_resumos:
            for uploaded_file in arquivos_resumo_carregados:
                try:
                    temp_file_path = os.path.join(temp_dir_resumos, uploaded_file.name)
                    with open(temp_file_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                except Exception as e_save:
                    st.error(f"Erro ao salvar o arquivo carregado '{uploaded_file.name}': {e_save}")
                    st.stop() 

            with st.spinner('🤖 Processando resumos, gerando histórias, traduzindo e criando imagens... Isso pode levar um bom tempo!'):
                try:
                    sucesso = iniciar_processamento_em_lote(temp_dir_resumos, idiomas_str_para_funcao)
                    
                    log_area.empty() 
                    if sucesso:
                        st.success(f"Processamento concluído com sucesso! 🎉 Preparando arquivos para download...", icon="✅")
                        st.balloons()

                        # Criar arquivo ZIP em memória
                        zip_buffer = io.BytesIO()
                        with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
                            for root, _, files in os.walk(temp_dir_resumos):
                                for file in files:
                                    file_path = os.path.join(root, file)
                                    # Adicionar arquivo ao ZIP, mantendo a estrutura de pastas relativa a temp_dir_resumos
                                    zip_file.write(file_path, os.path.relpath(file_path, temp_dir_resumos))
                        
                        zip_buffer.seek(0)
                        
                        st.download_button(
                            label="📥 Baixar Resultados (.zip)",
                            data=zip_buffer,
                            file_name="resultados_criador_historias.zip",
                            mime="application/zip",
                            use_container_width=True
                        )
                        st.info("Clique no botão acima para baixar todos os arquivos de entrada e saída processados.")

                    else:
                        st.error("O processamento encontrou um problema ou foi interrompido. Verifique os logs do aplicativo no Streamlit Cloud para mais detalhes.", icon="🚨")
                
                except ImportError as e_import: 
                     st.error(f"Falha crítica: {e_import}. O módulo 'main' ou suas dependências não puderam ser importados corretamente no início.")
                     st.exception(e_import)
                except Exception as e_process:
                    log_area.empty()
                    st.error(f"Ocorreu um erro inesperado durante o processamento: {e_process}", icon="🔥")
                    st.exception(e_process) 
else:
    st.markdown("### Como usar:")
    st.markdown("1. Carregue um ou mais arquivos de resumo (.txt) na **barra lateral à esquerda**.")
    st.markdown("2. Selecione os idiomas para tradução (opcional).")
    st.markdown("3. Clique em `Iniciar Processamento`.")
    st.markdown("4. Acompanhe o progresso e aguarde a mensagem de finalização aqui. Os logs detalhados podem ser visualizados no console do Streamlit Cloud.")