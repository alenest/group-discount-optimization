"""Генерация воспроизводимых тестовых экземпляров задачи со скидками по группам."""

# argparse разбирает параметры командной строки.
import argparse
# json читает конфигурацию и сохраняет экземпляры в JSON.
import json
# random создаёт воспроизводимые случайные данные.
import random
# math.ceil округляет сгенерированную вместимость вверх до целого числа.
from math import ceil
# Fraction позволяет точно считать вес после процентной скидки без ошибок float.
from fractions import Fraction
# Path удобно работает с путями в Windows, Linux и macOS.
from pathlib import Path
# Any используется для аннотации структуры JSON-конфигурации.
from typing import Any


def load_config(path: Path) -> dict[str, Any]:
    """Загрузить JSON-конфигурацию и проверить основные параметры генерации."""
    # Открываем файл в UTF-8, чтобы путь и содержимое корректно читались на разных ОС.
    with path.open("r", encoding="utf-8") as file:
        config = json.load(file)

    # Проверяем, что конфигурация представляет собой JSON-объект.
    if not isinstance(config, dict):
        raise ValueError("Конфигурация должна быть JSON-объектом.")

    # Эти ключи обязательны: без них генератор не знает размеры и диапазоны данных.
    required = {
        "item_counts", "instances_per_size", "group_count", "target_item_count",
        "weight_min", "weight_max", "utility_min", "utility_max",
        "discount_percent_min", "discount_percent_max",
        "bonus_percent_min", "bonus_percent_max", "capacity_ratio_percent",
    }
    # Сообщаем обо всех пропущенных настройках одним понятным сообщением.
    missing = sorted(required - config.keys())
    if missing:
        raise ValueError(f"В конфигурации отсутствуют поля: {', '.join(missing)}")

    # Размеры задач должны быть непустым списком положительных целых чисел.
    item_counts = config["item_counts"]
    if not isinstance(item_counts, list) or not item_counts:
        raise ValueError("item_counts должен быть непустым списком.")
    if any(type(count) is not int or count < 1 for count in item_counts):
        raise ValueError("Все значения item_counts должны быть положительными целыми числами.")

    # Проверяем настройки, задающие число экземпляров, групп и выбранных предметов.
    for key in ("instances_per_size", "group_count", "target_item_count"):
        if type(config[key]) is not int or config[key] < 1:
            raise ValueError(f"{key} должен быть положительным целым числом.")

    # Каждый создаваемый экземпляр должен содержать не меньше предметов, чем требуется выбрать.
    if config["target_item_count"] > min(item_counts):
        raise ValueError("target_item_count не может превышать наименьший размер задачи.")

    # Для текущей настройки каждая группа должна получить хотя бы один предмет.
    if config["group_count"] > min(item_counts):
        raise ValueError("group_count не может превышать наименьший размер задачи.")

    # Проверяем, что нижние границы диапазонов не превосходят верхние.
    for prefix in ("weight", "utility", "discount_percent", "bonus_percent"):
        minimum = config[f"{prefix}_min"]
        maximum = config[f"{prefix}_max"]
        if type(minimum) is not int or type(maximum) is not int or minimum > maximum:
            raise ValueError(f"Некорректный диапазон {prefix}_min / {prefix}_max.")

    # Вес генерируется целыми числами строго больше нуля.
    if config["weight_min"] < 1:
        raise ValueError("weight_min должен быть не меньше 1.")
    # Полезность в этой конфигурации генерируется положительными целыми числами.
    if config["utility_min"] < 1:
        raise ValueError("utility_min должен быть не меньше 1.")

    # Проценты скидки и бонуса должны лежать в диапазоне, указанном преподавателем.
    for key in ("discount_percent_min", "discount_percent_max",
                "bonus_percent_min", "bonus_percent_max"):
        if not 0 <= config[key] <= 50:
            raise ValueError(f"{key} должен находиться в диапазоне от 0 до 50.")

    # Доля ожидаемого веса — настройка генератора, а не условие математической задачи.
    if type(config["capacity_ratio_percent"]) is not int or not 0 <= config["capacity_ratio_percent"] <= 100:
        raise ValueError("capacity_ratio_percent должен быть целым числом от 0 до 100.")

    # Возвращаем проверенную конфигурацию вызывающему коду.
    return config


def split_items_between_groups(item_count: int, group_count: int) -> list[int]:
    """Распределить общее число предметов по группам максимально равномерно."""
    # divmod возвращает базовое число предметов в каждой группе и остаток.
    items_per_group, remainder = divmod(item_count, group_count)
    # Первые группы получают по одному дополнительному предмету, пока не распределён остаток.
    return [items_per_group + (1 if index < remainder else 0)
            for index in range(group_count)]


def generate_instance(
    item_count: int,
    config: dict[str, Any],
    seed: int,
    instance_id: str,
) -> dict[str, Any]:
    """Создать один экземпляр с непересекающимися списками предметов групп."""
    # Отдельный генератор делает результат воспроизводимым для указанного seed.
    rng = random.Random(seed)
    # Заранее определяем число предметов в каждой группе; сумма всегда равна item_count.
    group_sizes = split_items_between_groups(item_count, config["group_count"])
    # Здесь будут храниться группы вместе с их процентами и предметами.
    groups: list[dict[str, Any]] = []
    # Для расчёта вместимости сохраняем точные скорректированные веса всех предметов.
    adjusted_weights: list[Fraction] = []

    # Создаём каждую группу и задаём ей собственные проценты скидки и бонуса.
    for group_index, group_size in enumerate(group_sizes, start=1):
        # Проценты генерируются целыми числами от 0 до 50 включительно.
        discount = rng.randint(config["discount_percent_min"], config["discount_percent_max"])
        bonus = rng.randint(config["bonus_percent_min"], config["bonus_percent_max"])
        # Предметы каждой группы находятся только в её собственном списке.
        items: list[dict[str, Any]] = []

        # Генерируем уникальные идентификаторы и целочисленные веса/полезности предметов.
        for item_index in range(1, group_size + 1):
            # Вес выбирается из заданного в конфигурации целочисленного диапазона.
            weight = rng.randint(config["weight_min"], config["weight_max"])
            # Полезность выбирается независимо из заданного целочисленного диапазона.
            utility = rng.randint(config["utility_min"], config["utility_max"])
            # Идентификатор включает группу, поэтому предметы однозначно различимы в файле.
            item_id = f"G{group_index:02d}_I{item_index:05d}"
            # Добавляем предмет к списку текущей группы.
            items.append({"item_id": item_id, "weight": weight, "utility": utility})
            # Считаем вес после скидки точно, сохраняя формулу с делением на 100.
            adjusted_weights.append(Fraction(weight * (100 - discount), 100))

        # Добавляем сформированную группу в экземпляр.
        groups.append({
            "group_id": f"G{group_index:02d}",
            "weight_discount_percent": discount,
            "utility_bonus_percent": bonus,
            "items": items,
        })

    # Минимальный вес ровно Q предметов равен сумме Q наименьших скорректированных весов.
    # Вместимость не должна быть меньше этого значения: иначе экземпляр может оказаться недопустимым.
    lightest_weights = sorted(adjusted_weights)[:config["target_item_count"]]
    minimum_feasible_weight = sum(lightest_weights, Fraction(0, 1))

    # Рассчитываем средний скорректированный вес всех предметов точно, без ошибок float.
    total_adjusted_weight = sum(adjusted_weights, Fraction(0, 1))
    average_weight_for_q_items = total_adjusted_weight * Fraction(
        config["target_item_count"], item_count
    )

    # Берём заданную долю среднего веса Q предметов, но не опускаемся ниже гарантированно
    # допустимого веса Q самых лёгких предметов. Это правило нужно только для генерации тестов.
    capacity_by_ratio = average_weight_for_q_items * Fraction(
        config["capacity_ratio_percent"], 100
    )
    capacity_fraction = max(minimum_feasible_weight, capacity_by_ratio)
    # Вместимость задаётся целым числом; округление вверх сохраняет допустимость лёгкого набора.
    max_weight = ceil(capacity_fraction)

    # Возвращаем JSON-совместимую структуру одного экземпляра.
    return {
        "schema_version": 1,
        "instance_id": instance_id,
        "seed": seed,
        "max_weight": max_weight,
        "target_item_count": config["target_item_count"],
        "groups": groups,
        "generation": {
            "item_count": item_count,
            "group_count": config["group_count"],
            "weight_range": [config["weight_min"], config["weight_max"]],
            "utility_range": [config["utility_min"], config["utility_max"]],
            "discount_percent_range": [
                config["discount_percent_min"], config["discount_percent_max"]
            ],
            "bonus_percent_range": [
                config["bonus_percent_min"], config["bonus_percent_max"]
            ],
            "capacity_ratio_percent": config["capacity_ratio_percent"],
        },
    }


def save_instances(
    config: dict[str, Any],
    output_dir: Path,
    base_seed: int,
    instances_per_size: int,
) -> list[Path]:
    """Создать и сохранить заданное число экземпляров для каждого размера."""
    # Создаём каталог для выходных файлов, если его ещё нет.
    output_dir.mkdir(parents=True, exist_ok=True)
    # Сюда складываем пути всех созданных файлов, чтобы вывести их пользователю.
    saved_paths: list[Path] = []
    # Уникальный последовательный seed назначается каждому экземпляру.
    current_seed = base_seed

    # Перебираем размеры задач из конфигурации в указанном порядке.
    for item_count in config["item_counts"]:
        # Для каждого размера создаём указанное число разных экземпляров.
        for instance_number in range(1, instances_per_size + 1):
            # Формируем читаемый идентификатор экземпляра.
            instance_id = f"n{item_count}_instance{instance_number:03d}"
            # Создаём экземпляр с текущим seed.
            instance = generate_instance(item_count, config, current_seed, instance_id)
            # Добавляем seed к имени файла, чтобы было легко восстановить запуск.
            file_path = output_dir / f"{instance_id}_seed{current_seed}.json"

            # Сохраняем JSON с отступами, чтобы его можно было просматривать в VS Code.
            with file_path.open("w", encoding="utf-8") as file:
                json.dump(instance, file, ensure_ascii=False, indent=2)
                # Завершающий перевод строки удобен для диффов и ручного редактирования.
                file.write("\n")

            # Запоминаем путь и увеличиваем seed для следующего экземпляра.
            saved_paths.append(file_path)
            current_seed += 1

    # Возвращаем список файлов для итогового сообщения CLI и для тестов.
    return saved_paths


def main() -> None:
    """Точка входа при запуске модуля через python -m."""
    # Описываем параметры командной строки.
    parser = argparse.ArgumentParser(description="Генерация тестов задачи со скидками по группам.")
    parser.add_argument("--config", type=Path, default=Path("configs/generator.json"),
                        help="путь к JSON-конфигурации")
    parser.add_argument("--output", type=Path, default=Path("data/generated"),
                        help="каталог для созданных JSON-файлов")
    parser.add_argument("--seed", type=int, default=42,
                        help="первый seed; одинаковые параметры и seed дают одинаковые данные")
    parser.add_argument("--instances-per-size", type=int, default=None,
                        help="число экземпляров каждого размера; по умолчанию берётся из конфигурации")
    # Разбираем параметры, переданные пользователем в терминале.
    args = parser.parse_args()

    # Загружаем и проверяем конфигурацию до начала генерации.
    config = load_config(args.config)
    # CLI-параметр имеет приоритет; иначе используем значение из JSON.
    instances_per_size = (
        args.instances_per_size
        if args.instances_per_size is not None
        else config["instances_per_size"]
    )
    # Отрицательное или нулевое число экземпляров не имеет смысла.
    if instances_per_size < 1:
        parser.error("--instances-per-size должен быть положительным целым числом.")
    # Seed должен быть неотрицательным, чтобы метаданные были однозначными.
    if args.seed < 0:
        parser.error("--seed должен быть неотрицательным целым числом.")

    # Создаём все файлы и сообщаем их количество.
    paths = save_instances(config, args.output, args.seed, instances_per_size)
    print(f"Создано экземпляров: {len(paths)}")
    print(f"Каталог: {args.output.resolve()}")
    # Выводим имена, чтобы пользователю было видно, какие размеры были созданы.
    for path in paths:
        print(f"- {path.name}")


# Запускаем main только при непосредственном запуске этого модуля.
if __name__ == "__main__":
    main()
