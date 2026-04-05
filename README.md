# 💼 AI-Powered Purchasing & Sourcing Assistant

An intelligent web scraping and data extraction tool tailored for supply chain and procurement professionals. This application crawls supplier websites, downloads technical PDFs, and uses a local Large Language Model (LLM) to answer questions and generate structured supplier summary sheets.

---

## 🚀 Key Features

* **Smart Crawling:** Powered by `Crawl4AI` to bypass popups, navigate internal links, and extract clean markdown text.
* **Dynamic Deep Dive:** Use the `visiter [URL] [number_of_pages]` command to analyze specific pages or product catalogs on the fly without restarting the session.
* **On-Demand PDF Ingestion:** Automatically detects and downloads supplier PDFs (catalogs, data sheets) to a local folder and indexes them for the LLM.
* **Adaptive Language Detection:** The assistant automatically responds and builds the final vendor sheet in the same language as your questions (French or English).
* **Local vector storage:** Uses a lightweight TF-IDF memory to find the most relevant context across crawled pages and PDFs.

---

## 🛠️ Tech Stack

* **Crawler:** [Crawl4AI](https://github.com/unclecode/crawl4ai)
* **LLM Orchestration:** `LangChain`
* **Local LLM:** `Ollama` running `qwen2.5:1.5b` (Fast and efficient for local data processing)
* **Vectorization & Search:** `scikit-learn` (TF-IDF & Cosine Similarity)

---

## ⚙️ Installation & Setup

### 1. Clone the repository
```bash
git clone [https://github.com/saggadiamine-netizen/assistant-achats-ia.git](https://github.com/saggadiamine-netizen/assistant-achats-ia.git)
cd assistant-achats-ia
