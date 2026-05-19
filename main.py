import anthropic
from dotenv import load_dotenv
load_dotenv()

client = anthropic.Anthropic()
message = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=1000,
    temperature=0,
    messages=[
        {
            "role": "user",
            "content": "Hello, Claude",
        }
    ],
)
print(message.content)