import streamlit as st
import requests
import pandas as pd
import re
import time
from urllib.parse import quote
import plotly.express as px

# Config
EMAIL = "luciano@facunilagos.edu.br"
NCBI_EMAIL = EMAIL
NCBI_TOOL = "agente_luciano"
ELSEVIER_API_KEY = st.secrets.get("ELSEVIER_API_KEY", "")

HEADERS = {"User-Agent": f"BiblioAgent/1.0 (mailto:{EMAIL})"}

# Utilitários
def clean_text(text): return re.sub(r"\s+", " ", str(text or "")).strip()
def normalize_title(title): return re.sub(r"[^\w\s]", "", clean_text(title).lower())
def deduplicate_records(records):
    df = pd.DataFrame(records or [])
    if df.empty: return df
    df["doi_norm"] = df["doi"].fillna("").str.lower().str.strip()
    df["title_norm"] = df["title"].fillna("").apply(normalize_title)
    df_doi = df[df["doi_norm"] != ""].drop_duplicates("doi_norm")
    df_no_doi = df[df["doi_norm"] == ""].drop_duplicates("title_norm")
    final = pd.concat([df_doi, df_no_doi]).drop(columns=["doi_norm", "title_norm"], errors="ignore").reset_index(drop=True)
    return final

# PubMed
def search_pubmed(query, retmax=20):
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
    esearch = f"{base}esearch.fcgi?db=pubmed&term={quote(query)}&retmode=json&retmax={retmax}&tool={NCBI_TOOL}&email={quote(NCBI_EMAIL)}"
    r = requests.get(esearch, headers=HEADERS, timeout=30)
    if r.status_code != 200: return []
    ids = r.json().get("esearchresult", {}).get("idlist", [])
    if not ids: return []
    esummary = f"{base}esummary.fcgi?db=pubmed&id={','.join(ids)}&retmode=json&tool={NCBI_TOOL}&email={quote(NCBI_EMAIL)}"
    r2 = requests.get(esummary, headers=HEADERS, timeout=30)
    data = r2.json().get("result", {})
    results = []
    for pmid in ids:
        item = data.get(pmid, {})
        authors = "; ".join(a.get("name", "") for a in item.get("authors", []))
        doi = next((aid.get("value") for aid in item.get("articleids", []) if aid.get("idtype") == "doi"), "")
        results.append({"base": "PubMed", "title": clean_text(item.get("title")), "authors": authors, "year": str(item.get("pubdate", ""))[:4],
                        "journal": clean_text(item.get("fulljournalname")), "doi": doi, "id": pmid, "abstract": "", "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/", "query": query})
    return results

# Europe PMC, Crossref (igual anterior, copie se necessário - curto)
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
    items = r.json().get("message", {}).get("items", [])
    results = []
    for item in items:
        title = item.get("title", [""])
        authors = "; ".join(f"{a.get('given', '')} {a.get('family', '')}".strip() for a in item.get("author", []))
        year = str(item.get("issued", {}).get("date-parts", [[0]])[0][0]) if item.get("issued") else ""
        results.append({"base": "Crossref", "title": clean_text(title[0]), "authors": authors, "year": year, "journal": clean_text(item.get("container-title", [""])[0]),
                        "doi": item.get("DOI", ""), "id": item.get("DOI"), "abstract": clean_text(item.get("abstract")), "url": item.get("URL", ""), "query": query})
    return results

# Fallback Scholar (URL)
def search_google_scholar(query, _=20):
    return [{"base": "Google Scholar", "title": f"Busque aqui: [scholar.google.com/scholar?q={quote(query)}]", "url": f"https://scholar.google.com/scholar?q={quote(query)}", "query": query}]

# Placeholders
def search_scielo(query, _=20): return [{"base": "SciELO", "title": f"SciELO: {query}", "url": f"https://search.scielo.org/?q={quote(query)}", "query": query}]
def search_lilacs(query, _=20): return [{"base": "LILACS", "title": f"LILACS: {query}", "url": f"https://pesquisa.bvsalud.org/?q={quote(query)}", "query": query}]
def search_sciencedirect(query, _=20, api_key=""): return [{"base": "ScienceDirect", "title": "API Key ativa?" if api_key else "Configure key", "query": query}]

# Agente
@st.cache_data(ttl=600)
def agente(query, retmax=20, use_sd=False):
    records = []
    records += search_pubmed(query, retmax)
    time.sleep(0.5); records += search_europe_pmc(query, retmax)
    time.sleep(0.5); records += search_crossref(query, retmax)
    records += search_scielo(query, retmax)
    records += search_lilacs(query, retmax)
    if use_sd and ELSEVIER_API_KEY: records += search_sciencedirect(query, retmax, ELSEVIER_API_KEY)
    records += search_google_scholar(query, retmax)
    df = deduplicate_records(records).sort_values(["year", "base"], ascending=[False, True]).reset_index(drop=True)
    df = df[df["year"].str.isnumeric() & (df["year"].astype(int) >= 2016)]
    return df

# UI
st.set_page_config(layout="wide")
st.title("🔬 Agente Bibliográfico")
query = st.text_area("Query:", value='("musicoterapia" OR "terapia do riso") AND ("medicina humanizada")')
retmax = st.slider("Resultados/base:", 5, 30, 20)
ano_min = st.slider("Ano min:", 2010, 2026, 2016)
use_sd = st.checkbox("ScienceDirect")

if st.button("Buscar", type="primary"):
    df = agente(query, retmax, use_sd)
    df_f = df[df["year"].str.isnumeric() & (df["year"].astype(int) >= ano_min)]
    c1, c2, c3 = st.columns(3)
    c1.metric("Registros", len(df_f))
    c2.metric("Bases", df_f["base"].nunique())
    c3.metric("DOIs", df_f["doi"].nunique())
    col1, col2 = st.columns(2)
    col1.plotly_chart(px.histogram(df_f, x="year", color="base"))
    col2.plotly_chart(px.pie(df_f, names="base"))
    st.dataframe(df_f[["title", "authors", "year", "doi", "url"]])
    st.download_button("CSV", df_f.to_csv(index=False).encode(), "resultados.csv")
    st.download_button("Excel", df_f.to_excel(index=False), "resultados.xlsx")

st.caption("Prof. Luciano | Fac-Unilagos | 2026")
