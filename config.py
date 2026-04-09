import os
from dotenv import load_dotenv

# Carrega variáveis do .env (se existir)
load_dotenv()

# ==============================
# CONFIGURAÇÕES GERAIS
# ==============================

EMAIL = os.getenv("EMAIL_CONTATO", "seu_luciusrapagna@gmail.com")

USER_AGENT = f"AgenteBibliografico/1.0 (mailto:{EMAIL})"

# ==============================
# CHAVES DE API
# ==============================

NCBI_API_KEY = os.getenv("NCBI_API_KEY", "ed54fab73e9a9dac3dc4e29860550d3a2108")
ELSEVIER_API_KEY = os.getenv("ELSEVIER_API_KEY", "19eefb9f59e6a3d29da6a6e118bf6254")

# ==============================
# CONFIGURAÇÕES DO AGENTE
# ==============================

# Número padrão de resultados por base
DEFAULT_RESULTS = int(os.getenv("DEFAULT_RESULTS", 20))

# Timeout padrão das requisições
TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", 30))

# ==============================
# FUNÇÕES AUXILIARES
# ==============================

def check_keys():
    """
    Verifica se as chaves principais estão configuradas
    """
    status = {
        "NCBI_API_KEY": bool(NCBI_API_KEY),
        "ELSEVIER_API_KEY": bool(ELSEVIER_API_KEY),
        "EMAIL": bool(EMAIL)
    }
    return status


def print_config_status():
    """
    Mostra no terminal se tudo está configurado
    """
    status = check_keys()
    print("\n🔧 STATUS DAS CONFIGURAÇÕES:")
    for k, v in status.items():
        print(f"{k}: {'OK' if v else 'NÃO CONFIGURADO'}")