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

class PortalGenerator:
    """
    A generator that creates various types of Minecraft portals with appropriate frame structures, portal effects, and activation mechanisms.
    """
    def __init__(self, llm_client):
        self.llm_client = llm_client

    def generate(self, description: str) -> dict:
        """
        The core method that generates the build plan.
        """
        print(f"PortalGenerator: Generating for: {description}")

        system_prompt = """You are an expert Minecraft architect specializing in portal design. Your task is to design a Minecraft portal based on the user's description. The portal can be of type: nether, end, or custom.

For each portal type, consider:
- Frame structure: Appropriate block types and dimensions
- Portal effects: The visual portal block type and properties
- Activation mechanisms: How the portal is activated (flint and steel, eye of ender, etc.)
- Surrounding decorative elements if applicable

Output your design as a list of geometric primitives. Each primitive should include:
- shape_type: 'cube', 'frame', 'portal', 'decorative_element'
- position: {x, y, z} coordinates
- dimensions: {width, height, depth}
- block_type: Minecraft block ID
- properties: block state properties if needed
- metadata: any additional information

Ensure the design follows Minecraft portal mechanics and is buildable in the game."""
        
        user_prompt = f"Design task: {description}"
        
        success, llm_output = get_llm_response(self.llm_client, system_prompt, user_prompt)

        if not success or not isinstance(llm_output, list):
            print(f"PortalGenerator: Failed to get a valid list from LLM. Response: {llm_output}")
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

        generator = PortalGenerator(llm_client)
        build_plan = generator.generate(args.prompt)

        output_filename = f"{args.name}_{os.path.splitext(os.path.basename(__file__))[0]}.json"
        output_filepath = os.path.join(BUILD_DIR, output_filename)
        write_json_file(output_filepath, build_plan)
        print(f"PortalGenerator: Saved build plan to {output_filepath}")

    except Exception as e:
        print(f"An error occurred in PortalGenerator: {e}")
        import traceback
        traceback.print_exc()
