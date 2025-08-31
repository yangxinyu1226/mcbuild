
import os
import sys
import json
import argparse
import openai

# This script is standalone and does not import from the main project's src folder.

def get_api_key_from_config():
    """
    Reads the DeepSeek API key from the config files with correct priority.
    """
    # Priority 1: Check for 'deepseek_api_key' in api_keys.json
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'api_keys.json')
    try:
        with open(config_path, 'r') as f:
            keys = json.load(f)
            if isinstance(keys, dict) and "deepseek_api_key" in keys:
                key = keys["deepseek_api_key"]
                if key:
                    print("Found 'deepseek_api_key' in api_keys.json.")
                    return key
    except Exception:
        pass

    # Priority 2: Check api_keys_list.json
    api_keys_list_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'api_keys_list.json')
    try:
        with open(api_keys_list_path, 'r') as f:
            keys = json.load(f)
            if isinstance(keys, list) and keys:
                print("Found key in api_keys_list.json.")
                return keys[0] # The file is a list of key strings
    except Exception:
        pass
        
    return None # Return None if no key is found

def get_minecraft_item_list():
    """
    Reads the list of Minecraft items from the txt file.
    """
    list_path = os.path.join(os.path.dirname(__file__), '我的世界清单名称.txt')
    try:
        with open(list_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"Error reading item list: {e}")
        return ""

def generate_decoration(prompt: str, api_key: str, status_callback=print):
    """
    Generates a small 5x5x5 decoration using the deepseek model.
    The status_callback function is used to send status updates to the caller (e.g., a GUI).
    """
    output_dir = os.path.join(os.path.dirname(__file__), '..', 'box')
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    item_list = get_minecraft_item_list()
    if not item_list:
        status_callback("Warning: Could not read the Minecraft item list. The model may not perform well.")

    client = openai.OpenAI(
        api_key=api_key,
        base_url="https://api.deepseek.com/v1",
        timeout=60.0  # Set timeout to 60 seconds
    )

    system_prompt = f"""You are a Minecraft decoration designer. Your task is to design a small decoration based on the user's description and output a JSON object representing the structure.

Constraints:
1. The entire structure must fit within a 5x5x5 block area. The coordinates should be relative to the origin (0,0,0), so they must be between (0,0,0) and (4,4,4).
2. The output must be a single JSON object with one key: "blocks".
3. The "blocks" key must contain a list of block objects.
4. Each block object must have three integer properties: 'x', 'y', 'z' for coordinates, and one string property: 'block_type'.
5. The 'block_type' must be a valid Minecraft block name from the provided list. Do NOT include the "minecraft:" prefix.
6. Do not add any comments, explanations, or markdown code blocks around the JSON. The output must be only the raw JSON object.

Here is a list of available block types:
{item_list}
"""

    user_prompt = f"Design a small decoration based on this idea: {prompt}"

    status_callback("Generating decoration... This may take a moment.")

    try:
        response = client.chat.completions.create(
            model="deepseek-coder",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            stream=False
        )
        llm_output = response.choices[0].message.content
        status_callback("Successfully received response from model.")
        
        if llm_output.strip().startswith("```json"):
            llm_output = llm_output.strip()[7:-3].strip()
        
        data = json.loads(llm_output)

        data["description"] = prompt

        if "blocks" in data and isinstance(data["blocks"], list):
            filename = prompt.replace(" ", "_").replace("\"", "").replace("'", "")[:20]
            output_filepath = os.path.join(output_dir, f"{filename}.json")
            
            with open(output_filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            
            status_callback(f"Successfully saved decoration to {output_filepath}")
            return output_filepath
        else:
            status_callback("Error: The model's output was not in the expected format.")
            return None

    except Exception as e:
        status_callback(f"An error occurred: {e}")
        return None


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Small Decoration Generator for Minecraft.')
    parser.add_argument('--prompt', type=str, required=True, help='A short description of the decoration to generate.')
    
    args = parser.parse_args()
    
    retrieved_api_key = get_api_key_from_config()
    
    if retrieved_api_key:
        # It's possible the key from the file is still invalid, but we proceed.
        generate_decoration(args.prompt, retrieved_api_key)
    else:
        print("Error: Could not find a valid DeepSeek API key.")
        print("Please ensure 'deepseek_api_key' is set in 'config/api_keys.json' or that 'config/api_keys_list.json' is not empty.")
