# Manual commands for Git Bash (Windows)

Run from the FinRAG repository root. Review license/ignore rules before running commands.

```bash
mkdir -p research/_external_repos
```

Add this line to `.gitignore` after reviewing existing rules:

```gitignore
# Local-only external research clones; never commit these repositories
research/_external_repos/
research/papers/source_pdfs/*.pdf
```

Then shallow-clone references:

```bash
git clone --depth 1 https://github.com/phaihoang17/AI_financial.git research/_external_repos/AI_financial
git clone --depth 1 https://github.com/YuhangWuAI/tablerag.git research/_external_repos/yuhangwu-tablerag
git clone --depth 1 https://github.com/jacobyhsi/TabRAG.git research/_external_repos/jacobyhsi-TabRAG
git clone --depth 1 https://github.com/ThanhDatVN/vinumqa-numerical-reasoning.git research/_external_repos/vinumqa-numerical-reasoning
git clone --depth 1 https://github.com/AI-Application-and-Integration-Lab/FinLongDocQA.git research/_external_repos/FinLongDocQA
git clone --depth 1 https://github.com/lisun-ai/DocAgent.git research/_external_repos/DocAgent
```

Record the checked-out commit of each clone:

```bash
for d in research/_external_repos/*; do
  if [ -d "$d/.git" ]; then
    printf '%s ' "$d"
    git -C "$d" rev-parse HEAD
  fi
done
```

These commands only clone code; they do not install dependencies or run it. Keep the clones ignored and do not commit them.
