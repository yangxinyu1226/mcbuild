# src/main_planner.py
import os
import sys
import time
import json
import subprocess
import re
import traceback

# 将根目录添加到 sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(current_dir, '..'))

from src.util import get_llm_client, get_llm_response, read_json_file, write_json_file
from src.rcon_client import get_rcon_client, RconClient
from src.key_manager import get_next_api_key
from src.generator_designer import GeneratorDesigner

COMMAND_QUEUE_FILE = os.path.join(current_dir, '../command_queue.json')
BUILD_DIR = os.path.join(current_dir, '../build')
GENERATORS_DIR = os.path.join(current_dir, '../generators')
FINAL_PLAN_FILE = os.path.join(current_dir, '../final_build_plan.json')

def get_available_generators() -> list[str]:
    """扫描 generators 目录，返回所有可用的 .py 生成器脚本列表。"""
    if not os.path.exists(GENERATORS_DIR):
        return []
    return [f for f in os.listdir(GENERATORS_DIR) if f.endswith('.py') and not f.startswith('__')]

def route_request(client, user_prompt: str, available_generators: list[str]) -> dict:
    """智能路由：决定是分解任务还是设计新生成器。"""
    generator_list_str = "\n- ".join(available_generators)
    
    system_prompt = f"""You are a master controller for a Minecraft AI builder. Your primary function is to analyze a user's request and determine the best course of action based on a list of available tools (generator scripts).

Available Tools:
- {generator_list_str}

Based on the user's request, you have two choices:

1.  **run_existing_generators**: If the available tools are sufficient to fulfill the request, decompose the request into a JSON array of sub-tasks. Each task object must have `generator`, `name`, and `task` fields.

2.  **design_new_generator**: If the request requires a new, specialized capability that no existing tool can handle, you must request the creation of a new generator. Provide a detailed description of the new generator's purpose and a suggested filename for it.

**IMPORTANT**: Respond with a single JSON object. This object MUST have a single root key named `action`, whose value is either `run_existing_generators` or `design_new_generator`.

**Example 1: Using existing tools**
User Request: "Build a small wooden house with a garden."
Your JSON Response:
```json
{{
  "action": "run_existing_generators",
  "sub_tasks": [
    {{
      "generator": "building_generator.py",
      "name": "small_house",
      "task": "A small wooden house with a door and windows."
    }},
    {{
      "generator": "garden_generator.py",
      "name": "house_garden",
      "task": "A simple garden with some flowers and a path."
    }}
  ]
}}
```

**Example 2: Designing a new tool**
User Request: "Build a giant futuristic portal to another dimension."
Your JSON Response:
```json
{{
  "action": "design_new_generator",
  "new_generator_request": {{
    "description": "A generator capable of creating sci-fi and futuristic portals with glowing effects and complex geometric shapes.",
    "suggested_name": "portal_generator"
  }}
}}
```
"""
    
    user_prompt_for_llm = f"User Request: \"{user_prompt}\""
    print("总规划师：正在请求路由决策...")
    success, response = get_llm_response(client, system_prompt, user_prompt_for_llm)
    
    if success:
        print(f"总规划师：成功获取路由决策: {response}")
        return response
    else:
        print(f"总规划师：获取路由决策失败: {response}")
        return None

def clear_build_directory():
    """清理 build 目录中的所有 .json 文件。"""
    print("总规划师：正在清理 build 目录...")
    if not os.path.exists(BUILD_DIR):
        os.makedirs(BUILD_DIR)
        return
    for file_name in os.listdir(BUILD_DIR):
        if file_name.endswith('.json'):
            os.remove(os.path.join(BUILD_DIR, file_name))
    if os.path.exists(FINAL_PLAN_FILE):
        os.remove(FINAL_PLAN_FILE)

def run_generators(sub_tasks):
    """执行所有生成器子任务。"""
    print("总规划师：正在启动生成器...")
    for task in sub_tasks:
        generator_script = os.path.join(GENERATORS_DIR, task['generator'])
        if not os.path.exists(generator_script):
            print(f"警告：找不到指定的生成器脚本 '{task['generator']}'，已跳过。")
            continue
        
        cmd = [sys.executable, "-X", "utf8", generator_script, '--name', task['name'], '--prompt', task['task']]
        print(f"总规划师：运行指令: {' '.join(cmd)}")
        subprocess.run(cmd, check=True)
    print("总规划师：所有生成器执行完毕。")

def run_supervisor(prompt):
    """执行监理师程序。"""
    print("总规划师：正在启动监理师...")
    supervisor_script = os.path.join(current_dir, '../supervisor/supervisor.py')
    cmd = [sys.executable, "-X", "utf8", supervisor_script, '--prompt', prompt]
    subprocess.run(cmd, check=True)
    print("总规划师：监理师执行完毕。")

def execute_final_plan(rcon_client: RconClient, player_name: str):
    """组装并执行最终的建筑计划。"""
    print("总规划师：正在组装最终建筑方案...")
    final_plan = read_json_file(FINAL_PLAN_FILE)
    if not final_plan:
        print("总规划师：错误：找不到最终规划文件。建造中止。")
        return

    pos_success, pos_result = rcon_client.get_player_position(player_name)
    if not pos_success:
        print(f"总规划师：执行失败，无法获取玩家位置: {pos_result}")
        return
    base_x, base_y, base_z = pos_result

    final_block_list = []
    for component_plan in final_plan:
        component_file = os.path.join(BUILD_DIR, component_plan['file_name'])
        component_data = read_json_file(component_file)
        if not component_data:
            print(f"警告：找不到组件文件 {component_plan['file_name']}，已跳过。")
            continue
        
        offset = component_plan.get('offset', {'x': 0, 'y': 0, 'z': 0})
        for block in component_data.get('blocks', []):
            final_block_list.append({
                'x': int(base_x + offset.get('x', 0) + block['x']),
                'y': int(base_y + offset.get('y', 0) + block['y']),
                'z': int(base_z + offset.get('z', 0) + block['z']),
                'block_type': block['block_type']
            })
    
    print(f"总规划师：组装完成，总计 {len(final_block_list)} 个方块。准备施工！")
    rcon_client.execute_build(final_block_list)

def main_loop():
    """主事件循环。"""
    print("AI建筑总规划师已启动（动态进化架构）...")
    llm_client = get_llm_client(get_next_api_key())
    rcon_client = get_rcon_client()
    designer = GeneratorDesigner(llm_client)

    while True:
        try:
            requests = read_json_file(COMMAND_QUEUE_FILE)
            if not requests:
                time.sleep(1)
                continue
            
            request_data = requests.pop(0)
            write_json_file(COMMAND_QUEUE_FILE, requests)

            prompt = request_data['prompt']
            player_name = request_data['player']
            print(f"总规划师：接收到新任务: '{prompt}' (来自玩家: {player_name})")

            # --- 动态进化工作流 ---
            clear_build_directory()
            available_generators = get_available_generators()
            
            # 1. 智能路由决策
            route_decision = route_request(llm_client, prompt, available_generators)
            if not route_decision or 'action' not in route_decision:
                print("总规划师：路由决策失败或格式无效，任务中止。")
                continue

            action = route_decision['action']

            if action == 'design_new_generator':
                print("总规划师：决策为设计新生成器。")
                req = route_decision.get('new_generator_request', {})
                description = req.get('description', 'A new generator based on user prompt.')
                name = req.get('suggested_name', 'new_custom_generator')
                # Ensure the name doesn't have the extension, as it's added later
                if name.endswith('.py'):
                    name = name[:-3]

                success, result = designer.create_new_generator(description, name)
                if success:
                    print(f"总规划师：新生成器 '{name}.py' 创建成功！将重新处理任务。")
                    # 将任务重新放回队列进行下一轮处理
                    current_requests = read_json_file(COMMAND_QUEUE_FILE) or []
                    current_requests.insert(0, request_data)
                    write_json_file(COMMAND_QUEUE_FILE, current_requests)
                else:
                    print(f"总规划师：创建新生成器失败: {result}")
                continue # 结束当前循环，下一轮将包含新生成器

            elif action == 'run_existing_generators':
                print("总规划师：决策为使用现有生成器。")
                sub_tasks = route_decision.get('sub_tasks', [])
                if not sub_tasks:
                    print("总规划师：路由决策没有提供子任务，任务中止。")
                    continue
                
                # 2. 运行生成器
                run_generators(sub_tasks)

                # 3. 运行监理师
                run_supervisor(prompt)

                # 4. 组装并执行最终计划
                execute_final_plan(rcon_client, player_name)

            else:
                print(f"总规划师：未知的路由决策动作: {action}")

        except Exception as e:
            print(f"主循环发生致命错误: {e}")
            traceback.print_exc()
            time.sleep(5)

if __name__ == "__main__":
    main_loop()
