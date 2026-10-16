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

### `data.npz` (формат v2)

Для каждой группы в файле хранятся **два отдельных массива**, а не плоские `weights`/`profits`/`group_ids`:

- `group_001_weights`, `group_001_profits` — вес и полезность предметов группы 1;
- `group_002_weights`, `group_002_profits` — то же для группы 2;
- и так далее.

Ключи записаны в `meta.json` в полях `weights_key` и `profits_key` каждой группы — используйте их вместо жёстко зашитых имён.

### `meta.json`

Хранятся:

- `format_version` — версия формата (сейчас `2`);
- `n` — общее число предметов;
- `target_item_count` — требуемое число выбираемых предметов $Q$;
- `group_count` — число групп $K$;
- `capacity` — вместимость рюкзака $W_{\max}$;
- `seed` — seed генератора;
- `groups` — список групп, каждая с полями `id`, `weight_discount_percent`, `utility_bonus_percent`, `item_count`, `weights_key`, `profits_key`;
- `weight_range`, `utility_range`, `discount_percent_range`, `bonus_percent_range` — заявленные диапазоны генерации.

## Математическая модель

Имеется один рюкзак вместимости $W_{\max}$ и $n$ неделимых предметов, распределённых между $K$ непересекающимися группами. Нужно выбрать ровно $Q$ предметов. У предмета $i$ заданы исходные вес $w_i$ и полезность $u_i$. Для группы $k$ заданы скидка на вес $d_k$ и бонус к полезности $b_k$, выраженные в процентах:

```math
\widetilde{w}_i = w_i \left( 1 - \frac{d_{g_i}}{100} \right),
\qquad
\widetilde{u}_i = u_i \left( 1 + \frac{b_{g_i}}{100} \right),
```

где $g_i$ — группа, которой принадлежит предмет $i$. При бинарной переменной $x_i$, равной 1 для выбранного предмета и 0 в противном случае, модель имеет вид:

```math
\begin{aligned}
\max \quad & U = \sum_{i=1}^{n} \widetilde{u}_i \, x_i, \\
\text{при условиях} \quad
& \sum_{i=1}^{n} x_i = Q, \\
& \sum_{i=1}^{n} \widetilde{w}_i \, x_i \leq W_{\max}, \\
& x_i \in \{0, 1\}, \quad i = 1, \ldots, n.
\end{aligned}
```

Целевая функция максимизирует суммарную полезность выбранных предметов с учётом групповых бонусов. Первое ограничение требует выбрать ровно $Q$ предметов, второе ограничивает их суммарный вес после скидок. Бинарные переменные означают, что каждый предмет либо выбирается целиком, либо не выбирается.

## Готовый набор

В репозитории находятся 25 готовых экземпляров — по пять для каждого размера. Конкретные значения $Q$, $K$ и seed для каждого экземпляра смотрите в [`data/manifest.csv`](data/manifest.csv).

| Число предметов `n` | Экземпляров | `Q` в наборе | `K` в наборе |
|---:|---:|---|---|
| 10 | 5 | 5, 6, 7, 8, 10 | 3, 4, 5 |
| 20 | 5 | 3, 7, 14, 18, 20 | 2, 3, 5 |
| 50 | 5 | 5, 28, 36, 38, 45 | 2, 3, 4, 5 |
| 1 000 | 5 | 60, 316, 495, 804, 987 | 2, 4, 5 |
| 5 000 | 5 | 2218, 2636, 3675, 3988, 4051 | 2, 3, 5 |

Значения $Q$ и $K$ выбираются генератором случайно в диапазонах $Q \in [1, n]$ и $K \in [2, 5]$, поэтому в наборе встречаются как «лёгкие» экземпляры (малое $Q$), так и почти вырожденные ($Q \approx n$, когда нужно взять почти все предметы).

**Важно:** при $Q = n$ задача теряет смысл оптимизации — нужно взять все предметы, выбора нет. В текущем наборе есть такие экземпляры (например, `n_20/instance_001`). Если это нежелательно, набор можно перегенерировать с явными `--q-min` и `--q-max`, см. раздел «Генератор».

## Загрузка экземпляра

Через встроенный загрузчик:

```python
from group_discount_optimization.instance import load_instance

instance = load_instance("data/n_50/instance_001")
print(instance.weights)             # плоский массив всех весов
print(instance.profits)             # плоский массив всех полезностей
print(instance.group_ids)           # плоский массив ID групп
print(instance.capacity)
print(instance.target_item_count)
for group in instance.groups:
    print(group.group_id, group.weight_discount_percent, group.utility_bonus_percent)
```

Загрузчик сам читает `group_*_weights`, `group_*_profits` из `data.npz` согласно ключам в `meta.json` и собирает плоские массивы. Напрямую через NumPy нужно обращаться к **групповым** ключам, а не к плоским:

```python
import json
import numpy as np

with open("data/n_50/instance_001/meta.json", encoding="utf-8") as f:
    meta = json.load(f)

with np.load("data/n_50/instance_001/data.npz") as data:
    for group in meta["groups"]:
        w = data[group["weights_key"]]
        u = data[group["profits_key"]]
        print(group["id"], group["weight_discount_percent"], group["utility_bonus_percent"], w, u)
```

## Генератор

Генератор создаёт файлы `data.npz` и `meta.json` вместе с итоговым `manifest.csv`. По умолчанию он создаёт по пять экземпляров размеров 10, 20, 50, 1 000 и 5 000 предметов в `data/`:

```bash
python -m group_discount_optimization.generator --seed 42
```

Чтобы создать набор с **фиксированными** $Q$ и $K$ (например, $Q = 10$, $K = 3$ для всех экземпляров):

```bash
python -m group_discount_optimization.generator \
    --output data/fixed \
    --sizes 10 20 50 1000 5000 \
    --instances-per-size 5 \
    --min-groups 3 \
    --max-groups 3 \
    --q-min 10 \
    --q-max 10 \
    --seed 42
```

Доступные аргументы:

| Аргумент | По умолчанию | Что задаёт |
|---|---|---|
| `--output` | `data` | каталог для экземпляров |
| `--sizes` | `10 20 50 1000 5000` | список значений $n$ |
| `--instances-per-size` | `5` | сколько экземпляров на каждый размер |
| `--min-groups` | `2` | минимальное $K$ |
| `--max-groups` | `5` | максимальное $K$ |
| `--q-min` | `1` | минимальное $Q$ |
| `--q-max` | `None` | максимальное $Q$ (по умолчанию $= n$) |
| `--seed` | `42` | seed генератора |
| `--no-overwrite` | выкл. | не перезаписывать существующие каталоги |

Одинаковые параметры и `--seed` дают одинаковые данные. Не запускайте генератор перед каждым тестом: обычные запуски должны использовать уже сохранённые экземпляры.

## Установка и тесты

Требуется Python 3.11 или новее.

```bash
python -m venv venv
source venv/Scripts/activate
python -m pip install -e ".[dev]"
python -m pytest
```

В Git Bash на Windows команда `source venv/Scripts/activate` активирует Windows-виртуальное окружение.