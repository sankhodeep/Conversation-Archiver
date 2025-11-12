import json
from abc import ABC, abstractmethod

class ConversationParser(ABC):
    """Abstract base class for conversation parsers."""
    @abstractmethod
    def parse(self, file_path):
        """Parses a conversation file and returns a list of conversation chunks."""
        pass

class GeminiParser(ConversationParser):
    """Parses Gemini conversation files."""
    def parse(self, file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = f.read()

            json_start_index = data.find('{')
            if json_start_index == -1:
                raise ValueError("No JSON content found in the file.")

            json_data_str = data[json_start_index:]
            json_data = json.loads(json_data_str)

            chunks = json_data.get("chunkedPrompt", {}).get("chunks", [])
            if not chunks:
                raise ValueError("This does not appear to be a valid Gemini file.")

            conversation_parts = []
            user_prompt = None

            for chunk in chunks:
                role = chunk.get("role")
                is_thought = chunk.get("isThought", False)

                if is_thought:
                    continue

                if role == "user":
                    user_prompt = chunk.get("text", "").strip()
                elif role == "model":
                    current_user_text = user_prompt if user_prompt is not None else ""
                    part = {
                        "user_text": current_user_text,
                        "model_text": "",
                    }
                    if "text" in chunk:
                        part["model_text"] = chunk.get("text", "").strip()
                    if "inlineImage" in chunk:
                        part["model_image"] = chunk["inlineImage"]
                    conversation_parts.append(part)
                    if user_prompt is not None:
                        user_prompt = None
            return conversation_parts
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            raise ValueError(f"Invalid Gemini JSON format: {e}")


class QwenParser(ConversationParser):
    """Parses Qwen conversation files."""
    def parse(self, file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                json_data = json.load(f)

            # The top level is a list, so we take the first element.
            if not isinstance(json_data, list) or not json_data:
                raise ValueError("Qwen JSON should be a non-empty list.")

            messages_dict = json_data[0].get("chat", {}).get("history", {}).get("messages", {})
            if not messages_dict:
                raise ValueError("This does not appear to be a valid Qwen file.")


            # Sort messages by timestamp to ensure chronological order
            sorted_messages = sorted(messages_dict.values(), key=lambda msg: msg.get("timestamp", 0))

            conversation_parts = []
            user_prompt = None

            for message in sorted_messages:
                role = message.get("role")

                if role == "user":
                    user_prompt = message.get("content", "").strip()

                elif role == "assistant":
                    current_user_text = user_prompt if user_prompt is not None else ""
                    model_text = ""
                    # The actual response is nested inside content_list
                    if message.get("content_list"):
                        model_text = message["content_list"][0].get("content", "").strip()

                    part = {
                        "user_text": current_user_text,
                        "model_text": model_text,
                    }
                    conversation_parts.append(part)

                    if user_prompt is not None:
                        user_prompt = None

            return conversation_parts

        except (json.JSONDecodeError, KeyError, IndexError) as e:
            raise ValueError(f"Invalid Qwen JSON format: {e}")


def get_parser(model_name):
    """Factory function to get the correct parser."""
    if model_name.lower() == "gemini":
        return GeminiParser()
    elif model_name.lower() == "qwen":
        return QwenParser()
    # Add other parsers here
    else:
        # Default to Gemini for backward compatibility with existing platform names
        return GeminiParser()

def process_conversation_file(file_path, model_name):
    """
    Parses a conversation file using the appropriate parser based on the model name.
    """
    try:
        parser = get_parser(model_name)
        return parser.parse(file_path)
    except FileNotFoundError:
        print(f"Error: The file '{file_path}' was not found.")
        raise
    except ValueError as e:
        print(f"Error processing '{file_path}' for model '{model_name}': {e}")
        # Re-raise with a more user-friendly message
        raise ValueError(f"File format mismatch or parsing error. Please check if the file corresponds to the selected platform '{model_name}'. Details: {e}")
    except Exception as e:
        print(f"An unexpected error occurred while processing '{file_path}': {e}")
        raise
