# This is a template for a new Minecraft generator script.
# Placeholders will be replaced by the GeneratorDesigner.

import os
import sys
import json
import argparse

# Add root directory to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(current_dir, '..'))

from src.util import get_llm_client, get_llm_response, write_json_file, generate_blocks_from_task
from src.key_manager import get_next_api_key

BUILD_DIR = os.path.join(current_dir, '../build')

class RedstoneLampCircuitGenerator:
    """
    Generates functional redstone lamp circuits on a 10x10 foundation with proper wiring and power sources.
    """
    def __init__(self, llm_client):
        self.llm_client = llm_client

    def generate(self, description: str) -> dict:
        """
        The core method that generates the build plan.
        """
        print(f"RedstoneLampCircuitGenerator: Generating for: {description}")

        system_prompt = """You are an expert Minecraft redstone engineer. Design a functional redstone lamp circuit on a 10x10 foundation. The circuit must include:

1. Redstone lamps arranged in a logical pattern
2. Redstone dust for wiring connections
3. Redstone repeaters for signal extension and timing
4. Redstone comparators for signal comparison or measurement
5. Power sources (levers, buttons, pressure plates, or redstone blocks)
6. Supporting blocks like stone, wood, or other appropriate materials

Output the design as a list of geometric primitives with the following structure for each component:
- type: block type (e.g., 'redstone_lamp', 'redstone_dust', 'repeater', 'comparator')
- position: [x, y, z] coordinates relative to foundation center
- properties: block state properties (e.g., facing direction, powered state)
- function: brief description of the component's role in the circuit

Ensure the circuit is fully functional with proper signal flow and power distribution across the 10x10 area."""
        
        user_prompt = f"Design task: {description}"
        
        success, llm_output = get_llm_response(self.llm_client, system_prompt, user_prompt)

        if not success:
            print(f"RedstoneLampCircuitGenerator: LLM call failed. Response: {llm_output}")
            return { "description": description, "blocks": [] }

        # Robustness: Handle if LLM returns a dict with a key like 'components' or 'blocks'
        processed_output = []
        if isinstance(llm_output, list):
            processed_output = llm_output
        elif isinstance(llm_output, dict):
            for key in ['components', 'blocks', 'design', 'parts']:
                if key in llm_output and isinstance(llm_output[key], list):
                    processed_output = llm_output[key]
                    print(f"RedstoneLampCircuitGenerator: Found list in dictionary under key '{key}'.")
                    break
        
        if not processed_output:
            print(f"RedstoneLampCircuitGenerator: Failed to extract a valid list from LLM. Response: {llm_output}")
            return { "description": description, "blocks": [] }
        
        actual_block_commands = []
        for component_task in llm_output:
            blocks = generate_blocks_from_task(component_task)
            actual_block_commands.extend(blocks)

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
            "design_components": llm_output,
            "spatial_metadata": spatial_metadata
        }

        build_plan = {
            "description": description,
            "generated_structure": final_generated_structure,
            "blocks": actual_block_commands
        }
        
        return build_plan

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='A dynamically generated Minecraft AI Builder generator.')
    parser.add_argument('--name', type=str, required=True, help='Name of the task.')
    parser.add_argument('--prompt', type=str, required=True, help='Natural language prompt for generation.')
    args = parser.parse_args()

    try:
        api_key = get_next_api_key()
        llm_client = get_llm_client(api_key)

        generator = RedstoneLampCircuitGenerator(llm_client)
        build_plan = generator.generate(args.prompt)

        output_filename = f"{args.name}_{os.path.splitext(os.path.basename(__file__))[0]}.json"
        output_filepath = os.path.join(BUILD_DIR, output_filename)
        write_json_file(output_filepath, build_plan)
        print(f"RedstoneLampCircuitGenerator: Saved build plan to {output_filepath}")

    except Exception as e:
        print(f"An error occurred in RedstoneLampCircuitGenerator: {e}")
        import traceback
        traceback.print_exc()
