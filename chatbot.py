import os
import json
from groq import Groq
from dotenv import load_dotenv
from tools import AVAILABLE_FUNCTIONS, TOOL_SCHEMAS

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# Kept as one variable - easy to swap if this model ever gets deprecated
MODEL_NAME = "openai/gpt-oss-20b"

SYSTEM_PROMPT = (
    "You are a helpful assistant for Rinder, a student housing app in Fredericton. "
    "Answer general questions about listings - counts, price ranges, and which "
    "neighborhoods have listings. "
    "If the user mentions an area using an informal or partial name (e.g. 'near UNB', "
    "'downtown', 'east side'), first call get_available_areas to see the real "
    "neighborhood names, pick the closest match yourself, then use that exact matched "
    "name when calling get_price_range or get_listing_count. "
    "When calling find_ward_for_place, if it returns an error saying the place couldn't "
    "be found, do NOT give up or tell the user it failed. Instead, silently try again "
    "with a different, more complete or more formal version of the place name (e.g. "
    "'UNB campus' -> 'University of New Brunswick'; 'the mall' -> 'Regent Mall Fredericton'; "
    "'city hall' -> 'Fredericton City Hall, New Brunswick'). Keep trying different phrasings "
    "up to 3 times. Only respond to the user once you have a successful result - never "
    "mention the failed attempts, just give the final correct answer as if it worked the "
    "first time. If all attempts genuinely fail, only then tell the user you couldn't find it. "
    "Keep answers short, friendly, and conversational."
    "When you get a result from find_ward_for_place, always mention the 'matched_to' value in "
    "your answer so the user can see exactly which real place was found - never substitute in "
    "a different or more famous-sounding name than what the tool actually matched. If the "
    "user's request was vague (e.g. 'the mall', 'the store') and multiple real places could "
    "match, explicitly say which one was found and ask if they meant a different one."
    "For any question about averages, min/max, ranges, or 'which listing has the most/least X', "
    "always call get_stats instead of get_listings - it computes the real answer across ALL "
    "matching listings, not just a sample. Only use get_listings when the user wants to browse "
    "or see actual listing details, not compute a number. "
    "If you're asked about something from earlier in the conversation that you can no longer "
    "see in your context (for example, very early messages that have been trimmed for length), "
    "honestly say you don't have that information anymore rather than guessing what it might "
    "have been. "
    "For questions about furnished status, utilities included, or property type counts/percentages, "
    "always call get_field_counts instead of counting from get_listings yourself. "
)

# Instead of one shared list, keep a separate conversation per user_id
conversations = {}


def get_conversation(user_id):
    if user_id not in conversations:
        conversations[user_id] = [{"role": "system", "content": SYSTEM_PROMPT}]
    return conversations[user_id]

MAX_USER_TURNS = 6  # how many recent question/answer exchanges to keep


def get_role(message):
    """Handles both plain dicts and Groq's ChatCompletionMessage objects safely."""
    if isinstance(message, dict):
        return message.get("role")
    return getattr(message, "role", None)


def trim_conversation(conversation):
    """Keeps the system message plus only the most recent complete exchanges,
    to avoid hitting token limits. Only ever cuts at a user-message boundary,
    so it never breaks a tool-call sequence mid-way."""
    system_msg = conversation[0]
    rest = conversation[1:]

    user_indices = [i for i, m in enumerate(rest) if get_role(m) == "user"]
    if len(user_indices) <= MAX_USER_TURNS:
        return conversation

    cutoff = user_indices[-MAX_USER_TURNS]
    return [system_msg] + rest[cutoff:]

def chat(user_id, user_message):
    try:
        conversation = get_conversation(user_id)
        conversation.append({"role": "user", "content": user_message})
        conversation[:] = trim_conversation(conversation)
       
        max_tool_calls = 8  # gives enough room for a few retries on tricky place names
        for _ in range(max_tool_calls):
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=conversation,
                tools=TOOL_SCHEMAS,
                tool_choice="auto",
            )
            reply = response.choices[0].message
            conversation.append(reply)

            if not reply.tool_calls:
                return reply.content

            for tool_call in reply.tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)
                function_result = AVAILABLE_FUNCTIONS[function_name](**function_args)

                conversation.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(function_result),
                })

        return "Sorry, I'm having trouble answering that right now - could you try rephrasing?"

    except Exception as e:
        print(f"[ERROR in chat()]: {e}")  # so YOU can see what broke, in your own terminal
        return "Something went wrong on my end - please try again."


# --- Simple terminal chat loop, now testing as a specific fake user ---
if __name__ == "__main__":
    test_user_id = "U001"  # pretend we're logged in as this user
    print(f"Rinder chatbot ready (testing as {test_user_id}). Type 'quit' to exit.\n")
    while True:
        user_input = input("You: ")
        if user_input.lower() in ("quit", "exit"):
            break
        answer = chat(test_user_id, user_input)
        print(f"Bot: {answer}\n")