import os
import sys
import json

# Add root directory to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(current_dir, '..'))

from src.util import get_llm_client, get_llm_response, read_file_content

PROMPT_TEMPLATE_PATH = os.path.join(current_dir, '../generator_designer_prompt_fill.txt')
SCRIPT_TEMPLATE_PATH = os.path.join(current_dir, './generator_template.py.txt')
GENERATORS_DIR = os.path.join(current_dir, '../generators')

class GeneratorDesigner:
    """
    The Generator Designer dynamically creates new generator scripts by filling in a template.
    """
    def __init__(self, llm_client):
        self.llm_client = llm_client

    def create_new_generator(self, task_description: str, generator_name: str) -> tuple[bool, str]:
        """
        Generates a new generator script by filling in a template with an LLM.

        Args:
            task_description: A natural language description of what the new generator should do.
            generator_name: The desired filename for the new script (e.g., 'garden_generator').

        Returns:
            A tuple (success, message_or_filepath).
        """
        print(f"GeneratorDesigner: Received task to create '{generator_name}.py' using fill-in-the-blank method.")

        # 1. Read the prompt and script templates
        prompt_template = read_file_content(PROMPT_TEMPLATE_PATH)
        script_template = read_file_content(SCRIPT_TEMPLATE_PATH)
        if not prompt_template or not script_template:
            return False, "Error: Could not read prompt or script templates."

        # 2. Create the final prompt for the LLM
        final_prompt = prompt_template.format(user_request=task_description)

        print("GeneratorDesigner: Sending request to LLM to fill in the blanks...")
        # 3. Call the LLM to get the placeholder values
        # The system prompt is simple as the main instructions are in the user prompt
        success, response_json = get_llm_response(self.llm_client, "You are a code-filling assistant.", final_prompt, expect_json=True)

        if not success:
            return False, f"Error: LLM failed to provide placeholder values. Details: {response_json}"

        # 4. Validate the received JSON
        required_keys = ["CLASS_NAME", "DOCSTRING", "SYSTEM_PROMPT", "GENERATOR_LOGIC"]
        if not all(key in response_json for key in required_keys):
            return False, f"Error: LLM response was missing one or more required keys. Response: {response_json}"

        # 5. Fill in the template
        final_script_code = script_template.replace("##CLASS_NAME##", response_json["CLASS_NAME"])
        final_script_code = final_script_code.replace("##DOCSTRING##", response_json["DOCSTRING"])
        final_script_code = final_script_code.replace("##SYSTEM_PROMPT##", response_json["SYSTEM_PROMPT"])
        final_script_code = final_script_code.replace("##GENERATOR_LOGIC##", response_json["GENERATOR_LOGIC"])

        # 6. Save the new script
        output_path = os.path.join(GENERATORS_DIR, f"{generator_name}.py")
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(final_script_code)
            print(f"GeneratorDesigner: Successfully created new generator script at {output_path}")
            return True, output_path
        except IOError as e:
            return False, f"Error: Failed to write new generator script to {output_path}. Details: {e}"

if __name__ == '__main__':
    # This is a simple test case for the new GeneratorDesigner
    from src.key_manager import get_next_api_key
    
    test_task_desc = "A generator to create various styles of medieval castles, with walls, towers, and a main keep."
    test_gen_name = "castle_generator"

    print("--- Running GeneratorDesigner (Fill-in-the-Blank) Test ---")
    try:
        api_key = get_next_api_key()
        client = get_llm_client(api_key)
        designer = GeneratorDesigner(client)
        success, result = designer.create_new_generator(test_task_desc, test_gen_name)

        if success:
            print(f"\n[SUCCESS] New generator created: {result}")
            print("Please review the generated file to ensure correctness.")
        else:
            print(f"\n[FAILURE] Generator creation failed: {result}")
    except Exception as e:
        import traceback
        print(f"An error occurred during the test: {e}")
        traceback.print_exc()
    
    print("--- Test Complete ---")