# Guardrail obrigatorio: worktrees

Este diretorio (`github-main/`) e compartilhado por multiplas sessoes Claude Code
concorrentes. Trocar de branch ou rodar `git reset`/`git stash` aqui ja causou
perda/colisao de trabalho de outra sessao mais de uma vez (2026-07-14, 2026-08-25).

**Regra:** nunca faca `git checkout`/`git switch` de branch nem `git reset --hard`/
`git stash` diretamente neste diretorio para trabalho de mais de um comando. Para
qualquer tarefa que exija editar arquivos e trocar de branch, crie um worktree
dedicado primeiro:

```
git worktree add ../wt-<nome-curto-da-tarefa> -b <branch-da-tarefa> main
```

Trabalhe dentro desse worktree, commit e push por PR normalmente, depois:

```
git worktree remove ../wt-<nome-curto-da-tarefa>
```

Leituras (`git log`, `git status`, `git diff`, `git fetch`) no diretorio principal
sao seguras. Push de branch sem checkout local tambem e seguro
(`git push origin <local-branch>:<remote-branch>`).

`main` neste repositorio e protegida no GitHub (push direto e recusado) — todo
merge exige Pull Request.
