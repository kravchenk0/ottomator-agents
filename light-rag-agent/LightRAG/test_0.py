from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI()  # использует переменную окружения OPENAI_API_KEY

resp = client.responses.create(
    model="gpt-5",
    input="Напиши функцию factorial(n) на Python с проверками."
)
print(resp.output_text)
