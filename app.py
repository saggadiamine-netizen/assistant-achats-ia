import asyncio
import os
import shutil
import sys
from urllib.parse import urlparse, urljoin
import urllib.request
from pathlib import Path
import re

from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode, BrowserConfig, UndetectedAdapter
from crawl4ai.async_crawler_strategy import AsyncPlaywrightCrawlerStrategy

from langchain_ollama import ChatOllama
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_community.document_loaders import PyPDFLoader

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# --- CONFIGURATION INITIALE ---
OLLAMA_MODEL = "qwen2.5:1.5b"  
DOSSIER_TELECHARGEMENT_PC = os.path.join(os.path.expanduser("~"), "Downloads")


class LightMemory:
    """Gestion de la mémoire textuelle via vectorisation TF-IDF."""
    def __init__(self):
        self.documents = []
        
    def add_texts(self, texts):
        self.documents.extend(texts)
        
    def retrieve(self, query, k=5):
        if not self.documents:
            return ""
        
        vectorizer = TfidfVectorizer()
        try:
            tfidf_matrix = vectorizer.fit_transform(self.documents + [query])
            cosine_sim = cosine_similarity(tfidf_matrix[-1], tfidf_matrix[:-1])
            
            related_docs_indices = cosine_sim[0].argsort()[-k:][::-1]
            
            context = ""
            for idx in related_docs_indices:
                if cosine_sim[0][idx] > 0.05:
                    context += self.documents[idx] + "\n\n"
            return context
        except:
            return "\n\n".join(self.documents[:k])


async def collect_data_pro(start_url, max_pages):
    """Collecte les pages web et télécharge les PDF via Crawl4AI."""
    nom_domaine = urlparse(start_url).netloc
    nom_fournisseur = nom_domaine.replace("www.", "").split('.')[0]
    if not nom_fournisseur: nom_fournisseur = "fournisseur_inconnu"
    
    pdf_dir = os.path.join(DOSSIER_TELECHARGEMENT_PC, nom_fournisseur)
    
    print(f"\n🚀 Lancement du crawler ({max_pages} pages max) sur : {start_url}")
    print(f"📁 Dossier de destination : {pdf_dir}")
    
    Path(pdf_dir).mkdir(parents=True, exist_ok=True)
        
    domain = nom_domaine
    pages_to_visit = [start_url]
    visited_pages = set()
    all_documents = []

    browser_config = BrowserConfig(
        headless=True,          
        enable_stealth=True,      
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    adapter = UndetectedAdapter()
    crawler_strategy = AsyncPlaywrightCrawlerStrategy(
        browser_config=browser_config, 
        browser_adapter=adapter
    )

    config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        exclude_external_links=True,
        word_count_threshold=0, 
        remove_overlay_elements=True, 
        process_iframes=True,
        magic=True,
        session_id="session_fournisseur_achats",
        
        js_code="""
        (function() {
            const acceptTexts = [
                "Acceptez", "Accepter", "Tout accepter", "Accepter tout", "J'accepte", "Autoriser", "Autoriser tout", "Continuer et accepter", "Fermer et accepter", "OK", "D'accord",
                "Accept", "Accept all", "I accept", "Agree", "I agree", "Allow", "Allow all", "Consent", "Proceed", "Got it",
                "Alle akzeptieren", "Akzeptieren", "Einverstanden",
                "Accetto", "Accetta tutti", "Autorizza",
                "Aceptar", "Aceptar todo", "De acuerdo",
                "Aceitar", "Aceitar tous", "Concordo",
                "Accepteren", "Alle accepteren", "Akkoord",
                "Akceptuję", "Zgadzam się", "Zezwól na toutes"
            ];
            const buttons = Array.from(document.querySelectorAll('button, a'));
            for (let btn of buttons) {
                const text = btn.innerText.trim();
                if (acceptTexts.some(t => text.includes(t))) {
                    btn.click();
                    break;
                }
            }
        })();
        """
    )

    motifs_a_exclure = [
        r".*/news/.*", r".*/career.*", r".*/press/.*", r".*/legal/.*",
        r".*/investor.*", r".*/blog.*", r".*/event.*",
        r".*/privacy.*", r".*/recrutement.*", r".*/mentions.*"
    ]

    async with AsyncWebCrawler(crawler_strategy=crawler_strategy) as crawler:
        while pages_to_visit and len(visited_pages) < max_pages:
            url = pages_to_visit.pop(0)
            if url in visited_pages: continue

            print(f"📄 Analyse ({len(visited_pages)+1}/{max_pages}) : {url}")
            visited_pages.add(url)

            try:
                result = await crawler.arun(url=url, config=config)
                
                if result.success and result.markdown:
                    all_documents.append({"text": result.markdown.raw_markdown, "source": url})
                    
                    if result.links and "internal" in result.links:
                        for link in result.links["internal"]:
                            link_url = link["href"]
                            
                            if link_url.lower().endswith('.pdf'):
                                pdf_name = os.path.basename(urlparse(link_url).path)
                                full_pdf_url = urljoin(url, link_url)
                                pdf_path = os.path.join(pdf_dir, pdf_name)
                                
                                if not os.path.exists(pdf_path):
                                    try:
                                        full_pdf_url = full_pdf_url.replace(" ", "%20")
                                        req = urllib.request.Request(
                                            full_pdf_url, 
                                            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
                                        )
                                        with urllib.request.urlopen(req) as response:
                                            with open(pdf_path, 'wb') as out_file:
                                                shutil.copyfileobj(response, out_file)
                                        print(f"📥 PDF téléchargé : {pdf_name}")
                                    except Exception:
                                        pass
                            
                            elif any(link_url.lower().endswith(ext) for ext in ['.xlsx', '.xls', '.zip', '.docx', '.csv', '.png', '.jpg', '.jpeg']):
                                continue
                                
                            elif domain in link_url and link_url not in visited_pages:
                                ignore_page = False
                                for motif in motifs_a_exclure:
                                    if re.search(motif, link_url):
                                        ignore_page = True
                                        break
                                if not ignore_page and link_url not in pages_to_visit:
                                    pages_to_visit.append(link_url)
                                
                await asyncio.sleep(0.5)
            except Exception as e:
                print(f"❌ Erreur ignorée sur {url}")

    return all_documents, pdf_dir


def trigger_pdf_reading(memory, pdf_dir):
    """Lit les PDF non traités et les injecte dans la mémoire."""
    if not os.path.exists(pdf_dir): return False
    pdf_files = [f for f in os.listdir(pdf_dir) if f.endswith(".pdf")]
    
    dossier_temoins = os.path.join(pdf_dir, "read")
    Path(dossier_temoins).mkdir(parents=True, exist_ok=True)
    
    unread_pdfs = [f for f in pdf_files if not os.path.exists(os.path.join(dossier_temoins, f + ".read"))]
        
    if not unread_pdfs: 
        print("ℹ️ Aucun nouveau PDF à lire.")
        return False
        
    print(f"\n⚙️ Lecture et indexation de {len(unread_pdfs)} PDF(s) en cours...")
    success_count = 0
    for filename in unread_pdfs:
        pdf_path = os.path.join(pdf_dir, filename)
        try:
            loader = PyPDFLoader(pdf_path)
            pages = loader.load()
            
            pdf_texts = [page.page_content for page in pages if page.page_content.strip()]
            
            if pdf_texts:
                memory.add_texts(pdf_texts)
                
            path_temoin = os.path.join(dossier_temoins, filename + ".read")
            with open(path_temoin, 'w') as f: f.write('ok')
            print(f"  ✅ PDF lu et intégré : {filename}")
            success_count += 1
        except Exception as e:
            print(f"  ❌ Erreur de lecture sur {filename} : {e}")
            
    return success_count > 0


def ask_question(question, memory, llm):
    """Interroge le LLM en lui fournissant le contexte adéquat."""
    contexte = memory.retrieve(question, k=5)
    
    template = """Tu es un expert en achats et supply chain. Utilise les éléments de contexte suivants pour répondre à la question.
Essaie d'être le plus précis possible en te basant sur le contexte. Si l'information manque ou n'est pas claire, utilise tes connaissances générales pour guider l'utilisateur au mieux.

⚠️ RÈGLE DE LANGUE ABSOLUE : Tu dois obligatoirement répondre dans la MÊME LANGUE que celle utilisée dans la Question de l'utilisateur (si la question est en anglais, réponds en anglais. Si elle est en français, réponds en français).

Contexte : {context}
Question : {question}
Réponse :"""

    prompt = template.format(context=contexte, question=question)
    reponse = llm.invoke(prompt)
    return reponse.content


def generer_fiche_fournisseur(memory, historique_chat, pdf_dir, start_url, llm, liste_pdfs):
    """Génère et sauvegarde la fiche de synthèse au format texte."""
    print("\n📊 Génération de la fiche fournisseur structurée...")
    
    langue_cible = "français"
    mots_anglais = ['what', 'is', 'how', 'supplier', 'product', 'company', 'the', 'and']
    
    if historique_chat:
        derniere_q = historique_chat[-1][0].lower()
        if any(mot in derniere_q.split() for mot in mots_anglais):
            langue_cible = "anglais"
            
    nom_domaine = urlparse(start_url).netloc
    nom_deduit = nom_domaine.replace("www.", "").split('.')[0].capitalize()
    
    echanges_texte = ""
    for q, r in historique_chat:
        echanges_texte += f"Question : {q}\nRéponse : {r}\n\n"
        
    if liste_pdfs:
        pdfs_texte = "\n".join([f"▪ {pdf}" for pdf in liste_pdfs])
    else:
        pdfs_texte = "▪ Aucun document PDF collecté."
        
    prompt_fiche = f"""Tu es un acheteur professionnel. À partir des données récoltées (contexte) et des questions posées lors de la session (échanges ci-dessous), rédige une FICHE FOURNISSEUR synthétique, claire et ultra-pro pour l'entreprise {nom_deduit}.
    
    Informations de base :
    - Site web : {start_url}

    Utilise impérativement la structure graphique suivante pour ta réponse. Respecte scrupuleusement les bordures en étoiles et les symboles :
    
    **************************************************
    * FICHE SYNTHÈSE FOURNISSEUR         *
    **************************************************
    🌐 SOURCE : {start_url}
    🏭 SOCIÉTÉ : {nom_deduit}
    
    --------------------------------------------------
    📌 1. PRÉSENTATION & INFORMATIONS GÉNÉRALES
    --------------------------------------------------
    [Résume ici l'activité principale de {nom_deduit} et son positionnement]

    --------------------------------------------------
    📦 2. GAMME DE PRODUITS / SERVICES DE {nom_deduit}
    --------------------------------------------------
    [Résume ou catégorise brièvement les grandes familles de produits ou de solutions vendues par {nom_deduit}]

    --------------------------------------------------
    📑 3. LISTE DE PRODUITS
    --------------------------------------------------
    [Extrais du contexte l'ensemble des produits spécifiques ou solutions physiques vendus par {nom_deduit}.
    Liste-les sous forme de puces en écrivant obligatoirement le nom de la société devant chaque puce comme ceci : 
    ▪ {nom_deduit} - [Nom du produit]]

    --------------------------------------------------
    🚀 4. POINTS FORTS & ATOUTS (D'APRÈS LES ÉCHANGES)
    --------------------------------------------------
    [Synthétise les avantages ou les points clés discutés ou trouvés sous forme de puces avec le symbole '▪']

    --------------------------------------------------
    💬 5. SYNTHÈSE DES DISCUSSIONS
    --------------------------------------------------
    [Fais un résumé condensé et clair des questions posées par l'utilisateur et des réponses obtenues. N'affiche pas les questions brutes, écris un paragraphe fluide.]
    
    --------------------------------------------------
    📂 6. DOCUMENTS TECHNIQUES RATTACHÉS
    --------------------------------------------------
    [Affiche exactement cette liste de fichiers pour récapituler les PDFs enregistrés :]
    {pdfs_texte}
    
    --------------------------------------------------
    📝 7. TRANSCRIPTION BRUTE DES ÉCHANGES
    --------------------------------------------------
    Voici les questions posées lors de cette session et les réponses fournies :
    
    {echanges_texte}
    
    **************************************************
    * FIN DE LA FICHE FOURNISSEUR          *
    **************************************************
    
    Rédige l'intégralité de cette fiche en {langue_cible}. Ne laisse aucune instruction entre crochets dans le résultat final.
    """
    
    contexte_site = memory.retrieve("Présentation générale de l'entreprise, catalogue de produits, services et solutions", k=8)
    
    try:
        reponse_ia = llm.invoke(f"Contexte du site :\n{contexte_site}\n\n{prompt_fiche}")
        fiche_texte = reponse_ia.content
        
        nom_fichier = f"fiche_fournisseur_{nom_deduit.lower()}.txt"
        fiche_path = os.path.join(pdf_dir, nom_fichier)
        
        with open(fiche_path, 'w', encoding='utf-8') as f:
            f.write(fiche_texte)
        print(f"✅ Fiche créée avec succès : {nom_fichier}")
        
    except Exception as e:
        print(f"❌ Erreur lors de la génération de la fiche : {e}")


async def main():
    llm = ChatOllama(model=OLLAMA_MODEL, temperature=0.2)
    
    while True: 
        print("\n" + "="*50)
        print("💼 ASSISTANT ACHATS PROFESSIONNEL")
        print("="*50)
        
        url = input("\n🌐 Entrez l'URL du fournisseur à analyser : ").strip()
        if not url: break
            
        max_p = input("🔢 Combien de pages max à analyser ? (Par défaut: 20) : ")
        max_pages = int(max_p) if max_p.isdigit() else 20
        
        documents, current_pdf_dir = await collect_data_pro(url, max_pages)
        
        if not documents:
            print("❌ Aucune donnée collectée. Veuillez réessayer.")
            continue
            
        liste_pdfs = []
        if os.path.exists(current_pdf_dir):
            liste_pdfs = [f for f in os.listdir(current_pdf_dir) if f.endswith(".pdf")]
            
        memory = LightMemory()
        memory.add_texts([doc["text"] for doc in documents])
        
        print("\n🎉 Analyse terminée ! Les documents sont rangés.")
        print("-" * 35)
        print("📂 Liste des fichiers PDF récupérés :")
        if liste_pdfs:
            for pdf in liste_pdfs:
                print(f"  ▪ {pdf}")
        else:
            print("  ▪ Aucun document PDF n'a été collecté.")
        print("-" * 35)
        
        print("\n👉 Tapez 'quitter' pour fermer le programme.")
        print("👉 Tapez 'changer fournisseur' pour analyser un autre site.")
        print("👉 Tapez 'lire pdf' pour forcer la lecture des PDF.")
        print("👉 Tapez 'visiter [URL] [nombre_pages]' pour analyser un lien spécifique.")
        
        derniere_question = ""
        changement_fournisseur = False
        historique_chat = [] 
        
        while True:
            question = input("\n❓ Votre question : ").strip()
            
            # Application de lower() pour rendre les commandes insensibles à la casse
            question_cmd = question.lower()
            
            if question_cmd == 'quitter': 
                generer_fiche_fournisseur(memory, historique_chat, current_pdf_dir, url, llm, liste_pdfs)
                print("Au revoir !")
                return 
                
            elif question_cmd == 'changer fournisseur':
                generer_fiche_fournisseur(memory, historique_chat, current_pdf_dir, url, llm, liste_pdfs)
                changement_fournisseur = True
                break 
                
            elif question_cmd == 'lire pdf':
                succes = trigger_pdf_reading(memory, current_pdf_dir)
                if succes:
                    print("👍 Les PDFs ont bien été intégrés. Tu peux poser tes questions.")
                
            elif question_cmd.startswith('visiter '):
                # On sépare la commande originale (en préservant la casse de l'URL)
                parties = question.strip().split()
                
                url_specifique = parties[1] if len(parties) > 1 else ""
                nb_pages_specifiques = 1
                
                # Si l'utilisateur a précisé un chiffre
                if len(parties) > 2 and parties[-1].isdigit():
                    nb_pages_specifiques = int(parties[-1])
                    url_specifique = " ".join(parties[1:-1])
                
                print(f"🌐 Analyse approfondie ({nb_pages_specifiques} page(s) max) sur : {url_specifique}")
                
                try:
                    docs_sup, _ = await collect_data_pro(url_specifique, nb_pages_specifiques)
                    
                    if docs_sup:
                        memory.add_texts([doc["text"] for doc in docs_sup])
                        print(f"✅ {len(docs_sup)} nouvelle(s) page(s) ajoutée(s) à la mémoire !")
                        
                        if os.path.exists(current_pdf_dir):
                            liste_pdfs = [f for f in os.listdir(current_pdf_dir) if f.endswith(".pdf")]
                    else:
                        print("❌ Impossible d'extraire de nouvelles données.")
                        
                except Exception as e:
                    print(f"❌ Erreur lors de la visite du lien : {e}")
                
            elif question:
                derniere_question = question
                print("⏳ L'IA réfléchit...")
                reponse = ask_question(question, memory, llm)
                print(f"\n🤖 Réponse :\n{reponse}")
                historique_chat.append((question, reponse))
                
        if changement_fournisseur: continue


if __name__ == "__main__":
    asyncio.run(main())