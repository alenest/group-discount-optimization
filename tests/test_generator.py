"""Проверки ключевых свойств генератора тестовых экземпляров."""

# json нужен, чтобы проверить, что сохранённый файл читается как обычный JSON.
import json
# Path используется для временных каталогов и путей к конфигурации.
from pathlib import Path
# tempfile создаёт изолированный каталог, который удаляется после теста.
import tempfile
# unittest даёт простые проверки без дополнительных тестовых библиотек в логике генератора.
import unittest

# Импортируем проверку конфигурации, генерацию и сохранение экземпляров.
from group_discount_optimization.generator import (
    generate_instance,
    load_config,
    save_instances,
    split_items_between_groups,
)


# Путь к конфигурации проекта вычисляется относительно этого тестового файла.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "configs" / "generator.json"


class GeneratorTests(unittest.TestCase):
    """Проверяем размерности, воспроизводимость и согласованность данных."""

    def setUp(self) -> None:
        # Загружаем одну и ту же проверенную конфигурацию перед каждым тестом.
        self.config = load_config(CONFIG_PATH)

    def test_group_sizes_sum_to_item_count(self) -> None:
        # Проверяем размеры, не делящиеся на число групп нацело.
        sizes = split_items_between_groups(item_count=10, group_count=3)
        # В сумме должно получиться ровно столько предметов, сколько запросили.
        self.assertEqual(sum(sizes), 10)
        # Разница между самой большой и самой маленькой группой не больше одного предмета.
        self.assertLessEqual(max(sizes) - min(sizes), 1)

    def test_generation_is_reproducible(self) -> None:
        # Один и тот же seed и одна конфигурация должны давать одинаковый экземпляр.
        first = generate_instance(20, self.config, seed=123, instance_id="test")
        second = generate_instance(20, self.config, seed=123, instance_id="test")
        self.assertEqual(first, second)

    def test_requested_item_count_and_unique_group_assignment(self) -> None:
        # Генерируем экземпляр среднего размера.
        instance = generate_instance(50, self.config, seed=7, instance_id="test")
        # Число предметов по всем группам должно совпадать с размером экземпляра.
        items = [item for group in instance["groups"] for item in group["items"]]
        self.assertEqual(len(items), 50)
        # Каждый ID предмета должен быть уникален во всём экземпляре.
        item_ids = [item["item_id"] for item in items]
        self.assertEqual(len(item_ids), len(set(item_ids)))

    def test_generated_capacity_allows_at_least_one_selection(self) -> None:
        # Вместимость не должна быть меньше суммы Q наименьших скорректированных весов.
        instance = generate_instance(50, self.config, seed=19, instance_id="test")
        # Собираем все веса после скидок; вычисляем их в десятичных дробях для проверки.
        adjusted_weights = []
        for group in instance["groups"]:
            factor = 1 - group["weight_discount_percent"] / 100
            adjusted_weights.extend(item["weight"] * factor for item in group["items"])
        # Самые лёгкие Q предметов должны помещаться в сгенерированную вместимость.
        min_weight = sum(sorted(adjusted_weights)[:instance["target_item_count"]])
        self.assertLessEqual(min_weight, instance["max_weight"] + 1e-9)

    def test_percentages_are_in_the_required_range(self) -> None:
        # Каждый групповой коэффициент скидки и бонуса должен быть от 0 до 50 включительно.
        instance = generate_instance(1000, self.config, seed=33, instance_id="test")
        for group in instance["groups"]:
            self.assertGreaterEqual(group["weight_discount_percent"], 0)
            self.assertLessEqual(group["weight_discount_percent"], 50)
            self.assertGreaterEqual(group["utility_bonus_percent"], 0)
            self.assertLessEqual(group["utility_bonus_percent"], 50)

    def test_saves_valid_json_files(self) -> None:
        # Используем временный каталог, чтобы тест не оставлял выходные данные в проекте.
        with tempfile.TemporaryDirectory() as temporary_dir:
            output_dir = Path(temporary_dir)
            paths = save_instances(self.config, output_dir, base_seed=100, instances_per_size=1)
            # При пяти размерах и одном экземпляре каждого должны появиться пять файлов.
            self.assertEqual(len(paths), len(self.config["item_counts"]))
            # Каждый файл должен разбираться JSON-парсером и содержать ожидаемые поля.
            for path in paths:
                with path.open("r", encoding="utf-8") as file:
                    content = json.load(file)
                self.assertIn("groups", content)
                self.assertIn("max_weight", content)
                self.assertIn("target_item_count", content)


# Позволяем запускать тесты и напрямую командой python tests/test_generator.py.
if __name__ == "__main__":
    unittest.main()
