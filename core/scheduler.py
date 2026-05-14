"""
scheduler.py
定时任务调度器
- 支持执行 SQL / 数据同步 / 导出 等任务
- 支持 cron 表达式（简化版：每分钟/每小时/每天/每周/每月）
- 持久化到 config/scheduled_tasks.json
"""
import json
import os
import sys
import threading
import datetime
from typing import Callable, Optional


def _tasks_path() -> str:
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "config", "scheduled_tasks.json")


TASK_TYPE_SQL    = "sql"
TASK_TYPE_SYNC   = "sync"
TASK_TYPE_EXPORT = "export"
TASK_TYPE_BACKUP = "backup"

STATUS_ENABLED  = "enabled"
STATUS_DISABLED = "disabled"
STATUS_RUNNING  = "running"


class ScheduledTask:
    """定时任务数据模型"""
    def __init__(self, data: dict = None):
        d = data or {}
        self.id:          str  = d.get("id", "")
        self.name:        str  = d.get("name", "未命名")
        self.task_type:   str  = d.get("task_type", TASK_TYPE_SQL)
        self.status:      str  = d.get("status", STATUS_ENABLED)

        # 调度设置
        self.schedule_type: str  = d.get("schedule_type", "interval")  # interval | daily | weekly | monthly | cron
        self.interval_min:  int  = d.get("interval_min", 60)           # interval 模式：分钟间隔
        self.daily_time:    str  = d.get("daily_time", "00:00")        # daily 模式：HH:MM
        self.weekly_day:    int  = d.get("weekly_day", 0)              # weekly 模式：0=周一
        self.monthly_day:   int  = d.get("monthly_day", 1)             # monthly 模式：几号
        self.cron_expr:     str  = d.get("cron_expr", "")              # cron 原始表达式（仅显示）

        # 任务内容
        self.sql:           str  = d.get("sql", "")                    # SQL 类型
        self.conn_name:     str  = d.get("conn_name", "")
        self.db_name:       str  = d.get("db_name", "")
        self.sync_cfg:      dict = d.get("sync_cfg", {})               # sync 类型
        self.export_cfg:    dict = d.get("export_cfg", {})             # export 类型
        self.backup_cfg:    dict = d.get("backup_cfg", {})             # backup 类型：{tables:[], include_data:bool, backup_dir:str}
        self.description:   str  = d.get("description", "")

        # 执行记录
        self.last_run:      str  = d.get("last_run", "")
        self.last_result:   str  = d.get("last_result", "")
        self.run_count:     int  = d.get("run_count", 0)
        self.next_run:      str  = d.get("next_run", "")

    def to_dict(self) -> dict:
        return {
            "id":           self.id,
            "name":         self.name,
            "task_type":    self.task_type,
            "status":       self.status,
            "schedule_type": self.schedule_type,
            "interval_min": self.interval_min,
            "daily_time":   self.daily_time,
            "weekly_day":   self.weekly_day,
            "monthly_day":  self.monthly_day,
            "cron_expr":    self.cron_expr,
            "sql":          self.sql,
            "conn_name":    self.conn_name,
            "db_name":      self.db_name,
            "sync_cfg":     self.sync_cfg,
            "export_cfg":   self.export_cfg,
            "backup_cfg":   self.backup_cfg,
            "description":  self.description,
            "last_run":     self.last_run,
            "last_result":  self.last_result,
            "run_count":    self.run_count,
            "next_run":     self.next_run,
        }

    def calc_next_run(self) -> datetime.datetime:
        """计算下次执行时间"""
        now = datetime.datetime.now()
        if self.schedule_type == "interval":
            return now + datetime.timedelta(minutes=max(1, self.interval_min))
        elif self.schedule_type == "daily":
            try:
                h, m = map(int, self.daily_time.split(":"))
            except Exception:
                h, m = 0, 0
            next_dt = now.replace(hour=h, minute=m, second=0, microsecond=0)
            if next_dt <= now:
                next_dt += datetime.timedelta(days=1)
            return next_dt
        elif self.schedule_type == "weekly":
            target_wd = self.weekly_day
            days_ahead = (target_wd - now.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7
            return (now + datetime.timedelta(days=days_ahead)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
        elif self.schedule_type == "monthly":
            try:
                next_dt = now.replace(day=self.monthly_day, hour=0, minute=0, second=0)
                if next_dt <= now:
                    # 下个月
                    if now.month == 12:
                        next_dt = next_dt.replace(year=now.year + 1, month=1)
                    else:
                        next_dt = next_dt.replace(month=now.month + 1)
                return next_dt
            except Exception:
                return now + datetime.timedelta(days=30)
        else:
            return now + datetime.timedelta(hours=1)

    def update_next_run(self):
        self.next_run = self.calc_next_run().strftime("%Y-%m-%d %H:%M:%S")

    def is_due(self) -> bool:
        """是否到了执行时间"""
        if self.status != STATUS_ENABLED or not self.next_run:
            return False
        try:
            next_dt = datetime.datetime.strptime(self.next_run, "%Y-%m-%d %H:%M:%S")
            return datetime.datetime.now() >= next_dt
        except Exception:
            return False

    def schedule_label(self) -> str:
        """返回人类可读的调度描述"""
        t = self.schedule_type
        if t == "interval":
            if self.interval_min < 60:
                return f"每 {self.interval_min} 分钟"
            elif self.interval_min == 60:
                return "每小时"
            else:
                h = self.interval_min // 60
                return f"每 {h} 小时"
        elif t == "daily":
            return f"每天 {self.daily_time}"
        elif t == "weekly":
            days = ["周一","周二","周三","周四","周五","周六","周日"]
            return f"每{days[self.weekly_day % 7]}"
        elif t == "monthly":
            return f"每月 {self.monthly_day} 日"
        else:
            return self.cron_expr or "自定义"


class TaskScheduler:
    """任务调度器"""

    def __init__(self):
        self.tasks: list[ScheduledTask] = []
        self._timer: Optional[threading.Timer] = None
        self._lock  = threading.Lock()
        self._on_run: Optional[Callable[[ScheduledTask], None]] = None
        self.load()

    def set_run_callback(self, fn: Callable[[ScheduledTask], None]):
        """设置任务执行回调（主线程通过信号接收）"""
        self._on_run = fn

    # ── 持久化 ────────────────────────────────────
    def load(self):
        path = _tasks_path()
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.tasks = [ScheduledTask(d) for d in data]
            except Exception:
                self.tasks = []
        else:
            self.tasks = []

    def save(self):
        path = _tasks_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump([t.to_dict() for t in self.tasks], f,
                      ensure_ascii=False, indent=2)

    # ── CRUD ─────────────────────────────────────
    def add_task(self, task: ScheduledTask) -> ScheduledTask:
        import uuid
        task.id = str(uuid.uuid4())[:8]
        task.update_next_run()
        with self._lock:
            self.tasks.append(task)
        self.save()
        return task

    def update_task(self, task_id: str, **kwargs):
        with self._lock:
            for t in self.tasks:
                if t.id == task_id:
                    for k, v in kwargs.items():
                        setattr(t, k, v)
                    t.update_next_run()
                    break
        self.save()

    def delete_task(self, task_id: str):
        with self._lock:
            self.tasks = [t for t in self.tasks if t.id != task_id]
        self.save()

    def toggle_task(self, task_id: str) -> str:
        with self._lock:
            for t in self.tasks:
                if t.id == task_id:
                    t.status = (STATUS_DISABLED
                                if t.status == STATUS_ENABLED
                                else STATUS_ENABLED)
                    if t.status == STATUS_ENABLED:
                        t.update_next_run()
                    new_status = t.status
                    break
            else:
                new_status = ""
        self.save()
        return new_status

    def run_now(self, task_id: str):
        """立即触发一次任务（不等计时器）"""
        with self._lock:
            task = next((t for t in self.tasks if t.id == task_id), None)
        if task and self._on_run:
            self._on_run(task)

    # ── 调度循环 ─────────────────────────────────
    def start(self):
        self._schedule_next()

    def stop(self):
        if self._timer:
            self._timer.cancel()
            self._timer = None

    def _schedule_next(self):
        self._timer = threading.Timer(30, self._tick)
        self._timer.daemon = True
        self._timer.start()

    def _tick(self):
        """每 30 秒检查一次到期任务"""
        with self._lock:
            due_tasks = [t for t in self.tasks if t.is_due()]

        for task in due_tasks:
            task.status = STATUS_RUNNING
            if self._on_run:
                try:
                    self._on_run(task)
                except Exception as e:
                    task.last_result = f"[FAIL] {e}"
            # 更新执行记录
            task.last_run = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            task.run_count += 1
            task.status = STATUS_ENABLED
            task.update_next_run()

        if due_tasks:
            self.save()

        self._schedule_next()
