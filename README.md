# Group Discount Optimization

Набор **готовых сырых экземпляров** задачи выбора предметов с групповыми скидками и бонусами, загрузчик и генератор этих экземпляров. При запуске алгоритмов использовать уже сохранённые данные из `data/`: генератор повторно запускать не нужно.

## Формат данных

Структура каждого экземпляра повторяет подход старого проекта: отдельный каталог с `data.npz` и `meta.json`.

```text
data/
├── manifest.csv
├── n_10/
│   ├── instance_001/
│   │   ├── data.npz
│   │   └── meta.json
│   └── ...
├── n_20/
├── n_50/
├── n_1000/
└── n_5000/
```

В `data.npz` хранятся массивы одинаковой длины:

- `weights` — исходные целочисленные веса предметов;
- `profits` — исходная полезность предметов (имя сохранено по аналогии со старым репозиторием);
- `group_ids` — ID группы каждого предмета. Элемент с индексом `i` во всех трёх массивах описывает один и тот же предмет.

В `meta.json` хранятся вместимость рюкзака, требуемое количество предметов `target_item_count`, число групп, начальное значение генератора и параметры каждой группы: ID, скидка на вес, бонус к полезности и число предметов. Так исходные массивы и метаданные хранятся раздельно, как в исходном проекте.

## Математическая модель

Имеется один рюкзак вместимости \(W_{\max}\) и \(n\) неделимых предметов, распределённых между \(K\) непересекающимися группами. Нужно выбрать ровно \(Q\) предметов. У предмета \(i\) заданы исходные вес \(w_i\) и полезность \(u_i\). Для группы \(k\) заданы скидка на вес \(d_k\) и бонус к полезности \(b_k\), выраженные в процентах:

\[
\widetilde w_i=w_i\left(1-\frac{d_{g_i}}{100}\right),\qquad
\widetilde u_i=u_i\left(1+\frac{b_{g_i}}{100}\right),
\]

где \(g_i\) — группа, которой принадлежит предмет \(i\). При бинарной переменной \(x_i\), равной 1 для выбранного предмета и 0 в противном случае, модель имеет вид:

\[
\begin{aligned}
\max\quad & U=\sum_{i=1}^{n}\widetilde u_i x_i,\\
\text{при условиях}\quad
& \sum_{i=1}^{n}x_i=Q,\\
& \sum_{i=1}^{n}\widetilde w_i x_i\le W_{\max},\\
& x_i\in\{0,1\},\quad i=1,\ldots,n.
\end{aligned}
\]

## Готовый набор

В репозитории находятся 25 готовых экземпляров — по пять для каждого размера. Их можно читать напрямую, без генерации:

| Число предметов `n` | Выбрать ровно `Q` | Экземпляров |
|---:|---:|---:|
| 10 | 5 | 5 |
| 20 | 10 | 5 |
| 50 | 10 | 5 |
| 1 000 | 10 | 5 |
| 5 000 | 10 | 5 |

## Загрузка экземпляра

```python
from group_discount_optimization.instance import load_instance

instance = load_instance("data/n_50/instance_001")
print(instance.weights)
print(instance.profits)
print(instance.group_ids)
print(instance.capacity)
print(instance.target_item_count)
for group in instance.groups:
    print(group.group_id, group.weight_discount_percent, group.utility_bonus_percent)
```

Алгоритм может также напрямую открыть массивы через NumPy:

```python
import numpy as np

with np.load("data/n_50/instance_001/data.npz") as data:
    weights = data["weights"]
    profits = data["profits"]
    group_ids = data["group_ids"]
```

## Генератор

Генератор создаёт именно файлы `data.npz` и `meta.json`, а не JSON-конфигурацию для последующего создания данных. По умолчанию он создаёт пять экземпляров размеров 10, 20, 50, 1 000 и 5 000 предметов в `data/`:

```bash
python -m group_discount_optimization.generator --seed 42
```

Чтобы создать другой набор в отдельном каталоге:

```bash
python -m group_discount_optimization.generator --output data/experiment --sizes 10 100 1000 --instances-per-size 3 --groups 3 --seed 123
```

Одинаковые параметры и `--seed` дают одинаковые массивы и метаданные. Не запускай генератор перед каждым тестом: обычные тестовые запуски должны использовать уже сохранённые экземпляры.

## Установка и тесты

Требуется Python 3.11 или новее.

```bash
python -m venv venv
source venv/Scripts/activate
python -m pip install -e ".[dev]"
python -m pytest
```

В Git Bash на Windows команда `source venv/Scripts/activate` активирует Windows-виртуальное окружение.
