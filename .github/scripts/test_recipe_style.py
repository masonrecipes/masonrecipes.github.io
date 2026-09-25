#!/usr/bin/env python3
"""Public seam tests for the deterministic recipe style formatter."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import recipe_style as style  # noqa: E402


REPO = Path(__file__).resolve().parents[2]


class RecipeStyleTest(unittest.TestCase):
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
        self.assertEqual(style.normalize_title("chicken/beef tacos"), "Chicken/Beef Tacos")
        self.assertEqual(style.normalize_title("crock pot/instant pot chili"), "Crock Pot/Instant Pot Chili")
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
        self.assertIn("1. Add 2 Tbsp of olive oil to the Brussels sprouts.", formatted)

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

    def test_contractions_and_lowercase_t_are_not_tablespoons(self):
        line = "Don’t add 1 t salt; the bars aren’t done yet."
        self.assertEqual(style.normalize_text(line), line)

    def test_ascii_fractions_take_the_singular_unit(self):
        self.assertEqual(style.normalize_ingredient("1/2 cups Shredded Cheese"), "1/2 cup shredded cheese")
        self.assertEqual(style.normalize_ingredient("1 1/2 cup Sugar"), "1 1/2 cups sugar")
        self.assertEqual(style.normalize_ingredient("1/4 - 1/2 cup Olives"), "1/4 - 1/2 cups olives")

    def test_link_targets_proper_nouns_and_acronyms_keep_their_case(self):
        self.assertEqual(style.normalize_ingredient("1/4 Teaspoon [Himalayan Salt](http://amzn.to/2xhg3Tn)"),
                         "1/4 tsp [Himalayan salt](http://amzn.to/2xhg3Tn)")
        self.assertEqual(style.normalize_ingredient("2 Tablespoons WORCESTERSHIRE Sauce"), "2 Tbsp Worcestershire sauce")
        self.assertEqual(style.normalize_title("lexington bbq sauce"), "Lexington BBQ Sauce")

    def test_preparation_comma_is_added_only_when_the_line_has_none(self):
        self.assertEqual(style.normalize_ingredient("1 Onion Diced"), "1 onion, diced")
        self.assertEqual(style.normalize_ingredient("2 large eggs, lightly beaten"), "2 large eggs, lightly beaten")

    def test_first_person_ingredient_lines_are_kept_and_warned_about(self):
        for line in ("1 cup sauce (I used Huy Fongs)", "2 cups flour, my favorite", "salt, we like kosher"):
            self.assertTrue(style.is_first_person(line))
            self.assertEqual(style.normalize_ingredient(line), line.lower().replace("huy fongs", "Huy Fong").replace("(i ", "(I "))
        self.assertFalse(style.is_first_person("2 cups flour"))
        with tempfile.TemporaryDirectory() as directory:
            recipe = Path(directory) / "test.md"
            text = "# Chili\n\n## Ingredients\n\n- 1 jar my mom's salsa\n"
            recipe.write_text(text, encoding="utf-8")
            result = subprocess.run([str(REPO / "scripts/format-recipes.sh"), "--check", str(recipe)],
                                    text=True, capture_output=True)
            self.assertEqual(result.returncode, 0)
            self.assertIn("test.md:5: warning: first-person ingredient line to review: - 1 jar my mom's salsa", result.stderr)
            self.assertEqual(recipe.read_text(encoding="utf-8"), text)

    def test_prose_units_change_only_after_a_quantity_and_keep_sentence_punctuation(self):
        for line in ("Line with paper cups.", "Fill the muffin cups.", "Add a few cups of broth.",
                     "Makes about 2½ lb.", "Add 1 tsp. Stir well.", "Heat 2 Tbsp of the lard.", "Add 1 tsp of salt."):
            self.assertEqual(style.normalize_text(line), line)
        self.assertEqual(style.normalize_text("Add 2 tablespoons of oil."), "Add 2 Tbsp of oil.")

    def test_ingredient_lines_drop_of_after_a_spoon_measure_but_not_before_a_determiner(self):
        self.assertEqual(style.normalize_ingredient("2 Tablespoons of Butter"), "2 Tbsp butter")
        self.assertEqual(style.normalize_ingredient("2 Tbsp of the reserved juice"), "2 Tbsp of the reserved juice")
        self.assertEqual(style.normalize_ingredient("1 oz. 100% agave tequila"), "1 oz 100% agave tequila")

    def test_mixed_case_words_and_title_particles_keep_their_written_case(self):
        self.assertEqual(style.normalize_title("mcdonald's copycat"), "Mcdonald's Copycat")
        self.assertEqual(style.normalize_title("McDonald's copycat"), "McDonald's Copycat")
        self.assertEqual(style.normalize_title("steak tips au gratin"), "Steak Tips au gratin")
        self.assertEqual(style.normalize_title("Pico De Gallo"), "Pico de Gallo")
        self.assertEqual(style.normalize_ingredient("1 cup McDonald's Sauce"), "1 cup McDonald's sauce")

    def test_spelling_targets_are_restored_after_lowercasing(self):
        self.assertEqual(style.normalize_ingredient("1 cup Hellmann's Mayonnaise"), "1 cup Hellmann's mayonnaise")

    def test_front_matter_attribution_and_other_headings_are_left_alone(self):
        text = ("---\ntags:\n  - By Cup Mason\nauthor: \"T Mason\"\n---\n\n# Chili\n\n"
                "## Subgroups\n\nText.\n\n*Submitted by: Tablespoon Mason*\n")
        self.assertEqual(style.normalize_markdown(text), text)

    def test_cleaned_recipes_keep_their_pre_cleanup_numbers(self):
        baseline = json.loads((REPO / "recipe-number-baseline.json").read_text(encoding="utf-8"))
        for relative, expected in baseline.items():
            path = REPO / relative
            if path.exists():
                with self.subTest(recipe=relative):
                    self.assertEqual(style.numbers(path.read_text(encoding="utf-8")), expected)


if __name__ == "__main__":
    unittest.main()
