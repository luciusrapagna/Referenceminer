import streamlit as st
import pandas as pd
import requests
import re
import plotly.express as px

# Global Variables
NCBI_API_KEY = "ed54fab73e9a9dac3dc4e29860550d3a2108"
ELSEVIER_API_KEY = "19eefb9f59e6a3d29da6a6e118bf6254" # 
EMAIL = "luciusrapagna@gmail.com"
USER_AGENT = f"AgenteBibliografico/1.0 (mailto:{EMAIL})"

padrao = {
    "base": "",
    "title": "",
    "authors": "",
    "year": "",
    "journal": "",
    "doi": "",
    "abstract": "",
    "url": "",
    "query": ""
}

# Helper Functions
def buscar_pubmed(query, api_key=None, retmax=20):
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    params = {
        "db": "pubmed",
        "term": query,
        "retmode": "json",
        "retmax": retmax
    }
    if api_key:
        params["api_key"] = api_key

    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    return r.json()

def buscar_europepmc(query, page_size=20):
    url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
    params = {
        "query": query,
        "format": "json",
        "pageSize": page_size
    }
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    return r.json()

def buscar_crossref(query, email, rows=20):
    headers = {
        "User-Agent": f"AgenteBibliografico/1.0 (mailto:{email})"
    }
    url = "https://api.crossref.org/works"
    params = {
        "query.bibliographic": query,
        "rows": rows,
        "mailto": email
    }
    r = requests.get(url, headers=headers, params=params, timeout=30)
    r.raise_for_status()
    return r.json()

def buscar_sciencedirect(query, api_key, count=20):
    headers = {
        "X-ELS-APIKey": api_key,
        "Accept": "application/json"
    }
    url = "https://api.elsevier.com/content/search/sciencedirect"
    params = {
        "query": query,
        "count": count
    }
    r = requests.get(url, headers=headers, params=params, timeout=30)
    r.raise_for_status()
    return r.json()

def limpar_titulo(t):
    t = str(t).lower().strip()
    t = re.sub(r"[^\w\s]", "", t)
    t = re.sub(r"\s+", " ", t)
    return t

def deduplicar(df):
    df["doi_norm"] = df["doi"].fillna("").str.lower().str.strip()
    df["title_norm"] = df["title"].apply(limpar_titulo)

    com_doi = df[df["doi_norm"] != ""].drop_duplicates(subset="doi_norm", keep="first")
    sem_doi = df[df["doi_norm"] == ""].drop_duplicates(subset="title_norm", keep="first")

    final = pd.concat([com_doi, sem_doi], ignore_index=True)
    return final.drop(columns=["doi_norm", "title_norm"], errors="ignore")

# Agente de busca
def agente_busca(query):
    registros = []

    # PubMed
    try:
        pubmed_results = buscar_pubmed(query, api_key=NCBI_API_KEY)
        if pubmed_results and 'esearchresult' in pubmed_results and 'idlist' in pubmed_results['esearchresult']:
            for pmid in pubmed_results['esearchresult']['idlist']:
                record = padrao.copy()
                record['base'] = 'PubMed'
                record['title'] = f"PubMed Article (PMID: {pmid})"
                record['doi'] = ""
                record['url'] = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
                record['query'] = query
                registros.append(record)
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching from PubMed: {e}")
    except Exception as e:
        st.error(f"An unexpected error occurred processing PubMed results: {e}")

    # Europe PMC
    try:
        europepmc_results = buscar_europepmc(query)
        if europepmc_results and 'resultList' in europepmc_results and 'result' in europepmc_results['resultList']:
            for item in europepmc_results['resultList']['result']:
                record = padrao.copy()
                record['base'] = 'Europe PMC'
                record['title'] = item.get('title', '')
                record['authors'] = ', '.join([author.get('fullName', '') for author in item.get('authorList', {}).get('author', [])])
                record['year'] = item.get('pubYear', '')
                record['journal'] = item.get('journalTitle', '')
                record['doi'] = item.get('doi', '')
                record['abstract'] = item.get('abstractText', '')
                record['url'] = item.get('fullTextUrlList', {}).get('fullTextUrl', [{}])[0].get('url', '')
                record['query'] = query
                registros.append(record)
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching from Europe PMC: {e}")
    except Exception as e:
        st.error(f"An unexpected error occurred processing Europe PMC results: {e}")

    # Crossref
    try:
        crossref_results = buscar_crossref(query, EMAIL)
        if crossref_results and 'message' in crossref_results and 'items' in crossref_results['message']:
            for item in crossref_results['message']['items']:
                record = padrao.copy()
                record['base'] = 'Crossref'
                record['title'] = item.get('title', [''])[0] if item.get('title') else ''
                record['authors'] = ', '.join([author.get('given', '') + ' ' + author.get('family', '') for author in item.get('author', [])])
                record['year'] = item.get('published-print', {}).get('date-parts', [[None]])[0][0] if item.get('published-print') else ''
                record['journal'] = item.get('container-title', [''])[0] if item.get('container-title') else ''
                record['doi'] = item.get('DOI', '')
                record['url'] = item.get('URL', '')
                record['query'] = query
                registros.append(record)
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching from Crossref: {e}")
    except Exception as e:
        st.error(f"An unexpected error occurred processing Crossref results: {e}")

    # ScienceDirect
    try:
        sciencedirect_results = buscar_sciencedirect(query, ELSEVIER_API_KEY)
        if sciencedirect_results and 'search-results' in sciencedirect_results and 'entry' in sciencedirect_results['search-results']:
            for item in sciencedirect_results['search-results']['entry']:
                record = padrao.copy()
                record['base'] = 'ScienceDirect'
                record['title'] = item.get('dc:title', '')
                creators = item.get('prism:url', {}).get('creator', []) if 'prism:url' in item else []
                authors = []
                for creator_dict in creators:
                    author_name = creator_dict.get('$', '')
                    if author_name:
                        authors.append(author_name)
                record['authors'] = ', '.join(authors)

                record['year'] = item.get('prism:coverDate', '')[:4]
                record['journal'] = item.get('prism:publicationName', '')
                record['doi'] = item.get('prism:doi', '')
                record['abstract'] = item.get('prism:description', '')
                record['url'] = next((link['@href'] for link in item.get('link', []) if link.get('@rel') == 'full-text'), '')
                record['query'] = query
                registros.append(record)
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching from ScienceDirect: {e}")
    except Exception as e:
        st.error(f"An unexpected error occurred processing ScienceDirect results: {e}")


    df_result = pd.DataFrame(registros)
    if df_result.empty:
        df_result = pd.DataFrame(columns=padrao.keys())

    df_result = deduplicar(df_result)
    return df_result


# Streamlit App Layout and Logic
st.set_page_config(page_title="Agente Bibliográfico", layout="wide")

st.title("Agente de Busca Bibliográfica")
query_input = st.text_area("Digite a estratégia booleana", key="query_input")

usar_pubmed = st.checkbox("PubMed", value=True)
usar_epmc = st.checkbox("Europe PMC", value=True)
usar_crossref = st.checkbox("Crossref", value=True)
usar_sciencedirect = st.checkbox("ScienceDirect", value=True)
usar_scielo = st.checkbox("SciELO", value=True)
usar_lilacs = st.checkbox("LILACS", value=True)

with st.sidebar:
    st.header("Filtros")
    ano_min = st.number_input("Ano inicial", value=2015, key="ano_min_filter")
    ano_max = st.number_input("Ano final", value=2026, key="ano_max_filter")

# Initialize df in session state to persist it across reruns
if 'df_results' not in st.session_state:
    st.session_state.df_results = pd.DataFrame(columns=padrao.keys())

if st.button("Buscar"):
    if not query_input:
        st.warning("Por favor, digite uma estratégia booleana para buscar.")
    else:
        st.write("Executando busca...")
        st.session_state.df_results = agente_busca(query_input)

if not st.session_state.df_results.empty:
    df_display = st.session_state.df_results.copy()
    st.write("### Resultados da Busca")
    st.dataframe(df_display, use_container_width=True)

    col1, col2, col3 = st.columns(3)
    col1.metric("Total de registros", len(df_display))
    col2.metric("Bases consultadas", df_display["base"].nunique())
    col3.metric("DOIs únicos", df_display["doi"].nunique())

    df_display['year'] = pd.to_numeric(df_display['year'], errors='coerce')
    df_filtered_by_year = df_display[(df_display['year'] >= ano_min) & (df_display['year'] <= ano_max)].dropna(subset=['year'])

    if not df_filtered_by_year.empty:
        fig = px.histogram(df_filtered_by_year, x="year", title="Distribuição de Artigos por Ano")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Nenhum resultado para exibir no histograma após filtragem por ano.")

    csv = df_display.to_csv(index=False).encode("utf-8-sig")
    st.download_button("Baixar CSV", data=csv, file_name="resultados.csv", mime="text/csv")

    if not df_display.empty:
        selecionado = st.selectbox("Selecione um artigo", df_display["title"].tolist(), key="article_selector")
        if selecionado:
            art = df_display[df_display["title"] == selecionado].iloc[0]

            st.subheader(art["title"])
            st.write("**Autores:**", art["authors"])
            st.write("**Periódico:**", art["journal"])
            st.write("**Ano:**", art["year"])
            st.write("**DOI:**", art["doi"])
            st.write("**Resumo:**", art["abstract"])
    else:
        st.info("Nenhum artigo para selecionar.")

elif st.button("Buscar") and st.session_state.df_results.empty:
    st.info("Nenhum resultado encontrado para a sua busca.")
