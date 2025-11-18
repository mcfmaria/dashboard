import streamlit as st
import pandas as pd
import altair as alt
import json
from io import StringIO

# -------------------------
# Config
# -------------------------
st.set_page_config(page_title="Dashboard Serviços (JSON)", layout="wide")
PASSWORD = "main518179234"   # <-- mantenha ou troque

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

st.title("📊 Dashboard de Serviços (usando dados.json)")

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

col1, col2, col3 = st.columns(3)
col1.metric("📌 Média Geral", f"{media_total:.2f}" if media_total is not None else "—")
col2.metric("👷 Total de Turnos", int(total_turnos) if total_turnos is not None else "—")
col3.metric("🧾 Total de Serviços", int(total_servicos) if total_servicos is not None else "—")

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

# -------------------------
# GRÁFICO 3: Equipes por mês
# -------------------------
if "MÊS" in df.columns and "EQUIPE" in df.columns:
    st.subheader("Equipes por Mês")
    grafico3 = (
        alt.Chart(df)
        .mark_bar()
        .encode(
            x="MÊS:N",
            y="EQUIPE:Q",
            color="MÊS:N"
        )
        .properties(height=320)
    )
    st.altair_chart(grafico3, use_container_width=True)
else:
    st.info("Colunas 'MÊS' e/ou 'EQUIPE' ausentes — gráfico 3 não foi gerado.")

# -------------------------
# Opcional: botão para baixar o JSON atual (se veio do upload)
# -------------------------
st.markdown("---")
st.write("Opções:")
col_a, col_b = st.columns(2)

with col_a:
    if st.button("🔁 Recarregar dados (ler dados.json local)"):
        st.experimental_rerun()

with col_b:
    csv_btn = st.download_button(
        "📥 Baixar CSV",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name="dados_convertidos.csv",
        mime="text/csv"
    )

st.write("Observação: para voltar a usar o MongoDB, corrigiremos a URI depois — por hora você pode atualizar o arquivo `dados.json` na pasta do app e clicar em *Recarregar dados*.")
