import claude as Claude
import os


# https://github.com/jtsang4/claude-to-chatgpt/blob/main/claude_to_chatgpt/adapter.py
def convert_messages_to_prompt(messages):
    prompt = ""
    for message in messages:
        role = message["role"]
        content = message["content"]
        prompt += f"\n\n{role}: {content}"
    prompt += "\n\nAssistant: "
    return prompt


class claude:

    client = Claude.Client(os.environ.get('access_key'))

    @staticmethod
    def request_model(msg):

        prompt = convert_messages_to_prompt(msg)

        response = claude.client.create(
            prompt = prompt,
            model = os.environ.get('model')
        )

        return response.text

    
    @staticmethod
    def request_submodel(msg):

        prompt = convert_messages_to_prompt(msg)

        response = claude.client.create(
            prompt = prompt,
            model = os.environ.get('submodel')
        )

        return response.text


    @staticmethod
    def request_embed_model(text: str):
        vector = claude.client.embed(
            input = text,
            model=os.environ.get('embed_model'),
        )

        return vector