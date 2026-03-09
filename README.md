# 🔥 Achadinhos da Li - Content Creator 2025

Agente autônomo de criação de conteúdo para Instagram e TikTok, especializado em achadinhos da Shopee e AliExpress. O sistema utiliza IA (Groq, OpenAI, ElevenLabs) para minerar ofertas, gerar roteiros virais, narrar com voz ultra-realista e publicar automaticamente no Instagram.

## 🚀 Funcionalidades

-   **Mineiração Inteligente**: Busca as melhores ofertas filtradas por desconto e relevância.
-   **Suporte Multi-Plataforma**: Integração oficial e via scraping para Shopee e AliExpress.
-   **Geração de Vídeos (Reels & Stories)**:
    -   **Reels**: Foco em engajamento viral, legendas SEO robustas e carrosséis de imagens/vídeos.
    -   **Stories**: Foco em conversão, com anúncios de preço dinâmicos e CTA direto.
-   **Narração Premium**: Integração com ElevenLabs para vozes humanas cativantes.
-   **Publicação Automática**: Envio direto para o Instagram via Graph API (Meta).
-   **Backup em Nuvem**: Salvamento automático dos vídeos gerados no Google Drive.

## 🛠️ Tecnologias

-   **Backend**: Python, FastAPI, Uvicorn.
-   **IA/ML**: Groq (Llama 3), OpenAI (GPT-4), ElevenLabs (Vocal).
-   **Media Engine**: FFmpeg, MoviePy.
-   **Scraping**: Playwright Stealth.
-   **Database**: SQLite/PostgreSQL (via API VPS).

## 📁 Estrutura do Projeto

-   `backend/`: Lógica central, serviços de API e integrações.
-   `frontend/`: Interface de administração e revisão de vídeos.
-   `assets/`: Intros, músicas de fundo e modelos de fonte.
-   `config/`: Configurações de roteiro e prompts.
-   `testes/`: Conjunto de testes para validação de APIs e scrapers.

## ⚙️ Configuração

1. Clone o repositório.
2. Crie um arquivo `.env` baseado no exemplo abaixo:
   ```env
   OPENAI_API_KEY=sua_chave
   GROQ_API_KEY=sua_chave
   ELEVENLABS_API_KEY=sua_chave
   ID_APLICATIVO=seu_id_instagram
   INSTAGRAM_TOKEM=seu_token_instagram
   MELI_SECRET=war_token_vps
   VPS_UPLOAD_URL=url_vps
   ```
3. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```
4. Inicie o servidor:
   ```bash
   python main.py
   ```

## 📄 Licença

Este projeto é de uso privado. Todos os direitos reservados.
