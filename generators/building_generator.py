import os
import sys
import json
import argparse

# 将根目录添加到 sys.path，以便可以正确地调用其他目录的脚本
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(current_dir, '..'))

from src.util import get_llm_client, get_llm_response, write_json_file, generate_blocks_from_task
from src.key_manager import get_next_api_key

BUILD_DIR = os.path.join(current_dir, '../build')

class BuildingGenerator:
    """
    建筑生成器 - 负责生成各种类型的建筑，如房屋、塔楼、城堡等。
    """
    def __init__(self, llm_client):
        self.llm_client = llm_client

    def generate(self, description: str) -> dict:
        """
        根据描述生成建筑的结构和细节。
        Args:
            description: 建筑的自然语言描述。
        Returns:
            一个字典，包含建筑的方块布局和结构信息。
        """
        print(f"BuildingGenerator: Generating building for description: {description}")

        system_prompt = """你是一个Minecraft建筑设计师。请根据用户描述，输出一个JSON任务数组来建造建筑。

**规则:**
1.  **输出格式:** 必须是JSON数组。不要输出任何非JSON内容。
2.  **坐标系统:** 所有坐标都是相对于(0,0,0)的。
3.  **方块ID:** `block_type` 必须是标准的Minecraft ID。
4.  **空心结构:** 房屋、塔楼等建筑主体请使用 `hollow_cube` 工具。

**可用工具 (格式: `tool_name(args...)`):**
- `cube(x, y, z, size_x, size_y, size_z, block_type, hollow=False)`
- `hollow_cube(x, y, z, size_x, size_y, size_z, block_type)`
- `line(x1, y1, z1, x2, y2, z2, block_type)`
- `sphere(x, y, z, radius, block_type, hollow=True)`
- `cylinder(x, y, z, radius, height, block_type, hollow=False)`
- `pyramid(x, y, z, base_size, block_type)`
- `circle(x, y, z, radius, block_type, hollow=False)`
- `arch(x, y, z, radius, width, block_type)`
- `single_block(x, y, z, block_type)`

**示例输出:**
```json
[
  {
    "tool": "hollow_cube",
    "args": {
      "x": 0,
      "y": 0,
      "z": 0,
      "size_x": 7,
      "size_y": 5,
      "size_z": 7,
      "block_type": "minecraft:oak_planks"
    }
  }
]
```
"""    
        user_prompt = f"设计一个Minecraft建筑：{description}"
        print(f"BuildingGenerator: Sending prompt to LLM: {user_prompt}")

        success, llm_output = get_llm_response(self.llm_client, system_prompt, user_prompt)

        if not success:
            print(f"BuildingGenerator: Error from LLM: {llm_output}")
            return {"description": description, "generated_structure": {}, "blocks": []}
        
        # Validate LLM output structure
        if not isinstance(llm_output, list):
            print(f"BuildingGenerator: LLM output is not a list: {llm_output}")
            return {"description": description, "generated_structure": {}, "blocks": []}
        
        generated_components = []
        for item in llm_output:
            if not isinstance(item, dict) or 'tool' not in item or 'args' not in item:
                print(f"BuildingGenerator: Invalid component in LLM output: {item}")
                continue
            generated_components.append(item)

        print(f"BuildingGenerator: Received LLM output: {generated_components}")

        actual_block_commands = []
        for component_task in generated_components:
            blocks = generate_blocks_from_task(component_task)
            actual_block_commands.extend(blocks)

        # Calculate bounding box and dimensions
        min_x, min_y, min_z = float('inf'), float('inf'), float('inf')
        max_x, max_y, max_z = float('-inf'), float('-inf'), float('-inf')

        if actual_block_commands:
            for block in actual_block_commands:
                min_x = min(min_x, block['x'])
                min_y = min(min_y, block['y'])
                min_z = min(min_z, block['z'])
                max_x = max(max_x, block['x'])
                max_y = max(max_y, block['y'])
                max_z = max(max_z, block['z'])
            
            width = max_x - min_x + 1
            height = max_y - min_y + 1
            depth = max_z - min_z + 1
        else:
            min_x, min_y, min_z = 0, 0, 0
            max_x, max_y, max_z = 0, 0, 0
            width, height, depth = 0, 0, 0

        spatial_metadata = {
            "bounding_box": {
                "min_x": min_x, "min_y": min_y, "min_z": min_z,
                "max_x": max_x, "max_y": max_y, "max_z": max_z
            },
            "dimensions": {"width": width, "height": height, "depth": depth}
        }

        final_generated_structure = {
            "design_components": generated_components,
            "spatial_metadata": spatial_metadata
        }

        build_plan = {
            "description": description,
            "generated_structure": final_generated_structure, # Store the LLM's structured output with metadata
            "blocks": actual_block_commands
        }

        print(f"BuildingGenerator: Finished generating plan for: {description}")
        return build_plan

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Building Generator for Minecraft AI Builder.')
    parser.add_argument('--name', type=str, required=True, help='Name of the task.')
    parser.add_argument('--prompt', type=str, required=True, help='Natural language prompt for generation.')
    args = parser.parse_args()

    api_key = get_next_api_key()
    llm_client = get_llm_client(api_key)

    generator = BuildingGenerator(llm_client)
    build_plan = generator.generate(args.prompt)

    output_filename = f"{args.name}_{os.path.splitext(os.path.basename(__file__))[0]}.json"
    output_filepath = os.path.join(BUILD_DIR, output_filename)
    write_json_file(output_filepath, build_plan)
    print(f"BuildingGenerator: Saved build plan to {output_filepath}")
