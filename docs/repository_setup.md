# Создание удалённого репозитория на GitHub

1. Создать пустой репозиторий `group-discount-optimization` на GitHub. Не добавлять начальные README, лицензию или `.gitignore`, если они уже присутствуют в локальном проекте.
2. Распаковать архив и открыть терминал в каталоге `group-discount-optimization`.
3. Выполнить команды:

```bash
git init
git add .
git commit -m "Prepare project structure and mathematical model"
git branch -M main
git remote add origin https://github.com/alenest/group-discount-optimization.git
git push -u origin main
```

Если владелец или имя репозитория отличаются, скорректировать URL `origin`.

Старый `knapsack-metaheuristics` рекомендуется оставить отдельным репозиторием: новая задача имеет другую математическую постановку и свои экспериментальные данные.
