from dotenv import load_dotenv
from pathlib import Path

load_dotenv()
env_path = Path(__file__).resolve().parent.parent.parent / '.env'
load_dotenv(dotenv_path=env_path)