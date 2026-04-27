# Processador de DTFs — Tecnosup

App Windows para preparar imagens para impressão **DTF** (Direct to Film).
Remove o fundo branco/papel das imagens, deixa o fundo transparente e mantém apenas a arte para a impressora DTF — sem precisar abrir Photoshop ou repetir manualmente cada arquivo.

![Tecnosup](assets/logo.png)

---

## ✨ O que o app faz

Pega uma pasta com várias imagens (JPG, JPEG, PNG, PDF) e processa todas em lote:

- **Remove o fundo branco** automaticamente, deixando transparente
- **Limpa pontinhos e halos** ao redor dos traços
- **Reforça os traços** apagados de canetinha quando precisa
- **Converte PDFs** automaticamente em PNG (DPI 200/300/600 selecionável)
- Salva os PNGs prontos numa pasta `nome-da-pasta-saida/` ao lado da original

### 3 modos de processamento

| Modo | Quando usar |
|---|---|
| **Cartoon / IA** | Arte com fundo branco "limpo" (gerada por IA, vetorizada, cartoon) onde o branco interno é importante |
| **Escaneado** | Desenho escaneado, PDF, folha sulfite — remove o branco do papel |
| **Papel sujo** | Desenho escaneado em papel granulado/manchado — remove sujeira e reforça traços |

---

## 📦 Para usuários finais (instalar e usar)

1. Baixe o instalador: **`Setup_Tecnosup_DTF_X.X.X.exe`**
2. Duplo-clique. Se aparecer aviso azul do Windows SmartScreen, clique em **"Mais informações" → "Executar mesmo assim"**
3. Avance no wizard → **Instalar**
4. O atalho **"Processador de DTFs"** vai aparecer na área de trabalho e no menu iniciar
5. Pronto. Não precisa instalar Python, ImageMagick ou nada mais — tudo já vem embutido

### Como usar
1. Abra o app pelo atalho
2. Clique em **"Selecionar pasta"** e escolha a pasta com suas imagens
3. Escolha o modo (Cartoon / Escaneado / Papel sujo) e ajuste as opções
4. Clique em **"Iniciar processamento"**
5. Quando terminar, clique em **"Abrir pasta de saída"** — os PNGs prontos estarão lá

---

## 🛠️ Para desenvolvedores (build a partir do código)

### Pré-requisitos
- **Windows 10/11**
- **Python 3.10+** (testado com 3.12) — https://www.python.org/downloads/windows/
- **ImageMagick portable** — baixe `ImageMagick-X.X.X-portable-Q16-x64.zip` em https://imagemagick.org/script/download.php#windows e extraia em `vendor/ImageMagick/` de modo que `vendor/ImageMagick/magick.exe` exista
- **Inno Setup 6** (só pra gerar o instalador) — https://jrsoftware.org/isdl.php  ou `winget install JRSoftware.InnoSetup`

### Rodar em modo dev
```bash
# Instala as dependências e abre o app
run.bat
```
Ou sem janela de CMD: duplo-clique em `run.vbs`.

### Gerar o EXE + instalador
```bash
build_exe.bat
```
Isso vai:
1. Instalar as deps Python
2. Empacotar com PyInstaller → `dist/Processador de DTFs/`
3. Copiar o ImageMagick portable pra dentro do build
4. Compilar o instalador final com Inno Setup → `installer_output/Setup_Tecnosup_DTF_X.X.X.exe`

Pra atualizar a versão, edite a linha `#define AppVersion` em [installer.iss](installer.iss) antes de buildar.

---

## 📁 Estrutura do projeto

```
dtf_processor/
├── main.py                  # entrypoint (single-instance check + lança App)
├── requirements.txt
├── build.spec               # config do PyInstaller (splash, ícone, datas)
├── build_exe.bat            # build completo (PyInstaller + Inno Setup)
├── installer.iss            # script Inno Setup
├── run.bat / run.vbs        # rodar em modo dev
├── README.md
├── assets/
│   ├── logo.png             # logo Tecnosup (header do app)
│   ├── logo.ico             # ícone do .exe e instalador
│   └── splash.png           # tela de carregamento
├── src/
│   ├── app.py               # UI (CustomTkinter)
│   ├── processor.py         # lógica de processamento em thread
│   ├── magick.py            # detecção/wrapper do ImageMagick
│   └── utils.py             # helpers (paths, contagem, saída)
└── vendor/
    └── ImageMagick/         # portable (gitignored — baixe e extraia aqui)
```

---

## 🔧 Stack técnica

- **CustomTkinter** — UI moderna em tema escuro
- **PyMuPDF (fitz)** — rasteriza PDFs em PNG (sem depender de Ghostscript)
- **Pillow** — leitura/manipulação de imagens, geração do `.ico`
- **ImageMagick** (binário externo) — preserva pixel-a-pixel a lógica do `.bat` original (`-floodfill`, `-fuzz`, `-morphology`, `-level`, `-threshold`)
- **PyInstaller** — empacota tudo num único `.exe` portable + splash screen
- **Inno Setup** — instalador profissional Windows (atalhos, desinstalador, "Adicionar/Remover Programas")

> **Por que ImageMagick em vez de Pillow puro?** O `.bat` original usa `-floodfill +0+0` com `-fuzz` e `-morphology Open Diamond:1`. Reimplementar em Pillow produz resultado **visualmente diferente**. Mantendo o ImageMagick, garantimos pixel-identidade com o resultado já aprovado.

---

## ⚙️ Comandos ImageMagick (preservados do `.bat` original)

- **Cartoon / IA**
  `-fuzz F% -alpha set -channel rgba -fill none -floodfill +0+0 white [-channel rgba -fill "rgb(252,252,252)" -opaque "rgb(255,255,255)"]`
- **Escaneado**
  `[-level L%,100%] -alpha set -fuzz F% -transparent white [-channel A -threshold 10% -morphology Open Diamond:1 +channel]`
- **Papel sujo**
  `-level L%,100% -alpha set -fuzz F% -transparent white -channel A -threshold 12% -morphology Open Diamond:1 +channel`

---

## 🛡️ Antivírus e SmartScreen

Apps PyInstaller sem assinatura digital às vezes disparam falso-positivo:
- ✅ UPX desligado no [build.spec](build.spec) (principal causa)
- 💡 Pra eliminar de vez, submeta o instalador como falso-positivo em https://www.microsoft.com/wdsi/filesubmission (whitelist global em 1-3 dias)
- 💼 Solução definitiva: **Code Signing Certificate** (~R$1500-2500/ano)

Em ambiente corporativo controlado, adicionar a pasta de instalação como exceção nos antivírus dos PCs também resolve.

---

## 📝 Licença

Uso interno Tecnosup. ImageMagick é distribuído sob a [ImageMagick License](https://imagemagick.org/script/license.php).

---

**Desenvolvido por Tecnosup** — Suporte Tecnológico
