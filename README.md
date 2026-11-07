# Group Discount Optimization

Реализация задачи выбора ровно `Q` предметов в один рюкзак с пороговыми групповыми скидками и бонусами. Предметы могут входить в группы, а группа меняет учитываемый вес и полезность только после достижения порога.

## Математическая модель

Есть один рюкзак вместимости `W_max` и `n` уникальных неделимых предметов. Нужно выбрать ровно `Q` различных предметов с максимальной суммарной полезностью так, чтобы учитываемый вес не превышал `W_max`.

Каждый предмет `i` имеет исходный вес `w_i` и полезность `u_i`. Предмет может принадлежать не более чем одной группе. Группа `k` задаёт порог `t_k`, скидку на вес `d_k` в процентах и бонус к полезности `b_k` в процентах.

Если из группы `k` выбрано `s_k` предметов, индикатор активации равен

```text
y_k = 1, если s_k >= t_k,
y_k = 0, если s_k < t_k.
```

Для предмета из группы `k` учитываемые вес и полезность равны

```text
w~_i = w_i * (1 - d_k * y_k / 100),
u~_i = u_i * (1 + b_k * y_k / 100).
```

Оба эффекта включаются одновременно и применяются ко всем выбранным предметам группы, а не только к предметам сверх порога. Для предметов вне групп `w~_i = w_i` и `u~_i = u_i`.

Задача имеет вид

```text
max  sum u~_i * x_i
при  sum x_i = Q,
     sum w~_i * x_i <= W_max,
     x_i in {0, 1}.
```

Лимит веса и требование выбрать ровно `Q` предметов общие для всех групп. Подробная постановка и линеаризация порога описаны в [`docs/mathematical_model.md`](docs/mathematical_model.md).

## Состав репозитория

- модель предмета, группы и экземпляра, загрузчик `load_instance`;
- единый оценщик `evaluate_selection`, который применяет пороговые правила;
- генератор экземпляров с `manifest.csv` и контрольными суммами;
- полный перебор, жадные алгоритмы и решения без групповых эффектов;
- запуск экспериментов, сводные таблицы и графики;
- тесты модели, загрузчика, алгоритмов, генератора и анализа.

## Установка

Требуется Python 3.11 или новее.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

В Windows окружение активируется командой `.venv\Scripts\activate` или `.venv\Scripts\Activate.ps1`.

## Быстрый старт

```python
from group_discount_optimization import evaluate_selection, load_instance
from group_discount_optimization.algorithms import solve_greedy_group_aware

instance = load_instance("data/n_20/instance_001")
result = solve_greedy_group_aware(instance)

print("Выбрано:", result.selected_item_ids)
print("Вес:", result.total_weight, "из", instance.capacity)
print("Полезность:", result.total_utility)
print("Допустимо:", result.feasible)
print("Активные группы:", result.active_group_ids)
```

Все алгоритмы возвращают набор ID, который можно независимо проверить через `evaluate_selection(instance, selected_ids)`. Пороговые правила реализованы только в оценщике, поэтому алгоритмы не дублируют расчёт скидок и бонусов.

## Данные

В репозитории есть три набора:

- `data/` содержит 12 фиксированных экземпляров, по одному на размер `n = 12..100`, и контрольные суммы;
- `data_repeated/` содержит по 10 экземпляров на размер для усреднения результатов;
- `data_repeated_2425/` содержит дополнительные экземпляры для `n = 24` и `n = 25`.

Параметры генерации: `Q = 10`, 2 или 3 непересекающиеся группы, порог 4 или 5 предметов, скидка на вес 25-50 процентов, бонус к полезности 0-50 процентов, исходные веса и полезности от 1 до 100. В каждом экземпляре есть предметы вне групп.

Экземпляр хранится в каталоге `n_<n>/instance_<номер>/` и состоит из двух файлов:

- `data.npz`: массивы `item_ids`, `weights`, `utilities` и списки ID для каждой группы;
- `meta.json`: размеры, группы, пороги, скидки, бонусы, seed и контрольные распределения.

Каждый предмет хранится в общих массивах один раз. Списки групп не пересекаются, а ID, которых нет ни в одном списке, принадлежат предметам вне групп. Не следует путать `item_count` (размер группы) и `min_selected_for_discount` (порог активации).

Файл `manifest.csv` содержит индекс экземпляров, а `checksums.sha256` фиксирует контрольные суммы файлов набора. Формат подробно описан в [`docs/data_generation.md`](docs/data_generation.md).

## Алгоритмы

- `solve_exhaustive` перебирает все `C(n, Q)` наборов и находит точный оптимум. Применим на малых `n`.
- `solve_greedy_ratio` сортирует предметы по отношению `u_i / w_i` и добавляет их с проверкой веса.
- `solve_greedy_group_aware` учитывает группы: сравнивает добавление одного предмета и группового пакета до порога, а также перебирает распределение `Q` мест по группам.
- `solve_exhaustive_no_groups` и `solve_greedy_no_groups` решают задачу без групповых эффектов и служат точкой сравнения.

## Эксперименты

Запуск методов на наборе:

```bash
python -m group_discount_optimization.experiment --data data --output reports --exhaustive-max-n 25
```

Построение сводной таблицы и графиков:

```bash
python -m group_discount_optimization.analysis --results reports/results.csv --output reports
```

Несколько файлов результатов можно объединить одной командой:

```bash
python -m group_discount_optimization.analysis \
    --results reports/repeated_main/results.csv reports/repeated_2425/results.csv \
    --output reports \
    --merge-output reports/results.csv
```

Текущие таблицы, графики и выводы находятся в [`reports/report.md`](reports/report.md).

## Структура проекта

```text
.
├── data/                         фиксированные экземпляры
├── data_repeated/                экземпляры для повторных прогонов
├── data_repeated_2425/           дополнительные экземпляры для n = 24, 25
├── docs/                         модель, формат данных, планы и тезис
├── reports/                      результаты, сводки и графики
├── src/group_discount_optimization/
│   ├── instance.py               модель и загрузчик
│   ├── evaluation.py             оценщик решения
│   ├── generator.py              генератор экземпляров
│   ├── experiment.py             запуск экспериментов
│   ├── analysis.py               сводки и графики
│   └── algorithms/               полный перебор, жадные методы, базовые решения
├── tests/                        автоматические проверки
├── pyproject.toml
└── README.md
```

## Генерация данных

Стандартная команда создаёт или перезаписывает набор в `data/`:

```bash
python -m group_discount_optimization.generator --seed 42
```

Для отдельного набора укажите каталог и параметры:

```bash
python -m group_discount_optimization.generator \
    --output data/experiment \
    --sizes 15 20 30 \
    --instances-per-size 2 \
    --q 10 \
    --seed 123
```

Одинаковые параметры и seed дают одинаковые файлы.

## Тесты

```bash
python -m pytest
```

Тесты проверяют пороговые правила, ограничения задачи, загрузчик, генератор, алгоритмы, анализ результатов и неизменность сохранённого набора данных.

## Документация

- [`docs/mathematical_model.md`](docs/mathematical_model.md): постановка задачи и формулы;
- [`docs/data_generation.md`](docs/data_generation.md): формат данных и генератор;
- [`docs/algorithm_plan.md`](docs/algorithm_plan.md): описание алгоритмов;
- [`docs/thesis.md`](docs/thesis.md): текст тезиса, [`docs/thesis.docx`](docs/thesis.docx) и [`docs/thesis.pdf`](docs/thesis.pdf): готовые файлы;
- [`reports/report.md`](reports/report.md): результаты экспериментов.
