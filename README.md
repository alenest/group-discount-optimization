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

В `data.npz` у каждой группы есть собственные массивы: например, `group_001_weights` и `group_001_profits`. В `meta.json` указаны ключи этих массивов, размер группы, её скидка на вес и бонус к полезности. Размеры всех групп в сумме дают `n` — общее число предметов экземпляра.

В `meta.json` также хранятся вместимость рюкзака, точное количество выбираемых предметов `target_item_count` (`Q`), число групп и seed генератора. Загрузчик предоставляет и плоские `instance.weights`, `instance.profits`, `instance.group_ids` для алгоритмов, которым удобнее общий массив, но на диске данные каждой группы хранятся отдельно.

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

| Общее число предметов `n` | Число экземпляров |
|---:|---:|
| 10 | 5 |
| 20 | 5 |
| 50 | 5 |
| 1 000 | 5 |
| 5 000 | 5 |

`Q` и число групп выбираются отдельно для каждого экземпляра, поэтому их значения могут различаться даже при одинаковом `n`. По умолчанию `Q` лежит в диапазоне от 1 до `n`, а число групп — от 2 до 5.

## Загрузка экземпляра

```python
from group_discount_optimization.instance import load_instance

instance = load_instance("data/n_50/instance_001")
print(instance.capacity)
print(instance.target_item_count)
for group in instance.groups:
    print(group.group_id, group.weights, group.profits)
    print(group.weight_discount_percent, group.utility_bonus_percent)

# При необходимости доступны и плоские массивы для алгоритмов:
print(instance.weights)
print(instance.profits)
print(instance.group_ids)
```

Алгоритм может также напрямую открыть массивы через NumPy:

```python
import numpy as np

with np.load("data/n_50/instance_001/data.npz") as data:
    weights_group_1 = data["group_001_weights"]
    profits_group_1 = data["group_001_profits"]
```

## Генератор

Генератор создаёт именно файлы `data.npz` и `meta.json`, а не JSON-конфигурацию для последующего создания данных. По умолчанию он создаёт пять экземпляров размеров 10, 20, 50, 1 000 и 5 000 предметов в `data/`:

```bash
python -m group_discount_optimization.generator --seed 42
```

Чтобы создать другой набор в отдельном каталоге:

```bash
python -m group_discount_optimization.generator --output data/experiment --sizes 10 100 1000 --instances-per-size 5 --min-groups 2 --max-groups 6 --q-min 1 --q-max 100 --seed 123
```

`--sizes` задаёт общее число предметов во всём экземпляре, а не число предметов в каждой группе. `--min-groups` и `--max-groups` задают диапазон числа групп. `--q-min` и `--q-max` задают диапазон `Q`; если `--q-max` не передан, он равен `n` для каждого экземпляра.

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
