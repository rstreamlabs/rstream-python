"""Async stream wrapper used by tunnel accept and dial operations."""

from __future__ import annotations

import asyncio
from contextlib import suppress

from rstream.errors import RuntimeError


class RstreamStream:
    """Bidirectional byte stream carried by the rstream engine."""

    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        self._reader = reader
        self._writer = writer

    @property
    def reader(self) -> asyncio.StreamReader:
        return self._reader

    @property
    def writer(self) -> asyncio.StreamWriter:
        return self._writer

    async def read(self, n: int = -1) -> bytes:
        return await self._reader.read(n)

    async def readexactly(self, n: int) -> bytes:
        return await self._reader.readexactly(n)

    def write(self, data: bytes | bytearray | memoryview) -> None:
        self._writer.write(data)

    async def drain(self) -> None:
        await self._writer.drain()

    def write_eof(self) -> None:
        if self._writer.can_write_eof():
            self._writer.write_eof()

    def close(self) -> None:
        self._writer.close()

    async def wait_closed(self) -> None:
        with suppress(ConnectionError):
            await self._writer.wait_closed()

    async def __aenter__(self) -> RstreamStream:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: object | None,
    ) -> None:
        self.close()
        await self.wait_closed()


async def pipe_stream_to_local(
    stream: RstreamStream,
    host: str,
    port: int,
) -> None:
    _validate_local_endpoint(host, port)
    local_reader, local_writer = await asyncio.open_connection(host, port)
    local = RstreamStream(local_reader, local_writer)
    try:
        await asyncio.gather(
            _copy(stream.reader, local.writer),
            _copy(local.reader, stream.writer),
        )
    finally:
        stream.close()
        local.close()
        await asyncio.gather(
            stream.wait_closed(),
            local.wait_closed(),
            return_exceptions=True,
        )


async def _copy(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
) -> None:
    try:
        while chunk := await reader.read(64 * 1024):
            writer.write(chunk)
            await writer.drain()
        if writer.can_write_eof():
            writer.write_eof()
            await writer.drain()
    finally:
        writer.close()


def _validate_local_endpoint(host: str, port: int) -> None:
    if not host.strip():
        raise RuntimeError(
            "Local forward host is required.",
            code="ERR_RSTREAM_INVALID_LOCAL_ENDPOINT",
        )
    if not 1 <= port <= 65_535:
        raise RuntimeError(
            "Local forward port must be between 1 and 65535.",
            code="ERR_RSTREAM_INVALID_LOCAL_ENDPOINT",
        )
