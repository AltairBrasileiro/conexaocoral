"""Aplicação web do Consulado CoralJampa.

Este módulo centraliza a interface pública do projeto, com:
- configuração da página;
- área de apresentação do consulado;
- seção de próximos encontros;
- formulário de cadastro com validação básica.

A estrutura foi organizada em funções para facilitar a leitura,
manutenção e evolução futura do código.
"""

import calendar
import base64
import os
import re
from datetime import date
from pathlib import Path

import pandas as pd
import folium
import requests
import streamlit as st
from streamlit_folium import st_folium


CONSULADOS = pd.DataFrame(
    [
        {
            "nome": "Consulado CoralJampa",
            "cidade": "Joao Pessoa",
            "estado": "PB",
            "latitude": -7.1195,
            "longitude": -34.8450,
        }
    ]
)


def calcular_idade(data_nascimento: date) -> int:
    """Calcula a idade em anos a partir da data de nascimento."""
    hoje = date.today()
    idade = hoje.year - data_nascimento.year
    if (hoje.month, hoje.day) < (data_nascimento.month, data_nascimento.day):
        idade -= 1
    return idade


def formatar_data_brasileira(data: date) -> str:
    """Converte uma data para o formato brasileiro DD/MM/AAAA."""
    return data.strftime("%d/%m/%Y")


def formatar_whatsapp(valor: str) -> str:
    """Formata o telefone em um padrão legível, mantendo os números apenas."""
    numeros = re.sub(r"\D", "", valor)

    if len(numeros) == 11:
        return f"({numeros[:2]}) {numeros[2]} {numeros[3:7]}-{numeros[7:]}"
    if len(numeros) == 10:
        return f"({numeros[:2]}) {numeros[2:6]}-{numeros[6:]}"
    return valor.strip()


def validar_whatsapp(valor: str) -> bool:
    """Valida se um número de WhatsApp tem quantidade mínima aceitável."""
    numeros = re.sub(r"\D", "", valor)
    return len(numeros) in {10, 11}


@st.cache_data(ttl=15, show_spinner=False)
def carregar_consulados() -> pd.DataFrame:
    """Busca consulados na API compartilhada e usa fallback local se necessário."""
    api_url = os.getenv("CONEXAO_CORAL_API_URL", "http://localhost:8000").rstrip("/")
    try:
        response = requests.get(f"{api_url}/consulados", timeout=2)
        response.raise_for_status()
        consulados = pd.DataFrame(response.json())
        if not consulados.empty:
            return consulados
    except requests.RequestException:
        pass
    return CONSULADOS.copy()


def filtrar_consulados() -> pd.DataFrame:
    """Filtra os consulados cadastrados por cidade ou estado."""
    consulados = carregar_consulados()
    busca = st.text_input(
        "Buscar consulado",
        placeholder="Digite uma cidade ou UF, por exemplo: Joao Pessoa ou PB",
        key="busca_consulado",
    ).strip().lower()

    if not busca:
        return consulados

    mascara = (
        consulados["cidade"].str.lower().str.contains(busca, regex=False)
        | consulados["estado"].str.lower().str.contains(busca, regex=False)
        | consulados["nome"].str.lower().str.contains(busca, regex=False)
    )
    return consulados[mascara]


def carregar_icone_pin() -> str | None:
    """Converte logocj.png em data URI para uso seguro no marcador do mapa."""
    logo_path = Path(__file__).parent / "assets" / "logocj.png"
    if not logo_path.exists():
        return None

    imagem_base64 = base64.b64encode(logo_path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{imagem_base64}"


def criar_marcador_consulado(consulado: pd.Series, mapa: folium.Map) -> None:
    """Adiciona um pin com logocj.png ou fallback em formato de escudo."""
    icone_pin = carregar_icone_pin()
    if icone_pin:
        icone = folium.CustomIcon(icone_pin, icon_size=(48, 48), icon_anchor=(24, 48))
    else:
        icone = folium.DivIcon(
            html="""
            <div style="
                width: 42px;
                height: 50px;
                background: linear-gradient(145deg, #d71920 0 48%, #111 48% 100%);
                border: 3px solid #fff;
                border-radius: 8px 8px 20px 20px;
                color: #fff;
                display: flex;
                align-items: center;
                justify-content: center;
                font: 700 11px Arial, sans-serif;
                box-shadow: 0 3px 8px rgba(0,0,0,.45);
                transform: rotate(45deg);
            "><span style="transform: rotate(-45deg);">SCFC</span></div>
            """,
            icon_size=(52, 52),
            icon_anchor=(26, 45),
        )

    folium.Marker(
        location=[consulado["latitude"], consulado["longitude"]],
        tooltip=consulado["nome"],
        popup=folium.Popup(
            f"<strong>{consulado['nome']}</strong><br>"
            f"{consulado['cidade']} - {consulado['estado']}",
            max_width=260,
        ),
        icon=icone,
    ).add_to(mapa)


def obter_data_nascimento() -> date:
    """Retorna uma data de nascimento selecionada por dia, mês e ano."""
    ano_atual = date.today().year
    anos = list(range(ano_atual, 0, -1))

    col_dia, col_mes, col_ano = st.columns(3)

    with col_dia:
        dia_default = 1
        dia = st.selectbox("Dia", list(range(1, 32)), index=dia_default - 1)

    with col_mes:
        mes = st.selectbox("Mês", list(range(1, 13)), index=0)

    with col_ano:
        ano = st.selectbox("Ano", anos, index=0, help="Selecione o ano de nascimento.")

    ultimo_dia = calendar.monthrange(ano, mes)[1]
    dia = min(dia, ultimo_dia)
    return date(ano, mes, dia)


def configure_page() -> None:
    """Define a aparência e os metadados da página do app."""
    st.set_page_config(
        page_title="Conexao Coral",
        page_icon="⚽",
        layout="wide",
        initial_sidebar_state="collapsed",
    )


def apply_custom_css() -> None:
    """Aplica estilos visuais personalizados ao app."""
    st.markdown(
        """
        <style>
        .stApp {
            background: linear-gradient(180deg, #0d0d0d 0%, #111111 100%);
            color: #f5f5f5;
            margin: 0;
            padding: 0;
        }
        .block-container {
            padding-top: 0 !important;
            padding-left: 1rem !important;
            padding-right: 1rem !important;
            margin-top: 0 !important;
        }
        .main-title {
            color: #ff4d4d;
            text-align: center;
            font-weight: bold;
            font-size: 3rem;
            margin-bottom: 10px;
        }
        .stButton > button:hover {
            background: linear-gradient(135deg, #f44336 0%, #c62828 100%);
            transform: translateY(-1px);
            box-shadow: 0 14px 28px rgba(229, 57, 53, 0.38);
        }
        .stButton > button:focus,
        .stButton > button:focus-visible {
            outline: none;
            box-shadow: none;
        }
        div[data-testid="stForm"] {
            background: rgba(18, 18, 18, 0.9);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 22px;
            padding: 1.5rem 1.25rem;
            box-shadow: 0 16px 36px rgba(0, 0, 0, 0.28);
            max-width: 980px;
            margin: 0 auto;
        }
        .stTextInput > div > div > input,
        .stDateInput > div > div > input {
            border-radius: 12px;
            height: 3.25rem;
            background-color: #171717;
            color: white;
            border: 1px solid rgba(255,255,255,0.12);
            padding: 0.7rem 0.9rem;
            font-size: 1rem;
        }
        .stTextInput label, .stDateInput label {
            font-weight: 600;
            margin-bottom: 0.45rem;
            color: #f5f5f5;
        }
        .stForm > div > div {
            gap: 0.9rem;
        }
        [data-testid="stFormSubmitButton"] {
            display: flex;
            justify-content: center;
            margin-top: 0.5rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header() -> None:
    """Exibe o banner superior e o cabeçalho principal com imagem do logotipo."""
    banner_path = Path(__file__).parent / "assets" / "logocj2.png"

    if banner_path.exists():
        st.markdown('<div class="banner-wrapper">', unsafe_allow_html=True)
        st.image(banner_path, width="stretch")
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown(
        '<h1 class="main-title">Conexao Coral</h1>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p class="subtitle">Encontre o consulado coral mais perto de você</p>',
        unsafe_allow_html=True,
    )
    st.divider()


def render_consulate_map() -> None:
    """Exibe o mapa do Brasil com os consulados registrados na plataforma."""
    st.subheader("Encontre um consulado Coral próximo de você")
    consulados = filtrar_consulados()

    if consulados.empty:
        st.info("Nenhum consulado encontrado para essa busca.")
        return

    mapa = folium.Map(
        location=[-14.2350, -51.9253],
        zoom_start=3,
        tiles="OpenStreetMap",
        control_scale=True,
    )
    for _, consulado in consulados.iterrows():
        criar_marcador_consulado(consulado, mapa)
    st_folium(mapa, width="100%", height=520, returned_objects=[])
    st.dataframe(
        consulados[["nome", "cidade", "estado"]].rename(
            columns={"nome": "Consulado", "cidade": "Cidade", "estado": "UF"}
        ),
        hide_index=True,
        width="stretch",
    )


def render_about_and_events() -> None:
    """Mostra a descrição do consulado e os próximos encontros."""
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Sobre a Conexao Coral")
        st.write(
            "A Conexão Coral aproxima você dos consulados do Santa Cruz Futebol Clube espalhados pelo Brasil. "
            "Onde quer que haja um tricolor, nos unimos para acompanhar o Santa Cruz, organizar viagens e viver o amor pelo clube."
        )

    with col2:
        st.subheader("Proximos encontros")
        st.info("Fique atento às nossas redes sociais para saber o local do próximo jogo!")

    st.divider()


def render_registration_form() -> None:
    """Renderiza o formulário de cadastro com validação básica."""
    st.subheader("📩 Junte-se ao Consulado")

    with st.form(key="cadastro_form"):
        nome = st.text_input("Nome Completo", placeholder="Digite seu nome completo")
        whatsapp = st.text_input(
            "WhatsApp com DDD",
            placeholder="(83) 99999-9999",
            max_chars=15,
        )

        st.markdown("<label style='display:block; margin-bottom:0.5rem; font-weight:600;'>Data de Nascimento</label>", unsafe_allow_html=True)
        data_nascimento = obter_data_nascimento()

        bairro = st.text_input("Bairro onde mora em João Pessoa", placeholder="Ex.: Manaíra")

        submit_button = st.form_submit_button(label="Enviar Cadastro")

        if submit_button:
            if not nome.strip():
                st.warning("Por favor, informe o nome completo.")
                return

            if not validar_whatsapp(whatsapp):
                st.warning("Por favor, informe um WhatsApp válido com DDD e número.")
                return

            if calcular_idade(data_nascimento) < 18:
                st.warning("Cadastro permitido apenas para maiores de 18 anos.")
                return

            whatsapp_formatado = formatar_whatsapp(whatsapp)

            st.success(
                f"Obrigado, {nome.strip()}! Seu cadastro foi recebido com sucesso."
            )
            st.caption(f"WhatsApp: {whatsapp_formatado}")
            st.caption(
                f"Data de nascimento informada: {formatar_data_brasileira(data_nascimento)}"
            )

            if bairro.strip():
                st.caption(f"Bairro informado: {bairro.strip()}")


def render_footer() -> None:
    """Exibe o rodapé final da página."""
    st.markdown("---")
    st.caption("© Conexao Coral - Todos os direitos reservados.")


def main() -> None:
    """Ponto de entrada principal da aplicação."""
    configure_page()
    apply_custom_css()
    render_header()
    render_consulate_map()
    render_about_and_events()
    render_registration_form()
    render_footer()


if __name__ == "__main__":
    main()