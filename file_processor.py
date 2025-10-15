import json

def process_conversation_file(file_path):
    """
    Reads a conversation file, extracts the user and model chunks (including images),
    and returns them as a list of dictionaries.

    Args:
        file_path (str): The path to the input file.

    Returns:
        list: A list of dictionaries, where each dictionary represents a
              conversation part. It can contain 'user_text', 'model_text',
              and/or 'model_image'. Returns an empty list if an error occurs.

    Raises:
        ValueError: If the file content is invalid (e.g., no JSON found).
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = f.read()

        # Find the start of the JSON content
        json_start_index = data.find('{')
        if json_start_index == -1:
            raise ValueError("No JSON content found in the file.")

        json_data_str = data[json_start_index:]
        json_data = json.loads(json_data_str)

        chunks = json_data.get("chunkedPrompt", {}).get("chunks", [])

        conversation_parts = []
        user_prompt = None

        for chunk in chunks:
            role = chunk.get("role")
            is_thought = chunk.get("isThought", False)

            if is_thought:
                continue  # Skip thoughts

            if role == "user":
                user_prompt = chunk.get("text", "").strip()

            elif role == "model":
                # Determine if we have a pending user prompt to pair with
                current_user_text = user_prompt if user_prompt is not None else ""

                part = {
                    "user_text": current_user_text,
                    "model_text": "", # Default to empty
                }

                if "text" in chunk:
                    part["model_text"] = chunk.get("text", "").strip()

                if "inlineImage" in chunk:
                    part["model_image"] = chunk["inlineImage"]

                conversation_parts.append(part)

                # A user prompt is only used for the first model response that follows it
                if user_prompt is not None:
                    user_prompt = None

        return conversation_parts

    except FileNotFoundError:
        print(f"Error: The file '{file_path}' was not found.")
        raise
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from the file '{file_path}'.")
        raise ValueError("Invalid JSON format.")
    except Exception as e:
        print(f"An unexpected error occurred while processing '{file_path}': {e}")
        raise