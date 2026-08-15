class GatewayException(Exception):
    def __init__(self, status_code: int, code: str, message: str, service: str | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.service = service


class UpstreamResponseException(GatewayException):
    def __init__(self, status_code: int, service: str, message: str) -> None:
        super().__init__(status_code, "UPSTREAM_ERROR", message, service)


class UpstreamUnavailableException(GatewayException):
    def __init__(self, service: str, message: str) -> None:
        super().__init__(503, "UPSTREAM_UNAVAILABLE", message, service)
