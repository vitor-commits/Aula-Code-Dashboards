import os
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import date
from io import BytesIO

# --------------------- Configuração básica ---------------------
st.set_page_config(page_title="Dashboard de RH", layout="wide", page_icon="📈")
st.title("Dashboard de RH 📈")
st.markdown("<style>div.block-container{padding-top:1rem;}</style>", unsafe_allow_html=True)
st.markdown("<style>h1 {text-align: center;}</style>", unsafe_allow_html=True)

# Mapeamento de nomes de colunas para padronização
COL_MAP = {
    "Data de Nascimento": "data_nascimento",
    "Data de Contratacao": "data_contratacao",
    "Data de Demissao": "data_demissao",
    "Salario Base": "salario_base",
    "Custo Total Mensal": "custo_total_mensal",
    "Impostos": "impostos",
    "Beneficios": "beneficios",
    "VT": "vt",
    "VR": "vr",
    "Nome Completo": "nome_completo",
    "Área": "area",
    "Nível": "nivel",
    "Cargo": "cargo",
    "Sexo": "sexo",
    "Idade": "idade",
    "Status": "status",
    "Avaliação do Funcionário": "avaliacao_funcionario",
    "Tempo de Casa (meses)": "tempo_de_casa_meses"
}

DATE_COLS = ["data_nascimento", "data_contratacao", "data_demissao"]

# Se o arquivo estiver na mesma pasta do app.py, pode deixar assim.
# Ajuste para o caminho local caso esteja em outra pasta (ex.: r"C:\...\BaseFuncionarios.xlsx")
DEFAULT_EXCEL_PATH = "BaseFuncionarios.xlsx"

# --------------------- Funções utilitárias ---------------------
def brl(x: float) -> str:
    """Formata um float para o padrão de moeda R$ (BRL)."""
    if pd.isna(x) or not isinstance(x, (int, float)):
        return "R$ 0,00"
    try:
        return f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return "R$ 0,00"

def prepare_df(df: pd.DataFrame) -> pd.DataFrame:
    """Prepara e limpa o DataFrame, padronizando dados e criando colunas derivadas."""
    # Renomeia colunas para padronização
    df.columns = [COL_MAP.get(c, c.lower().replace(' ', '_').replace('-', '_')) for c in df.columns]

    # Padroniza textos
    for c in df.select_dtypes(include="object").columns:
        df[c] = df[c].astype(str).str.strip().fillna('')

    # Datas
    for c in DATE_COLS:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], dayfirst=True, errors="coerce")

    # Padroniza Sexo
    if "sexo" in df.columns:
        df["sexo"] = (
            df["sexo"].str.upper()
            .replace({"MASCULINO": "M", "FEMININO": "F"})
            .replace({'M':'♂️ Masculino', 'F': '♀️ Feminino'})
            .fillna('')
        )

    # Garante numéricos e preenche com a mediana para maior precisão
    numeric_cols = ["salario_base", "impostos", "beneficios", "vt", "vr", "avaliacao_funcionario"]
    for col in numeric_cols:
        if col not in df.columns:
            df[col] = 0.0
        # Tenta converter para numérico e, se houver erro, preenche com a mediana
        df[col] = pd.to_numeric(df[col], errors="coerce")
        df[col] = df[col].fillna(df[col].median() if df[col].median() is not np.nan else 0.0)

    # Colunas derivadas
    today = pd.Timestamp(date.today())

    if "data_nascimento" in df.columns:
        df["idade"] = ((today - df["data_nascimento"]).dt.days // 365).clip(lower=0)

    if "data_contratacao" in df.columns:
        meses = (today.year - df["data_contratacao"].dt.year) * 12 + \
                (today.month - df["data_contratacao"].dt.month)
        df["tempo_de_casa_meses"] = meses.clip(lower=0)

    if "data_demissao" in df.columns:
        df["status"] = np.where(df["data_demissao"].notna(), "Desligado", "Ativo")
    else:
        df["status"] = "Ativo"
    
    df["custo_total_mensal"] = df[["salario_base", "impostos", "beneficios", "vt", "vr"]].sum(axis=1)
    return df

@st.cache_data
def load_from_path(path: str) -> pd.DataFrame:
    """Carrega dados de um arquivo Excel de um caminho local."""
    df = pd.read_excel(path, sheet_name=0, engine="openpyxl")
    return prepare_df(df)

@st.cache_data
def load_from_bytes(uploaded_bytes, file_type: str) -> pd.DataFrame:
    """Carrega dados de um arquivo enviado via upload, suportando .xlsx e .csv."""
    if file_type == 'csv':
        df = pd.read_csv(uploaded_bytes)
    else:
        df = pd.read_excel(uploaded_bytes, sheet_name=0, engine="openpyxl")
    return prepare_df(df)

# --------------------- Sidebar: fonte de dados e navegação ---------------------
with st.sidebar:
    st.header("Fonte de Dados 📥")
    up = st.file_uploader("Carregar Arquivo (.xlsx/.csv)", type=["xlsx", "csv"])
    caminho_manual = st.text_input("Ou caminho do arquivo local", value=DEFAULT_EXCEL_PATH)
    st.divider()

    page = st.radio("Selecione a página", ["Visão Geral", "Análise de Salário e Desempenho", "Análise de Retenção"])
    st.divider()
    
    # --------------------- Carregamento com erros visíveis ---------------------
    df = None
    fonte = None
    if up is not None:
        try:
            file_type = 'csv' if up.name.endswith('.csv') else 'xlsx'
            df = load_from_bytes(up, file_type)
            fonte = "Upload"
        except Exception as e:
            st.error(f"Erro ao ler o arquivo (Upload): {e}")
            st.info("Verifique se o arquivo está no formato correto e se as colunas estão presentes.")
            st.stop()
    else:
        try:
            if not os.path.exists(caminho_manual):
                st.error(f"Arquivo não encontrado em: {caminho_manual}")
                st.info("Dica: coloque o arquivo na mesma pasta do app.py ou ajuste o caminho acima.")
                st.stop()
            df = load_from_path(caminho_manual)
            fonte = "Caminho"
        except Exception as e:
            st.error(f"Erro ao ler o arquivo (Caminho): {e}")
            st.info("Verifique se o arquivo está no formato correto e se as colunas estão presentes.")
            st.stop()

    st.caption(f"Dados carregados via **{fonte}**. Linhas: {len(df)} | Colunas: {len(df.columns)}")

    with st.expander("Ver colunas detectadas e dados brutos"):
        st.write(list(df.columns))
        st.dataframe(df.head())

    # --------------------- Filtros ---------------------
    st.header("Filtros 🔎")
    def msel(col_name: str, display_name: str):
        if col_name in df.columns:
            vals = sorted([v for v in df[col_name].dropna().unique() if v])
            return st.multiselect(display_name, vals)
        return []

    area_sel = msel("area", "Área")
    nivel_sel = msel("nivel", "Nível")
    cargo_sel = msel("cargo", "Cargo")
    sexo_sel = msel("sexo", "Sexo")
    status_sel = msel("status", "Status")
    nome_busca = st.text_input("Buscar por Nome Completo")

    def date_bounds(series: pd.Series):
        s = series.dropna()
        if s.empty: return None
        return (s.min().date(), s.max().date())

    contr_bounds = date_bounds(df["data_contratacao"]) if "data_contratacao" in df.columns else None
    demis_bounds = date_bounds(df["data_demissao"]) if "data_demissao" in df.columns else None

    if contr_bounds:
        d1, d2 = st.date_input("Período de Contratação", value=contr_bounds)
    else:
        d1, d2 = None, None
    if demis_bounds:
        d3, d4 = st.date_input("Período de Demissão", value=demis_bounds)
    else:
        d3, d4 = None, None

    if "idade" in df.columns and not df["idade"].dropna().empty:
        ida_min, ida_max = int(df["idade"].min()), int(df["idade"].max())
        faixa_idade = st.slider("Faixa Etária", ida_min, ida_max, (ida_min, ida_max))
    else: faixa_idade = None

    if "salario_base" in df.columns and not df["salario_base"].dropna().empty:
        sal_min, sal_max = float(df["salario_base"].min()), float(df["salario_base"].max())
        faixa_sal = st.slider("Faixa de Salário Base", float(sal_min), float(sal_max), (float(sal_min), float(sal_max)))
    else: faixa_sal = None

# Aplica filtros
df_f = df.copy()

def apply_in(df_, col, values):
    if values and col in df_.columns: return df_[df_[col].isin(values)]
    return df_

df_f = apply_in(df_f, "area", area_sel)
df_f = apply_in(df_f, "nivel", nivel_sel)
df_f = apply_in(df_f, "cargo", cargo_sel)
df_f = apply_in(df_f, "sexo", sexo_sel)
df_f = apply_in(df_f, "status", status_sel)

if nome_busca and "nome_completo" in df_f.columns:
    df_f = df_f[df_f["nome_completo"].str.contains(nome_busca, case=False, na=False)]
if faixa_idade and "idade" in df_f.columns:
    df_f = df_f[(df_f["idade"] >= faixa_idade[0]) & (df_f["idade"] <= faixa_idade[1])]
if faixa_sal and "salario_base" in df_f.columns:
    df_f = df_f[(df_f["salario_base"] >= faixa_sal[0]) & (df_f["salario_base"] <= faixa_sal[1])]
if d1 and d2 and "data_contratacao" in df_f.columns:
    df_f = df_f[(df_f["data_contratacao"].isna()) | ((df_f["data_contratacao"] >= pd.to_datetime(d1)) & (df_f["data_contratacao"] <= pd.to_datetime(d2)))]
if d3 and d4 and "data_demissao" in df_f.columns:
    df_f = df_f[(df_f["data_demissao"].isna()) | ((df_f["data_demissao"] >= pd.to_datetime(d3)) & (df_f["data_demissao"] <= pd.to_datetime(d4)))]

# --------------------- KPIs ---------------------
def k_headcount_ativo(d): return int((d["status"] == "Ativo").sum()) if "status" in d.columns else 0
def k_desligados(d): return int((d["status"] == "Desligado").sum()) if "status" in d.columns else 0
def k_folha(d): return float(d.loc[d["status"] == "Ativo", "salario_base"].sum()) if ("status" in d.columns and "salario_base" in d.columns) else 0.0
def k_custo_total(d): return float(d.loc[d["status"] == "Ativo", "custo_total_mensal"].sum()) if ("status" in d.columns and "custo_total_mensal" in d.columns) else 0.0
def k_idade_media(d): return float(d["idade"].mean()) if "idade" in d.columns and len(d) > 0 else 0.0
def k_tempo_casa_medio(d):
    col = "tempo_de_casa_meses"
    return float(d[col].mean()) if col in d.columns and len(d) > 0 else 0.0
def k_avaliacao_media(d):
    col = "avaliacao_funcionario"
    return float(d[col].mean()) if col in d.columns and len(d) > 0 else 0.0
def k_turnover(d):
    total_desligados = k_desligados(d)
    total_colaboradores = k_headcount_ativo(d) + total_desligados
    if total_colaboradores == 0: return 0.0
    return (total_desligados / total_colaboradores) * 100

# Função para download de gráfico
def download_chart(fig, filename):
    st.download_button(
        label=f"Baixar Gráfico",
        data=fig.to_image(format="png"),
        file_name=f"{filename}.png",
        mime="image/png"
    )
    
# --------------------- Layout por página ---------------------

if page == "Visão Geral":
    st.subheader("📊 Métricas Chave")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("👥 Ativos", k_headcount_ativo(df_f))
    col2.metric("❌ Desligados", k_desligados(df_f))
    col3.metric("💲 Folha Salarial", brl(k_folha(df_f)))
    col4.metric("💰 Custo Total", brl(k_custo_total(df_f)))
    col5, col6, col7, col8 = st.columns(4)
    col5.metric("🧠 Idade Média", f"{k_idade_media(df_f):.1f} anos")
    col6.metric("🏠 Tempo de Casa Médio", f"{k_tempo_casa_medio(df_f):.1f} meses")
    col7.metric("⭐ Avaliação Média", f"{k_avaliacao_media(df_f):.2f}")
    col8.metric("🔄 Taxa de Turnover", f"{k_turnover(df_f):.2f}%")

    st.divider()

    st.subheader("📈 Gráficos de Análise")
    colA, colB = st.columns(2)
    with colA:
        if "area" in df_f.columns:
            d = df_f.groupby("area").size().reset_index(name="Headcount")
            if not d.empty:
                fig = px.bar(d, x="area", y="Headcount", title="Headcount por Área")
                st.plotly_chart(fig, use_container_width=True)
                download_chart(fig, "headcount_por_area")
    with colB:
        if "salario_base" in df_f.columns and not df_f["salario_base"].dropna().empty:
            fig = px.histogram(df_f, x="salario_base", nbins=20, title="Distribuição de Salários Base")
            st.plotly_chart(fig, use_container_width=True)
            download_chart(fig, "distribuicao_salarios")

    colC, colD = st.columns(2)
    with colC:
        if "idade" in df_f.columns and not df_f["idade"].dropna().empty:
            fig = px.histogram(df_f, x="idade", nbins=20, title="Distribuição de Idade")
            st.plotly_chart(fig, use_container_width=True)
            download_chart(fig, "distribuicao_de_idade")
    with colD:
        if "sexo" in df_f.columns:
            d = df_f["sexo"].value_counts().reset_index()
            d.columns = ["Sexo", "Contagem"]
            if not d.empty:
                fig = px.pie(d, values="Contagem", names="Sexo", title="Distribuição por Sexo")
                st.plotly_chart(fig, use_container_width=True)
                download_chart(fig, "distribuicao_por_sexo")

    st.divider()
    with st.expander("Tabela de Dados Filtrados 📋"):
        all_cols = list(df.columns)
        selected_cols = st.multiselect("Selecione as colunas para exibir", all_cols, default=all_cols)
        if selected_cols:
            st.dataframe(df_f[selected_cols], use_container_width=True)
        else:
            st.info("Selecione as colunas que deseja exibir na tabela.")
        csv_bytes = df_f.to_csv(index=False).encode("utf-8")
        st.download_button("Baixar CSV filtrado", data=csv_bytes, file_name="funcionarios_filtrado.csv", mime="text/csv")
        to_excel = st.toggle("Gerar Excel filtrado para download")
        if to_excel:
            buff = BytesIO()
            with pd.ExcelWriter(buff, engine="openpyxl") as writer:
                df_f.to_excel(writer, index=False, sheet_name="Filtrado")
            st.download_button("Baixar Excel filtrado", data=buff.getvalue(), file_name="funcionarios_filtrado.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

elif page == "Análise de Salário e Desempenho":
    st.header("Análise de Salário e Desempenho")
    if "salario_base" in df.columns and "avaliacao_funcionario" in df.columns and "nivel" in df.columns:
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            st.subheader("Salário por Nível")
            fig_box = px.box(df_f, x="nivel", y="salario_base", title="Distribuição Salarial por Nível")
            st.plotly_chart(fig_box, use_container_width=True)
            download_chart(fig_box, "salario_por_nivel")
        with col_s2:
            st.subheader("Salário vs. Avaliação")
            fig_scatter = px.scatter(df_f, x="salario_base", y="avaliacao_funcionario", color="area",
                                    hover_data=["nome_completo", "cargo"], title="Salário Base vs. Avaliação do Funcionário")
            st.plotly_chart(fig_scatter, use_container_width=True)
            download_chart(fig_scatter, "salario_vs_avaliacao")

    st.divider()

    if "salario_base" in df.columns and "tempo_de_casa_meses" in df.columns and not df_f.empty:
        st.subheader("Heatmap de Salário e Tempo de Casa")
        df_f["faixa_salario"] = pd.cut(df_f["salario_base"], bins=10, labels=[f"Faixa {i}" for i in range(1, 11)])
        df_f["faixa_tempo"] = pd.cut(df_f["tempo_de_casa_meses"], bins=10, labels=[f"Faixa {i}" for i in range(1, 11)])
        d = df_f.groupby(["faixa_salario", "faixa_tempo"]).size().reset_index(name="count")
        
        fig_hm = px.density_heatmap(d, x="faixa_salario", y="faixa_tempo", z="count", title="Heatmap de Salário e Tempo de Casa")
        st.plotly_chart(fig_hm, use_container_width=True)
        download_chart(fig_hm, "heatmap_salario_tempo_casa")
    
elif page == "Análise de Retenção":
    st.header("Análise de Retenção e Turnover")
    
    col_t1, col_t2 = st.columns(2)
    with col_t1:
        st.subheader("Taxa de Turnover por Área (%)")
        if "area" in df_f.columns and "status" in df_f.columns and not df_f.empty:
            turnover_por_area = df_f.groupby("area")["status"].apply(lambda x: (x == "Desligado").sum() / len(x) * 100).reset_index(name="taxa_turnover")
            fig_turnover = px.bar(turnover_por_area, x="area", y="taxa_turnover", title="Taxa de Turnover por Área")
            st.plotly_chart(fig_turnover, use_container_width=True)
            download_chart(fig_turnover, "turnover_por_area")
    with col_t2:
        st.subheader("Distribuição de Tempo de Casa")
        if "tempo_de_casa_meses" in df_f.columns and not df_f["tempo_de_casa_meses"].dropna().empty:
            fig_hist = px.histogram(df_f, x="tempo_de_casa_meses", nbins=20, title="Distribuição de Tempo de Casa")
            st.plotly_chart(fig_hist, use_container_width=True)
            download_chart(fig_hist, "distribuicao_tempo_casa")

    st.divider()
    
    st.subheader("Análise de Retenção por Cohort")
    if "data_contratacao" in df.columns and "data_demissao" in df.columns:
        df_cohort = df.copy()
        # Define o Cohort (mês de contratação)
        df_cohort["cohort"] = df_cohort["data_contratacao"].dt.to_period("M")
        
        # Filtra apenas funcionários com data de contratação
        df_cohort = df_cohort.dropna(subset=["data_contratacao"])
        
        # Cria uma coluna para meses desde a contratação
        df_cohort["meses_desde_contratacao"] = (df_cohort["data_contratacao"].dt.to_period("M").astype(int) - df_cohort["cohort"].astype(int))

        # Calcula a retenção (funcionários ativos por mês de contratação)
        cohort_counts = df_cohort.groupby(["cohort", "meses_desde_contratacao"]).size().reset_index(name="headcount")
        
        cohort_sizes = cohort_counts[cohort_counts["meses_desde_contratacao"] == 0][["cohort", "headcount"]]
        cohort_sizes.rename(columns={'headcount': 'cohort_size'}, inplace=True)
        
        retention = pd.merge(cohort_counts, cohort_sizes, on="cohort")
        retention["taxa_retencao"] = retention["headcount"] / retention["cohort_size"]
        
        fig_retention = px.line(retention, x="meses_desde_contratacao", y="taxa_retencao", color="cohort",
                                title="Taxa de Retenção por Cohort (Grupo de Contratação)")
        st.plotly_chart(fig_retention, use_container_width=True)
        download_chart(fig_retention, "retencao_por_cohort")





