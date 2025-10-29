"""Définissez ici vos clés API privées.

Copiez ce fichier si besoin et remplacez les valeurs vides par vos propres
identifiants. Ce fichier est chargé automatiquement par l’application si la
variable d’environnement correspondante n’est pas définie.
"""

# Clé API Semantic Scholar (optionnelle mais recommandée pour lever la limite
# de requêtes anonymes). Laissez la chaîne vide si vous ne disposez pas de clé.
SEMANTIC_SCHOLAR_API_KEY = ""

# Proxy SOCKS Tor (recommandé). Exemple : "socks5h://127.0.0.1:9050"
TOR_SOCKS_PROXY = ""

# Proxy HTTP optionnel si vous avez configuré un tunnel HTTP local vers Tor.
# Exemple : "http://127.0.0.1:9152"
TOR_PROXY = ""

# Répertoire du Tor Browser Bundle (optionnel). Renseignez ce chemin si vous
# souhaitez que l’application démarre automatiquement Tor via Stem. Exemple :
# "/Applications/Tor Browser.app/Contents/Resources/TorBrowser"
TOR_BROWSER_PATH = ""

# Paramètres du port de contrôle Tor (optionnels). Configurez ces valeurs si
# vous avez activé ControlPort 9051 (ou un autre port) dans torrc afin de
# permettre à l’application d’envoyer le signal NEWNYM via Stem.
TOR_CONTROL_PORT = ""

# Mot de passe du port de contrôle (optionnel). Laissez vide si vous utilisez
# CookieAuthentication 1 dans torrc.
TOR_CONTROL_PASSWORD = ""
