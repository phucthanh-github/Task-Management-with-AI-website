from datetime import timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from bson import ObjectId

from .database import get_db
from .mail import send_deadline_email
from .utils import utc_now
from .services.todo_service import TodoService

scheduler = AsyncIOScheduler()

async def check_deadlines_job():
    db = get_db()
    if db is None:
        print("[Scheduler] DB connection is not initialized yet. Skipping deadline email check.")
        return
        
    now = utc_now()
    deadline_threshold = now + timedelta(hours=24)
    
    query = {
        "status": {"$in": ["pending", "in_progress"]},
        "deadline": {
            "$gt": now,
            "$lte": deadline_threshold
        },
        "reminded": {"$ne": True}
    }
    
    try:
        cursor = db.todos.find(query)
        todos_to_remind = await cursor.to_list(length=100)
        
        if not todos_to_remind:
            return
            
        print(f"[Scheduler] Found {len(todos_to_remind)} upcoming todo(s) within 24 hours.")
        
        for todo in todos_to_remind:
            user_id = todo.get("user_id")
            user = await db.users.find_one({"_id": ObjectId(user_id)})
            if not user:
                continue
                
            user_email = user.get("email")
            todo_title = todo.get("title")
            todo_deadline = todo.get("deadline")
            
            sent = send_deadline_email(user_email, todo_title, todo_deadline)
            if sent:
                await db.todos.update_one(
                    {"_id": todo["_id"]},
                    {"$set": {"reminded": True, "updated_at": utc_now()}}
                )
                print(f"[Scheduler] Marked todo '{todo_title}' as reminded.")
    except Exception as e:
        print(f"[Scheduler] Error running deadline check job: {e}")

async def update_overdue_todos_job():
    db = get_db()
    if db is None:
        return
    try:
        count = await TodoService.update_overdue_todos(db)
        if count > 0:
            print(f"[Scheduler] Overdue job: Transitioned {count} todo(s) to overdue status.")
    except Exception as e:
        print(f"[Scheduler] Error running overdue transition job: {e}")

def start_scheduler():
    if not scheduler.running:
        scheduler.add_job(check_deadlines_job, "interval", minutes=1, id="check_deadlines_job_id")
        scheduler.add_job(update_overdue_todos_job, "interval", minutes=1, id="update_overdue_todos_job_id")
        scheduler.start()
        print("[Scheduler] Scheduler started (checking email reminders and overdue tasks every 1 minute).")

def shutdown_scheduler():
    if scheduler.running:
        scheduler.shutdown()
        print("[Scheduler] Scheduler stopped.")
