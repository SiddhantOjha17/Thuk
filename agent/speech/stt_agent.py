# from agents import Agent
# from agents import Runner
# from pydantic import BaseModel


# PROMPT = """
# You are a Financial Data Extractor. Your task is to extract the following information based on the transaction.

# Make sure you follow this schema:
# 1. Description: (Short description if the transaction)
# 2. Amount: (Money spent)
# 3. Category: (If provided else Misc.)

# There may be more than one transaction in a given text, You **must** identify and extract all of them. 
#  """

# agent = Agent(
#     name="Financial Data Extractor",
#     instructions=PROMPT,
# )


# async def main():
#     result = await Runner.run(agent, "I Spent 5000 on alcohol today at 9 am ")
#     print(result.final_output)


from agents import Agent, Runner
from pydantic import BaseModel
import typing as T
import asyncio
from dotenv import load_dotenv
load_dotenv(r'D:\PersonalProjects\ExpeBot\.env')


async def run_agent(input_text):
    class Transaction(BaseModel):
        amount: float
        description: str
        category: T.Literal["Travel", "Dining", "Shopping", "Misc"]

    finance_agent = Agent(
        name="Financial Agent",
        instructions="""You are a financial analyst agent. Your job is
        to extract entities from a given text related to
        a transaction. 
        As output, you must produce a
        structured output containing the relevant schema.
        """,
        output_type=Transaction)

    result = await Runner.run(
        starting_agent=finance_agent,
        input=input_text
    )
    return result


if __name__ =='__main__':
    result=asyncio.run(run_agent('I Spent 5000 on alcohol today at 9 am'))
    print(result)