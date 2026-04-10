import json
import os
import urllib.request
from urllib.error import HTTPError, URLError

from dotenv import load_dotenv
from openai import OpenAI
from openai import OpenAIError

load_dotenv()

DEFAULT_MODEL = "gpt-4o"

def get_openai_client() -> OpenAI:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing OPENAI_API_KEY environment variable.")

    return OpenAI(api_key=api_key)


def get_cnb_exchange_rate(currency: str):
    url = "https://www.cnb.cz/en/financial-markets/foreign-exchange-market/central-bank-exchange-rate-fixing/central-bank-exchange-rate-fixing/daily.txt"

    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            text = response.read().decode("utf-8")
    except (HTTPError, URLError, TimeoutError) as exc:
        return {"error": f"Failed to fetch CNB exchange rates: {exc}"}

    lines = text.splitlines()
    if len(lines) < 3:
        return {"error": "CNB rate list is empty or has an unexpected format."}

    rate_date = lines[0]

    for line in lines[2:]:
        parts = line.split("|")
        if len(parts) < 5:
            continue

        try:
            code = parts[3]
            amount = int(parts[2])
            rate = float(parts[4].replace(",", "."))
        except ValueError:
            continue

        if code == currency.upper():
            return {
                "currency": code,
                "rate_date": rate_date,
                "amount": amount,
                "rate_czk": rate,
            }

    return {"error": f"Currency {currency.upper()} was not found in the CNB rate list."}


tools = [
    {
        "type": "function",
        "function": {
            "name": "get_cnb_exchange_rate",
            "description": "Returns the current CNB exchange rate for a currency code such as EUR or USD.",
            "parameters": {
                "type": "object",
                "properties": {
                    "currency": {
                        "type": "string",
                        "description": "Currency code, for example EUR or USD.",
                    }
                },
                "required": ["currency"],
            },
        },
    }
]

available_functions = {
    "get_cnb_exchange_rate": get_cnb_exchange_rate,
}

def ask_llm(question: str, model: str = DEFAULT_MODEL):
    try:
        client = get_openai_client()
    except RuntimeError as exc:
        return str(exc)

    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": question},
    ]

    try:
        first_response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tools,
            tool_choice="auto",
        )
    except OpenAIError as exc:
        return f"OpenAI request failed: {exc}"

    message = first_response.choices[0].message

    if not message.tool_calls:
        return message.content

    messages.append(
        {
            "role": "assistant",
            "content": message.content or "",
            "tool_calls": [],
        }
    )

    for tool_call in message.tool_calls:
        function_name = tool_call.function.name

        if function_name not in available_functions:
            return f"Model requested an unknown tool: {function_name}"

        try:
            function_args = json.loads(tool_call.function.arguments or "{}")
        except json.JSONDecodeError:
            return f"Model returned invalid arguments for tool: {function_name}"

        try:
            function_result = available_functions[function_name](**function_args)
        except TypeError:
            return f"Tool {function_name} received invalid arguments: {function_args}"

        messages[-1]["tool_calls"].append(
            {
                "id": tool_call.id,
                "type": "function",
                "function": {
                    "name": function_name,
                    "arguments": json.dumps(function_args),
                },
            }
        )
        messages.append(
            {
                "role": "tool",
                "tool_call_id": tool_call.id,
                "name": function_name,
                "content": json.dumps(function_result),
            }
        )

    try:
        second_response = client.chat.completions.create(
            model=model,
            messages=messages,
        )
    except OpenAIError as exc:
        return f"OpenAI follow-up request failed: {exc}"

    return second_response.choices[0].message.content

if __name__ == "__main__":
    answer = ask_llm("What is the current EUR exchange rate from CNB? Use the tool and answer in one short sentence.")
    print(answer)
