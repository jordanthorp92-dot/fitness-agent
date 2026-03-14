import json
import requests
from datetime import datetime, timedelta
import pytz
from pathlib import Path

class FitnessAgent:
    """Your Personal Fitness AI Agent with Food API & Coaching"""
    
    def __init__(self, timezone="Asia/Bangkok"):
        self.timezone = pytz.timezone(timezone)
        self.local_tz = timezone
        
        # Load all data files with error handling
        self.macro_goals = self.load_json("macro_goals.json", self.default_macro_goals())
        self.workout_schedule = self.load_json("workout_schedule.json", self.default_workout_schedule())
        self.ped_schedule = self.load_json("ped_schedule.json", self.default_ped_schedule())
        self.custom_foods = self.load_json("custom_foods.json", {})
        self.daily_macros = self.load_json("daily_macros.json", self.default_daily_macros())
        self.reminder_state = self.load_json("reminder_state.json", {})
        self.user_settings = self.load_json("user_settings.json", self.default_user_settings())
        
        # Check if it's a new day and reset if needed
        self.check_and_reset_day()
    
    def load_json(self, filename, default):
        """Load JSON with error handling"""
        try:
            with open(filename, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"⚠️  {filename} not found, creating with defaults")
            self.save_json(filename, default)
            return default
        except json.JSONDecodeError:
            print(f"⚠️  {filename} corrupted, starting fresh")
            self.save_json(filename, default)
            return default
        except Exception as e:
            print(f"⚠️  Error loading {filename}: {e}")
            return default
    
    def save_json(self, filename, data):
        """Save JSON with error handling"""
        try:
            with open(filename, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"❌ Error saving {filename}: {e}")
    
    # ===== DEFAULT DATA STRUCTURES =====
    
    def default_macro_goals(self):
        return {
            "daily_targets": {"protein": 185, "carbs": 150, "fat": 80, "calories": 2000},
            "tracking_days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
            "slippage_percentage": 5,
            "allowed_ranges": {
                "protein": {"min": 176, "max": 194, "target": 185},
                "carbs": {"min": 143, "max": 158, "target": 150},
                "fat": {"min": 76, "max": 84, "target": 80},
                "calories": {"min": 1900, "max": 2100, "target": 2000}
            }
        }
    
    def default_workout_schedule(self):
        return {
            "weekly_schedule": {
                "Monday": {"training": "Lower Body", "type": "weights"},
                "Tuesday": {"training": "Rest", "type": "rest"},
                "Wednesday": {"training": "Sprints + Upper Body", "type": "mixed"},
                "Thursday": {"training": "Rest", "type": "rest"},
                "Friday": {"training": "5K Run + Lower Body", "type": "mixed"},
                "Saturday": {"training": "Rest", "type": "rest"},
                "Sunday": {"training": "10K Run + Upper Body", "type": "mixed"}
            }
        }
    
    def default_ped_schedule(self):
        return {
            "injection_schedule": {
                "Monday": {"injections": [{"compound": "Test 250", "dosage": "0.2cc"}, {"compound": "Primo", "dosage": "0.55cc"}, {"compound": "HCG", "dosage": "0.15cc"}]},
                "Wednesday": {"injections": [{"compound": "Test 250", "dosage": "0.2cc"}, {"compound": "Primo", "dosage": "0.55cc"}, {"compound": "HCG", "dosage": "0.15cc"}]},
                "Friday": {"injections": [{"compound": "Test 250", "dosage": "0.2cc"}, {"compound": "Primo", "dosage": "0.55cc"}, {"compound": "HCG", "dosage": "0.15cc"}]},
                "Sunday": {"injections": [{"compound": "Test 250", "dosage": "0.2cc"}, {"compound": "Primo", "dosage": "0.55cc"}, {"compound": "HCG", "dosage": "0.15cc"}]}
            }
        }
    
    def default_daily_macros(self):
        now = datetime.now(pytz.timezone("Asia/Bangkok")).strftime("%Y-%m-%d")
        return {
            "date": now,
            "meals_logged": [],
            "daily_totals": {"calories": 0, "protein": 0, "carbs": 0, "fat": 0},
            "last_reset": now
        }
    
    def default_user_settings(self):
        return {
            "chat_id": None,
            "timezone": "Asia/Bangkok",
            "skip_tracking_today": False
        }
    
    # ===== DAY RESET LOGIC =====
    
    def check_and_reset_day(self):
        """Check if it's a new day and reset macros if needed"""
        now = datetime.now(self.timezone).strftime("%Y-%m-%d")
        
        if self.daily_macros.get("last_reset") != now:
            self.daily_macros = self.default_daily_macros()
            self.daily_macros["last_reset"] = now
            self.user_settings["skip_tracking_today"] = False
            self.save_json("daily_macros.json", self.daily_macros)
            self.save_json("user_settings.json", self.user_settings)
    
    # ===== FOOD API INTEGRATION =====
    
    def search_food_api(self, food_name, quantity=1):
        """Search USDA then Nutritionix API for food"""
        # Try Nutritionix first (faster)
        result = self.search_nutritionix(food_name, quantity)
        if result:
            return result
        
        # Fall back to USDA
        result = self.search_usda(food_name, quantity)
        if result:
            return result
        
        return None
    
    def search_nutritionix(self, food_name, quantity):
        """Search Nutritionix API"""
        try:
            url = "https://www.nutritionix.com/search/instant"
            params = {"q": food_name, "limit": 1}
            response = requests.get(url, params=params, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("common"):
                    item = data["common"][0]
                    return {
                        "name": item.get("food_name", food_name),
                        "calories": item.get("nf_calories", 0) * quantity,
                        "protein": item.get("nf_protein", 0) * quantity,
                        "carbs": item.get("nf_total_carbohydrate", 0) * quantity,
                        "fat": item.get("nf_total_fat", 0) * quantity,
                        "source": "Nutritionix"
                    }
        except Exception as e:
            print(f"Nutritionix API error: {e}")
        
        return None
    
    def search_usda(self, food_name, quantity):
        """Search USDA FoodData Central API"""
        try:
            url = "https://fdc.nal.usda.gov/api/foods/search"
            params = {
                "query": food_name,
                "pageSize": 1,
                "api_key": "DEMO_KEY"
            }
            response = requests.get(url, params=params, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("foods"):
                    item = data["foods"][0]
                    nutrients = {n["nutrientName"]: n.get("value", 0) for n in item.get("foodNutrients", [])}
                    
                    return {
                        "name": item.get("description", food_name),
                        "calories": nutrients.get("Energy", 0) * quantity / 100,
                        "protein": nutrients.get("Protein", 0) * quantity / 100,
                        "carbs": nutrients.get("Carbohydrate, by difference", 0) * quantity / 100,
                        "fat": nutrients.get("Total lipid (fat)", 0) * quantity / 100,
                        "source": "USDA"
                    }
        except Exception as e:
            print(f"USDA API error: {e}")
        
        return None
    
    # ===== FOOD LOGGING =====
    
    def log_food(self, food_name, quantity=1):
        """Log food with API lookup or custom food"""
        self.check_and_reset_day()
        
        # Try custom foods first
        food_lower = food_name.lower().strip()
        if food_lower in self.custom_foods:
            food = self.custom_foods[food_lower]
            return self._add_to_macros(food_name, food, quantity)
        
        # Try API
        food = self.search_food_api(food_name, quantity)
        if not food:
            return f"❌ Food '{food_name}' not found in database.\n\nUse: <b>add food: {food_name} | calories | protein | carbs | fat</b>\nExample: <b>add food: my chicken | 559 | 49 | 56 | 15</b>"
        
        return self._add_to_macros(food_name, food, quantity)
    
    def _add_to_macros(self, food_name, food, quantity):
        """Add food to daily macros"""
        calories = round(food["calories"])
        protein = round(food["protein"])
        carbs = round(food["carbs"])
        fat = round(food["fat"])
        
        self.daily_macros["meals_logged"].append({
            "food": food_name,
            "quantity": quantity,
            "calories": calories,
            "protein": protein,
            "carbs": carbs,
            "fat": fat,
            "timestamp": datetime.now(self.timezone).isoformat(),
            "time": datetime.now(self.timezone).strftime("%H:%M")
        })
        
        self.daily_macros["daily_totals"]["calories"] += calories
        self.daily_macros["daily_totals"]["protein"] += protein
        self.daily_macros["daily_totals"]["carbs"] += carbs
        self.daily_macros["daily_totals"]["fat"] += fat
        
        self.save_json("daily_macros.json", self.daily_macros)
        
        remaining = self._get_remaining_macros()
        return f"""✅ Logged: {food_name}
<b>+{protein}p | +{carbs}c | +{fat}f</b>

📊 Remaining today:
Protein: {remaining['protein']}g
Carbs: {remaining['carbs']}g
Fat: {remaining['fat']}g"""
    
    def add_custom_food(self, name, calories, protein, carbs, fat):
        """Add custom food to user's database"""
        try:
            calories = int(calories)
            protein = int(protein)
            carbs = int(carbs)
            fat = int(fat)
            
            if any(x < 0 for x in [calories, protein, carbs, fat]):
                return "❌ Macros cannot be negative!"
            
            food_lower = name.lower().strip()
            
            if food_lower in self.custom_foods:
                return f"⚠️ '{name}' already exists. Overwrite? (Y/N)"
            
            self.custom_foods[food_lower] = {
                "calories": calories,
                "protein": protein,
                "carbs": carbs,
                "fat": fat
            }
            
            self.save_json("custom_foods.json", self.custom_foods)
            return f"✅ Saved: {name}\n{calories} cal | {protein}p | {carbs}c | {fat}f"
        
        except ValueError:
            return "❌ Invalid format. Use: add food: name | calories | protein | carbs | fat"
    
    # ===== MACRO TRACKING & COACHING =====
    
    def _get_remaining_macros(self):
        """Calculate remaining macros"""
        targets = self.macro_goals["allowed_ranges"]
        totals = self.daily_macros["daily_totals"]
        
        return {
            "protein": max(0, targets["protein"]["max"] - totals["protein"]),
            "carbs": max(0, targets["carbs"]["max"] - totals["carbs"]),
            "fat": max(0, targets["fat"]["max"] - totals["fat"])
        }
    
    def get_macro_status(self):
        """Check macro status with coaching"""
        self.check_and_reset_day()
        today = datetime.now(self.timezone).strftime("%A")
        
        if today not in self.macro_goals["tracking_days"]:
            return "📅 Today is not a tracking day."
        
        targets = self.macro_goals["allowed_ranges"]
        totals = self.daily_macros["daily_totals"]
        
        protein_status = self._check_macro(totals["protein"], targets["protein"])
        carbs_status = self._check_macro(totals["carbs"], targets["carbs"])
        fat_status = self._check_macro(totals["fat"], targets["fat"])
        calories_status = self._check_macro(totals["calories"], targets["calories"])
        
        coaching = self._generate_coaching_message(totals, targets)
        
        message = f"""🎯 MACRO STATUS
{'='*35}
Protein: {totals['protein']}g / {targets['protein']['target']}g {protein_status}
Carbs: {totals['carbs']}g / {targets['carbs']['target']}g {carbs_status}
Fat: {totals['fat']}g / {targets['fat']['target']}g {fat_status}
Calories: {totals['calories']} / {targets['calories']['target']} {calories_status}

{'='*35}
{coaching}

Meals logged: {len(self.daily_macros['meals_logged'])}"""
        
        return message
    
    def _check_macro(self, current, target_range):
        """Check if macro is on track"""
        if target_range["min"] <= current <= target_range["max"]:
            return "✅"
        elif current < target_range["min"]:
            return f"⬇️ ({target_range['min'] - current}g needed)"
        else:
            return f"⬆️ (+{current - target_range['max']}g over)"
    
    def _generate_coaching_message(self, totals, targets):
        """Generate intelligent coaching feedback"""
        protein_needed = max(0, targets["protein"]["min"] - totals["protein"])
        carbs_needed = max(0, targets["carbs"]["min"] - totals["carbs"])
        fat_needed = max(0, targets["fat"]["min"] - totals["fat"])
        
        if protein_needed == 0 and carbs_needed == 0 and fat_needed == 0:
            return "Perfect macros! You're hitting your targets exactly."
        
        suggestions = []
        if protein_needed > 0:
            servings = protein_needed / 31
            suggestions.append(f"Protein: Need {protein_needed}g more → {servings:.1f}x chicken breast 100g")
        
        if carbs_needed > 0:
            servings = carbs_needed / 28
            suggestions.append(f"Carbs: Need {carbs_needed}g more → {servings:.1f} cups rice")
        
        if fat_needed > 0:
            suggestions.append(f"Fat: Need {fat_needed}g more (add olive oil or nuts)")
        
        return "\n".join(suggestions) if suggestions else "You're on track!"
    
    # ===== WORKOUT FEATURES =====
    
    def get_todays_workout(self):
        """Get today's workout"""
        today = datetime.now(self.timezone).strftime("%A")
        workout = self.workout_schedule["weekly_schedule"].get(today)
        
        if not workout:
            return f"❌ No workout data for {today}"
        
        return f"""💪 TODAY'S WORKOUT ({today.upper()})
{'='*35}
{workout['training']}
{'='*35}
Let's go! 🔥"""
    
    def get_week_schedule(self):
        """Get full week schedule"""
        message = "📅 WEEKLY SCHEDULE\n" + "="*35 + "\n"
        
        for day, workout in self.workout_schedule["weekly_schedule"].items():
            emoji = "💪" if workout["type"] != "rest" else "😴"
            message += f"{emoji} {day}: {workout['training']}\n"
        
        return message + "="*35
    
    # ===== INJECTION FEATURES =====
    
    def get_todays_injections(self):
        """Get today's injections"""
        today = datetime.now(self.timezone).strftime("%A")
        injections = self.ped_schedule["injection_schedule"].get(today)
        
        if not injections:
            return f"✅ NO INJECTIONS TODAY ({today})"
        
        message = f"💉 INJECTIONS ({today.upper()})\n" + "="*35 + "\n"
        
        for inj in injections["injections"]:
            message += f"{inj['compound']} — {inj['dosage']}\n"
        
        return message + "="*35
    
    def get_injection_schedule(self):
        """Get full week injection schedule"""
        message = "💉 INJECTION SCHEDULE\n" + "="*35 + "\n"
        
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        
        for day in days:
            if day in self.ped_schedule["injection_schedule"]:
                compounds = [i["compound"] for i in self.ped_schedule["injection_schedule"][day]["injections"]]
                message += f"📍 {day}: {', '.join(compounds)}\n"
            else:
                message += f"⭕ {day}: Rest\n"
        
        return message + "="*35
    
    # ===== STATE MANAGEMENT =====
    
    def set_skip_tracking(self):
        """Skip tracking for today"""
        self.user_settings["skip_tracking_today"] = True
        self.save_json("user_settings.json", self.user_settings)
        return "✅ Skipping macro tracking today. Injection & workout reminders still active."
    
    def resume_tracking(self):
        """Resume tracking for today"""
        self.user_settings["skip_tracking_today"] = False
        self.save_json("user_settings.json", self.user_settings)
        return "✅ Resumed tracking today!"
    
    def reset_daily_macros(self):
        """Manual reset"""
        self.daily_macros = self.default_daily_macros()
        self.save_json("daily_macros.json", self.daily_macros)
        return "✅ Macros reset for new day!"
    
    def save_chat_id(self, chat_id):
        """Save user's chat ID"""
        self.user_settings["chat_id"] = chat_id
        self.save_json("user_settings.json", self.user_settings)
    
    # ===== SUMMARY =====
    
    def get_daily_summary(self):
        """Get full daily summary"""
        self.check_and_reset_day()
        today = datetime.now(self.timezone).strftime("%A")
        workout = self.workout_schedule["weekly_schedule"].get(today)
        injections = self.ped_schedule["injection_schedule"].get(today)
        
        summary = f"""{'='*40}
📊 DAILY SUMMARY - {today.upper()}
{'='*40}

💪 Workout: {workout['training'] if workout else 'No data'}

💉 Injections: """
        
        if injections:
            for inj in injections["injections"]:
                summary += f"\n  • {inj['compound']} {inj['dosage']}"
        else:
            summary += "None today"
        
        summary += f"""

🎯 Macros:
  Protein: {self.daily_macros['daily_totals']['protein']}g / {self.macro_goals['daily_targets']['protein']}g
  Carbs: {self.daily_macros['daily_totals']['carbs']}g / {self.macro_goals['daily_targets']['carbs']}g
  Fat: {self.daily_macros['daily_totals']['fat']}g / {self.macro_goals['daily_targets']['fat']}g
  Calories: {self.daily_macros['daily_totals']['calories']} / {self.macro_goals['daily_targets']['calories']}

{'='*40}"""
        
        return summary
