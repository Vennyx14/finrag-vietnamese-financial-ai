# Repository Review — jacobyhsi/TabRAG

- **URL:** https://github.com/jacobyhsi/TabRAG
- **Audit status:** Initial reference note; pin the current commit and inspect source/tests before implementation.
- **License caution:** The prior review identified CC BY-NC 4.0; re-check the exact license file and terms at the selected commit before any code reuse. Noncommercial restrictions can matter for a portfolio or future commercial project.

## Candidate areas to inspect

The prior review described structured representation/parsing for tabular documents and a vision-language/embedding stack. Verify exact models, preprocessing, and the required GPU/CPU resources from source and configuration.

## FinRAG application

Study table layout preservation and structured parsing concepts. Reimplement a lightweight equivalent if useful, rather than importing the full stack.

## Hardware and licensing

The user's RTX 3050 has limited VRAM (approximately 4 GB based on current project context). A large VLM/embedding pipeline may not fit or may require quantization/offloading. Benchmark memory and latency before considering it. Do not assume the code license also covers model weights or datasets.
