@echo off
REM Navega para o diretório do aplicativo Streamlit
cd /D "C:\Users\Giovany Santos\Desktop\CRIADOR DE HISTÓRIAS"

REM Inicia o aplicativo Streamlit
echo Iniciando o aplicativo Criador de Histórias e Imagens...
streamlit run app.py

REM Mantém o console aberto após o Streamlit ser interrompido (opcional)
REM Se você fechar o navegador e interromper o Streamlit com Ctrl+C no console,
REM esta pausa permitirá que você veja quaisquer mensagens finais antes do console fechar.
REM Se preferir que o console feche automaticamente, pode remover a linha abaixo.
pause 