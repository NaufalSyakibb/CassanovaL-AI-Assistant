import requests
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.tools import tool

# Load environment variables (ensure your MISTRAL_API_KEY is in your .env file)
load_dotenv()

# Define the custom weather tool
@tool('get_weather', description='Return weather information for a given city', return_direct=False)
def get_weather(city: str):
    """Fetches weather data from wttr.in in JSON format."""
    response = requests.get(f'https://wttr.in/{city}?format=j1')
    return response.json()

# Initialize the agent
# Note: Ensure you have the langchain-openai package installed for gpt-4o-mini
agent = create_agent(
    model='mistral-7b-mini', # <--- Add this comma
    tools=[get_weather],
    system_prompt='You are a helpful weather assistant...'
)

# Invoke the agent with a query
response = agent.invoke({
    'messages': [
        {'role': 'user', 'content': 'What is the weather like in Vienna?'}
    ]
})

# Print the output
print(response)

print(response['messages'][-1])
