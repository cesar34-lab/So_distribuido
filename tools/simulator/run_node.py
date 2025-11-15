import asyncio

async def main():
    print("Simulador de 3 nodos inicializado...")
    await asyncio.sleep(1)
    print("Nodos levantados")

if __name__ == "__main__":
    asyncio.run(main())
