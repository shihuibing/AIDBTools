#!/usr/bin/env python3
"""
测试 AIAgent 新增的任务列表和工具调用计数功能。
"""
import sys
sys.path.insert(0, '.')

from core.ai_agent import AIAgent

def mock_execute_fn(sql):
    """模拟 SQL 执行函数"""
    print(f"[Mock] 执行 SQL: {sql}")
    return [], []

def test_task_list():
    print("=== 测试任务列表功能 ===")
    agent = AIAgent(execute_fn=mock_execute_fn)
    
    # 添加任务
    task1 = agent.add_task("分析用户表结构")
    task2 = agent.add_task("统计用户数量", status="pending", metadata={"priority": "high"})
    print(f"添加的任务 ID: {task1}, {task2}")
    
    # 获取任务列表
    tasks = agent.get_tasks()
    print(f"当前任务数: {len(tasks)}")
    for t in tasks:
        print(f"  - {t['id']}: {t['description']} ({t['status']})")
    
    # 完成任务
    success = agent.complete_task(task1)
    print(f"完成任务 {task1}: {success}")
    
    tasks = agent.get_tasks()
    for t in tasks:
        print(f"  - {t['id']}: {t['description']} ({t['status']})")
        if t['status'] == 'completed':
            print(f"    完成时间: {t['completed_at']}")

def test_tool_call_counts():
    print("\n=== 测试工具调用计数功能 ===")
    agent = AIAgent(execute_fn=mock_execute_fn)
    
    # 模拟调用一些工具
    agent.increment_tool_call("think")
    agent.increment_tool_call("sql")
    agent.increment_tool_call("sql")
    agent.increment_tool_call("obs")
    agent.increment_tool_call("done")
    
    counts = agent.get_tool_call_counts()
    print("工具调用计数:")
    for tool, count in counts.items():
        print(f"  {tool}: {count}")

def test_integration():
    print("\n=== 测试集成（模拟一次 Agent 运行） ===")
    agent = AIAgent(execute_fn=mock_execute_fn)
    
    # 模拟一次任务分解
    task_id = agent.add_task("查询数据库版本")
    print(f"创建任务: {task_id}")
    
    # 模拟 Agent 内部工具调用
    agent.increment_tool_call("think")
    agent.increment_tool_call("sql")
    agent.increment_tool_call("obs")
    agent.increment_tool_call("done")
    
    # 完成任务
    agent.complete_task(task_id)
    
    print("任务列表:")
    for t in agent.get_tasks():
        print(f"  - {t['description']}: {t['status']}")
    
    print("工具调用计数:")
    for tool, count in agent.get_tool_call_counts().items():
        print(f"  {tool}: {count}")

if __name__ == "__main__":
    test_task_list()
    test_tool_call_counts()
    test_integration()
    print("\n所有测试通过")