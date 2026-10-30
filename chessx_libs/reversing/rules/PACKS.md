# Pacotes de regras opcionais (triagem #25)

O ChessX **embute só** as regras `cx.*` (MIT) em `rules/builtin/`. Nada é baixado
automaticamente: a triagem nunca faz rede. Para usar regras de terceiros, baixe
**você mesmo**, num diretório fora do repositório, e aponte `CHESSX_TRIAGE_RULES`
(requer `yara-python` para arquivos `.yar`).

| Pacote | Licença (verificada 2026-10-30) | Política |
|---|---|---|
| reversinglabs/reversinglabs-yara-rules | MIT (© 2020 ReversingLabs) | opcional; mantenha o LICENSE junto (NOTICE) |
| Neo23x0/signature-base | Detection Rule License 1.1 | opcional; o campo `author` do meta é preservado em `matched[].author` (exigência da DRL) |
| Yara-Rules/rules | GPL-2.0 | só via caminho local do usuário; nunca copiar para o repo |
| elastic/protections-artifacts | Elastic License 2.0 | evitado: diretórios com LICENSE ELv2 são ignorados |
| InQuest/awesome-yara | CC BY 4.0 (é só uma lista) | apenas índice para descoberta; não é pacote |

Exemplo (manual, fora do ChessX):

```sh
git clone --depth 1 https://github.com/reversinglabs/reversinglabs-yara-rules ~/yara/rl
git clone --depth 1 https://github.com/Neo23x0/signature-base ~/yara/sigbase
export CHESSX_TRIAGE_RULES=~/yara/rl/yara/ransomware:~/yara/sigbase/yara
python -m chessx_libs.reversing.triage amostra.bin --json
```

Só os arquivos diretamente dentro de cada diretório listado são carregados (sem recursão,
sem includes, sem escapar por symlink). `engines.packs` no relatório mostra diretório,
licença detectada e número de arquivos.
