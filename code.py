import streamlit as st
import pandas as pd
import altair as alt
import json
from io import StringIO

# -------------------------
# Config
# -------------------------
st.set_page_config(page_title="Dashboard Serviços (JSON)", layout="wide")
PASSWORD = "ln11Col13@"   # <-- mantenha ou troque

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

st.title("📊 Produtividade UPS")
st.write("Útima atualização: 18/11/2025 14:59")


# -------------------------
# Função: carregar JSON local ou via upload
# -------------------------
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
        # uploaded_file é um BytesIO; ler como texto
        s = StringIO(uploaded_file.getvalue().decode("utf-8"))
        data = json.load(s)
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Erro ao ler JSON enviado: {e}")
        return None

# Tenta carregar dados.json local
df = load_json_from_file("dados.json")

# Se não existir, pede upload
if df is None:
    st.warning("Arquivo `dados.json` não encontrado na pasta do app. Faça upload do arquivo JSON ou coloque `dados.json` na mesma pasta do app.")
    uploaded = st.file_uploader("Enviar dados.json", type=["json"])
    if uploaded:
        df = load_json_from_uploader(uploaded)
    else:
        st.stop()

# -------------------------
# Pré-processamento simples
# -------------------------
# tenta converter colunas numéricas automaticamente
for col in df.columns:
    # remove espaços no começo/fim de nomes
    df.rename(columns={col: col.strip()}, inplace=True)

# tentar converter tipos numéricos quando fizer sentido
for col in df.columns:
    # se mais da metade das células forem convertíveis para número, converte
    non_null = df[col].dropna().astype(str)
    convertible = non_null.apply(lambda x: x.replace(",", ".").replace(" ", "")).str.replace(r'[^\d\.\-]', '', regex=True)
    num_count = convertible.replace('', pd.NA).dropna().shape[0]
    if num_count >= max(1, int(0.5 * max(1, non_null.shape[0]))):
        # tenta conversão segura
        try:
            df[col] = pd.to_numeric(non_null.apply(lambda x: x.replace(",", ".") if isinstance(x, str) else x), errors="coerce")
            # reindex to original length (manter NaNs onde necessário)
            df[col] = df[col].reindex(df.index)
        except Exception:
            pass

# Se colunas com acentos específicos não existirem, avisar
required_cols = ["MÉDIA", "TURNOS", "TOTAL", "PREFIXO", "CLASSE", "MÊS", "EQUIPE"]
missing = [c for c in required_cols if c not in df.columns]
if missing:
    st.warning(f"As colunas esperadas não foram todas encontradas no JSON: {missing}\nVerifique os nomes (maiúsculas/acento/espacos). Você pode continuar, mas alguns cards/plots podem falhar.")

# Mostrar preview
st.subheader("Pré-visualização dos dados")
st.dataframe(df, use_container_width=True)

# -------------------------
# MÉDIA GERAL DE TURNOS
# -------------------------
if "TURNOS" in df.columns:
    media_turnos = df["TURNOS"].mean()
else:
    media_turnos = None

# -------------------------
# CARDS (tenta proteger contra colunas faltando)
# -------------------------
def safe_mean(col):
    try:
        return df[col].mean()
    except Exception:
        return None

def safe_sum(col):
    try:
        return df[col].sum()
    except Exception:
        return None

media_total = safe_mean("MÉDIA")
total_turnos = safe_sum("TURNOS")
total_servicos = safe_sum("TOTAL")

col1, col2, col3, col4 = st.columns(4)
col1.metric("📌 Média Geral", f"{media_total:.2f}" if media_total else "—")
col2.metric("👷 Total de Turnos", int(total_turnos) if total_turnos else "—")
col3.metric("🧾 Total de Serviços", int(total_servicos) if total_servicos else "—")
col4.metric("📊 Média de TURNOS", f"{media_turnos:.2f}" if media_turnos else "—")

# --------------------------------------------
# FILTROS INTERDEPENDENTES (ESTILO POWER BI)
# --------------------------------------------
with st.sidebar:
    st.markdown("## 📌 Filtros")

df_filtered = df.copy()

with st.sidebar:

    # Ordem desejada dos filtros
    filter_order = ["PREFIXO", "EQUIPE", "CLASSE", "SUPERVISOR", "MÊS", "TURNOS"]

    for col in filter_order:

        if col not in df.columns:
            continue

        # ---------- FILTRO ESPECIAL DE TURNOS ----------
        if col == "TURNOS":
            st.markdown("### Turnos")

            turnos_options = list(range(1, 15+1))  # 1–15
            turnos_validos = sorted(df_filtered["TURNOS"].dropna().unique())

            # Interseção entre 1..15 e valores existentes
            avail = [t for t in turnos_options if t in turnos_validos]

            selected_turnos = st.multiselect(
                "Quantidade de Turnos",
                avail,
                default=avail
            )

            df_filtered = df_filtered[df_filtered["TURNOS"].isin(selected_turnos)]
            continue

        # ---------- FILTRO NORMAL (TEXTOS) ----------
        st.markdown(f"### {col}")

        # AQUI ESTÁ O SEGREDO! → opções vêm do df_filtered
        options = sorted(df_filtered[col].dropna().unique())

        selected = st.selectbox(
            f"Selecionar {col}",
            ["Todos"] + options,
            key=f"select_{col}"
        )

        if selected != "Todos":
            df_filtered = df_filtered[df_filtered[col] == selected]

# Agora df_filtered contém TUDO filtrado
df = df_filtered



# -------------------------
# GRÁFICO 1: CLASSE por PREFIXO (barras empilhadas)
# -------------------------
if "PREFIXO" in df.columns and "CLASSE" in df.columns:
    st.subheader("Distribuição de CLASSE por PREFIXO")
    grafico1 = (
        alt.Chart(df)
        .mark_bar()
        .encode(
            x=alt.X("PREFIXO:N", title="PREFIXO"),
            y=alt.Y("count():Q", title="Quantidade"),
            color=alt.Color("CLASSE:N", title="CLASSE")
        )
        .properties(height=350)
    )
    st.altair_chart(grafico1, use_container_width=True)
else:
    st.info("Colunas 'PREFIXO' e/ou 'CLASSE' ausentes — gráfico 1 não foi gerado.")

# -------------------------
# GRÁFICO 2: Donut da CLASSE total
# -------------------------
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
else:
    st.info("Coluna 'CLASSE' ausente — donut não foi gerado.")







