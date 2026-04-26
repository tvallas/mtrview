from __future__ import annotations

import uvicorn

from mtrview.config import Settings


def main() -> None:
    settings = Settings.from_env()
    uvicorn.run("mtrview.app:app", host=settings.http_host, port=settings.http_port)


if __name__ == "__main__":
    main()
