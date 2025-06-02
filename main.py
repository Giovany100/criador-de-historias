import openai
import requests
import json
import os
import random
import configparser
import time
import glob # Adicionado para listar arquivos
# import cloudscraper # Revertendo temporariamente o cloudscraper
import re # Adicionado para uso em extrair_titulo_slug
from unidecode import unidecode # Adicionado para slugify

# --- CONFIGURAÇÃO INICIAL ---
CONFIG_FILE = 'config.ini'
NOMES_IDIOMAS_DIR = 'nomes_idiomas'
PASTA_SAIDA_PRINCIPAL = 'resultados_processamento' # Novo diretório base para todas as saídas

# Criar diretórios se não existirem
try:
    # Os diretórios ROTEIROS_GERADOS_DIR e IMAGENS_GERADAS_DIR não são mais criados globalmente aqui,
    # pois a estrutura de saída será por resumo dentro de PASTA_SAIDA_PRINCIPAL.
    for diretorio in [NOMES_IDIOMAS_DIR, PASTA_SAIDA_PRINCIPAL]:
        if not os.path.exists(diretorio):
            os.makedirs(diretorio)
except OSError as e:
    print(f"FATAL: Erro ao criar diretórios iniciais ({NOMES_IDIOMAS_DIR}, {PASTA_SAIDA_PRINCIPAL}): {e}")
    print("Verifique as permissões da pasta ou se os nomes não conflitam com arquivos existentes.")
    input("Pressione Enter para fechar...") # Pausa para ver o erro no console
    exit()

def carregar_configuracoes_com_fallback(config_parser=None):
    """
    Carrega configurações priorizando variáveis de ambiente e depois o arquivo config.ini.
    Retorna um dicionário com as configurações.
    """
    configs = {}
    
    # Carregar do config.ini se um parser for fornecido
    cfg_parser = config_parser
    if cfg_parser is None:
        cfg_parser = configparser.ConfigParser()
        if os.path.exists(CONFIG_FILE):
            cfg_parser.read(CONFIG_FILE)
        else:
            print(f"AVISO: Arquivo de configuração '{CONFIG_FILE}' não encontrado. Algumas configurações podem precisar ser definidas via variáveis de ambiente.")

    def get_config_value(section, key, env_var_name, default=None, is_critical=False):
        value = os.getenv(env_var_name)
        if value:
            print(f"INFO: Carregada configuração '{key}' da variável de ambiente '{env_var_name}'.")
            return value
        if cfg_parser and cfg_parser.has_section(section) and cfg_parser.has_option(section, key):
            value_from_file = cfg_parser.get(section, key)
            # Evitar usar valores placeholder do arquivo se a variável de ambiente não estiver definida
            if "SUA_CHAVE_" in value_from_file.upper() or "SEU_ENDPOINT_" in value_from_file.upper():
                 if is_critical:
                    raise ValueError(f"Configuração crítica '{key}' no arquivo '{CONFIG_FILE}' é um placeholder ('{value_from_file}') e a variável de ambiente '{env_var_name}' não está definida.")
                 else:
                    print(f"AVISO: Configuração '{key}' no arquivo '{CONFIG_FILE}' é um placeholder ('{value_from_file}') e a variável de ambiente '{env_var_name}' não está definida. Usando default: {default}")
                    return default
            print(f"INFO: Carregada configuração '{key}' do arquivo '{CONFIG_FILE}'.")
            return value_from_file
        if is_critical:
            raise ValueError(f"Configuração crítica '{key}' não encontrada nem na variável de ambiente '{env_var_name}' nem no arquivo '{CONFIG_FILE}'.")
        return default

    # API Keys
    configs['OPENAI_API_KEY'] = get_config_value('API_KEYS', 'OPENAI_API_KEY', 'OPENAI_API_KEY', is_critical=True)
    configs['GOAPI_API_KEY'] = get_config_value('API_KEYS', 'GOAPI_API_KEY', 'GOAPI_API_KEY', default='GOAPI_KEY_NAO_CONFIGURADA')
    configs['GOAPI_ENDPOINT_URL'] = get_config_value('API_KEYS', 'GOAPI_ENDPOINT_URL', 'GOAPI_ENDPOINT_URL', default='GOAPI_ENDPOINT_NAO_CONFIGURADO')

    # OpenAI Models
    configs['MODELO_GERACAO_HISTORIA'] = get_config_value('OPENAI_MODELS', 'GERACAO_HISTORIA', 'MODELO_GERACAO_HISTORIA', default='gpt-3.5-turbo')
    configs['MODELO_SUBSTITUICAO_NOMES'] = get_config_value('OPENAI_MODELS', 'SUBSTITUICAO_NOMES', 'MODELO_SUBSTITUICAO_NOMES', default='gpt-3.5-turbo')
    configs['MODELO_TRADUCAO'] = get_config_value('OPENAI_MODELS', 'TRADUCAO', 'MODELO_TRADUCAO', default='gpt-3.5-turbo')
    configs['MODELO_DESCRICAO_PERSONAGENS'] = get_config_value('OPENAI_MODELS', 'DESCRICAO_PERSONAGENS', 'MODELO_DESCRICAO_PERSONAGENS', default='gpt-3.5-turbo')
    configs['MODELO_CRIACAO_PROMPTS_IMAGEM'] = get_config_value('OPENAI_MODELS', 'CRIACAO_PROMPTS_IMAGEM', 'MODELO_CRIACAO_PROMPTS_IMAGEM', default='gpt-3.5-turbo')
    
    return configs

# Carregar configurações globais
try:
    app_configs = carregar_configuracoes_com_fallback()
    
    openai_api_key_from_config = app_configs.get('OPENAI_API_KEY')
    if not openai_api_key_from_config: # A criticidade já é tratada em get_config_value
        raise ValueError("Chave da API OpenAI não configurada.")
    openai.api_key = openai_api_key_from_config
    
    GOAPI_API_KEY = app_configs.get('GOAPI_API_KEY')
    GOAPI_ENDPOINT_URL = app_configs.get('GOAPI_ENDPOINT_URL')
    
    if GOAPI_API_KEY == 'GOAPI_KEY_NAO_CONFIGURADA' or GOAPI_ENDPOINT_URL == 'GOAPI_ENDPOINT_NAO_CONFIGURADO':
        print("AVISO: Chave da API GoAPI ou URL do endpoint não configurados via Secrets ou config.ini. A geração de imagens pode falhar.")

    MODELO_GERACAO_HISTORIA = app_configs.get('MODELO_GERACAO_HISTORIA')
    MODELO_SUBSTITUICAO_NOMES = app_configs.get('MODELO_SUBSTITUICAO_NOMES')
    MODELO_TRADUCAO = app_configs.get('MODELO_TRADUCAO')
    MODELO_DESCRICAO_PERSONAGENS = app_configs.get('MODELO_DESCRICAO_PERSONAGENS')
    MODELO_CRIACAO_PROMPTS_IMAGEM = app_configs.get('MODELO_CRIACAO_PROMPTS_IMAGEM')

except (configparser.Error, FileNotFoundError, ValueError) as e: # configparser.Error é mais genérico
    print(f"Erro fatal ao carregar configurações: {e}")
    print(f"Por favor, verifique seus Streamlit Secrets (para deploy) ou o arquivo '{CONFIG_FILE}' (para execução local). Saindo.")
    # Em um ambiente Streamlit, exit() pode não ser ideal, mas para erros críticos de config é necessário.
    # Se for dentro de um app Streamlit, st.error() e st.stop() seriam melhores, mas aqui é o setup inicial do main.py.
    exit()

# --- FUNÇÕES DE APOIO ---
def chamar_openai_api(prompt_sistema, prompt_usuario, modelo, temperatura=0.7, max_tokens=2000):
    """Função genérica para chamar a API da OpenAI com prompt de sistema e usuário."""
    try:
        messages = []
        if prompt_sistema:
            messages.append({"role": "system", "content": prompt_sistema})
        messages.append({"role": "user", "content": prompt_usuario})

        response = openai.chat.completions.create(
            model=modelo,
            messages=messages,
            temperature=temperatura,
            max_tokens=max_tokens
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Erro ao chamar a API da OpenAI: {e}")
        return None

def carregar_nomes_por_idioma(codigo_idioma):
    """Carrega a lista de nomes masculinos e femininos para um idioma específico."""
    arquivo_nomes = os.path.join(NOMES_IDIOMAS_DIR, f"{codigo_idioma.lower()}.json")
    if not os.path.exists(arquivo_nomes):
        print(f"Arquivo de nomes para o idioma '{codigo_idioma}' não encontrado em '{arquivo_nomes}'.")
        return None, None
    try:
        with open(arquivo_nomes, 'r', encoding='utf-8') as f:
            dados = json.load(f)
        return dados.get("masculino", []), dados.get("feminino", [])
    except Exception as e:
        print(f"Erro ao carregar ou parsear o arquivo de nomes '{arquivo_nomes}': {e}")
        return None, None

# --- PARTE 1: GERAÇÃO E PROCESSAMENTO DE ROTEIROS ---
def gerar_historia_original(resumo_usuario, base_filename, pasta_historias_pt, titulo_principal=None):
    """
    Gera uma história em 11 partes:
    1. Gera 11 títulos de capítulos.
    2. Gera o conteúdo para cada capítulo.
    3. Adiciona uma CTA no final.
    """
    print(f"\n--- Iniciando Geração de História em Partes para: {base_filename}.txt ---")

    # --- FASE 1: GERAR 11 TÍTULOS PARA OS CAPÍTULOS ---
    prompt_sistema_titulos = "Você é um roteirista criativo especializado em estruturar narrativas longas em capítulos."
    prompt_usuario_titulos = f"""Com base no seguinte resumo de uma história, crie exatamente 11 títulos de capítulos concisos e envolventes.
Cada título deve dar uma pista do conteúdo principal daquele capítulo, mantendo o suspense e o interesse.
Liste os títulos numerados de 1 a 11. Não adicione nenhuma outra explicação ou texto além da lista de títulos.

Resumo da História:
{resumo_usuario}

Exemplo de formato de Resposta:
1. Título do Capítulo Um
2. Título do Capítulo Dois
...
11. Título do Capítulo Onze

Seus 11 títulos:"""

    print("\nGerando 11 títulos para os capítulos...")
    resposta_titulos_str = chamar_openai_api(prompt_sistema_titulos, prompt_usuario_titulos, MODELO_GERACAO_HISTORIA, temperatura=0.7, max_tokens=500)

    if not resposta_titulos_str:
        print(f"Erro: Não foi possível gerar os títulos para '{base_filename}.txt'. Resposta da API vazia.")
        return None

    titulos_partes = []
    try:
        linhas_titulos = resposta_titulos_str.strip().split('\n')
        for linha in linhas_titulos:
            linha_strip = linha.strip()
            if '. ' in linha_strip: # Procura por 'N. Título'
                titulo_potencial = linha_strip.split('. ', 1)[1].strip()
                if titulo_potencial:
                    titulos_partes.append(titulo_potencial)
            elif linha_strip and (len(linha_strip) > 3 and not linha_strip[0].isdigit()): # Heurística para linhas que são só o título
                 titulos_partes.append(linha_strip)
        
        # Fallback se a extração inicial não retornou nada mas a resposta existe
        if not titulos_partes and resposta_titulos_str.strip():
            print("Aviso: Primeira tentativa de extração de títulos falhou, tentando método de fallback com as linhas.")
            titulos_partes = [l.strip().split('. ', 1)[-1].strip() for l in linhas_titulos if l.strip() and '. ' in l.strip()]
            if not titulos_partes: # Se ainda vazio, usar as linhas diretamente se forem poucas
                 titulos_partes = [l.strip() for l in linhas_titulos if l.strip() and len(l.strip()) > 5] # Evitar linhas muito curtas/vazias

        if not titulos_partes or len(titulos_partes) == 0:
            raise ValueError("Nenhum título pôde ser extraído da resposta da API.")

        if len(titulos_partes) > 11:
            print(f"Aviso: Foram gerados {len(titulos_partes)} títulos. Usando os primeiros 11.")
            titulos_partes = titulos_partes[:11]
        elif len(titulos_partes) < 11 and len(titulos_partes) > 0: # Só avisa se gerou algum, mas menos que 11
            print(f"Aviso: Foram gerados apenas {len(titulos_partes)} títulos, em vez dos 11 esperados. A história poderá ser mais curta ou incompleta.")
        elif len(titulos_partes) == 0: # Se chegou aqui zero, o raise ValueError acima deveria ter pego.
             raise ValueError("Lista de títulos ficou vazia após processamento.")

    except Exception as e:
        print(f"Erro crítico ao processar os títulos gerados para '{base_filename}.txt': {e}")
        print(f"Resposta recebida para títulos (problemática):\n{resposta_titulos_str}")
        caminho_arquivo_erro_titulos = os.path.join(pasta_historias_pt, f"{base_filename}_titulos_ERRO.txt")
        with open(caminho_arquivo_erro_titulos, 'w', encoding='utf-8') as f_err:
            f_err.write(f"Resumo do usuário:\n{resumo_usuario}\n\nResposta da API (títulos):\n{resposta_titulos_str}")
        print(f"Detalhes do erro dos títulos salvos em: {caminho_arquivo_erro_titulos}")
        return None

    print("\n--- Títulos Gerados ---")
    for i, titulo in enumerate(titulos_partes):
        print(f"{i+1}. {titulo}")
    print("------------------------")

    # Salvar os títulos e resumo antes de prosseguir para a geração de conteúdo
    caminho_arquivo_titulos_salvos = os.path.join(pasta_historias_pt, f"{base_filename}_titulos_gerados.txt")
    with open(caminho_arquivo_titulos_salvos, 'w', encoding='utf-8') as f_titulos:
        f_titulos.write("Resumo da História:\n")
        f_titulos.write(resumo_usuario + "\n\n")
        f_titulos.write("Títulos Gerados:\n")
        for i, titulo in enumerate(titulos_partes):
            f_titulos.write(f"{i+1}. {titulo}\n")
    print(f"Títulos gerados e resumo salvos em: {caminho_arquivo_titulos_salvos}")

    # --- FASE 2: GERAR CONTEÚDO PARA CADA PARTE (Iterativamente) ---
    print("\nGerando conteúdo para cada parte da história...")
    historia_completa_partes = []
    texto_parte_anterior_para_contexto = "" # Inicializa o contexto da parte anterior

    for i, titulo_parte_atual in enumerate(titulos_partes):
        print(f"\nGerando Parte {i+1}/{len(titulos_partes)}: '{titulo_parte_atual}'...")
        
        prompt_sistema_parte = "Você é um escritor de histórias continuadas, focado em desenvolver capítulos de uma narrativa maior de forma coesa e sequencial."
        lista_titulos_formatada = "\n".join([f"{idx+1}. {t}" for idx, t in enumerate(titulos_partes)])

        # Construção do prompt do usuário para a parte atual
        prompt_usuario_parte = f"""Estamos construindo uma história capítulo por capítulo. Abaixo estão o resumo geral da história e a lista completa de títulos dos capítulos para seu conhecimento do arco narrativo completo.

Resumo Geral da História:
{resumo_usuario}

Lista Completa de Títulos dos Capítulos (para referência do fluxo geral):
{lista_titulos_formatada}

"""
        # Adicionar contexto da parte anterior, se não for a primeira parte
        if texto_parte_anterior_para_contexto:
            prompt_usuario_parte += f"""--- INÍCIO DO TEXTO DA PARTE ANTERIOR (PARTE {i}) ---
{texto_parte_anterior_para_contexto}
--- FIM DO TEXTO DA PARTE ANTERIOR (PARTE {i}) ---

Baseado no texto da parte anterior e no título da parte atual, continue a história.
"""
        else: # Primeira parte
            prompt_usuario_parte += "Este é o início da história.\n"

        prompt_usuario_parte += f"""Agora, escreva o conteúdo completo, detalhado e extenso para o CAPÍTULO ATUAL ({i+1}): '{titulo_parte_atual}'.
Concentre-se em desenvolver os eventos, diálogos, emoções dos personagens e descrições de ambiente de forma rica e substancial para ESTE capítulo, garantindo que ele continue de forma fluida e natural a partir da parte anterior (se houver).
O texto deve ser uma narrativa fluida em terceira pessoa. 
IMPORTANTE: NÃO inclua o título do capítulo ('{titulo_parte_atual}') novamente no corpo do texto que você vai gerar. Gere APENAS a história para esta parte, como se fosse um fluxo contínuo.
Garanta que este capítulo seja longo e bem desenvolvido.
"""
            
        conteudo_parte = chamar_openai_api(prompt_sistema_parte, prompt_usuario_parte, MODELO_GERACAO_HISTORIA, temperatura=0.7, max_tokens=3000) 

        if not conteudo_parte or (conteudo_parte.strip().upper() == "OK" or len(conteudo_parte.strip()) < 150):
            print(f"Erro: Conteúdo gerado para a Parte {i+1} ('{titulo_parte_atual}') é inválido ou muito curto.")
            print(f"Resposta da API para Parte {i+1} (primeiros 200 chars): {conteudo_parte[:200]}...")
            caminho_arquivo_erro_parte = os.path.join(pasta_historias_pt, f"{base_filename}_parte_{i+1}_ERRO.txt")
            with open(caminho_arquivo_erro_parte, 'w', encoding='utf-8') as f_err_parte:
                f_err_parte.write(f"Resumo: {resumo_usuario}\nLista de Títulos:\n{lista_titulos_formatada}\nContexto Anterior:\n{texto_parte_anterior_para_contexto}\n\nTítulo da Parte Atual: {titulo_parte_atual}\n\nResposta da API (Conteúdo da Parte):\n{conteudo_parte}")
            print(f"Detalhes do erro da Parte {i+1} salvos em: {caminho_arquivo_erro_parte}")
            print("Interrompendo a geração desta história devido ao erro na parte.")
            return None 
        
        conteudo_limpo = conteudo_parte.strip()
        historia_completa_partes.append(conteudo_limpo)
        texto_parte_anterior_para_contexto = conteudo_limpo # Atualiza para a próxima iteração

        print(f"Parte {i+1} gerada com {len(conteudo_limpo)} caracteres.")
        # Pequena pausa entre as partes para não sobrecarregar a API rapidamente
        if i < len(titulos_partes) - 1:
            print("Aguardando 3 segundos antes da próxima parte...")
            time.sleep(3) 

    if not historia_completa_partes or len(historia_completa_partes) != len(titulos_partes):
        print(f"Erro: Falha ao gerar todas as partes da história para '{base_filename}.txt'. Número de partes geradas não confere.")
        return None

    historia_final_sem_cta = "\n\n".join(historia_completa_partes) # Une as partes com parágrafos duplos

    # --- FASE 3: ADICIONAR CALL TO ACTION (CTA) ---
    print("\nAdicionando Call to Action (CTA)...")
    
    prompt_user_cta = f"""Ao final do roteiro a seguir, insira uma Call to Action (CTA) clara e impactante.
Motive o público a interagir, deixando comentários, compartilhando a história ou se inscrevendo no canal.
Certifique-se de que a CTA esteja alinhada com o tom emocional da história e seja direcionada ao público acima de 55 anos.
Mantenha a mensagem breve, mas inspiradora.

A CTA deve ser um parágrafo separado que será adicionado ao final do texto.
Responda APENAS com o texto da Call to Action. Não inclua saudações ou texto adicional.

Trecho final da história (para dar contexto sobre o tom):
...
{historia_final_sem_cta[-1000:]} # Envia os últimos 1000 caracteres da história para contexto de tom

Call to Action:"""
    prompt_system_cta = "Você é um especialista em marketing de conteúdo e redação publicitária, com foco em engajar o público sênior (55+)."
    cta_texto_gerado_pt = chamar_openai_api(prompt_system_cta, prompt_user_cta, MODELO_GERACAO_HISTORIA, temperatura=0.7, max_tokens=200)

    if not cta_texto_gerado_pt or len(cta_texto_gerado_pt.strip()) < 10:
        print("Aviso: Não foi possível gerar a CTA de forma satisfatória ou a resposta foi muito curta. Usando uma CTA padrão.")
        print(f"Resposta da API para CTA: {cta_texto_gerado_pt}")
        cta_texto_gerado_pt = "Gostou desta história emocionante? Sua opinião é muito valiosa para nós! Deixe um comentário abaixo, compartilhe com seus amigos e familiares, e não se esqueça de se inscrever no canal para não perder nenhuma de nossas futuras narrativas. Sua interação nos inspira a continuar criando!"
    else:
        print(f"CTA Gerada (PT): {cta_texto_gerado_pt}")

    # Salvar a história completa em PT (partes + CTA) para referência e uso na geração de imagens
    historia_pt_concatenada_para_salvar = ""
    if titulo_principal:
        historia_pt_concatenada_para_salvar += titulo_principal + "\n\n"
    
    historia_pt_concatenada_para_salvar += historia_final_sem_cta + "\n\n---\n" + cta_texto_gerado_pt.strip()
    nome_arquivo_final_pt = f"{base_filename}_roteiro_completo_pt_com_cta.txt"
    caminho_arquivo_historia_completa_pt = os.path.join(pasta_historias_pt, nome_arquivo_final_pt)
    with open(caminho_arquivo_historia_completa_pt, 'w', encoding='utf-8') as f:
        f.write(historia_pt_concatenada_para_salvar)
    print(f"História completa em Português (com CTA) salva em: {caminho_arquivo_historia_completa_pt}")
    
    # Remover o arquivo temporário sem CTA, se existir (agora o principal é o concatenado acima)
    caminho_arquivo_historia_sem_cta = os.path.join(pasta_historias_pt, f"{base_filename}_roteiro_partes_sem_cta.txt")
    if os.path.exists(caminho_arquivo_historia_sem_cta):
        try:
            os.remove(caminho_arquivo_historia_sem_cta)
            # print(f"Arquivo temporário '{caminho_arquivo_historia_sem_cta}' removido.") # Opcional: log menos verboso
        except OSError as e:
            print(f"Erro ao remover arquivo temporário '{caminho_arquivo_historia_sem_cta}': {e}")

    # Retorna a LISTA de partes de conteúdo PT e a CTA PT separadamente
    return historia_completa_partes, cta_texto_gerado_pt.strip()

def substituir_nomes_e_mapear(historia_texto, nomes_masculinos, nomes_femininos, idioma_destino_nome, base_filename):
    """Identifica nomes na história, cria um mapeamento para novos nomes e depois substitui esses nomes no texto."""
    print(f"\nIniciando identificação e mapeamento de nomes em '{base_filename}.txt' para o idioma: {idioma_destino_nome.upper()}...")
    
    # ETAPA 1: Identificar nomes e gerar o mapeamento via API
    prompt_sistema_identificacao = "Você é um assistente de análise de texto especializado em identificar nomes de personagens em narrativas e sugerir substituições consistentes para um idioma específico."
    prompt_usuario_identificacao = f"""Analise a seguinte história em português:
--- HISTÓRIA ORIGINAL (PORTUGUÊS) ---
{historia_texto}
--- FIM DA HISTÓRIA ORIGINAL ---

Sua tarefa OBRIGATÓRIA é:
1. Identificar todos os nomes próprios de personagens na história. Para cada nome de personagem identificado, infira o sexo provável (masculino ou feminino).
2. Para CADA nome original de personagem identificado, você DEVE OBRIGATORIAMENTE escolher um nome novo e DIFERENTE da lista apropriada (masculina ou feminina) para o idioma '{idioma_destino_nome.upper()}' fornecida abaixo. NÃO reutilize o nome original como o novo nome, mesmo que ele pareça pertencer ao idioma de destino. O objetivo é adaptar os nomes.
   É CRUCIAL que o mesmo nome original (Ex: João) seja SEMPRE mapeado para o MESMO nome novo escolhido (Ex: Giovanni).

Listas de Nomes para '{idioma_destino_nome.upper()}' (Use OBRIGATORIAMENTE estas listas para as sugestões de novos nomes):
Nomes Masculinos: {', '.join(nomes_masculinos)}
Nomes Femininos: {', '.join(nomes_femininos)}

Se um nome original não tiver um equivalente claro ou se as listas estiverem vazias para um determinado sexo, você pode indicar isso, mas priorize a substituição usando as listas.
Responda EXATAMENTE no seguinte formato JSON, contendo APENAS a lista de mapeamento de nomes. Não adicione nenhuma explicação, introdução, conclusão ou qualquer texto fora da estrutura JSON especificada abaixo:
{{
  "mapeamento_nomes": [
    {{"nome_original": "NomeOriginalExemplo1", "novo_nome": "NovoNomeItalianoExemplo1", "sexo_inferido": "masculino"}},
    {{"nome_original": "NomeOriginalExemplo2", "novo_nome": "NovoNomeItalianoExemplo2", "sexo_inferido": "feminino"}}
    // ... (inclua um objeto para cada nome de personagem identificado e mapeado para um NOVO nome do idioma de destino)
  ]
}}
"""

    resposta_mapeamento_json_str = chamar_openai_api(prompt_sistema_identificacao, prompt_usuario_identificacao, MODELO_SUBSTITUICAO_NOMES, temperatura=0.6, max_tokens=1000) # Max tokens menor, pois só esperamos o JSON do mapeamento

    if not resposta_mapeamento_json_str:
        print(f"Erro: A API não retornou resposta para o mapeamento de nomes ('{base_filename}.txt').")
        return None, None

    try:
        # Limpar possível formatação de bloco de código markdown da resposta JSON
        if resposta_mapeamento_json_str.startswith("```json"):
            resposta_mapeamento_json_str = resposta_mapeamento_json_str[7:]
            if resposta_mapeamento_json_str.endswith("```"):
                resposta_mapeamento_json_str = resposta_mapeamento_json_str[:-3]
        resposta_mapeamento_json_str = resposta_mapeamento_json_str.strip()
        
        dados_resposta_mapeamento = json.loads(resposta_mapeamento_json_str)
        mapeamento_nomes = dados_resposta_mapeamento.get("mapeamento_nomes")

        if not mapeamento_nomes:
            print(f"Aviso: A API não retornou um mapeamento de nomes válido ou a lista está vazia para '{base_filename}.txt'. Resposta: {resposta_mapeamento_json_str}")
            # Mesmo com mapeamento vazio, podemos prosseguir, a história não será alterada.
            # Isso pode ser útil se a história não tiver personagens com nomes a serem trocados.
            # Considerar retornar historia_texto original se mapeamento_nomes for None ou vazio.
            mapeamento_nomes = [] # Garante que é uma lista para o próximo passo
            # return historia_texto, [] # Opção: Se não há nomes, não há o que substituir

    except json.JSONDecodeError as e:
        print(f"Erro ao decodificar JSON da resposta da OpenAI para mapeamento de nomes ('{base_filename}.txt'): {e}")
        print(f"Resposta recebida (mapeamento problemático):\n{resposta_mapeamento_json_str}")
        return None, None
    except Exception as e:
        print(f"Erro inesperado ao processar resposta do mapeamento de nomes ('{base_filename}.txt'): {e}")
        return None, None

    print(f"Mapeamento de nomes gerado para '{base_filename}.txt'.")
    if not mapeamento_nomes:
        print("Nenhum nome foi identificado para substituição.")
        return historia_texto, [] # Retorna a história original e um mapeamento vazio

    # ETAPA 2: Substituir os nomes no texto original usando o mapeamento obtido (localmente)
    print(f"Substituindo nomes no texto de '{base_filename}.txt' localmente...")
    historia_com_nomes_substituidos = historia_texto
    
    # É importante ordenar o mapeamento pelos nomes originais mais longos primeiro
    # para evitar substituições parciais incorretas (ex: "Ana" em "Anabel" se "Ana" for substituído primeiro).
    # No entanto, nomes de personagens geralmente são distintos o suficiente.
    # Uma abordagem mais simples é iterar como está, mas CUIDADO se houver nomes que são substrings de outros.
    # Para maior robustez, pode-se usar regex com word boundaries, mas string.replace é mais simples aqui.
    
    substituicoes_feitas = 0
    for item_mapa in mapeamento_nomes:
        nome_original = item_mapa.get("nome_original")
        novo_nome = item_mapa.get("novo_nome")
        if nome_original and novo_nome:
            # Usar uma forma de substituição que respeite palavras inteiras seria ideal,
            # mas para nomes próprios, um replace direto pode ser suficiente na maioria dos casos.
            # Exemplo: re.sub(r'\b' + re.escape(nome_original) + r'\b', novo_nome, historia_com_nomes_substituidos)
            # Por simplicidade, vamos usar replace direto por enquanto.
            if nome_original in historia_com_nomes_substituidos:
                 historia_com_nomes_substituidos = historia_com_nomes_substituidos.replace(nome_original, novo_nome)
                 substituicoes_feitas +=1
                 print(f"  '{nome_original}' -> '{novo_nome}'")
    
    if substituicoes_feitas == 0 and len(mapeamento_nomes) > 0:
        print("Aviso: Mapeamento de nomes foi gerado, mas nenhum nome original foi encontrado/substituído no texto. Verifique a consistência dos nomes.")
    elif substituicoes_feitas > 0:
        print(f"{substituicoes_feitas} substituições de nomes realizadas no texto.")

    return historia_com_nomes_substituidos, mapeamento_nomes

def traduzir_bloco_texto(texto_para_traduzir, idioma_destino_codigo, idioma_destino_nome, modelo_traducao_openai, nome_base_arquivo="", desc_bloco="bloco de texto"):
    """Traduz um bloco de texto fornecido para o idioma de destino."""
    if not texto_para_traduzir.strip():
        # print(f"Aviso: Bloco de texto para tradução ({desc_bloco} de '{nome_base_arquivo}') está vazio. Retornando string vazia.")
        return "" # Retorna vazio se não há nada a traduzir

    # print(f"  Traduzindo {desc_bloco} para {idioma_destino_nome.upper()} (primeiros 50 chars: '{texto_para_traduzir[:50].replace('\n',' ')}...')...")
    
    prompt_sistema_traducao = "Você é um tradutor especialista."
    prompt_usuario_traducao = f"""Traduza o seguinte texto (que já teve nomes de personagens adaptados para o idioma {idioma_destino_nome.upper()}, se aplicável) para o idioma {idioma_destino_nome.upper()}.

IMPORTANTE: Respeite rigorosamente a formatação do texto original, incluindo parágrafos e quebras de linha, se houver.
Os nomes próprios de personagens, se presentes, já foram adaptados para o idioma de destino; mantenha-os exatamente como estão no texto fornecido. Não os traduza novamente nem os modifique.
Sua resposta deve conter APENAS o texto traduzido, sem nenhuma introdução, conclusão ou qualquer outra informação adicional.

Texto para tradução:
{texto_para_traduzir}"""
    
    texto_traduzido = chamar_openai_api(prompt_sistema_traducao, prompt_usuario_traducao, modelo_traducao_openai, max_tokens=4000) # max_tokens para a resposta
    
    if not texto_traduzido:
        print(f"Erro ao traduzir {desc_bloco} para '{nome_base_arquivo}'. Retornando texto original do bloco.")
        return texto_para_traduzir # Retorna o original em caso de erro na tradução do bloco
    
    return texto_traduzido.strip()

# --- PARTE 2: CRIAÇÃO DE IMAGENS ---
def identificar_personagens_principais(historia_original_pt, base_filename):
    """Identifica os 2 personagens principais da história original."""
    print(f"\nIdentificando os 2 personagens principais em '{base_filename}.txt'...")
    prompt_sistema_ident_personagens = "Você é um analista de narrativas focado em identificar os protagonistas de uma história."
    prompt_usuario_ident_personagens = f"""Leia a história abaixo com atenção. Sua tarefa é identificar os **2 personagens principais** da narrativa, que na grande maioria das vezes formarão o casal central da história.
Para isso, considere os seguintes critérios:

- Presença recorrente: o personagem aparece em múltiplas cenas ou capítulos da história.

- Importância para o enredo: as ações ou decisões desse personagem impactam diretamente o rumo da história.

- Desenvolvimento emocional ou de caráter: o personagem passa por transformações, desafios ou descobertas significativas.

- Interação e relacionamento central: Se houver um relacionamento romântico ou uma parceria muito próxima que seja o foco da história, esses dois personagens são os principais.

Após a análise, liste APENAS os nomes dos **2 personagens principais** identificados, separados por vírgula.
Se, por acaso, a história tiver apenas um personagem central claro, liste apenas esse personagem.
Não inclua nenhuma outra explicação ou texto na sua resposta.

Exemplo de resposta para um casal: PersonagemA, PersonagemB
Exemplo de resposta para um único protagonista: PersonagemA

História (em português):
{historia_original_pt}"""
    print(f"DEBUG: Início da história enviada para identificar personagens: {historia_original_pt[:500]}...")
    resposta = chamar_openai_api(prompt_sistema_ident_personagens, prompt_usuario_ident_personagens, MODELO_DESCRICAO_PERSONAGENS, temperatura=0.2, max_tokens=50) # Temperatura mais baixa para mais determinismo, max_tokens ajustado para 2 nomes
    if resposta:
        personagens = [p.strip() for p in resposta.split(',') if p.strip()]
        if len(personagens) > 2:
            print(f"Aviso: A IA identificou {len(personagens)} ({', '.join(personagens)}), mas estamos considerando apenas os 2 primeiros para '{base_filename}.txt'.")
            personagens = personagens[:2]
        elif len(personagens) == 1:
            print(f"A IA identificou apenas 1 personagem principal ({personagens[0]}) para '{base_filename}.txt'.")
        elif len(personagens) == 0:
            print(f"A IA não conseguiu identificar personagens principais claros para '{base_filename}.txt'. Resposta: {resposta}")
            return []
        
        print(f"Os 2 Personagens principais identificados (IA) para '{base_filename}.txt': {', '.join(personagens)}")
        return personagens
    print(f"A IA não retornou resposta para identificação de personagens em '{base_filename}.txt'.")
    return []

def criar_descricao_personagem(nome_personagem, historia_original_pt, base_filename):
    """Cria características detalhadas para um personagem."""
    print(f"\nGerando descrição para o personagem: {nome_personagem} (de '{base_filename}.txt')...")
    prompt_sistema_desc_personagem = "Você é um escritor criativo especializado em descrições de personagens."
    prompt_usuario_desc_personagem = f"""A partir da história a seguir (em português), escreva uma descrição detalhada de {nome_personagem}, incluindo:

- Idade aproximada (baseando-se em pistas textuais ou contexto);

- Características físicas (como cor dos olhos, cabelos, tipo físico, altura, marcas ou traços marcantes);

- Roupas típicas que ele(a) costuma usar ao longo da história (citando cores, estilo, ocasiões em que aparecem);

- Postura e presença — como esse personagem costuma se comportar ou ser percebido pelos outros visualmente.

A descrição deve ser natural, cinematográfica e evocativa, como se fosse utilizada em um roteiro ou livro. 
Evite listas secas; prefira parágrafos fluidos e visualmente ricos.

Exemplo de estilo de resposta esperada (adapte para o personagem {nome_personagem} e a história fornecida):
João parece ter cerca de 35 anos, com uma postura naturalmente ereta que transparece disciplina e distância. Seus olhos são de um castanho escuro quase opaco, geralmente vazios, exceto quando fixam os de Sílvia — ali há algo quebrado, mas vivo. O cabelo é curto, bem penteado, com alguns fios já prateados nas têmporas. Veste-se sempre com elegância silenciosa: ternos escuros sob medida, camisas sem gravata, sapatos engraxados — como se o mundo fosse um negócio a ser vencido, mesmo quando tudo desaba. Sua presença impõe respeito, mas também instiga curiosidade. Há algo nele que parece sempre prestes a desmoronar — e isso o torna irresistivelmente humano.

Agora, gere a descrição para {nome_personagem} com base na seguinte história (em português):

História:
{historia_original_pt}"""
    descricao = chamar_openai_api(prompt_sistema_desc_personagem, prompt_usuario_desc_personagem, MODELO_DESCRICAO_PERSONAGENS, max_tokens=600)
    if descricao:
        print(f"Descrição de {nome_personagem} (de '{base_filename}.txt'): {descricao[:200]}...")
    return descricao

def criar_prompt_imagem_paragrafo(paragrafo_texto, num_paragrafo, base_filename):
    """Cria a parte descritiva EM INGLÊS de um prompt de imagem para um parágrafo."""
    # print(f"\nGerando prompt de imagem para o parágrafo {num_paragrafo} de '{base_filename}.txt'...")
    prompt_sistema_img_paragrafo = "Você é um especialista em criar descrições visuais para prompts de IA de geração de imagem."
    prompt_usuario_img_paragrafo = f"""Analise o seguinte parágrafo de uma história (originalmente em português). Sua tarefa é gerar uma descrição concisa e visualmente rica EM INGLÊS para um prompt de imagem que represente a cena descrita neste parágrafo específico. 
Considere os seguintes critérios para construir sua descrição em inglês:

- Ambiente: onde a cena se passa?

- Personagens visíveis: quem está na cena?

- Ações e emoções: o que está acontecendo?

- Objetos ou elementos relevantes.

- Luz e clima.

Sua descrição em inglês deve ser clara, visual, evocativa e cinematográfica, pronta para ser usada como parte de um prompt maior para um gerador de imagens. 
Evite repetições e generalizações vagas — prefira detalhes específicos. 
Concentre-se apenas no conteúdo do parágrafo fornecido abaixo.

Parágrafo da história (em português):
{paragrafo_texto}

Descrição EM INGLÊS para prompt de imagem (baseada SOMENTE no parágrafo acima):"""
    
    prompt_meio_ingles = chamar_openai_api(prompt_sistema_img_paragrafo, prompt_usuario_img_paragrafo, MODELO_CRIACAO_PROMPTS_IMAGEM, max_tokens=200)
    
    if not prompt_meio_ingles:
        return None

    # CORREÇÃO APLICADA AQUI ADICIONANDO UM ESPAÇO ANTES DE --ar
    prompt_final = (
        f"image prompt: An ultra-realistic image. {prompt_meio_ingles}. "
        f"shadows that enhance your expression, soft light on your face. Created using: Canon EOS R5, f/2.8 aperture, Caravaggio-inspired lighting, high-resolution details, hyperrealistic details, 8K resolution, high definition, photorealistic textures, natural lighting, depth of field, intricate detailed details. --ar 16:9 --v 6.1 --style raw"
    )
    return prompt_final

def criar_prompt_imagem_personagem(nome_personagem, descricao_personagem_pt, base_filename, num_prompt, cref_url=None):
    """Cria a parte descritiva EM INGLÊS de um prompt de imagem para um personagem."""
    # print(f"\nGerando prompt de imagem {num_prompt} para o personagem: {nome_personagem} (de '{base_filename}.txt')...")
    prompt_sistema_img_personagem = "Você é um especialista em criar descrições visuais de personagens para prompts de IA de geração de imagem."
    prompt_usuario_img_personagem = f"""Com base na descrição detalhada do personagem fornecida abaixo (originalmente em português), 
crie uma descrição concisa e altamente visual EM INGLÊS para um prompt de imagem. 
O objetivo é retratar o personagem {nome_personagem} de forma realista ou semi-realista.\n\nA descrição em inglês para o prompt de imagem deve condensar os seguintes aspectos do personagem, extraídos da descrição detalhada:

- Idade aparente;

- Características físicas marcantes (cor da pele, olhos, cabelo, altura, expressão);

- Estilo de roupa típico (com detalhes como cores, tecidos e época, se houver);

- Um cenário ou fundo que combine com o personagem ou um momento chave da história (ex: cafeteria aconchegante, escritório elegante, rua chuvosa);

- O tom emocional da imagem (ex: romântico, melancólico, acolhedor, tenso).\n\nO resultado deve ser uma frase EM INGLÊS, fluida e rica em detalhes visuais, adequada para ser parte de um prompt maior para um gerador de imagens. 
Siga o estilo: \"A woman in her early 30s with curly brown hair, wearing a soft beige dress, in a cozy sunlit cafe, thoughtful and serene mood.\" (Adapte para o personagem e sua descrição).\n\nDescrição detalhada do personagem {nome_personagem} (em português, use como base para criar a descrição para o prompt de imagem em inglês):
{descricao_personagem_pt}

Descrição EM INGLÊS para prompt de imagem (concisa, visual, baseada na descrição detalhada acima):"""
    
    prompt_meio_ingles = chamar_openai_api(prompt_sistema_img_personagem, prompt_usuario_img_personagem, MODELO_CRIACAO_PROMPTS_IMAGEM, max_tokens=200)

    if not prompt_meio_ingles:
        return None

    novo_prompt_base_str = (
        f"image prompt: An ultra-realistic image. {prompt_meio_ingles}. "
        f"shadows that enhance your expression, soft light on your face. Created using: Canon EOS R5, f/2.8 aperture, Caravaggio-inspired lighting, high-resolution details, hyperrealistic details, 8K resolution, high definition, photorealistic textures, natural lighting, depth of field, intricate detailed details."
    )

    if cref_url:
        prompt_final = f"{novo_prompt_base_str} --cref {cref_url} --ar 16:9 --v 6.1 --style raw"
    else:
        prompt_final = f"{novo_prompt_base_str} --ar 16:9 --v 6.1 --style raw"
        
    return prompt_final

def gerar_imagem_goapi(prompt_texto, nome_arquivo_saida_base, base_filename, pasta_imagens, apenas_obter_urls=False):
    """Gera uma imagem usando a GoAPI e salva, ou apenas retorna as URLs. 
    Se uma grade de 4 for retornada, tenta salvar as 4 individualmente (se não apenas_obter_urls)."""
    print(f"\nIniciando geração de imagem com GoAPI para: {nome_arquivo_saida_base} (de '{base_filename}.txt')...")
    if apenas_obter_urls:
        print("Modo: Apenas obter URLs, o download das imagens será pulado.")
    print(f"Prompt enviado (primeiros 100 chars): {prompt_texto[:100]}...")
    
    MAX_TASK_CREATE_ATTEMPTS = 3
    TASK_CREATE_RETRY_DELAY = 5 # segundos
    MAX_DOWNLOAD_ATTEMPTS = 3
    DOWNLOAD_RETRY_DELAY = 5 # segundos

    # Verifica novamente aqui para garantir, embora a verificação principal seja no carregamento das configs
    global GOAPI_API_KEY, GOAPI_ENDPOINT_URL # Necessário se não forem passadas como argumento
    goapi_key_placeholder = 'SUA_CHAVE_GOAPI_AQUI'
    goapi_endpoint_placeholder = 'SEU_ENDPOINT_GOAPI_AQUI'

    if not GOAPI_API_KEY or GOAPI_API_KEY == goapi_key_placeholder or \
       not GOAPI_ENDPOINT_URL or GOAPI_ENDPOINT_URL == goapi_endpoint_placeholder:
        print("Chave da API GoAPI ou URL do endpoint não configurados corretamente. Pulando geração de imagem.")
        return None

    headers = { 'X-API-Key': GOAPI_API_KEY, 'Content-Type': 'application/json' }
    create_task_payload = { "model": "midjourney", "task_type": "imagine", "input": {"prompt": prompt_texto} }
    task_id = None
    
    for attempt in range(MAX_TASK_CREATE_ATTEMPTS):
        try:
            print(f"Enviando solicitação de criação de tarefa para GoAPI para '{nome_arquivo_saida_base}' (Tentativa {attempt + 1}/{MAX_TASK_CREATE_ATTEMPTS})...")
            response_create = requests.post(GOAPI_ENDPOINT_URL, headers=headers, json=create_task_payload, timeout=60)
            response_create.raise_for_status() # Levanta um erro para códigos HTTP 4xx/5xx
            resposta_create_json = response_create.json()

            # Adicionando log do prompt em caso de erro de validação específico da GoAPI
            if resposta_create_json.get("code") != 200 and isinstance(resposta_create_json.get("data"), dict):
                error_data = resposta_create_json.get("data", {}).get("error", {})
                if error_data.get("code") == 10000 and "failed to check prompt" in error_data.get("message", "").lower():
                    print(f"!!! ERRO DE VALIDAÇÃO DO PROMPT PELA GoAPI (erro GoAPI 10000) !!!")
                    print(f"Prompt enviado que causou o erro:")
                    print(prompt_texto)

            if resposta_create_json.get("code") == 200 and isinstance(resposta_create_json.get("data"), dict):
                task_id = resposta_create_json["data"].get("task_id")
            
            if not task_id:
                print(f"Erro na tentativa {attempt + 1}: Não foi possível obter task_id da resposta de criação. Resposta: {json.dumps(resposta_create_json, indent=2)}")
                if resposta_create_json.get("code") != 200:
                     print(f"Prompt que pode ter levado ao erro (task_id não obtido):")
                     print(prompt_texto)
                # Não retorna None imediatamente, tenta novamente se houver mais tentativas
            else:
                print(f"Tarefa criada com ID: {task_id} para '{nome_arquivo_saida_base}'")
                break # Sucesso, sair do loop de tentativas

        except requests.exceptions.RequestException as e:
            print(f"Erro na requisição de criação de tarefa para GoAPI ('{nome_arquivo_saida_base}') (Tentativa {attempt + 1}/{MAX_TASK_CREATE_ATTEMPTS}): {e}")
            if e.response is not None: print(f"Detalhes do erro da GoAPI: {e.response.text}")
        except Exception as e: # Captura outras exceções como json.JSONDecodeError se a resposta não for JSON válido
            print(f"Erro inesperado ao criar tarefa com GoAPI ('{nome_arquivo_saida_base}') (Tentativa {attempt + 1}/{MAX_TASK_CREATE_ATTEMPTS}): {e}")
        
        if attempt < MAX_TASK_CREATE_ATTEMPTS - 1:
            print(f"Aguardando {TASK_CREATE_RETRY_DELAY}s antes da próxima tentativa de criação de tarefa...")
            time.sleep(TASK_CREATE_RETRY_DELAY)
        else:
            print(f"Todas as {MAX_TASK_CREATE_ATTEMPTS} tentativas de criação de tarefa falharam para '{nome_arquivo_saida_base}'.")
            return None # Falhou todas as tentativas
            
    if not task_id: # Se saiu do loop sem task_id (deveria ter sido pego pelo return None acima, mas como segurança)
        print(f"Falha crítica: task_id não obtido após todas as tentativas para '{nome_arquivo_saida_base}'.")
        return None

    get_task_url_template = f"{GOAPI_ENDPOINT_URL}/{{task_id_placeholder}}"
    get_headers = {'X-API-Key': GOAPI_API_KEY}
    polling_attempts = 0
    max_polling_attempts = 60 
    poll_interval = 10

    while polling_attempts < max_polling_attempts:
        polling_attempts += 1
        print(f"Consultando status da tarefa {task_id} ('{nome_arquivo_saida_base}') (Tentativa {polling_attempts}/{max_polling_attempts})...")
        try:
            get_task_url = get_task_url_template.replace("{task_id_placeholder}", task_id)
            response_get = requests.get(get_task_url, headers=get_headers, timeout=30)
            response_get.raise_for_status()
            resposta_get_json = response_get.json()
            task_data = None
            if isinstance(resposta_get_json, dict) and resposta_get_json.get("code") == 200:
                if isinstance(resposta_get_json.get("data"), dict):
                     task_data = resposta_get_json["data"]
            
            if not task_data:
                print(f"Não foi possível obter dados da tarefa {task_id} ('{nome_arquivo_saida_base}') na tentativa {polling_attempts}. Resposta: {resposta_get_json}")
                time.sleep(poll_interval)
                continue

            status = task_data.get("status")
            print(f"Status atual da tarefa {task_id} ('{nome_arquivo_saida_base}'): {status}")

            if status == "completed":
                output = task_data.get("output", {})
                image_urls_list = output.get("temporary_image_urls") 
                
                if apenas_obter_urls:
                    if image_urls_list and isinstance(image_urls_list, list) and len(image_urls_list) > 0:
                        print(f"Tarefa {task_id} ('{base_filename}.txt') completada. URLs obtidas: {len(image_urls_list)}")
                        return image_urls_list # Retorna a lista de URLs
                    else:
                        # Fallback para image_urls ou image_url se temporary_image_urls não estiver presente
                        fallback_urls = output.get("image_urls")
                        if fallback_urls and isinstance(fallback_urls, list) and len(fallback_urls) > 0:
                             print(f"Tarefa {task_id} ('{base_filename}.txt') completada. Usando fallback image_urls. URLs obtidas: {len(fallback_urls)}")
                             return fallback_urls
                        
                        singular_url = output.get("image_url")
                        if singular_url and isinstance(singular_url, str):
                            print(f"Tarefa {task_id} ('{base_filename}.txt') completada. Usando fallback image_url (singular). URL obtida.")
                            return [singular_url]
                            
                        print(f"Tarefa {task_id} ('{base_filename}.txt') completada, mas não foi possível encontrar URLs de imagem válidas no modo 'apenas_obter_urls'. Output: {json.dumps(output, indent=2)}")
                        return None 

                arquivos_salvos = []
                if image_urls_list and isinstance(image_urls_list, list) and len(image_urls_list) > 0:
                    print(f"Tarefa {task_id} ('{base_filename}.txt') completada! Encontradas {len(image_urls_list)} URL(s) em temporary_image_urls, salvando individualmente...")
                    for idx, img_url in enumerate(image_urls_list):
                        if not img_url or not isinstance(img_url, str):
                            print(f"  Aviso: URL inválida encontrada na lista temporary_image_urls (índice {idx}): {img_url}. Pulando.")
                            continue
                        
                        img_downloaded_successfully = False
                        for download_attempt in range(MAX_DOWNLOAD_ATTEMPTS):
                            try:
                                print(f"  Baixando imagem {idx+1}/{len(image_urls_list)}: {img_url} (Tentativa {download_attempt + 1}/{MAX_DOWNLOAD_ATTEMPTS})")
                                download_headers = {
                                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36",
                                    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
                                    "Referer": "https://www.midjourney.com/app/",
                                }
                                response_img = requests.get(img_url, timeout=120, headers=download_headers, stream=True)
                                response_img.raise_for_status()
                                img_data = response_img.content
                                if not img_data:
                                    print(f"  Aviso (Tentativa {download_attempt + 1}): Download da imagem {idx+1}/{len(image_urls_list)} ({img_url}) retornou conteúdo vazio.")
                                    # Considerar como falha para tentar novamente
                                    if download_attempt < MAX_DOWNLOAD_ATTEMPTS - 1:
                                        time.sleep(DOWNLOAD_RETRY_DELAY)
                                    continue # Tenta novamente ou falha após todas as tentativas
                                
                                nome_arquivo_individual = f"{os.path.splitext(nome_arquivo_saida_base)[0]}_grid_{idx+1}{os.path.splitext(nome_arquivo_saida_base)[1]}"
                                caminho_completo_saida_individual = os.path.join(pasta_imagens, nome_arquivo_individual)
                                with open(caminho_completo_saida_individual, 'wb') as handler:
                                    handler.write(img_data)
                                print(f"  Imagem {idx+1}/{len(image_urls_list)} salva em: {caminho_completo_saida_individual}")
                                arquivos_salvos.append(caminho_completo_saida_individual)
                                img_downloaded_successfully = True
                                break # Sucesso no download, sair do loop de tentativas de download

                            except requests.exceptions.RequestException as e_download_req:
                                print(f"  Erro na requisição ao baixar imagem individual {img_url} (Tentativa {download_attempt + 1}/{MAX_DOWNLOAD_ATTEMPTS}): {e_download_req}")
                                if e_download_req.response is not None:
                                    print(f"  Status Code: {e_download_req.response.status_code}")
                                    try:
                                        preview = e_download_req.response.content[:200]
                                        print(f"  Preview da resposta (até 200 bytes): {preview}")
                                    except Exception:
                                        print("  Não foi possível obter preview da resposta.")
                            except Exception as e_download_generic:
                                print(f"  Erro genérico ao baixar/salvar imagem individual {img_url} (Tentativa {download_attempt + 1}/{MAX_DOWNLOAD_ATTEMPTS}): {e_download_generic}")
                            
                            if download_attempt < MAX_DOWNLOAD_ATTEMPTS - 1:
                                print(f"    Aguardando {DOWNLOAD_RETRY_DELAY}s antes da próxima tentativa de download...")
                                time.sleep(DOWNLOAD_RETRY_DELAY)
                        
                        if not img_downloaded_successfully:
                            print(f"  Falha ao baixar a imagem {img_url} após {MAX_DOWNLOAD_ATTEMPTS} tentativas. Pulando esta imagem.")
                            
                    return arquivos_salvos if arquivos_salvos else None
                else:
                    # temporary_image_urls estava vazio ou não era uma lista válida.
                    # Verificar fallbacks, mas não tentar download por eles nesta etapa.
                    if output.get("image_urls") and isinstance(output.get("image_urls"), list) and len(output.get("image_urls")) > 0:
                        print(f"Aviso: temporary_image_urls não encontrado/vazio. Encontrado image_urls (fallback) para '{base_filename}.txt'. Download por este fallback desativado.")
                    elif output.get("image_url"):
                        print(f"Aviso: temporary_image_urls e image_urls não encontrados/vazios. Encontrado image_url (fallback singular) para '{base_filename}.txt'. Download por este fallback desativado.")
                    else:
                        print(f"Tarefa {task_id} ('{base_filename}.txt') completada, mas não foi possível encontrar URLs de imagem válidas. Output: {json.dumps(output, indent=2)}")
                    return None # Retorna None se temporary_image_urls falhou e os fallbacks estão desativados para download

            elif status in ["failed", "staged"]:
                error_info = task_data.get("error", {})
                error_message = error_info.get("message", "Erro desconhecido.")
                print(f"Tarefa {task_id} ('{nome_arquivo_saida_base}') falhou ou está em estado problemático ({status}). Erro: {error_message}")
                print(f"  Prompt que resultou nesta falha específica: {prompt_texto}") # Log Adicional
                return None
            elif status in ["pending", "processing"]:
                time.sleep(poll_interval)
            else:
                print(f"Status desconhecido ou inesperado para a tarefa {task_id} ('{nome_arquivo_saida_base}'): {status}. Interrompendo.")
                return None        
        except requests.exceptions.RequestException as e:
            print(f"Erro na requisição de Get Task para GoAPI ('{nome_arquivo_saida_base}', tentativa {polling_attempts}): {e}")
            if e.response is not None: print(f"Detalhes do erro da GoAPI: {e.response.text}")
            time.sleep(poll_interval)
        except Exception as e:
            print(f"Erro inesperado durante o polling da tarefa {task_id} ('{nome_arquivo_saida_base}', tentativa {polling_attempts}): {e}")
            time.sleep(poll_interval)
    
    print(f"Tarefa {task_id} ('{nome_arquivo_saida_base}') não completada após {max_polling_attempts} tentativas. Desistindo.")
    return None

# --- FUNÇÃO PRINCIPAL REATORADA ---
def iniciar_processamento_em_lote(pasta_resumos_input, idiomas_para_traduzir_str_input):
    print(f"[DEBUG] main.py: Iniciando 'iniciar_processamento_em_lote'.")
    print(f"[DEBUG] main.py: Pasta de resumos recebida: {pasta_resumos_input}")
    
    # Lista os arquivos .txt na pasta de resumos
    arquivos_resumo_txt = glob.glob(os.path.join(pasta_resumos_input, '*.txt'))
    print(f"[DEBUG] main.py: Arquivos .txt encontrados em '{pasta_resumos_input}': {arquivos_resumo_txt}")

    if not arquivos_resumo_txt:
        print(f"[DEBUG] main.py: Nenhum arquivo .txt encontrado em '{pasta_resumos_input}'. Encerrando processamento de lote sem ação aparente, mas retornará sucesso se nenhum erro ocorrer.")
        # A função original continua e retorna True no final se não processar arquivos.
        # Manter esse comportamento para não quebrar o fluxo do app.py.

    print(f"INFO: Iniciando processamento em lote para arquivos em: {pasta_resumos_input}")

    if not os.path.isdir(pasta_resumos_input):
        print(f"Erro: O caminho '{pasta_resumos_input}' não é uma pasta válida ou não existe. Saindo.")
        return False # Indica falha

    idiomas_selecionados = [idioma.strip() for idioma in idiomas_para_traduzir_str_input.split(',') if idioma.strip()]

    mapa_nomes_idiomas = {
        "italiano": "Italiano", "ingles": "Inglês", "espanhol": "Espanhol",
        "polones": "Polonês", "romeno": "Romeno", "alemao": "Alemão",
        "frances": "Francês", "hungaro": "Húngaro", "grego": "Grego",
        "croata": "Croata", "espanhol_mx": "Espanhol (México)", "suica": "Suíço",
    }

    arquivos_resumo = glob.glob(os.path.join(pasta_resumos_input, "*.txt"))
    if not arquivos_resumo:
        print(f"Nenhum arquivo .txt encontrado na pasta '{pasta_resumos_input}'. Saindo.")
        return False # Indica falha

    print(f"\\nEncontrados {len(arquivos_resumo)} arquivos de resumo para processar: {', '.join(os.path.basename(f) for f in arquivos_resumo)}")

    for idx_resumo, caminho_arquivo_resumo in enumerate(arquivos_resumo):
        nome_base_arquivo_original = os.path.splitext(os.path.basename(caminho_arquivo_resumo))[0]
        print(f"\\n--- PROCESSANDO RESUMO {idx_resumo + 1}/{len(arquivos_resumo)}: {nome_base_arquivo_original}.txt ---")
        
        pasta_mae_resumo = os.path.join(PASTA_SAIDA_PRINCIPAL, nome_base_arquivo_original)
        pasta_historias_pt_local = os.path.join(pasta_mae_resumo, "HISTORIAS_PT")
        pasta_imagens_local = os.path.join(pasta_mae_resumo, "IMAGENS")
        pasta_prompts_local = os.path.join(pasta_mae_resumo, "PROMPTS")

        os.makedirs(pasta_mae_resumo, exist_ok=True)
        os.makedirs(pasta_historias_pt_local, exist_ok=True)
        os.makedirs(pasta_imagens_local, exist_ok=True)
        os.makedirs(pasta_prompts_local, exist_ok=True)
        
        titulo_do_resumo = None
        resumo_para_geracao = ""
        try:
            with open(caminho_arquivo_resumo, 'r', encoding='utf-8') as f_resumo:
                linhas_resumo = [linha.strip() for linha in f_resumo.readlines()]
            
            if linhas_resumo:
                if linhas_resumo[0]:
                    titulo_do_resumo = linhas_resumo[0]
                if len(linhas_resumo) > 1:
                    resumo_para_geracao = "\\n".join(linhas_resumo[1:]).strip()
                elif titulo_do_resumo and not resumo_para_geracao:
                    pass
            
            if not titulo_do_resumo and not resumo_para_geracao and linhas_resumo:
                if not titulo_do_resumo:
                    resumo_para_geracao = "\\n".join(linhas_resumo).strip()

            if not resumo_para_geracao and not titulo_do_resumo:
                print(f"O arquivo de resumo '{nome_base_arquivo_original}.txt' está vazio ou contém apenas espaços em branco. Pulando.")
                continue
            elif not resumo_para_geracao and titulo_do_resumo:
                print(f"Aviso: O arquivo de resumo '{nome_base_arquivo_original}.txt' contém um título ('{titulo_do_resumo}') mas nenhum corpo de resumo. A qualidade da história pode ser afetada se a IA não tiver resumo suficiente.")

        except Exception as e:
            print(f"Erro ao ler o arquivo de resumo '{nome_base_arquivo_original}.txt': {e}. Pulando.")
            continue

        retorno_geracao = gerar_historia_original(resumo_para_geracao, 
                                                  nome_base_arquivo_original, 
                                                  pasta_historias_pt_local, 
                                                  titulo_principal=titulo_do_resumo)
        
        if retorno_geracao is None:
            print(f"Não foi possível gerar a história original para '{nome_base_arquivo_original}.txt'. Pulando para o próximo resumo.")
            continue
        
        lista_partes_pt, cta_texto_pt = retorno_geracao

        if not lista_partes_pt:
            print(f"A geração da história para '{nome_base_arquivo_original}.txt' não retornou partes de conteúdo. Pulando.")
            continue
            
        historia_original_pt_completa_para_analise = "\\n\\n".join(lista_partes_pt) + "\\n\\n---\\n" + cta_texto_pt

        for cod_idioma in idiomas_selecionados:
            nome_idioma_map = mapa_nomes_idiomas.get(cod_idioma, cod_idioma.capitalize())
            print(f"\\n--- Processando tradução para {nome_idioma_map.upper()} para '{nome_base_arquivo_original}.txt' ---")
            
            # Traduzir o título primeiro, se existir
            titulo_traduzido_idioma = ""
            if titulo_do_resumo:
                print(f"  Traduzindo Título ('{titulo_do_resumo}') para {nome_idioma_map.upper()}...")
                titulo_traduzido_idioma = traduzir_bloco_texto(
                    titulo_do_resumo, 
                    cod_idioma, 
                    nome_idioma_map, 
                    MODELO_TRADUCAO, 
                    nome_base_arquivo_original, 
                    "Título"
                )
                if not titulo_traduzido_idioma:
                    print(f"    Aviso: Falha ao traduzir o título. Será usado o título original em português se disponível, ou nenhum título.")
                    titulo_traduzido_idioma = titulo_do_resumo # Fallback para o título original em PT se a tradução falhar mas o título existir
            
            nomes_m, nomes_f = carregar_nomes_por_idioma(cod_idioma)
            if nomes_m is None or nomes_f is None or (not nomes_m and not nomes_f):
                print(f"Não foi possível carregar nomes ou listas de nomes vazias para {nome_idioma_map}. Pulando este idioma para '{nome_base_arquivo_original}.txt'.")
                continue
            
            _, mapeamento_nomes = substituir_nomes_e_mapear(historia_original_pt_completa_para_analise, nomes_m, nomes_f, nome_idioma_map, nome_base_arquivo_original)

            if mapeamento_nomes is None:
                print(f"Não foi possível obter o mapeamento de nomes para {nome_idioma_map} ('{nome_base_arquivo_original}.txt'). Tradução não será realizada.")
                continue
            
            caminho_mapeamento = os.path.join(pasta_prompts_local, f"{nome_base_arquivo_original}_mapeamento_nomes_{cod_idioma}.json")
            with open(caminho_mapeamento, 'w', encoding='utf-8') as f_map:
                json.dump(mapeamento_nomes, f_map, indent=2, ensure_ascii=False)
            print(f"Mapeamento de nomes para {nome_idioma_map} salvo em: {caminho_mapeamento}")

            partes_traduzidas_idioma_atual = []
            print(f"\\nIniciando tradução parte a parte para {nome_idioma_map.upper()}...")
            for idx_parte, parte_pt_original in enumerate(lista_partes_pt):
                parte_pt_com_nomes_subst = parte_pt_original
                if mapeamento_nomes:
                    for item_mapa in mapeamento_nomes:
                        nome_original = item_mapa.get("nome_original")
                        novo_nome = item_mapa.get("novo_nome")
                        if nome_original and novo_nome:
                            if nome_original in parte_pt_com_nomes_subst:
                                parte_pt_com_nomes_subst = parte_pt_com_nomes_subst.replace(nome_original, novo_nome)
                
                print(f"  Traduzindo Parte {idx_parte + 1}/{len(lista_partes_pt)} para {nome_idioma_map.upper()}...")
                parte_traduzida = traduzir_bloco_texto(parte_pt_com_nomes_subst, 
                                                       cod_idioma, 
                                                       nome_idioma_map, 
                                                       MODELO_TRADUCAO, 
                                                       nome_base_arquivo_original, 
                                                       f"Parte {idx_parte + 1}")
                partes_traduzidas_idioma_atual.append(parte_traduzida)
                time.sleep(1)
            
            print(f"  Traduzindo CTA para {nome_idioma_map.upper()}...")
            cta_pt_com_nomes_subst = cta_texto_pt
            if mapeamento_nomes: 
                for item_mapa in mapeamento_nomes:
                    nome_original = item_mapa.get("nome_original")
                    novo_nome = item_mapa.get("novo_nome")
                    if nome_original and novo_nome:
                        if nome_original in cta_pt_com_nomes_subst:
                             cta_pt_com_nomes_subst = cta_pt_com_nomes_subst.replace(nome_original, novo_nome)
            
            cta_traduzida_idioma = traduzir_bloco_texto(cta_pt_com_nomes_subst, 
                                                        cod_idioma, 
                                                        nome_idioma_map, 
                                                        MODELO_TRADUCAO, 
                                                        nome_base_arquivo_original, 
                                                        "CTA")

            # Montar a história traduzida final, incluindo o título traduzido
            historia_traduzida_final_com_titulo = ""
            if titulo_traduzido_idioma:
                 historia_traduzida_final_com_titulo += titulo_traduzido_idioma + "\n\n"
            
            historia_traduzida_final_com_titulo += "\\n\\n".join(partes_traduzidas_idioma_atual) + "\\n\\n---\\n" + cta_traduzida_idioma
            
            pasta_historia_trad_idioma = os.path.join(pasta_mae_resumo, f"HISTORIAS_{cod_idioma.lower()}")
            os.makedirs(pasta_historia_trad_idioma, exist_ok=True)
            caminho_arquivo_traduzido = os.path.join(pasta_historia_trad_idioma, f"{nome_base_arquivo_original}_roteiro_traduzido_{cod_idioma.lower()}.txt")
            with open(caminho_arquivo_traduzido, 'w', encoding='utf-8') as f_trad:
                f_trad.write(historia_traduzida_final_com_titulo)
            print(f"História traduzida para {nome_idioma_map.upper()} salva em: {caminho_arquivo_traduzido}")

        print(f"\\n--- Iniciando Geração de Imagens para '{nome_base_arquivo_original}.txt' (baseado na história original em Português) ---")
        
        todos_os_prompts_imagem = [] # Mantida para salvar os textos dos prompts e talvez para um log final

        personagens_principais = identificar_personagens_principais(historia_original_pt_completa_para_analise, nome_base_arquivo_original)
        
        if personagens_principais:
            # Ajustar a mensagem de log para refletir a busca por 2 personagens
            if len(personagens_principais) == 1:
                print(f"Processando 1 personagem principal identificado para '{nome_base_arquivo_original}.txt'...")
            else: # Pode ser 0 ou 2, ou mais se a função anterior falhar em limitar
                print(f"Gerando descrições e prompts para os {len(personagens_principais)} personagem(ns) principal(is) identificado(s) de '{nome_base_arquivo_original}.txt'...")
            
            for i, nome_p in enumerate(personagens_principais):
                # Garantir que processemos no máximo os 2 primeiros personagens retornados
                if i >= 2: 
                    print(f"Limitando o processamento aos 2 primeiros personagens principais identificados para '{nome_base_arquivo_original}.txt'. Personagem '{nome_p}' e seguintes serão ignorados.")
                    break
                
                desc_char_pt = criar_descricao_personagem(nome_p, historia_original_pt_completa_para_analise, nome_base_arquivo_original)
                if not desc_char_pt:
                    print(f"Não foi possível criar descrição para o personagem {nome_p} ('{nome_base_arquivo_original}.txt'). Pulando este personagem.")
                    continue

                print(f"\\nProcessando personagem: {nome_p}")
                cref_url_escolhida = None

                # 1. Gerar o primeiro prompt para obter a URL de referência
                prompt_referencia_obj = criar_prompt_imagem_personagem(nome_p, desc_char_pt, nome_base_arquivo_original, 1) # num_prompt = 1 para referência
                
                if prompt_referencia_obj:
                    # Salvar o texto do prompt de referência
                    prompt_ref_filename_base = f"{nome_base_arquivo_original}_personagem_{nome_p.replace(' ','_')}_prompt_referencia"
                    prompt_ref_filename_txt = f"{prompt_ref_filename_base}.txt"
                    caminho_prompt_ref = os.path.join(pasta_prompts_local, prompt_ref_filename_txt)
                    with open(caminho_prompt_ref, 'w', encoding='utf-8') as f_prompt:
                        f_prompt.write(prompt_referencia_obj)
                    print(f"  Texto do prompt de referência salvo em: {caminho_prompt_ref}")
                    
                    # Chamar GoAPI para obter URLs, sem baixar
                    print(f"  Obtendo URL de referência para {nome_p}...")
                    urls_referencia = gerar_imagem_goapi(
                        prompt_referencia_obj, 
                        f"{prompt_ref_filename_base}_TEMP", # Nome base temporário, não será salvo
                        nome_base_arquivo_original, 
                        pasta_imagens_local, 
                        apenas_obter_urls=True
                    )

                    if urls_referencia and isinstance(urls_referencia, list) and len(urls_referencia) > 0:
                        cref_url_escolhida = random.choice(urls_referencia)
                        print(f"  URL de referência escolhida para {nome_p}: {cref_url_escolhida}")
                    else:
                        print(f"  Não foi possível obter URLs de referência para {nome_p}. Os prompts subsequentes para este personagem serão gerados sem --cref.")
                else:
                    print(f"  Não foi possível criar o prompt de referência para {nome_p}.")

                # 2. Gerar 5 prompts para o personagem (os 4 últimos com --cref, se disponível)
                # O primeiro já foi "usado" para cref, então vamos gerar +4 com cref, ou 5 normais se cref falhou.
                # Melhor: gerar 5 prompts no total. O primeiro é normal, os 4 seguintes usam cref.
                # O prompt_referencia_obj já é o primeiro. Agora geramos os próximos 4 com cref.
                # Total de 5 prompts por personagem: 1 de referência (texto salvo, imagem não baixada intencionalmente) + 4 com cref (texto salvo, imagem baixada)
                # Ou, se cref_url_escolhida for None, geraremos 5 prompts normais.

                num_prompts_por_personagem = 5
                for j in range(num_prompts_por_personagem):
                    num_prompt_atual = j + 1
                    prompt_img_p = None
                    
                    # O primeiro prompt (j=0) é sempre sem cref para estabelecer a referência.
                    # Os subsequentes (j > 0) usam cref_url_escolhida SE disponível.
                    # No entanto, a lógica acima já cuidou do prompt de referência (num_prompt=1).
                    # Agora vamos gerar os 5 prompts que serão efetivamente usados para criar imagens.
                    # Se cref_url_escolhida existe, todos os 5 usarão. Não, isso não é o pedido.
                    # Pedido: 1º prompt normal (não baixa img), escolhe 1 das 4. Próximos 4 usam --cref com essa URL.

                    # Reformulando:
                    # O prompt_referencia_obj (num_prompt=1) foi feito.
                    # Agora, 5 prompts onde o primeiro usa a descrição original, e os 4 seguintes também, mas todos com --cref (se disponível)
                    # Não, o pedido é: 1 prompt (não baixa). Seus resultados dão a cref_url.
                    # DEPOIS, gerar 5 prompts (que serão baixados) usando essa cref_url.
                    # Se a descrição do personagem (desc_char_pt) for a mesma, os 5 prompts serão muito parecidos.
                    # A ideia do num_prompt no criar_prompt_imagem_personagem talvez fosse para variar algo, mas não está sendo usado para variar a descrição.
                    
                    # Vamos seguir: "Gerar 5 prompts para cada personagem"
                    # O primeiro (j=0) NÃO usa cref_url.
                    # Os 4 seguintes (j=1 a j=4) USAM cref_url, se disponível.

                    if j == 0: # Primeiro prompt dos 5 "finais"
                        # Este é o prompt que realmente será usado para a primeira imagem do personagem.
                        # Se cref_url_escolhida foi obtida ANTES (do prompt de referência separado), ela NÃO deve ser usada aqui.
                        # Mas o usuário quer 5 prompts. O 1º prompt de referência não conta para os 5 finais?
                        # "vai gerar o primeiro prompt do personagem 1, não vai baixar nenhuma imagem desse primeiro prompt, vai escolher de forma aleatória uma imagem ... para gerar os próximos 5 prompts"
                        # Isso significa 1 (referência) + 5 (com cref) = 6 prompts no total por personagem?
                        # Ou 1 (referência) e os *4* seguintes usam cref, totalizando 5 (1 ref + 4 com cref)?
                        # "Gerar 5 prompts para cada personagens" e "próximos 5 prompts desse persobagem com o --cref" é um pouco contraditório.
                        # Vou assumir 1 prompt de referência (não baixado) + 5 prompts com cref (baixados). Total 6.
                        # Se for 1 prompt de referência + 4 com cref, mudo o range para 4.

                        # Opção A: 1 prompt de referência (não baixado) + 5 prompts com cref (baixados).
                        # O loop de j vai de 0 a 4 (5 iterações). Todos usarão cref_url_escolhida.
                        
                        # Opção B: O primeiro dos 5 é normal, os 4 seguintes usam cref.
                        # prompt_atual_usa_cref = (j > 0 and cref_url_escolhida is not None)
                        # prompt_img_p = criar_prompt_imagem_personagem(nome_p, desc_char_pt, nome_base_arquivo_original, num_prompt_atual, cref_url=cref_url_escolhida if prompt_atual_usa_cref else None)
                        
                        # Relendo: "vai gerar o primeiro prompt do personagem 1... vai escolher ... para gerar os próximos 5 prompts desse personagem com o --cref"
                        # Isso soa como 1 prompt inicial (não baixado) + 5 prompts subsequentes (baixados, todos com cref).
                        # O loop de 'j' irá de 0 a 4 para os 5 prompts *com cref*.

                        if not cref_url_escolhida:
                            print(f"  Gerando prompt {num_prompt_atual}/{num_prompts_por_personagem} para {nome_p} (sem --cref, pois referência não foi obtida).")
                            prompt_img_p = criar_prompt_imagem_personagem(nome_p, desc_char_pt, nome_base_arquivo_original, num_prompt_atual, cref_url=None)
                        else:
                            print(f"  Gerando prompt {num_prompt_atual}/{num_prompts_por_personagem} para {nome_p} (com --cref).")
                            prompt_img_p = criar_prompt_imagem_personagem(nome_p, desc_char_pt, nome_base_arquivo_original, num_prompt_atual, cref_url=cref_url_escolhida)
                    
                    else: # j > 0 (prompts 2, 3, 4, 5)
                         # Esta lógica é para Opção B. Vou com a interpretação 1 ref + 5 com cref.
                         # Então a lógica acima para j=0 já cobre tudo dentro do loop de 5.
                         # O if j==0 else não é necessário se todos os 5 usam o mesmo cref (ou nenhum se falhou).
                        pass # Removendo a lógica do if/else j==0, pois o bloco acima já decide o uso do cref.

                    # Lógica simplificada para os 5 prompts que serão baixados:
                    # Todos os 5 usam cref_url_escolhida se ela existir.
                    # Se não existir, nenhum dos 5 usa.
                    
                    prompt_img_p = criar_prompt_imagem_personagem(
                        nome_p, 
                        desc_char_pt, 
                        nome_base_arquivo_original, 
                        num_prompt_atual, # Este é o número do prompt (1 a 5) para este personagem
                        cref_url=cref_url_escolhida # Usa a URL de referência para todos os 5, se disponível
                    )

                    if prompt_img_p:
                        img_filename_base = f"{nome_base_arquivo_original}_personagem_{nome_p.replace(' ','_')}_prompt{num_prompt_atual}"
                        prompt_personagem_filename_txt = f"{img_filename_base}.txt"
                        caminho_prompt_personagem = os.path.join(pasta_prompts_local, prompt_personagem_filename_txt)
                        with open(caminho_prompt_personagem, 'w', encoding='utf-8') as f_prompt:
                            f_prompt.write(prompt_img_p)
                        
                        # Adicionar à lista para download
                        todos_os_prompts_imagem.append({"nome_arquivo": f"{img_filename_base}.png", "prompt": prompt_img_p, "nome_base_arquivo_original": nome_base_arquivo_original, "pasta_imagens_local": pasta_imagens_local})
                        print(f"    Prompt {num_prompt_atual} para {nome_p} adicionado à fila de geração.")
                    else:
                        print(f"  Não foi possível criar o prompt de imagem {num_prompt_atual} para {nome_p} ('{nome_base_arquivo_original}.txt')")
        else:
             print(f"Não foi possível identificar personagens principais para '{nome_base_arquivo_original}.txt'. Geração de imagens de personagens será pulada.")

        if not todos_os_prompts_imagem:
            print(f"\\nNenhum prompt de imagem foi gerado para '{nome_base_arquivo_original}.txt'.")
        else:
            print(f"\\nTotal de {len(todos_os_prompts_imagem)} prompts de imagem a serem gerados para '{nome_base_arquivo_original}.txt'.")
            for k, item_prompt in enumerate(todos_os_prompts_imagem):
                print(f"\\n({k+1}/{len(todos_os_prompts_imagem)}) Processando imagem: {item_prompt['nome_arquivo']}")
                # A chamada a gerar_imagem_goapi agora é feita aqui, garantindo que apenas_obter_urls=False (padrão)
                gerar_imagem_goapi(
                    item_prompt["prompt"], 
                    item_prompt["nome_arquivo"], 
                    item_prompt["nome_base_arquivo_original"], # Passar o nome_base_arquivo_original
                    item_prompt["pasta_imagens_local"]  # Passar a pasta_imagens_local
                )
                if k < len(todos_os_prompts_imagem) - 1:
                    print("Aguardando 5 segundos antes da próxima imagem para não sobrecarregar a API...")
                    time.sleep(5) 
        
        print(f"\\n--- PROCESSAMENTO DO RESUMO '{nome_base_arquivo_original}.txt' CONCLUÍDO ---")
        if idx_resumo < len(arquivos_resumo) - 1:
             print("Aguardando 15 segundos antes de processar o próximo resumo...")
             time.sleep(15)
    # ... Fim do conteúdo movido da main() original ...

    print("\\n--- TODOS OS RESUMOS FORAM PROCESSADOS ---")
    return True # Indica sucesso

if __name__ == "__main__":
    # Mantém a interatividade para execução direta do script via console
    pasta_resumos = input("\\nForneça o caminho para a pasta contendo os arquivos de resumo (.txt): ")
    idiomas_str = input("\\nPara quais idiomas você quer traduzir os roteiros? "
                                    "(Ex: italiano,polones,frances ou deixe em branco para não traduzir): ").lower()
    
    resultado = iniciar_processamento_em_lote(pasta_resumos, idiomas_str)
    
    if resultado:
        print("\\nProcesso concluído com sucesso pelo script direto.")
    else:
        print("\\nProcesso falhou ou foi interrompido (ver logs acima).")
    
    input("Pressione Enter para fechar o console...") # Mantido para execução direta

# A linha input("Pressione Enter para fechar...") que estava no final do arquivo globalmente foi removida.
# Ela agora está apenas dentro do if __name__ == "__main__".