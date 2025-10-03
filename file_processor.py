import json

def process_conversation_file(file_path):
    """
    Reads a conversation file, extracts the user and model chunks,
    and returns them as a list of dictionaries.

    Args:
        file_path (str): The path to the input file.

    Returns:
        list: A list of dictionaries, where each dictionary represents a
              conversation chunk with "user_text" and "model_text".
              Returns an empty list if an error occurs.

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

        conversation_pairs = []
        user_prompt = None

        for chunk in chunks:
            role = chunk.get("role")
            text = chunk.get("text", "").strip()
            is_thought = chunk.get("isThought", False)

            if role == "user":
                # Store the user's prompt and wait for the model's response
                user_prompt = text
            elif role == "model" and not is_thought and user_prompt is not None:
                # Once we have a model response, pair it with the last user prompt
                conversation_pairs.append({
                    "user_text": user_prompt,
                    "model_text": text
                })
                # Reset user_prompt to ensure we don't reuse it
                user_prompt = None

        return conversation_pairs

    except FileNotFoundError:
        print(f"Error: The file '{file_path}' was not found.")
        raise
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from the file '{file_path}'.")
        raise ValueError("Invalid JSON format.")
    except Exception as e:
        print(f"An unexpected error occurred while processing '{file_path}': {e}")
        raise