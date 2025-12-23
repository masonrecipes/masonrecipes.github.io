# Mason Recipes

Welcome to Mason Recipes! A collection of delicious recipes curated by the Mason family.

## 🔍 Quick Search

<input type="text" id="searchInput" placeholder="Search recipes..." style="width: 100%; max-width: 400px; padding: 8px; border: 1px solid #ddd; border-radius: 4px;">
<div id="searchResults"></div>

## Table of Contents

- [About](#about)
- [How to Use](#how-to-use)
- [Recipe Categories](#recipe-categories)
- [Contributing](#contributing)
- [Contact](#contact)

---

## About

This repository contains a curated collection of family recipes, from appetizers and sides to desserts and drinks. Each recipe is documented in markdown format for easy reading and sharing.

## How to Use

1. Browse the [recipes folder](recipes/) for all available recipes
2. Use the search bar above to find recipes by name or ingredient
3. Click on any recipe to view the full details and instructions
4. Feel free to share and adapt recipes to your taste!

## Recipe Categories

Quick access to popular recipe types:

- **Appetizers & Dips**: Buffalo wings, dips, queso
- **Main Courses**: Curries, tacos, casseroles, roasted meats
- **Sides**: Soups, greens, fries, salads
- **Desserts**: Pies, cookies, cakes, candy
- **Beverages**: Margaritas, sangria, punch
- **Sauces & Condiments**: Marinades, pesto, hot sauce

## Contributing

Have a recipe to add? Feel free to submit a pull request!

## Contact

See [contact.md](recipes/contact.md) for more information.

---

<script>
document.getElementById('searchInput').addEventListener('keyup', function(e) {
  const searchTerm = e.target.value.toLowerCase();
  const resultsDiv = document.getElementById('searchResults');
  
  if (searchTerm.length === 0) {
    resultsDiv.innerHTML = '';
    return;
  }
  
  // Recipe files data (populate manually or fetch dynamically)
  const recipes = [
    { name: 'Air Fried Buffalo Wings', path: 'recipes/air_fried_buffalo_wings.md' },
    { name: 'Almond Pistachio Fat Bombs', path: 'recipes/almond_pistachio_fat_bombs.md' },
    { name: 'Baked Zucchini Casserole', path: 'recipes/baked_zucchini_casserole.md' },
    { name: 'Beer Cheese', path: 'recipes/beer_cheese.md' },
    { name: 'Beihl Oatmeal Cookies', path: 'recipes/beihl_oatmeal_cookies.md' },
    { name: 'Best White Chocolate Chip Cookies', path: 'recipes/best_white_chocolate_chip_cookies.md' },
    { name: 'Buckeyes', path: 'recipes/buckeyes.md' },
    { name: 'Buffalo Chicken Dip', path: 'recipes/buffalo_chicken_dip.md' },
    { name: 'Butterscotch Pie', path: 'recipes/butterscotch_pie.md' },
    { name: 'Buttery Chicken', path: 'recipes/buttery_chicken.md' },
    { name: 'Caribbean Jerk Marinade', path: 'recipes/caribbean_jerk_marinade.md' },
    { name: 'Caribbean Paella', path: 'recipes/caribbean_paella.md' },
    { name: 'Cheesy Keto Chicken Fajita Casserole', path: 'recipes/cheesy_keto_chicken_fajita_casserole.md' },
    { name: 'Chicken Crust Pizza', path: 'recipes/chicken_crust_pizza.md' },
    { name: 'Chicken Curry Casserole', path: 'recipes/chicken_curry_casserole.md' },
    { name: 'Chicken Cutlets', path: 'recipes/chicken_cutlets.md' },
    { name: 'Chicken Tikka Masala', path: 'recipes/chicken_tikka_masala.md' },
    { name: 'Chipotle Fish Tacos', path: 'recipes/chipotle_fish_tacos.md' },
    { name: 'Chocolate Chip Cookies', path: 'recipes/chocolate_chip_cookies.md' },
    { name: 'Chorizo Queso', path: 'recipes/chorizo_queso.md' },
    { name: 'Cindys Buffalo Ungh Chicken Dip', path: 'recipes/cindys_buffalo_ungh_chicken_dip.md' },
    { name: 'Cindys Shrimp and Grits', path: 'recipes/cindys_shrimp_and_grits.md' },
    { name: 'Classic Margarita', path: 'recipes/classic_margarita.md' },
    { name: 'Coconut Chocolate Fat Bomb Squares', path: 'recipes/coconut_chocolate_fat_bomb_squares_like_mounds.md' },
    { name: 'Coconut Cupcakes with Cream Cheese Frosting', path: 'recipes/coconut_cupcakes_with_a_cream_cheese_buttercream_frosting.md' },
    { name: 'Crock Pot Potato Soup', path: 'recipes/crock_pot_potato_soup.md' },
    { name: 'Davids Sangria', path: 'recipes/davids_sangria.md' },
    { name: 'Dill Dip', path: 'recipes/dill_dip.md' },
    { name: 'Dukes Keto Mayonnaise', path: 'recipes/dukes_keto_mayonnaise.md' },
    { name: 'Emilys French Toast Casserole', path: 'recipes/emilys_french_toast_casserole.md' },
    { name: 'Feta Bake Dip', path: 'recipes/feta_bake_dip.md' },
    { name: 'Fresh Apple Cake with Hot Caramel Sauce', path: 'recipes/fresh_apple_cake_with_hot_caramel_sauce.md' },
    { name: 'Fresh Pesto', path: 'recipes/fresh_pesto.md' },
    { name: 'Garlicky Oven Fries', path: 'recipes/garlicky_oven_fries.md' },
    { name: 'Greek Salad', path: 'recipes/greek_salad.md' },
    { name: 'Green Enchilada Sauce', path: 'recipes/green_enchilada_sauce.md' },
    { name: 'Guacamole', path: 'recipes/guacamole.md' },
    { name: 'Harissa Tunisian Hot Sauce', path: 'recipes/harissa_tunisian_hot_sauce.md' },
    { name: 'Homemade Noodles', path: 'recipes/homemade_noodles.md' },
    { name: 'Italian Chorizo Shakshouka', path: 'recipes/italian_chorizo_shakshouka.md' },
    { name: 'Italian Sausage Soup', path: 'recipes/italian_sausage_soup.md' },
    { name: 'Jannys Ginger Cookies', path: 'recipes/jannys_ginger_cookies.md' },
    { name: 'Jans Pie Crust', path: 'recipes/jans_pie_crust.md' },
    { name: 'Julies Tortilla Soup', path: 'recipes/julies_tortilla_soup.md' },
    { name: 'Katys Banana Pudding', path: 'recipes/katys_banana_pudding.md' },
    { name: 'Katys Ranch Water', path: 'recipes/katys_ranch_water.md' },
    { name: 'Keto Chocolate Pudding', path: 'recipes/keto_chocolate_pudding.md' },
    { name: 'Keto Margarita', path: 'recipes/keto_margarita.md' },
    { name: 'Keto Peanut Butter Pie', path: 'recipes/keto_peanut_butter_pie.md' },
    { name: 'Kickin Turnip Greens', path: 'recipes/kickin_turnip_greens.md' },
    { name: 'Kristas Tartine Bread', path: 'recipes/kristas_tartine_bread.md' },
    { name: 'Lemon Bars', path: 'recipes/lemon_bars.md' },
    { name: 'Mexican Cream Cheese Dip', path: 'recipes/mexican_cream_cheese_dip.md' },
    { name: 'Mikes Amish Aunts Sausage Gravy', path: 'recipes/mikes_amish_aunts_sausage_gravy.md' },
    { name: 'Mikes Caramels', path: 'recipes/mikes_caramels.md' },
    { name: 'Mikes Gin Fizzy', path: 'recipes/mikes_gin_fizzy.md' },
    { name: 'Mikes Mighty Meaty Soup', path: 'recipes/mikes_mighty_meaty_soup.md' },
    { name: 'Mikes Quick Fajitas', path: 'recipes/mikes_quick_fajitas.md' },
    { name: 'My Favorite Casserole', path: 'recipes/my_favorite_casserole.md' },
    { name: 'Never Fail Fudge', path: 'recipes/never_fail_fudge.md' },
    { name: 'Oatmeal Bread', path: 'recipes/oatmeal_bread.md' },
    { name: 'Peach Crisp', path: 'recipes/peach_crisp.md' },
    { name: 'Peach Crumb Pie', path: 'recipes/peach_crumb_pie.md' },
    { name: 'Peanut Butter Cups', path: 'recipes/peanut_butter_cups.md' },
    { name: 'Pork Carnitas', path: 'recipes/pork_carnitas.md' },
    { name: 'Pork Ribs in Slow Cooker', path: 'recipes/pork_ribs_in_slow_cooker.md' },
    { name: 'Potato Kale Soup', path: 'recipes/potato_kale_soup.md' },
    { name: 'Potato Rusks', path: 'recipes/potato_rusks.md' },
    { name: 'Protein Marshmallows', path: 'recipes/protein_marshmallows.md' },
    { name: 'Pumpkin Praline Cake', path: 'recipes/pumpkin_praline_cake.md' },
    { name: 'Randy Masons Margarita', path: 'recipes/randy_masons_margarita.md' },
    { name: 'Red Raspberry Pie', path: 'recipes/red_raspberry_pie.md' },
    { name: 'Rhubarb Cookies', path: 'recipes/rhubarb_cookies.md' },
    { name: 'Rosemary Nuts', path: 'recipes/rosemary_nuts.md' },
    { name: 'Rum Cake to Die For', path: 'recipes/rum_cake_to_die_for.md' },
    { name: 'Rum Punch', path: 'recipes/rum_punch.md' },
    { name: 'Salmon with Mango Salsa', path: 'recipes/salmon_with_mango_salsa.md' },
    { name: 'Santa Fe Soup', path: 'recipes/santa_fe_soup.md' },
    { name: 'Sausage Brunch Casserole', path: 'recipes/sausage_brunch_casserole.md' }
  ];
  
  const matches = recipes.filter(recipe => 
    recipe.name.toLowerCase().includes(searchTerm)
  );
  
  if (matches.length === 0) {
    resultsDiv.innerHTML = '<p style="color: #666; margin-top: 10px;">No recipes found.</p>';
  } else {
    const html = '<div style="margin-top: 10px;"><strong>Found ' + matches.length + ' recipe(s):</strong><ul style="list-style: none; padding-left: 0;">' + 
      matches.map(recipe => `<li><a href="${recipe.path}">${recipe.name}</a></li>`).join('') + 
      '</ul></div>';
    resultsDiv.innerHTML = html;
  }
});
</script>

