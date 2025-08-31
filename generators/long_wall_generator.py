
import os
import sys
import json
import math
import argparse

# Add root directory to sys.path to import from src
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(current_dir, '..'))

from src.util import get_llm_client, get_llm_response, write_json_file, generate_blocks_from_task
from src.key_manager import get_next_api_key

BUILD_DIR = os.path.join(current_dir, '../build')

class SmartWallGenerator:
    """
    An intelligent wall generator that decides whether to use a segmented or single-call approach.
    """
    SEGMENT_LENGTH = 15  # The standard length of one wall segment
    SEGMENTATION_THRESHOLD = 20 # If the wall is longer than this, use segmented generation

    def __init__(self, llm_client):
        self.llm_client = llm_client

    def _extract_parameters(self, description: str) -> dict:
        """Uses an LLM call to extract structured parameters from a natural language description."""
        print("SmartWallGenerator: Step 1 - Extracting parameters from description...")
        system_prompt = """Your task is to parse the user's request for a wall and extract key parameters. Respond with only a JSON object.

        The parameters to extract are:
        - `length`: The total length of the wall (integer).
        - `height`: The height of the wall (integer).
        - `material`: A suggested primary Minecraft block ID for the wall (e.g., "minecraft:cobblestone").

        If a parameter is not mentioned, use a reasonable default (e.g., length=15, height=5, material="minecraft:stone_bricks").

        Example Request: "a very tall and long cobblestone wall, about 50 blocks long and 10 high"
        Example Output:
        ```json
        {
          "length": 50,
          "height": 10,
          "material": "minecraft:cobblestone"
        }
        ```
        """
        success, params = get_llm_response(self.llm_client, system_prompt, description)
        if not success or not isinstance(params, dict):
            print("SmartWallGenerator: Warning - Failed to extract parameters, using defaults.")
            return {"length": 15, "height": 5, "material": "minecraft:stone_bricks"}
        
        # Ensure essential keys have default values if missing
        params.setdefault("length", 15)
        params.setdefault("height", 5)
        params.setdefault("material", "minecraft:stone_bricks")
        print(f"SmartWallGenerator: Extracted parameters: {params}")
        return params

    def _generate_single_call(self, length: int, height: int, material: str) -> list:
        """Generates the entire wall in a single API call."""
        print(f"SmartWallGenerator: Using single-call generation for wall (Length: {length}).")
        system_prompt = """You are a Minecraft builder. Your task is to design a wall section based on the provided parameters and output a JSON array of primitive tools to build it. The wall should have some variation and detail, not just be a flat rectangle."""
        user_prompt = f"Design a wall with length={length}, height={height}, made primarily of {material}. The origin (0,0,0) should be one corner of the wall."
        
        success, components = get_llm_response(self.llm_client, system_prompt, user_prompt)
        if not success:
            print("SmartWallGenerator: Single-call generation failed.")
            return []
        return components

    def _generate_segmented(self, length: int, height: int, material: str) -> list:
        """Generates a long wall by repeatedly generating and assembling smaller segments."""
        print(f"SmartWallGenerator: Using segmented generation for wall (Length: {length}).")
        num_segments = math.ceil(length / self.SEGMENT_LENGTH)
        remaining_length = length
        all_components = []
        current_x_offset = 0

        system_prompt = f"""You are a Minecraft builder. Your task is to design a standard wall segment with a specific length and height. The wall should have some variation and detail. The origin (0,0,0) of the segment should be one of its bottom corners. Output a JSON array of primitive tools to build it."""

        for i in range(num_segments):
            segment_len = min(self.SEGMENT_LENGTH, remaining_length)
            print(f"SmartWallGenerator: Generating segment {i+1}/{num_segments} with length {segment_len}...")
            user_prompt = f"Design a wall segment with length={segment_len}, height={height}, made primarily of {material}."
            
            success, segment_components = get_llm_response(self.llm_client, system_prompt, user_prompt)
            if not success:
                print(f"SmartWallGenerator: Failed to generate segment {i+1}. Skipping.")
                continue

            # Add offset to the components of the current segment
            for comp in segment_components:
                comp['args']['x'] = comp['args'].get('x', 0) + current_x_offset
            
            all_components.extend(segment_components)
            current_x_offset += segment_len
            remaining_length -= segment_len
            
        return all_components

    def generate(self, description: str) -> dict:
        """The main generation method with intelligent decision-making."""
        # Step 1: AI Parameter Extraction
        params = self._extract_parameters(description)
        length = params['length']
        height = params['height']
        material = params['material']

        # Step 2: Decision Logic
        if length > self.SEGMENTATION_THRESHOLD:
            # Step 3A: Large Task - Use segmented generation
            generated_components = self._generate_segmented(length, height, material)
        else:
            # Step 3B: Small Task - Use single-call generation
            generated_components = self._generate_single_call(length, height, material)

        if not generated_components:
            print("SmartWallGenerator: Generation resulted in no components.")
            return {"description": description, "generated_structure": {}, "blocks": []}

        # Final assembly and metadata calculation (same as other generators)
        actual_block_commands = [block for task in generated_components for block in generate_blocks_from_task(task)]
        min_x, min_y, min_z = (float('inf'),) * 3
        max_x, max_y, max_z = (float('-inf'),) * 3

        if actual_block_commands:
            for block in actual_block_commands:
                min_x, min_y, min_z = min(min_x, block['x']), min(min_y, block['y']), min(min_z, block['z'])
                max_x, max_y, max_z = max(max_x, block['x']), max(max_y, block['y']), max(max_z, block['z'])
            width, final_height, depth = max_x - min_x + 1, max_y - min_y + 1, max_z - min_z + 1
        else:
            min_x, min_y, min_z, max_x, max_y, max_z, width, final_height, depth = (0,) * 9

        spatial_metadata = {
            "bounding_box": {"min_x": min_x, "min_y": min_y, "min_z": min_z, "max_x": max_x, "max_y": max_y, "max_z": max_z},
            "dimensions": {"width": width, "height": final_height, "depth": depth}
        }
        final_generated_structure = {"design_components": generated_components, "spatial_metadata": spatial_metadata}

        return {
            "description": description,
            "generated_structure": final_generated_structure,
            "blocks": actual_block_commands
        }

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Smart Wall Generator for Minecraft AI Builder.')
    parser.add_argument('--name', type=str, required=True, help='Name of the task.')
    parser.add_argument('--prompt', type=str, required=True, help='Natural language prompt for the wall.')
    args = parser.parse_args()

    api_key = get_next_api_key()
    llm_client = get_llm_client(api_key)

    generator = SmartWallGenerator(llm_client)
    build_plan = generator.generate(args.prompt)

    output_filename = f"{args.name}_{os.path.splitext(os.path.basename(__file__))[0]}.json"
    output_filepath = os.path.join(BUILD_DIR, output_filename)
    write_json_file(output_filepath, build_plan)
    print(f"SmartWallGenerator: Saved build plan to {output_filepath}")
