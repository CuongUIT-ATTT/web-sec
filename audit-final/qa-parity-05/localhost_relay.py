"""Host-only TCP relay to the isolated QA container; no container egress change."""
import asyncio
import ipaddress
import sys

async def main(target):
    assert ipaddress.ip_address(target).is_private
    async def accept(reader, writer):
        async def copy(source, destination):
            while chunk := await source.read(65536):
                destination.write(chunk)
                await destination.drain()
        upstream = None
        try:
            remote, upstream = await asyncio.wait_for(asyncio.open_connection(target, 8000), 5)
            tasks = [asyncio.create_task(copy(reader, upstream)), asyncio.create_task(copy(remote, writer))]
            _, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
        except (OSError, asyncio.TimeoutError):
            pass
        finally:
            writer.close()
            if upstream:
                upstream.close()
    server = await asyncio.start_server(accept, '127.0.0.1', 18080)
    async with server:
        await server.serve_forever()

asyncio.run(main(sys.argv[1]))
