"""Run the bot: python -m devtrade_bot"""

import asyncio

from .bot import main

if __name__ == "__main__":
    asyncio.run(main())
