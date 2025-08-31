# supervisor/supervisor.py
import argparse
import os
import sys
import json

# 将 src 目录添加到 sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(current_dir, '..'))

from src.util import get_llm_client, get_llm_response, read_json_file, write_json_file
from src.key_manager import get_next_api_key # Added this import

def main():
    parser = argparse.ArgumentParser(description="监理师：整合所有建筑部件并生成最终建造规划。")
    parser.add_argument("--prompt", type=str, required=True, help="玩家的原始建筑指令。")

    args = parser.parse_args()

    print("监理师已启动...正在检查 build 目录。")

    build_dir = os.path.join(current_dir, '../build')
    if not os.path.exists(build_dir) or not os.listdir(build_dir):
        print("监理师：build 目录为空，无需执行。")
        return

    # 1. 读取所有生成的JSON文件
    build_components = []
    component_files = [f for f in os.listdir(build_dir) if f.endswith('.json')]
    for file_name in component_files:
        file_path = os.path.join(build_dir, file_name)
        component_data = read_json_file(file_path)
        if component_data:
            # 包含完整的 component_data，其中应包含 generated_structure 和 spatial_metadata
            build_components.append({
                "file_name": file_name,
                "description": component_data.get("description"),
                "generated_structure": component_data.get("generated_structure", {}),
                "blocks_count": len(component_data.get("blocks", []))
            })

    if not build_components:
        print("监理师：未能从 build 目录加载任何建筑组件。")
        return

    print(f"监理师：找到了 {len(build_components)} 个建筑组件。")

    # 2. 构建发送给LLM的提示
    system_prompt = """你是一个顶级的《我的世界》建筑结构总工程师。你的核心任务是解决一个复杂的3D空间布局问题：将一系列独立的建筑组件，根据玩家的意图，组合成一个结构合理、无缝连接的宏伟建筑。

**首要原则：绝不允许组件重叠！**

**你的思考过程应遵循以下算法：**

1.  **寻找地基**: 首先，从组件列表中识别出最适合作为基础的组件（例如，`flat_land_generator` 生成的地形，或建筑的主体 `building_generator`）。将它的偏移量设置为 `{\"x\": 0, \"y\": 0, \"z\": 0}`。

2.  **逐个放置**: 遍历剩余的每个组件，思考它与已放置组件的逻辑关系（例如，“屋顶”应该在“墙体”的**正上方**，“道路”应该**连接**“大门”和“花园”）。

3.  **精确计算偏移**: 根据逻辑关系，利用已有组件的 `bounding_box` (边界框) 来计算新组件的 `offset`。
    *   **例1 (垂直堆叠)**: 如果要将“屋顶”放在“主楼”上，则屋顶的 `offset.y` 应该等于主楼的 `bounding_box.max_y + 1`。`offset.x` 和 `offset.z` 应与主楼对齐。
    *   **例2 (水平邻接)**: 如果要将“附属建筑”放在“主楼”的东边（X轴正方向），则其 `offset.x` 应该等于主楼的 `bounding_box.max_x + 1`。

4.  **最终验证**: 在确定所有偏移量后，在脑中进行一次最终检查，确保没有任何两个组件的最终边界框（组件偏移量 + 组件尺寸）会发生碰撞。

**输入格式:**
你将收到一个JSON对象，包含:
- `original_prompt`: 玩家的原始指令。
- `components`: 一个建筑组件的列表，每个组件都包含 `file_name`, `description`, 和 `generated_structure` (内含 `spatial_metadata`，其中有 `bounding_box` 和 `dimensions`)。

**输出格式:**
你必须只返回一个JSON数组，其中每个元素都包含 `file_name` 和你计算出的 `offset` (`x`, `y`, `z`)。

**示例输出:**
```json
[
  {
    "file_name": "main_hall_building_generator.json",
    "offset": {"x": 0, "y": 0, "z": 0}
  },
  {
    "file_name": "roof_pyramid_generator.json",
    "offset": {"x": 0, "y": 6, "z": 0}
  }
]
```
请严格遵守此流程，进行精确的计算，确保建筑的完美组装。
"""

    user_prompt_data = {
        "original_prompt": args.prompt,
        "components": build_components
    }
    user_prompt = json.dumps(user_prompt_data, indent=2, ensure_ascii=False)

    print("监理师：正在请求大模型进行最终规划...")

    # 3. 调用LLM
    try:
        api_key = get_next_api_key()
        client = get_llm_client(api_key)
        success, final_plan = get_llm_response(client, system_prompt, user_prompt)

        if not success:
            print(f"监理师：大模型规划失败: {final_plan}")
            sys.exit(1)

        print("监理师：成功从大模型获取最终布局规划。")

        # 4. 保存最终规划
        final_plan_path = os.path.join(build_dir, '../final_build_plan.json')
        write_json_file(final_plan_path, final_plan)

        print(f"监理师：最终建筑规划已保存到 {final_plan_path}")

    except Exception as e:
        print(f"监理师在执行过程中发生错误: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()