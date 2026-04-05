import subprocess
import sys

# Liste de toutes les bibliothèques nécessaires pour l'Assistant Achats
# (Version allégée sans ChromaDB)
bibliotheques = [
    "crawl4ai[all]",        # Le robot d'aspiration web ultra-performant
    "langchain",             # Le squelette pour lier l'IA à nos données
    "langchain-ollama",      # Pour connecter Ollama à LangChain
    "langchain-core",        # Les briques de base de LangChain
    "langchain-community",   # Les extensions de la communauté
    "pypdf",                 # Le lecteur de fichiers PDF
    "scikit-learn",         # ✨ NOUVEAU : Pour la recherche TF-IDF ultra-légère
    "requests",              # Pour gérer les téléchargements simples si besoin
    "beautifulsoup4"         # Pour le parsing d'appoint
]

def installer_tout():
    print("🚀 Début de l'installation des outils pour l'Assistant Achats...\n")
    
    for biblio in bibliotheques:
        print(f"⏳ Installation de : {biblio}...")
        try:
            # Cette commande simule le fameux "pip install" directement en Python
            subprocess.check_call([sys.executable, "-m", "pip", "install", biblio])
            print(f"✅ {biblio} installé avec succès !\n")
        except Exception as e:
            print(f"❌ Erreur lors de l'installation de {biblio}: {e}\n")
            
    print("🎉 Toutes les bibliothèques Python ont été traitées !")
    print("\n💡 TRÈS IMPORTANT : Puisque tu utilises Crawl4AI, n'oublie pas d'exécuter")
    print("la commande suivante dans ton terminal pour finaliser l'installation du navigateur :")
    print("   python -m playwright install chrome")

if __name__ == "__main__":
    installer_tout()