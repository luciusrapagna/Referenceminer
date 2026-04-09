import streamlit as st
import pandas as pd
import plotly.express as px
from st_aggrid import AgGrid, GridOptionsBuilder
import numpy as np
import io

st.set_page_config(page_title="Dashboard Bibliográfico", layout="wide", page_icon="🔍")
st.title("🔍 Dashboard Bibliográfico - Saúde/Ecologia")

# Uploader de CSV (substitui Drive)
uploaded_file = st.sidebar.file_uploader("📁 Upload CSV do Agente", type="csv")
if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
    df['year'] = pd.to_numeric(df['year'], errors='coerce').fillna(1900).astype(int)
    df['citation_count'] = pd.to_numeric(df['citation_count'], errors='coerce').fillna(0).astype(int)
    
    st.sidebar.success(f"✅ {len(df)} resultados carregados!")
    
    # Filtros
    st.sidebar.header("🔧 Filtros")
    fontes = st.sidebar.multiselect("Fontes:", options=sorted(df['source'].unique()), default=sorted(df['source'].unique()))
    min_year, max_year = st.sidebar.slider("Ano:", int(df['year'].min()), int(df['year'].max()), (int(df['year'].min()), int(df['year'].max())))
    min_cit, max_cit = st.sidebar.slider("Citações:", 0, int(df['citation_count'].max()), (0, int(df['citation_count'].max())))
    
    # Filtra
    df_filt = df[(df['source'].isin(fontes)) & (df['year'].between(min_year, max_year)) & (df['citation_count'].between(min_cit, max_cit))].reset_index(drop=True)
    
    st.metric("📊 Filtrados", len(df_filt), delta=f"de {len(df)}")
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("📈 Por Fonte")
        fig_bar = px.bar(df_filt['source'].value_counts().reset_index(), x='source', y='count', color='source')
        st.plotly_chart(fig_bar, use_container_width=True)
    
    with col2:
        st.subheader("📈 Por Ano")
        yearly = df_filt.groupby('year').size().reset_index(name='count')
        fig_line = px.line(yearly, x='year', y='count', markers=True)
        st.plotly_chart(fig_line, use_container_width=True)
    
    st.subheader("📊 Citações x Ano")
    fig_scatter = px.scatter(df_filt, x='year', y='citation_count', color='source', size='citation_count', hover_data=['title'])
    st.plotly_chart(fig_scatter, use_container_width=True)
    
    # Tabela
    st.subheader("📋 Tabela")
    gb = GridOptionsBuilder.from_dataframe(df_filt)
    gb.configure_pagination(paginationPageSize=10)
    grid_options = gb.build()
    AgGrid(df_filt, gridOptions=grid_options, height=400)
    
    # Export
    csv_buffer = df_filt.to_csv(index=False).encode('utf-8')
    st.download_button("📥 CSV Filtrado", csv_buffer, "resultados_filtrados.csv")
else:
    st.info("👆 Upload o CSV do agente para começar!")
