import streamlit as st
import pandas as pd
import altair as alt
import json
from io import StringIO

# ---------------------------------------------------------
# CONFIGURAÇÃO
# ---------------------------------------------------------
st.set_page_config(page_title="Dashboard Serviços (JSON)", layout="wide")
PASSWORD = "ln11Col13@"

# ---------------------------------------------------------
# LOGIN
# ---------------------------------------------------------
def check_password():
    with st.sidebar:
        st.title("🔐 Login")
        pwd = st.text_input("Digite a senha", type="password")
        if pwd == PASSWORD:
            return True
        elif pwd:
            st.error("Senha incorreta!")
    return False

if not check_password():
    st.stop()

st.title("📊 Produtividade UPS — Mensal")
st.write("Última atualização: 18/11/2025 14:59")

# ---------------------------------------------------------
# FUNÇÕES PARA CARREGAR DADOS
# ---------------------------------------------------------
def load_json_from_file(path="dados.json"):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return pd.DataFrame(data)
    except FileNotFoundError:
        return None
    except Exception as e:
        st.error(f"Erro ao ler {path}: {e}")
        return None

def load_json_from_uploader(uploaded_file):
    try:
        s = StringIO(uploaded_file.getvalue().decode("utf-8"))
        data = json.load(s)
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Erro ao ler JSON enviado: {e}")
        return None

# Carregar base local

df = load_json_from_file("dados.json")

# Se não carregar, pedir upload
if df is None:
    st.warning("Arquivo `dados.json` não encontrado. Envie um JSON válido.")
    uploaded = st.file_uploader("Enviar dados.json", type=["json"])
    if uploaded:
        df = load_json_from_uploader(uploaded)
    else:
        st.stop()

# ---------------------------------------------------------
# PRÉ-PROCESSAMENTO
# ---------------------------------------------------------
# Limpar nomes das colunas

df.columns = [c.strip() for c in df.columns]

# Converter números quando possível
for col in df.columns:
    non_null = df[col].dropna().astype(str)
    convertible = non_null.str.replace(r"[^0-9,.-]", "", regex=True)
    if convertible.shape[0] > 0:
        try:
            df[col] = pd.to_numeric(convertible.str.replace(",", "."), errors="ignore")
        except:
            pass

# ---------------------------------------------------------
# SALVAR BASE ORIGINAL PARA VISUALIZAÇÃO
# ---------------------------------------------------------
df_original = df.copy()

# ---------------------------------------------------------
# CARDS SUPERIORES (antes dos filtros)
# ---------------------------------------------------------
def safe_mean(col):
    try:
        return df[col].mean()
    except:
        return None

def safe_sum(col):
    try:
        return df[col].sum()
    except:
        return None

media_total = safe_mean("MÉDIA")
total_turnos = safe_sum("TURNOS")
total_servicos = safe_sum("TOTAL")
media_turnos = df["TURNOS"].mean() if "TURNOS" in df.columns else None

colA, colB, colC, colD = st.columns(4)
colA.metric("📌 Média Geral", f"{media_total:.2f}" if media_total else "—")
colB.metric("👷 Total de Turnos", int(total_turnos) if total_turnos else "—")
colC.metric("🧾 Total de Serviços", int(total_servicos) if total_servicos else "—")
colD.metric("📊 Média de TURNOS", f"{media_turnos:.2f}" if media_turnos else "—")

# ---------------------------------------------------------
# FILTROS — ESTILO POWER BI
# ---------------------------------------------------------
with st.sidebar:
    st.markdown("## 📌 Filtros")

df_filtered = df.copy()

with st.sidebar:
    filter_order = ["PREFIXO", "EQUIPE", "CLASSE", "SUPERVISOR", "MÊS", "TURNOS"]

    for col in filter_order:
        if col not in df.columns:
            continue

        # FILTRO ESPECIAL DE TURNOS
        if col == "TURNOS":
            st.markdown("### Turnos")

            turnos_options = list(range(1, 16))
            existentes = sorted(df_filtered["TURNOS"].dropna().unique())
            avail = [t for t in turnos_options if t in existentes]

            selected = st.multiselect(
                "Quantidade de Turnos", avail, default=avail
            )

            df_filtered = df_filtered[df_filtered["TURNOS"].isin(selected)]
            continue

        # FILTROS NORMAIS
        st.markdown(f"### {col}")
        options = sorted(df_filtered[col].dropna().unique())

        selected = st.selectbox(
            f"Selecionar {col}", ["Todos"] + options, key=f"filter_{col}"
        )

        if selected != "Todos":
            df_filtered = df_filtered[df_filtered[col] == selected]

# O df final passa a ser df_filtered
df = df_filtered

# ---------------------------------------------------------
# GRÁFICO — MÉDIA DAS EQUIPES POR MÊS (ORDENADO)
# ---------------------------------------------------------
if "EQUIPE" in df.columns and "MÊS" in df.columns and "MÉDIA" in df.columns:

    st.subheader("📌 Média das Equipes por Mês (ordenado)")

    # Ordenar por média DESC
    df_sort = df.groupby(["EQUIPE", "MÊS"]).agg({"MÉDIA": "mean"}).reset_index()
    df_sort = df_sort.sort_values("MÉDIA", ascending=False)

    grafico_mensal = (
        alt.Chart(df_sort)
        .mark_bar()
        .encode(
            x=alt.X("EQUIPE:N", sort="-y", title="Equipe"),
            y=alt.Y("MÉDIA:Q", title="Média da Execução"),
            color=alt.Color("MÊS:N", title="Mês"),
            tooltip=["EQUIPE", "MÊS", "MÉDIA"]
        )
        .properties(height=400)
    )

    st.altair_chart(grafico_mensal, use_container_width=True)
else:
    st.info("Faltam colunas para gerar o gráfico de média mensal.")

# ---------------------------------------------------------
# OUTROS GRÁFICOS EXISTENTES (PREFIXO x CLASSE e DONUT)
# ---------------------------------------------------------
if "PREFIXO" in df.columns and "CLASSE" in df.columns:
    st.subheader("Distribuição de CLASSE por PREFIXO")
    grafico1 = (
        alt.Chart(df)
        .mark_bar()
        .encode(
            x=alt.X("PREFIXO:N", title="PREFIXO"),
            y=alt.Y("count():Q", title="Quantidade"),
            color=alt.Color("CLASSE:N", title="Classe")
        )
        .properties(height=350)
    )
    st.altair_chart(grafico1, use_container_width=True)

if "CLASSE" in df.columns:
    st.subheader("Classe total")
    df_classe = df["CLASSE"].value_counts().reset_index()
    df_classe.columns = ["CLASSE", "QTD"]
    donut = (
        alt.Chart(df_classe)
        .mark_arc(innerRadius=70)
        .encode(
            theta="QTD:Q",
            color="CLASSE:N"
        )
        .properties(height=300)
    )
    st.altair_chart(donut, use_container_width=True)

# ---------------------------------------------------------
# PRÉ-VISUALIZAÇÃO DOS DADOS — AGORA NO FINAL
# ---------------------------------------------------------
st.subheader("📄 Pré-visualização dos Dados Filtrados")
st.dataframe(df, use_container_width=True)

st.subheader("📄 Pré-visualização da Base Original (sem filtro)")
st.dataframe(df_original, use_container_width=True)
