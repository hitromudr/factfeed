import asyncio
from deep_translator import GoogleTranslator

translator = GoogleTranslator(source="auto", target="ru")

def do_trans(text):
    return translator.translate(text)

async def main():
    texts = ["Cat", "Dog", "Bird", "Mouse", "Elephant", "Tiger", "Lion", "Bear"]
    loop = asyncio.get_running_loop()
    tasks = [loop.run_in_executor(None, do_trans, t) for t in texts]
    results = await asyncio.gather(*tasks)
    for orig, res in zip(texts, results):
        print(f"{orig} -> {res}")

asyncio.run(main())
