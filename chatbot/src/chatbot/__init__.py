def main() -> None:
    from dotenv import load_dotenv

    from chatbot.app import run

    load_dotenv()
    run()
