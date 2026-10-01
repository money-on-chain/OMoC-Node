from common.run_uvicorn import run_uvicorn
from oracle.src import oracle_settings


def main():
    run_uvicorn("oracle.src.app:app", oracle_settings.ORACLE_PORT)


if __name__ == "__main__":
    main()
