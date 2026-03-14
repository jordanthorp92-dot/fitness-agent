import json
import requests
from datetime import datetime, time
import pytz
import time as time_module
import threading
from apscheduler.schedulers.background import BackgroundScheduler
from fitness_agent import FitnessAgent
from dotenv import load_dotenv
import os
load_dotenv()
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

TELEGRAM_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
TIMEZONE = "Asia/Bangkok"

class TelegramFitnessBot:
    """Telegram Bot with Automatic Reminders"""
    
    def __init__(self):
        self.agent = FitnessAgent(timezone=TIMEZONE)
        self.last_update_id = 0
        self.tz = pytz.timezone(TIMEZONE)
        self.scheduler = BackgroundScheduler(timezone=TIMEZONE)
        self.reminders_sent_today = {}
        self.load_reminder_schedule()
        self.setup_reminders()
    
    def load_reminder_schedule(self):
        """Load reminder schedule"""
        try:
            with open("reminder_schedule.json", "r") as f:
                self.reminder_schedule = json.load(f)
        except FileNotFoundError:
            self.reminder_schedule = self.create_default_reminders()
            self.save_reminder_schedule()
    
    def save_reminder_schedule(self):
        """Save reminder schedule"""
        with open("reminder_schedule.json", "w") as f:
            json.dump(self.reminder_schedule, f, indent=2)
    
    def create_default_reminders(self):
        """Create default reminders based on your schedule"""
        return {
            "reminders": [
                {"day": "Monday", "time": "10:30", "type": "workout", "name": "Lower Body"},
                {"day": "Wednesday", "time": "05:30", "type": "run", "name": "Sprints"},
                {"day": "Wednesday", "time": "10:30", "type": "workout", "name": "Upper Body"},
                {"day": "Friday", "time": "05:30", "type": "run", "name": "5K Run"},
                {"day": "Friday", "time": "10:30", "type": "workout", "name": "Lower Body"},
                {"day": "Sunday", "time": "05:30", "type": "run", "name": "10K Run"},
                {"day": "Sunday", "time": "10:30", "type": "workout", "name": "Upper Body"},
                {"day": "Monday", "time": "20:30", "type": "injection"},
                {"day": "Wednesday", "time": "20:30", "type": "injection"},
                {"day": "Friday", "time": "20:30", "type": "injection"},
                {"day": "Sunday", "time": "20:30", "type": "injection"},
                {"day": "Monday", "time": "20:30", "type": "summary"},
                {"day": "Tuesday", "time": "20:30", "type": "summary"},
                {"day": "Wednesday", "time": "20:30", "type": "summary"},
                {"day": "Thursday", "time": "20:30", "type": "summary"},
                {"day": "Friday", "time": "20:30", "type": "summary"}
            ]
        }
    
    def send_message(self, chat_id, text):
        """Send Telegram message"""
        if not chat_id:
            print("❌ No chat_id set. First message needed to set it.")
            return False
        
        url = f"{TELEGRAM_API_URL}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML"
        }
        
        try:
            response = requests.post(url, json=payload, timeout=10)
            return response.status_code == 200
        except Exception as e:
            print(f"❌ Error sending message: {e}")
            return False
    
    def get_updates(self):
        """Get new Telegram messages"""
        url = f"{TELEGRAM_API_URL}/getUpdates"
        payload = {"offset": self.last_update_id + 1, "timeout": 30}
        
        try:
            response = requests.post(url, json=payload, timeout=35)
            return response.json()
        except Exception as e:
            print(f"❌ Error getting updates: {e}")
            return {"ok": False, "result": []}
    
    # ===== REMINDER SCHEDULER SETUP =====
    
    def setup_reminders(self):
        """Setup all reminders in scheduler"""
        for reminder in self.reminder_schedule["reminders"]:
            day = reminder["day"]
            time_str = reminder["time"]
            reminder_type = reminder["type"]
            
            hour, minute = map(int, time_str.split(":"))
            
            job_id = f"{day}_{time_str}_{reminder_type}"
            
            try:
                self.scheduler.add_job(
                    self.send_reminder,
                    'cron',
                    day_of_week=self.day_to_cron(day),
                    hour=hour,
                    minute=minute,
                    args=[reminder],
                    id=job_id,
                    replace_existing=True
                )
                print(f"✅ Scheduled: {job_id}")
            except Exception as e:
                print(f"❌ Error scheduling {job_id}: {e}")
    
    def day_to_cron(self, day_name):
        """Convert day name to cron day of week"""
        days = {
            "Monday": 0,
            "Tuesday": 1,
            "Wednesday": 2,
            "Thursday": 3,
            "Friday": 4,
            "Saturday": 5,
            "Sunday": 6
        }
        return days.get(day_name, 0)
    
    def send_reminder(self, reminder):
        """Send a reminder"""
        chat_id = self.agent.user_settings.get("chat_id")
        if not chat_id:
            print("⚠️  No chat_id yet. Skipping reminder.")
            return
        
        reminder_type = reminder.get("type")
        
        try:
            if reminder_type == "workout":
                message = self._build_workout_reminder(reminder)
            elif reminder_type == "run":
                message = self._build_run_reminder(reminder)
            elif reminder_type == "injection":
                message = self._build_injection_reminder()
            elif reminder_type == "summary":
                message = self._build_summary_reminder()
            else:
                return
            
            self.send_message(chat_id, message)
            print(f"✅ Sent reminder: {reminder_type}")
        except Exception as e:
            print(f"❌ Error sending reminder: {e}")
    
    def _build_workout_reminder(self, reminder):
        """Build workout reminder message"""
        name = reminder.get("name", "")
        return f"""💪 <b>Gym Workout Reminder</b>

<b>{name}</b> training in 1 hour!

Time to gear up and hit it! 🔥"""
    
    def _build_run_reminder(self, reminder):
        """Build run reminder message"""
        name = reminder.get("name", "")
        return f"""🏃 <b>Run Reminder</b>

<b>{name}</b> in 30 minutes!

Time to warm up and get going! 💪"""
    
    def _build_injection_reminder(self):
        """Build injection reminder message"""
        today = datetime.now(self.tz).strftime("%A")
        injections = self.agent.ped_schedule["injection_schedule"].get(today)
        
        if not injections:
            return "✅ No injections today"
        
        message = "💉 <b>Injection Time Tonight</b>\n\n"
        for inj in injections["injections"]:
            message += f"• {inj['compound']} — {inj['dosage']}\n"
        
        return message
    
    def _build_summary_reminder(self):
        """Build daily macro summary"""
        today = datetime.now(self.tz).strftime("%A")
        
        if today not in self.agent.macro_goals["tracking_days"]:
            return "📅 Today is not a tracking day."
        
        if self.agent.user_settings.get("skip_tracking_today"):
            return None  # Skip if user said "not tracking today"
        
        targets = self.agent.macro_goals["allowed_ranges"]
        totals = self.agent.daily_macros["daily_totals"]
        
        protein_status = self._check_status(totals["protein"], targets["protein"])
        carbs_status = self._check_status(totals["carbs"], targets["carbs"])
        fat_status = self._check_status(totals["fat"], targets["fat"])
        
        coaching = self.agent._generate_coaching_message(totals, targets)
        
        message = f"""🎯 <b>Daily Macro Summary</b>

<b>Protein:</b> {totals['protein']}g / {targets['protein']['target']}g {protein_status}
<b>Carbs:</b> {totals['carbs']}g / {targets['carbs']['target']}g {carbs_status}
<b>Fat:</b> {totals['fat']}g / {targets['fat']['target']}g {fat_status}
<b>Calories:</b> {totals['calories']} / {targets['calories']['target']}

<b>Coaching:</b>
{coaching}"""
        
        return message
    
    def _check_status(self, current, target_range):
        """Quick status check"""
        if target_range["min"] <= current <= target_range["max"]:
            return "✅"
        elif current < target_range["min"]:
            return f"⬇️ (need {target_range['min'] - current}g)"
        else:
            return f"⬆️ (+{current - target_range['max']}g over)"
    
    # ===== MESSAGE PROCESSING =====
    
    def process_message(self, chat_id, message_text):
        """Process user message"""
        message_lower = message_text.strip().lower()
        
        # Auto-save chat ID on first message
        if not self.agent.user_settings.get("chat_id"):
            self.agent.save_chat_id(chat_id)
            return "✅ Chat ID saved! Your bot is now active.\n\nType 'help' for commands."
        
        # Handle commands
        if message_lower == "help":
            return self._get_help()
        
        elif message_lower == "summary":
            return self.agent.get_daily_summary()
        
        elif message_lower == "status":
            return self.agent.get_macro_status()
        
        elif message_lower == "today workout":
            return self.agent.get_todays_workout()
        
        elif message_lower == "week":
            return self.agent.get_week_schedule()
        
        elif message_lower == "today inject" or message_lower == "inject today":
            return self.agent.get_todays_injections()
        
        elif message_lower == "inject schedule":
            return self.agent.get_injection_schedule()
        
        elif message_lower == "reset":
            return self.agent.reset_daily_macros()
        
        elif message_lower == "today i am not tracking":
            return self.agent.set_skip_tracking()
        
        elif message_lower == "resume tracking":
            return self.agent.resume_tracking()
        
        elif message_lower.startswith("log "):
            food = message_lower[4:]
            return self.agent.log_food(food)
        
        elif message_lower.startswith("add food:"):
            parts = message_lower.split("|")
            if len(parts) == 5:
                try:
                    name = parts[0].replace("add food:", "").strip()
                    calories = int(parts[1].strip())
                    protein = int(parts[2].strip())
                    carbs = int(parts[3].strip())
                    fat = int(parts[4].strip())
                    return self.agent.add_custom_food(name, calories, protein, carbs, fat)
                except ValueError:
                    return "❌ Invalid format. Use: add food: name | calories | protein | carbs | fat"
            else:
                return "❌ Invalid format. Use: add food: name | calories | protein | carbs | fat"
        
        else:
            return self._get_help()
    
    def _get_help(self):
        """Help message"""
        return """🤖 <b>FITNESS AGENT COMMANDS</b>

📊 <b>Macro Tracking:</b>
• log [food] - Log a meal
• status - Check progress
• add food: [name] | [cal] | [p] | [c] | [f]

💪 <b>Workouts:</b>
• today workout - What's today?
• week - Full week schedule

💉 <b>Injections:</b>
• today inject - What to inject?
• inject schedule - Full week

📱 <b>Other:</b>
• summary - Full dashboard
• today i am not tracking - Skip macros
• resume tracking - Resume tracking
• help - This message"""
    
    # ===== MAIN BOT LOOP =====
    
    def run(self):
        """Main bot loop"""
        print("🤖 Starting Fitness Agent Telegram Bot...")
        print(f"Bot: @Jordans_fitness_bot")
        print(f"Timezone: {TIMEZONE}")
        
        # Start scheduler
        self.scheduler.start()
        print("✅ Scheduler started - reminders active!")
        
        print("📡 Listening for messages...\n")
        
        try:
            while True:
                try:
                    updates = self.get_updates()
                    
                    if updates.get("ok"):
                        for update in updates.get("result", []):
                            self.last_update_id = update["update_id"]
                            
                            if "message" in update:
                                message = update["message"]
                                chat_id = message["chat"]["id"]
                                text = message.get("text", "")
                                user = message["chat"].get("first_name", "User")
                                
                                print(f"[{datetime.now(self.tz).strftime('%H:%M:%S')}] {user}: {text}")
                                
                                response = self.process_message(chat_id, text)
                                if response:
                                            self.send_message(chat_id, response)
                                
                                print("→ Response sent\n")
                    
                    time_module.sleep(0.5)
                
                except KeyboardInterrupt:
                    break
                except Exception as e:
                    print(f"❌ Error: {e}")
                    time_module.sleep(5)
        
        finally:
            self.scheduler.shutdown()
            print("\n✋ Bot stopped.")


if __name__ == "__main__":
    bot = TelegramFitnessBot()
    bot.run()
