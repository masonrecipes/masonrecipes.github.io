#!/usr/bin/env python3
"""Public seam tests for the deterministic recipe style formatter."""

import json
import os
import hashlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import recipe_style as style  # noqa: E402


REPO = Path(__file__).resolve().parents[2]


class RecipeStyleTest(unittest.TestCase):
    def test_style_is_machine_readable_and_names_the_house_conventions(self):
        source = json.loads((REPO / "recipe-style.json").read_text(encoding="utf-8"))
        self.assertEqual(source, style.STYLE)
        self.assertEqual({key: source["headings"][key] for key in ("ingredients", "instructions", "notes")}, {
            "ingredients": "Ingredients", "instructions": "Instructions", "notes": "Notes"})
        self.assertEqual(source["headings"]["subgroups"], "Title case")
        self.assertEqual(source["units"]["tablespoon"]["canonical"], "Tbsp")
        self.assertEqual(source["units"]["teaspoon"]["canonical"], "tsp")
        self.assertEqual(source["units"]["cup"]["plural"], "cups")
        self.assertEqual(source["units"]["ounce"]["canonical"], "oz")
        self.assertEqual(source["units"]["pound"]["canonical"], "lb")
        self.assertEqual(source["first_person"]["family_written"], "keep")
        self.assertEqual(source["first_person"]["copied_source_aside"], "move_to_neutral_note")

    def test_ingredient_units_lowercase_and_preparation_are_normalized(self):
        self.assertEqual(style.normalize_ingredient("1 Tablespoon Olive Oil"), "1 Tbsp olive oil")
        self.assertEqual(style.normalize_ingredient("2 tablespoons CHOPPED ONION"), "2 Tbsp chopped onion")
        self.assertEqual(style.normalize_ingredient("1 cup Diced Celery"), "1 cup diced celery")
        self.assertEqual(style.normalize_ingredient("2 cup CELERY, CHOPPED"), "2 cups celery, chopped")
        self.assertEqual(style.normalize_ingredient("3 OUNCES Dark Chocolate"), "3 oz dark chocolate")
        self.assertEqual(style.normalize_ingredient("1 lbs. Ground Beef"), "1 lb ground beef")
        self.assertEqual(style.normalize_ingredient("1.5 tablespoons Coconut Oil"), "1.5 Tbsp coconut oil")

    def test_fraction_spelling_and_unit_forms_preserve_the_quantity(self):
        self.assertEqual(style.normalize_ingredient("1/2 teaspoons Vanilla Extract"), "1/2 tsp vanilla extract")
        self.assertEqual(style.normalize_ingredient("½ Tablespoons Granulated Sugar"), "½ Tbsp granulated sugar")
        self.assertEqual(style.numbers("½ Tablespoons Granulated Sugar"),
                         style.numbers(style.normalize_ingredient("½ Tablespoons Granulated Sugar")))

    def test_titles_keep_connectors_symbols_and_parentheses_sensible(self):
        self.assertEqual(style.normalize_title("chili with beef and/or lamb & peas (quick dinner)"),
                         "Chili with Beef and/or Lamb & Peas (Quick Dinner)")
        self.assertEqual(style.normalize_title("beef and/or pork"), "Beef and/or Pork")
        self.assertEqual(style.normalize_title("rum cake to die for"), "Rum Cake to Die For")

    def test_ingredient_subgroups_keep_the_ingredient_normalizer_active(self):
        formatted = style.normalize_markdown(
            "# sausage mozarella pizza\n\n## ingredients\n\n### pizza dough\n\n"
            "- 1 Tablespoon Olive Oil\n\n### pizza toppings\n\n- Shredded Mozarella\n")
        self.assertIn("# Sausage Mozzarella Pizza", formatted)
        self.assertIn("### Pizza Dough", formatted)
        self.assertIn("- 1 Tbsp olive oil", formatted)
        self.assertIn("### Pizza Toppings", formatted)
        self.assertIn("- shredded mozzarella", formatted)

    def test_units_and_spelling_are_normalized_in_instructions_too(self):
        formatted = style.normalize_markdown(
            "# brussel sprouts\n\n## ingredients\n\n- 1 lb Brussel Sprouts\n\n"
            "## instructions\n\n1. Add 2 Tablespoons of olive oil to the Brussel sprouts.\n")
        self.assertIn("# Brussels Sprouts", formatted)
        self.assertIn("- 1 lb Brussels sprouts", formatted)
        self.assertIn("1. Add 2 Tbsp olive oil to the Brussels sprouts.", formatted)

    def test_format_script_checks_then_normalizes_without_changing_numbers(self):
        with tempfile.TemporaryDirectory() as directory:
            recipe = Path(directory) / "test.md"
            before = "# chili with beef and/or lamb\n\n## ingredients\n\n- ½ Tablespoons Olive Oil\n\n## instructions\n\n1. Cook 10 minutes.\n"
            recipe.write_text(before, encoding="utf-8")
            command = [str(REPO / "scripts/format-recipes.sh")]
            checked = subprocess.run(command + ["--check", str(recipe)], text=True, capture_output=True)
            self.assertNotEqual(checked.returncode, 0)
            subprocess.run(command + [str(recipe)], check=True, text=True, capture_output=True)
            after = recipe.read_text(encoding="utf-8")
            self.assertIn("# Chili with Beef and/or Lamb", after)
            self.assertIn("- ½ Tbsp olive oil", after)
            self.assertEqual(style.numbers(before), style.numbers(after))
            subprocess.run(command + ["--check", str(recipe)], check=True, text=True, capture_output=True)

    def test_all_cleaned_recipes_match_the_pre_cleanup_number_baseline(self):
        baseline = json.loads((REPO / "recipe-number-baseline.json").read_text(encoding="utf-8"))
        rows = [path.relative_to(REPO).as_posix() + "\0" + json.dumps(
            style.numbers(path.read_text(encoding="utf-8")), sort_keys=True)
            for path in sorted((REPO / "docs/recipes").rglob("*.md"))]
        self.assertEqual(len(rows), baseline["recipe_count"])
        digest = hashlib.sha256("\n".join(rows).encode()).hexdigest()
        self.assertEqual(digest, baseline["sha256"])


if __name__ == "__main__":
    unittest.main()
