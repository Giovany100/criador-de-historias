import streamlit as st
import openai
import os

# Configuração da chave da API OpenAI
openai.api_key = os.getenv('OPENAI_API_KEY')

st.title('Criador de Histórias')

# Interface do usuário
tema = st.text_input('Digite o tema da história:')
personagens = st.text_input('Digite os personagens principais:')
genero = st.selectbox('Escolha o gênero:', ['Aventura', 'Fantasia', 'Comédia', 'Drama', 'Terror'])

if st.button('Criar História'):
    if tema and personagens:
        prompt = f"Crie uma história curta de {genero} sobre {tema} com os seguintes personagens: {personagens}. A história deve ser em português e ter no máximo 500 palavras."
        
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Você é um escritor criativo especializado em criar histórias curtas e envolventes."},
                    {"role": "user", "content": prompt}
                ]
            )
            
            historia = response.choices[0].message.content
            st.write(historia)
            
        except Exception as e:
            st.error('Ocorreu um erro ao gerar a história. Por favor, tente novamente.') 