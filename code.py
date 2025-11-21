import streamlit as st
import pandas as pd
import altair as alt
import json
from io import StringIO

# -------------------------
# Config
# -------------------------
st.set_page_config(page_title="Dashboard Serviços (JSON)", layout="wide")
loj = "ln11Col13@"   # <-- mantenha ou troque

def check_password():
    with st.sidebar:
        st.title("🔐 Login")
        pwd = st.text_input("Digite a senha", type="password")
        if pwd == loj:
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
# remove espaços nos nomes das colunas
df.columns = [c.strip() for c in df.columns]

# normaliza colunas categóricas que você usa nos filtros
categorical_cols = ["PREFIXO", "EQUIPE", "CLASSE", "SUPERVISOR", "MÊS"]
for c in categorical_cols:
    if c in df.columns:
        # converte para string, remove 'nan' literal, tira espaços
        df[c] = df[c].astype(str).fillna("").replace("nan", "").apply(lambda x: x.strip())

# tenta converter TURNOS para int quando fizer sentido
if "TURNOS" in df.columns:
    try:
        # remove decimais desnecessários e converte para inteiro quando possível
        df["TURNOS"] = pd.to_numeric(df["TURNOS"], errors="coerce")
        # dropna temporariamente para checar se todos são inteiros
        non_null = df["TURNOS"].dropna()
        if not non_null.empty:
            # se todos são próximos a inteiros, convert para int
            if (non_null.round() == non_null).all():
                df["TURNOS"] = df["TURNOS"].round().astype("Int64")
    except Exception:
        pass

# tenta converter outras colunas numéricas automaticamente (se quiser manter)
for col in df.columns:
    if col not in categorical_cols + ["TURNOS"]:
        non_null = df[col].dropna().astype(str)
        convertible = non_null.apply(lambda x: x.replace(",", ".").replace(" ", "")).str.replace(r'[^\d\.\-]', '', regex=True)
        num_count = convertible.replace('', pd.NA).dropna().shape[0]
        if num_count >= max(1, int(0.5 * max(1, non_null.shape[0]))):
            try:
                df[col] = pd.to_numeric(non_null.apply(lambda x: x.replace(",", ".") if isinstance(x, str) else x), errors="coerce")
                df[col] = df[col].reindex(df.index)
            except Exception:
                pass

# Se colunas com acentos específicos não existirem, avisar (mas continua)
required_cols = ["MÉDIA", "TURNOS", "TOTAL", "PREFIXO", "CLASSE", "MÊS", "EQUIPE"]
missing = [c for c in required_cols if c not in df.columns]
if missing:
    st.warning(f"As colunas esperadas não foram todas encontradas no JSON: {missing}\nVerifique os nomes (maiúsculas/acento/espacos). Você pode continuar, mas alguns cards/plots podem falhar.")

# Mostrar preview (opcional)
st.subheader("Pré-visualização dos dados")
st.dataframe(df, use_container_width=True)

# -------------------------
# MÉDIA GERAL DE TURNOS
# -------------------------
if "TURNOS" in df.columns:
    media_turnos = df["TURNOS"].dropna().astype(float).mean()
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
# FILTROS INTERDEPENDENTES (SIDEBAR, ESTILO POWER BI)
# --------------------------------------------
with st.sidebar:
    st.markdown("## 📌 Filtros")

# Começa com df completo e aplica filtros em sequência
df_filtered = df.copy()

with st.sidebar:
    # ordem de filtros - ajuste conforme preferir
    filter_order = ["PREFIXO", "EQUIPE", "CLASSE", "SUPERVISOR", "MÊS", "TURNOS"]

    for col in filter_order:
        if col not in df.columns:
            continue

        # Texto / categóricos (SELECTBOX)
        if col != "TURNOS":
            st.markdown(f"### {col}")

            # opções VEM do df_filtered (para interdependência)
            opts = df_filtered[col].dropna().unique().tolist()
            # garantir que são strings limpas e ordenadas
            opts = sorted([str(x).strip() for x in opts if str(x).strip() != ""])

            if len(opts) == 0:
                opts = ["Todos"]
            else:
                opts = ["Todos"] + opts

            selected = st.selectbox(f"Selecionar {col}", opts, key=f"filter_{col}")

            # aplica
            if selected != "Todos":
                # filtra comparando string trimmed (evita espaços)
                df_filtered = df_filtered[df_filtered[col].astype(str).str.strip() == str(selected).strip()]

        # TURNOS (multiselect com 1..15, mas mostrando só disponíveis)
        else:
            st.markdown("### TURNOS")
            # opções possíveis entre 1 e 15
            turnos_full = list(range(1, 16))
            # quais turnos existem no df_filtered atualmente?
            valid_turnos = sorted([int(x) for x in df_filtered["TURNOS"].dropna().unique() if str(x).strip() != ""])
            # intersecta com 1..15 (mantém ordem)
            avail = [t for t in turnos_full if t in valid_turnos]
            if not avail:
                # se não houver, tenta mostrar todos 1..15 pra evitar erro
                avail = turnos_full

            selected_turnos = st.multiselect("Quantidade de Turnos", avail, default=avail, key="filter_TURNOS")

            if selected_turnos:
                df_filtered = df_filtered[df_filtered["TURNOS"].isin(selected_turnos)]
            else:
                # se nada selecionado, não filtra (mantém tudo)
                pass

# substitui df pelo filtrado para o restante do dashboard
df = df_filtered

# -------------------------
# GRÁFICO 1: CLASSE por PREFIXO (barras empilhadas)
# -------------------------
if "PREFIXO" in df.columns and "CLASSE" in df.columns and not df.empty:
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
    st.info("Colunas 'PREFIXO' e/ou 'CLASSE' ausentes ou sem dados — gráfico 1 não foi gerado.")

# -------------------------
# GRÁFICO 2: Donut da CLASSE total
# -------------------------
if "CLASSE" in df.columns and not df.empty:
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

# -------------------------
# GRÁFICO 2: Média Mensal
# -------------------------

if "EQUIPE" in df.columns and "MÊS" in df.columns and not df.empty:
    st.subheader("Média das equipes por mês")
    
    grafico1 = (
        alt.Chart(df)
        .mark_bar()
        .encode(
            x=alt.X("EQUIPE:N", title="Equipe"),
            y=alt.Y("mean(MÉDIA):Q", title="Média"),
            color=alt.Color("MÊS:N", title="Mês"),
            tooltip=["EQUIPE", "MÊS", "mean(MÉDIA)"]
            st.write["mean(MÉDIA)"]
        )
        .properties(height=350)
    )

    st.altair_chart(grafico1, use_container_width=True)

else:
    st.info("Colunas 'EQUIPE' e/ou 'MÊS' ausentes ou sem dados — gráfico não gerado.")
