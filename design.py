import os
import time
import json
import argparse

from langchain.chat_models import init_chat_model
from langchain_core.messages import SystemMessage, HumanMessage

from build import *


def engineer_prompt(user_prompt: str, model: str = "gemini-2.5-flash", model_provider: str = "google_genai") -> str:
    llm = init_chat_model(model=model, model_provider=model_provider)

    system_prompt = """
    You are a professional prompt engineer specializing in guiding AI-powered Minecraft builders.
    Your goal is to take a vague user request for a build and rewrite it into an explicit, precise, and implementable prompt.

    **Your output must contain:**
    A clear, 7-10 step *construction plan* explaining proportion, dimensions (if unspecified, longest side ~100 blocks), which parts are to be built first and which tool types should be used for each.
    Each step should not exceed 25 words.
    The more vague the user's request, the more liberty you have, and the more detail YOU have to add to compensate.
    
    **Available tools:**
    - `FillSpec`: The most versatile tool, creates or replace cuboid regions with blocks or air.
    - `BeamSpec`: Efficiently create hollow or filled beams, cylinders and square prisms from the start to end point.
    - `PlaneSpec`: Efficiently create planes, possibly tilted.
    
    Pay careful consideration to order, for example, avoid failures like:
    - performing shaping operations before adding **all** relevant parts (e.g., add the deck of a ship before shaping the hull, or it would hang over)
    - adding interior elements before building the object's body (or at least a skeleton) might cause them to end up outside

    Your output must consist strictly of only the construction plan, no commentary or markdown cells.
    """

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt)
    ]

    print("Refining prompt... (please wait)", end=" ", flush=True)
    refined = f"[{user_prompt}]\n"+llm.invoke(messages).content.strip()
    print("(done)")
    return refined


def create_toolcalls(user_prompt: str, model: str = "gemini-2.5-flash", model_provider: str = "google_genai", blueprint_path: str = None):
    llm = init_chat_model(model=model, model_provider=model_provider)
    llm = llm.bind_tools([FillSpec, BeamSpec, PlaneSpec], tool_choice="any")

    system_prompt = """
    You are an expert Minecraft builder assisting an architect in visualizing design ideas by constructing prototypes in Creative Mode.
    Your goal is to use the available tool calls to *physically construct* the structure described by the user — not to describe it in text. Each tool call corresponds to a Minecraft command execution.
    
    **Important rules:**
    1. All coordinates must be non-negative: every block must be placed within or above (0, 0, 0).
    3. The user will later reposition the build, so absolute coordinates in Minecraft are irrelevant.
    4. Always construct in proportionally accurate, coherent shapes that resemble the requested object.
    
    **Available tools:**
    - `FillSpec`: The most versatile tool, creates or replace cuboid regions with blocks or air.
    - `BeamSpec`: Efficiently create hollow or filled beams, cylinders and square prisms from the start to end point.
    - `PlaneSpec`: Efficiently create planes, possibly tilted.
    
    **For every tool call:**
    - Specify exact coordinates and block types.
    - Include a short explanation of *what* that call constructs (e.g., "north wall," "roof layer," "foundation floor").
    - Do not output text, explanations, or summaries — only structured tool calls.
    
    **Construction guidelines:**
    - (0, 0, 0) must be a corner of the construction.
    - Ensure symmetry, realism, and playability (e.g., hollow interiors, accessible doors).
    - When building natural or artistic shapes (like trees, fountains, or hills), approximate using rectangular or stacked sections.
    
    The user's prompt will describe what to build. Your entire output should consist solely of the appropriate tool calls required to construct it. No response is required; you must actually call the tools, not just specify the tools to be called.
    """

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt)
    ]

    blueprint_path = blueprint_path
    if blueprint_path is None:
        blueprint_path = f"blueprint_{int(time.time())}.json"

    print("Creating blueprint... (please wait)", end=" ", flush=True)
    output = llm.invoke(messages)
    print("(done)")
    response = output.content.strip()
    tool_calls = output.tool_calls

    blueprint_data = {
        "refined_prompt": user_prompt,
        "response_text": response,
        "tool_calls": tool_calls
    }

    with open(blueprint_path, "x") as f:
        json.dump(blueprint_data, f, indent=4)

    print(f"Blueprint saved to {blueprint_path}!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI-powered Minecraft structure builder")
    parser.add_argument("--prompt", type=str, default="Realistic model of RMS Titanic", help="Your natural-language build description.")
    parser.add_argument("--model", type=str, default="gemini-2.5-flash", help="LLM to use (API must be configured), for list see https://api.python.langchain.com/en/latest/chat_models/langchain.chat_models.base.init_chat_model.html")
    parser.add_argument("--provider", type=str, default="google_genai", help="Model provider (API must be configured), for list see https://api.python.langchain.com/en/latest/chat_models/langchain.chat_models.base.init_chat_model.html")
    parser.add_argument("--blueprint_path", type=str, default=None, help="Path to save the generated blueprint JSON.")

    args = parser.parse_args()

    refined_prompt = engineer_prompt(args.prompt, model=args.model, model_provider=args.provider)
    create_toolcalls(refined_prompt, model=args.model, model_provider=args.provider, blueprint_path=args.blueprint_path)