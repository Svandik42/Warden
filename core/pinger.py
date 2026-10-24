from datetime import datetime
import icmplib
from .models import ErrorKind, PingResult

def ping(
    host_id: int,
    address: str,
    count: int = 1,
    interval: float = 0,
    timeout_ms: int = 1000,
    privileged: bool = False,
) -> PingResult:
    try:
        timeout_s = timeout_ms / 1000.0

        response = icmplib.ping(
            address,
            count=count,
            interval=interval,
            timeout=timeout_s,
            privileged=privileged,
        )

        if response.is_alive:
            return PingResult(
                host_id=host_id,
                timestamp=datetime.now(),
                ok=True,
                rtt_ms=response.avg_rtt,
                error=None,
            )

        return PingResult(
            host_id=host_id,
            timestamp=datetime.now(),
            ok=False,
            rtt_ms=None,
            error=ErrorKind.TIMEOUT,
        )

    except icmplib.exceptions.NameLookupError as e:
        error, details = ErrorKind.UNKNOWN_HOST, str(e)
    except icmplib.exceptions.SocketPermissionError as e:
        error, details = ErrorKind.INSUFFICIENT_PERMISSIONS, str(e)
    except icmplib.exceptions.ICMPSocketError as e:
        error, details = ErrorKind.ICMP_SOCKET_ERROR, str(e)
    except Exception as e:
        error, details = ErrorKind.OTHER, f"{type(e).__name__}: {e}"

    return PingResult(
        host_id=host_id,
        timestamp=datetime.now(),
        ok=False,
        rtt_ms=None,
        error=error,
        details=details,
    )


if __name__ == "__main__":
    result = ping(
            host_id=1,
            address="8.8.8.8",
            count=10,
            interval=0,
            timeout_ms=1000,
    )
    print(result)

    print(f"Success: {result.ok}")
    print(f"Round-trip time: {result.rtt_ms} ms")
    print(f"Error: {result.error}")
    print(f"Timestamp: {result.timestamp}")
    print(f"Host ID: {result.host_id}")
