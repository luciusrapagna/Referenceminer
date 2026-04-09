import streamlit as st
import requests
import pandas as pd
import re
import time
from urllib.parse import quote
from scholarly import scholarly
from bs4 import BeautifulSoup
import plotly.express as px

# Config (edite EMAIL)
EMAIL = "luciusrapagna@gmail.com"
NCBI_EMAIL = lucianorapagna@id.uff.br
NCBI_TOOL = "agente_luciano"
ELSEVIER_API_KEY = st.secrets.get("ELSEVIER_API_KEY", "19eefb9f59e6a3d29da6a6e118bf6254")  # Render Secrets

HEADERS = {"User-Agent": f"BiblioAgent/1.0 (mailto:{EMAIL})"}

# Utilitários
def clean_text(text): return re.sub(r"\s+", " ", str(text or "")).strip()
def normalize_title(title): return re.sub(r"[^\w\s]", "", clean_text(title).lower())
def deduplicate_records(records):
    if not records: return pd.DataFrame()
    df = pd.DataFrame(records)
    df["doi_norm"] = df["doi"].fillna("").str.lower().str.strip()
    df["title_norm"] = df["title"].fillna("").apply(normalize_title)
    df_doi = df[df["doi_norm"] != ""].drop_duplicates("doi_norm")
    df_no_doi = df[df["doi_norm"] == ""].drop_duplicates("title_norm")
    final = pd.concat([df_doi, df_no_doi]).drop(columns=["doi_norm", "title_norm"], errors="ignore").reset_index(drop=True)
    return final

# Conectores (simplificados e robustos)
def search_pubmed(query, retmax=20):
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
    esearch = f"{base}esearch.fcgi?db=pubmed&term={quote(query)}&retmode=json&retmax={retmax}&tool={NCBI_TOOL}&email={quote(NCBI_EMAIL)}"
    r = requests.get(esearch, headers=HEADERS, timeout=30)
    if r.status_code != 200: return []
    ids = r.json()["esearchresult"]["idlist"]
    if not ids: return []
    esummary = f"{base}esummary.fcgi?db=pubmed&id={','.join(ids)}&retmode=json&tool={NCBI_TOOL}&email={quote(NCBI_EMAIL)}"
    r2 = requests.get(esummary, headers=HEADERS, timeout=30)
    data = r2.json()["result"]
    results = []
    for pmid in ids:
        item = data.get(pmid, {})
        authors = "; ".join(a.get("name", "") for a in item.get("authors", []))
        doi = next((aid["value"] for aid in item.get("articleids", []) if aid["idtype"] == "doi"), "")
        results.append({"base": "PubMed", "title": clean_text(item.get("title")), "authors": authors, "year": str(item.get("pubdate", ""))[:4],
                        "journal": clean_text(item.get("fulljournalname")), "doi": doi, "id": pmid, "abstract": "", "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/", "query": query})
    return results

def search_europe_pmc(query, page_size=20):
    url = f"https://www.ebi.ac.uk/europepmc/webservice/rest/search?query={quote(query)}&pageSize={page_size}&resultType=lite"
    r = requests.get(url, headers=HEADERS, timeout=30)
    if r.status_code != 200: return []
    data = r.json()
    results = []
    for hit in data.get("resultList", {}).get("result", []):
        authors = "; ".join(a.get("author", {}).get("fullName", "") for a in hit.get("authorList", {}).get("author", []))
        results.append({"base": "Europe PMC", "title": clean_text(hit.get("title")), "authors": authors, "year": hit.get("pubYear", ""),
                        "journal": clean_text(hit.get("journalTitle")), "doi": hit.get("doi", ""), "id": hit.get("id"), "abstract": clean_text(hit.get("abstAct")), "url": hit.get("URL", ""), "query": query})
    return results

def search_crossref(query, rows=20):
    url = f"https://api.crossref.org/works?query.bibliographic={quote(query)}&rows={rows}&mailto={quote(EMAIL)}"
    r = requests.get(url, headers=HEADERS, timeout=30)
    if r.status_code != 200: return []
    items = r.json()["message"]["items"]
    results = []
    for item in items:
        title = item.get("title", [""])
        authors = "; ".join(f"{a.get('given', '')} {a.get('family', '')}".strip() for a in item.get("author", []))
        year = str(item.get("issued", {}).get("date-parts", [[0]])[0][0]) if item.get("issued") else ""
        results.append({"base": "Crossref", "title": clean_text(title[0]), "authors": authors, "year": year, "journal": clean_text(item.get("container-title", [""])[0]),
                        "doi": item.get("DOI", ""), "id": item.get("DOI"), "abstract": clean_text(item.get("abstract")), "url": item.get("URL", ""), "query": query})
    return results

def search_google_scholar(query, num_results=20):
    try:
        search_query = scholarly.search_pubs(query)
        results = []
        for i, result in enumerate(search_query):
            if i >= num_results: break
            bib = result.get('bib', {})
            results.append({"base": "Google Scholar", "title": clean_text(bib.get('title')), "authors": "; ".join(bib.get('author', [])), "year": bib.get('pub_year', ''),
                            "journal": clean_text(bib.get('venue')), "doi": "", "id": result.get('pub_url'), "abstract": "", "url": result.get('eprint_url') or result.get('pub_url'), "query": query})
        return results
    except: return [{"base": "Google Scholar", "title": "Erro de acesso", "query": query}]

# Placeholder para SciELO/LILACS/SD (simples)
def search_scielo(query, _=20): return [{"base": "SciELO", "title": f"Busca em SciELO: {query}", "url": f"https://search.scielo.org/?q={quote(query)}", "query": query}]
def search_lilacs(query, _=20): return [{"base": "LILACS", "title": f"Busca em LILACS: {query}", "url": f"https://pesquisa.bvsalud.org/?q={quote(query)}", "query": query}]
def search_sciencedirect(query, count=20, api_key=""):
    if not api_key: return [{"base": "ScienceDirect", "title": "API Key necessária", "query": query}]
    # Implemente full parse se key ativa
    return [{"base": "ScienceDirect", "title": f"ScienceDirect (key ativa): {query}", "query": query}]

# Agente principal
@st.cache_data
def agente(query, retmax=20, use_sd=False):
    records = []
    records += search_pubmed(query, retmax)
    time.sleep(0.5); records += search_europe_pmc(query, retmax)
    time.sleep(0.5); records += search_crossref(query, retmax)
    records += search_scielo(query, retmax); records += search_lilacs(query, retmax)
    if use_sd and ELSEVIER_API_KEY: records += search_sciencedirect(query, retmax, ELSEVIER_API_KEY)
    records += search_google_scholar(query, retmax)
    df = deduplicate_records(records).sort_values(["year", "base"], ascending=[False, True]).reset_index(drop=True)
    df = df[df["year"].str.isnumeric().astype(int).ge(2016)]  # 10 anos
    return df

# UI
st.title("🔬 Agente Bibliográfico - Prof. Luciano")
st.markdown("Dashboard para revisões sistemáticas | Fac-Unilagos")

col1, col2 = st.columns([3,1])
with col1: query = st.text_area("Query Booleana:", value='("musicoterapia" OR "terapia do riso") AND ("medicina humanizada")', height=80)
with col2:
    retmax = st.slider("Resultados/base:", 5, 50, 20)
    ano_min = st.slider("Ano min:", 2010, 2026, 2016)
    use_sd = st.checkbox("ScienceDirect")

if st.button("🚀 Buscar", type="primary"):
    df = agente(query, retmax, use_sd)
    df_f = df[df["year"].str.isnumeric().astype(int).ge(ano_min)]
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Registros", len(df_f))
    c2.metric("Bases", df_f["base"].nunique())
    c3.metric("DOIs", df_f["doi"].nunique())
    
    col1, col2 = st.columns(2)
    with col1: st.plotly_chart(px.histogram(df_f, x="year", color="base", title="Por Ano/Base"), use_container_width=True)
    with col2: st.plotly_chart(px.pie(df_f, names="base", title="Por Base"), use_container_width=True)
    
    st.dataframe(df_f[["title", "authors", "year", "doi", "url"]], use_container_width=True)
    
    csv = df_f.to_csv(index=False).encode('utf-8-sig')
    st.download_button("📥 CSV", csv, "resultados.csv")
    st.download_button("📥 Excel", df_f.to_excel(index=False), "resultados.xlsx")

st.caption("© 2026 Prof. Luciano | Otimizado para projeto humanized medicine")